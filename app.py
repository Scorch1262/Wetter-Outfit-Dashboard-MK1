#!/usr/bin/env python3
"""Outfit-Dashboard-MK1

Lokales Web-Dashboard, das aus dem eigenen Kleiderschrank passend zum
Tageswetter und zur gewählten Aktivität ein farblich stimmiges Outfit
zusammenstellt. Läuft auf PC, Raspberry Pi und GL.iNet-Routern (OpenWrt).

Start:  python3 app.py
"""

import copy
import json
import logging
import os
import random
import re
import sys
import time
import uuid

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

import outfit as ofit
import weather as wx
from storage import JsonStore
from version import APP_NAME, __version__

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("OUTFIT_CONFIG", os.path.join(BASE_DIR, "config.json"))

DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8095,
    "data_dir": "data",
    "max_upload_mb": 12,
    "weather_cache_minutes": 15,
    "weather_verify_ssl": True,
}

DEFAULT_SETTINGS = {
    "location": {"name": "", "lat": None, "lon": None},
    "activities": [
        {"id": "alltag", "name": "Alltag"},
        {"id": "buero", "name": "Büro"},
        {"id": "sport", "name": "Sport"},
        {"id": "freizeit", "name": "Freizeit"},
        {"id": "draussen", "name": "Draußen / Wandern"},
    ],
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    stream=sys.stdout)
log = logging.getLogger("outfit")


# ---------------------------------------------------------------------------
# Konfiguration & Speicher
# ---------------------------------------------------------------------------

def load_config():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except (OSError, ValueError) as exc:
            log.warning("config.json nicht lesbar (%s) – Standardwerte werden genutzt", exc)
    else:
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh, indent=2)
            log.info("config.json mit Standardwerten angelegt: %s", CONFIG_PATH)
        except OSError as exc:
            log.warning("config.json konnte nicht angelegt werden: %s", exc)
    return cfg


CONFIG = load_config()
DATA_DIR = CONFIG["data_dir"]
if not os.path.isabs(DATA_DIR):
    DATA_DIR = os.path.join(BASE_DIR, DATA_DIR)
IMAGE_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

settings_store = JsonStore(os.path.join(DATA_DIR, "settings.json"), DEFAULT_SETTINGS)
clothes_store = JsonStore(os.path.join(DATA_DIR, "clothes.json"), {"items": []})

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(CONFIG["max_upload_mb"]) * 1024 * 1024
app.config["JSON_AS_ASCII"] = False
app.json.ensure_ascii = False


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def slugify(name):
    repl = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    s = name.strip().lower()
    for k, v in repl.items():
        s = s.replace(k, v)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or uuid.uuid4().hex[:6]


def image_kind(data):
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:4] == b"GIF8":
        return "gif"
    return None


def remove_image(filename):
    if not filename:
        return
    path = os.path.join(IMAGE_DIR, os.path.basename(filename))
    try:
        os.remove(path)
    except OSError:
        pass


def clamp_num(value, lo, hi, default):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, round(v, 1)))


def parse_item_fields(form, existing=None):
    """Validiert die Formularfelder eines Kleidungsstücks."""
    item = dict(existing or {})
    errors = []

    name = (form.get("name") or "").strip()[:80]
    if not name:
        errors.append("Bitte einen Namen angeben.")
    item["name"] = name

    typ = form.get("type")
    if typ not in ofit.TYPE_IDS:
        errors.append("Unbekannter Typ.")
    item["type"] = typ

    color = form.get("color")
    if color not in ofit.COLOR_BY_ID:
        errors.append("Bitte eine Farbe wählen.")
    item["color"] = color

    valid_acts = {a["id"] for a in settings_store.load()["activities"]}
    acts = form.getlist("activities") if hasattr(form, "getlist") else form.get("activities", [])
    item["activities"] = [a for a in acts if a in valid_acts]

    t_lo, t_hi = ofit.TEMP_SCALE
    r_lo, r_hi = ofit.RAIN_SCALE
    tmin = clamp_num(form.get("temp_min"), t_lo, t_hi, 5)
    tmax = clamp_num(form.get("temp_max"), t_lo, t_hi, 25)
    rmin = clamp_num(form.get("rain_min"), r_lo, r_hi, 0)
    rmax = clamp_num(form.get("rain_max"), r_lo, r_hi, 5)
    if tmin > tmax:
        tmin, tmax = tmax, tmin
    if rmin > rmax:
        rmin, rmax = rmax, rmin
    item.update({"temp_min": tmin, "temp_max": tmax, "rain_min": rmin, "rain_max": rmax})
    return item, errors


def save_upload(file_storage, item_id):
    data = file_storage.read()
    if not data:
        return None, None
    kind = image_kind(data)
    if not kind:
        return None, "Bildformat nicht unterstützt (erlaubt: JPG, PNG, WEBP, GIF)."
    filename = f"{item_id}-{int(time.time())}.{kind}"
    with open(os.path.join(IMAGE_DIR, filename), "wb") as fh:
        fh.write(data)
    return filename, None


def current_weather():
    loc = settings_store.load()["location"]
    return wx.get_weather(loc.get("lat"), loc.get("lon"),
                          cache_minutes=CONFIG["weather_cache_minutes"],
                          verify_ssl=CONFIG["weather_verify_ssl"])


@app.context_processor
def inject_globals():
    return {"version": __version__, "app_name": APP_NAME}


# ---------------------------------------------------------------------------
# Seiten
# ---------------------------------------------------------------------------

@app.route("/")
def page_user():
    return render_template("index.html", page="user")


@app.route("/einstellungen")
def page_settings():
    return render_template("settings.html", page="settings")


@app.route("/nutzungsbedingungen")
def page_terms():
    return render_template("terms.html", page="terms")


@app.route("/bilder/<path:filename>")
def serve_image(filename):
    filename = os.path.basename(filename)
    if not os.path.exists(os.path.join(IMAGE_DIR, filename)):
        abort(404)
    return send_from_directory(IMAGE_DIR, filename, max_age=7 * 24 * 3600)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/api/meta")
def api_meta():
    s = settings_store.load()
    return jsonify({
        "version": __version__,
        "types": ofit.TYPES,
        "colors": ofit.COLORS,
        "temp_scale": ofit.TEMP_SCALE,
        "rain_scale": ofit.RAIN_SCALE,
        "activities": s["activities"],
        "location": s["location"],
    })


@app.get("/api/weather")
def api_weather():
    return jsonify(current_weather())


@app.get("/api/outfit")
def api_outfit():
    activity = request.args.get("activity") or "alle"
    items = clothes_store.load()["items"]
    w = current_weather()
    target = w.get("target") if w.get("ok") else None
    result = ofit.build_outfit(items, activity=activity, target=target, rng=random.SystemRandom())
    result["weather_ok"] = bool(target)
    return jsonify(result)


@app.get("/api/clothes")
def api_clothes():
    return jsonify(clothes_store.load()["items"])


@app.post("/api/clothes")
def api_clothes_create():
    item, errors = parse_item_fields(request.form)
    upload = request.files.get("image")
    if not upload or not upload.filename:
        errors.append("Bitte ein Bild auswählen.")
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400
    item["id"] = uuid.uuid4().hex[:12]
    filename, err = save_upload(upload, item["id"])
    if err or not filename:
        return jsonify({"ok": False, "errors": [err or "Leere Bilddatei."]}), 400
    item["image"] = filename
    item["created"] = int(time.time())
    clothes_store.update(lambda d: d["items"].append(item))
    log.info("Kleidungsstück angelegt: %s (%s)", item["name"], item["type"])
    return jsonify({"ok": True, "item": item})


@app.post("/api/clothes/<item_id>")
def api_clothes_update(item_id):
    items = clothes_store.load()["items"]
    existing = next((i for i in items if i["id"] == item_id), None)
    if not existing:
        return jsonify({"ok": False, "errors": ["Kleidungsstück nicht gefunden."]}), 404
    item, errors = parse_item_fields(request.form, existing)
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400
    upload = request.files.get("image")
    old_image = None
    if upload and upload.filename:
        filename, err = save_upload(upload, item_id)
        if err:
            return jsonify({"ok": False, "errors": [err]}), 400
        if filename:
            old_image, item["image"] = existing.get("image"), filename

    def apply(data):
        for idx, cur in enumerate(data["items"]):
            if cur["id"] == item_id:
                data["items"][idx] = item
    clothes_store.update(apply)
    remove_image(old_image)
    return jsonify({"ok": True, "item": item})


@app.delete("/api/clothes/<item_id>")
def api_clothes_delete(item_id):
    removed = {}

    def apply(data):
        keep = []
        for cur in data["items"]:
            if cur["id"] == item_id:
                removed["image"] = cur.get("image")
            else:
                keep.append(cur)
        data["items"] = keep
    clothes_store.update(apply)
    if "image" not in removed:
        return jsonify({"ok": False, "errors": ["Kleidungsstück nicht gefunden."]}), 404
    remove_image(removed["image"])
    return jsonify({"ok": True})


@app.get("/api/settings")
def api_settings():
    return jsonify(settings_store.load())


@app.post("/api/settings/location")
def api_settings_location():
    body = request.get_json(silent=True) or {}
    try:
        lat = float(body.get("lat"))
        lon = float(body.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "errors": ["Ungültige Koordinaten."]}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"ok": False, "errors": ["Koordinaten außerhalb des gültigen Bereichs."]}), 400
    name = (body.get("name") or f"{lat:.3f}, {lon:.3f}").strip()[:120]
    loc = {"name": name, "lat": round(lat, 4), "lon": round(lon, 4)}

    def apply(data):
        data["location"] = loc
    settings_store.update(apply)
    log.info("Standort gesetzt: %s (%s, %s)", name, lat, lon)
    return jsonify({"ok": True, "location": loc})


@app.post("/api/settings/activities")
def api_settings_activities():
    body = request.get_json(silent=True) or {}
    incoming = body.get("activities")
    if not isinstance(incoming, list):
        return jsonify({"ok": False, "errors": ["Ungültige Daten."]}), 400
    result, seen = [], set()
    for a in incoming:
        name = str(a.get("name", "")).strip()[:40]
        if not name:
            continue
        aid = a.get("id") or slugify(name)
        aid = re.sub(r"[^a-z0-9-]", "", str(aid).lower()) or slugify(name)
        if aid in seen or aid == "alle":
            aid = f"{aid}-{uuid.uuid4().hex[:4]}"
        seen.add(aid)
        result.append({"id": aid, "name": name})

    settings_store.update(lambda d: d.__setitem__("activities", result))

    # gelöschte Aktivitäten aus allen Kleidungsstücken entfernen
    valid = {a["id"] for a in result}

    def clean(data):
        for item in data["items"]:
            item["activities"] = [x for x in item.get("activities", []) if x in valid]
    clothes_store.update(clean)
    return jsonify({"ok": True, "activities": result})


@app.get("/api/geocode")
def api_geocode():
    try:
        return jsonify({"ok": True, "results": wx.geocode(request.args.get("q", ""),
                                                          verify_ssl=CONFIG["weather_verify_ssl"])})
    except Exception as exc:
        return jsonify({"ok": False, "errors": [f"Ortssuche fehlgeschlagen: {exc}"]}), 502


@app.errorhandler(413)
def too_large(_err):
    return jsonify({"ok": False, "errors": [f"Datei zu groß (max. {CONFIG['max_upload_mb']} MB)."]}), 413


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

def main():
    host, port = CONFIG["host"], int(CONFIG["port"])
    log.info("%s v%s startet auf http://%s:%s (Daten: %s)", APP_NAME, __version__, host, port, DATA_DIR)
    try:
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)
    except OSError as exc:
        log.error("Webserver konnte nicht starten (Port %s belegt?): %s", port, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
