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
import shutil
import sys
import tempfile
import time
import uuid
import zipfile

from flask import Flask, abort, jsonify, render_template, request, send_file, send_from_directory

import outfit as ofit
import weather as wx
from storage import JsonStore
from version import APP_NAME, __version__

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8095,
    "data_dir": "data",
    "max_upload_mb": 12,
    "max_backup_mb": 300,
    "weather_cache_minutes": 15,
    "weather_verify_ssl": True,
}

DEFAULT_SETTINGS = {
    "schema": 1,
    "location": {"name": "", "lat": None, "lon": None},
    "activities": [
        {"id": "alltag", "name": "Alltag"},
        {"id": "buero", "name": "Büro"},
        {"id": "sport", "name": "Sport"},
        {"id": "freizeit", "name": "Freizeit"},
        {"id": "draussen", "name": "Draußen / Wandern"},
    ],
}
DEFAULT_CLOTHES = {"schema": 1, "items": []}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    stream=sys.stdout)
log = logging.getLogger("outfit")


# ---------------------------------------------------------------------------
# Persistentes Datenverzeichnis
#
# Programmdateien und Nutzerdaten liegen getrennt. Der Programmordner kann bei
# einem Update komplett ausgetauscht werden, ohne dass Aktivitäten, Standort,
# Kleidungsstücke, Fotos oder die Konfiguration verloren gehen.
#
#   OpenWrt / GL.iNet:  /srv/outfit-dashboard
#   PC / Raspberry Pi:  ~/.outfit-dashboard
#   frei wählbar über die Umgebungsvariable OUTFIT_HOME
#
# Inhalt:  config.json, data/settings.json, data/clothes.json, data/images/,
#          backups/
# ---------------------------------------------------------------------------

def _inside(path, parent):
    path, parent = os.path.realpath(path), os.path.realpath(parent)
    return path == parent or path.startswith(parent + os.sep)


def resolve_home():
    env = os.environ.get("OUTFIT_HOME")
    if env:
        home = env
    elif os.path.exists("/etc/openwrt_release"):
        home = "/srv/outfit-dashboard"
    else:
        home = os.path.join(os.path.expanduser("~"), ".outfit-dashboard")
    home = os.path.abspath(home)
    if _inside(home, BASE_DIR):
        log.warning("Datenverzeichnis %s liegt im Programmordner – bei Updates droht Datenverlust!", home)
    try:
        os.makedirs(home, exist_ok=True)
    except OSError as exc:
        log.error("Datenverzeichnis %s nicht anlegbar (%s) – nutze Programmordner", home, exc)
        home = os.path.join(BASE_DIR, "userdata")
        os.makedirs(home, exist_ok=True)
    return home


HOME_DIR = resolve_home()
BACKUP_DIR = os.path.join(HOME_DIR, "backups")

_env_cfg = os.environ.get("OUTFIT_CONFIG")
if _env_cfg and not _inside(_env_cfg, BASE_DIR):
    CONFIG_PATH = os.path.abspath(_env_cfg)
else:
    # eine Konfiguration im Programmordner (alte Installationen) wird übernommen
    CONFIG_PATH = os.path.join(HOME_DIR, "config.json")


def migrate_legacy():
    """Übernimmt Daten aus v1.0.0, die noch im Programmordner lagen."""
    legacy_cfg = _env_cfg if (_env_cfg and _inside(_env_cfg, BASE_DIR)) else os.path.join(BASE_DIR, "config.json")
    legacy_data_dir = os.path.join(BASE_DIR, "data")

    if os.path.exists(legacy_cfg) and not os.path.exists(CONFIG_PATH):
        try:
            with open(legacy_cfg, "r", encoding="utf-8") as fh:
                old = json.load(fh)
            dd = old.get("data_dir", "data")
            if not os.path.isabs(dd):
                legacy_data_dir = os.path.join(BASE_DIR, dd)
                old["data_dir"] = "data"  # künftig relativ zum Datenverzeichnis
            with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(old, fh, indent=2)
            log.info("Konfiguration übernommen: %s -> %s", legacy_cfg, CONFIG_PATH)
        except (OSError, ValueError) as exc:
            log.warning("Alte config.json nicht übernehmbar: %s", exc)

    new_data = os.path.join(HOME_DIR, "data")
    has_new = any(os.path.exists(os.path.join(new_data, f)) for f in ("clothes.json", "settings.json"))
    has_old = any(os.path.exists(os.path.join(legacy_data_dir, f)) for f in ("clothes.json", "settings.json"))
    if has_old and not has_new and not _inside(new_data, legacy_data_dir):
        try:
            shutil.copytree(legacy_data_dir, new_data, dirs_exist_ok=True)
            log.info("Daten übernommen: %s -> %s (alter Ordner kann gelöscht werden)", legacy_data_dir, new_data)
        except OSError as exc:
            log.error("Datenübernahme fehlgeschlagen: %s", exc)


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


migrate_legacy()
CONFIG = load_config()
DATA_DIR = CONFIG["data_dir"]
if not os.path.isabs(DATA_DIR):
    DATA_DIR = os.path.join(HOME_DIR, DATA_DIR)
IMAGE_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

settings_store = JsonStore(os.path.join(DATA_DIR, "settings.json"), DEFAULT_SETTINGS)
clothes_store = JsonStore(os.path.join(DATA_DIR, "clothes.json"), DEFAULT_CLOTHES)


def normalize_item(item):
    """Ergänzt fehlende Felder – ältere oder künftige Datenstände bleiben lesbar."""
    item.setdefault("name", "Ohne Namen")
    if item.get("type") not in ofit.TYPE_IDS:
        item["type"] = "sonstiges"
    if item.get("color") not in ofit.COLOR_BY_ID:
        item["color"] = "grau"
    if not isinstance(item.get("activities"), list):
        item["activities"] = []
    for key, default in (("temp_min", 5), ("temp_max", 25), ("rain_min", 0), ("rain_max", 5)):
        try:
            item[key] = float(item.get(key, default))
        except (TypeError, ValueError):
            item[key] = float(default)
    item.setdefault("image", "")
    item.setdefault("created", 0)
    return item


def load_items():
    return [normalize_item(i) for i in clothes_store.load()["items"] if isinstance(i, dict) and i.get("id")]


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = max(int(CONFIG["max_upload_mb"]), int(CONFIG["max_backup_mb"])) * 1024 * 1024
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
    if len(data) > int(CONFIG["max_upload_mb"]) * 1024 * 1024:
        return None, f"Bild zu groß (max. {CONFIG['max_upload_mb']} MB)."
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
    items = load_items()
    w = current_weather()
    target = w.get("target") if w.get("ok") else None
    result = ofit.build_outfit(items, activity=activity, target=target, rng=random.SystemRandom())
    result["weather_ok"] = bool(target)
    return jsonify(result)


@app.get("/api/clothes")
def api_clothes():
    return jsonify(load_items())


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
    items = load_items()
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


# ---------------------------------------------------------------------------
# Datenspeicher, Sicherung und Wiederherstellung
# ---------------------------------------------------------------------------

IMAGE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}\.(jpg|png|webp|gif)$")


def _dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def write_backup(target):
    """Schreibt settings.json, clothes.json und alle Fotos als ZIP nach target."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as zf:  # Fotos sind schon komprimiert
        zf.writestr("backup.json", json.dumps({"app": APP_NAME, "version": __version__,
                                               "created": int(time.time())}, indent=2))
        zf.writestr("settings.json", json.dumps(settings_store.load(), indent=2, ensure_ascii=False))
        zf.writestr("clothes.json", json.dumps(clothes_store.load(), indent=2, ensure_ascii=False))
        for name in sorted(os.listdir(IMAGE_DIR)):
            if IMAGE_NAME_RE.match(name):
                zf.write(os.path.join(IMAGE_DIR, name), "images/" + name)


def auto_backup(reason):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"auto-{time.strftime('%Y%m%d-%H%M%S')}-{reason}.zip")
    write_backup(path)
    old = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("auto-"))
    for f in old[:-3]:  # nur die letzten 3 automatischen Sicherungen behalten
        try:
            os.remove(os.path.join(BACKUP_DIR, f))
        except OSError:
            pass
    return path


@app.get("/api/storage")
def api_storage():
    items = load_items()
    try:
        st = os.statvfs(DATA_DIR)
        free = st.f_bavail * st.f_frsize
    except (OSError, AttributeError):
        free = None
    return jsonify({
        "home_dir": HOME_DIR,
        "data_dir": DATA_DIR,
        "config_path": CONFIG_PATH,
        "program_dir": BASE_DIR,
        "items": len(items),
        "activities": len(settings_store.load()["activities"]),
        "data_bytes": _dir_size(DATA_DIR),
        "free_bytes": free,
    })


@app.get("/api/backup")
def api_backup_download():
    fh = tempfile.TemporaryFile()
    write_backup(fh)
    fh.seek(0)
    name = f"outfit-sicherung-{time.strftime('%Y-%m-%d')}.zip"
    return send_file(fh, mimetype="application/zip", as_attachment=True, download_name=name)


@app.post("/api/backup")
def api_backup_restore():
    upload = request.files.get("backup")
    if not upload:
        return jsonify({"ok": False, "errors": ["Keine Datei übertragen."]}), 400
    # auf den Datenträger statt in den RAM – wichtig auf dem Router
    tmp = tempfile.NamedTemporaryFile(dir=HOME_DIR, prefix="restore-", suffix=".zip", delete=False)
    tmp.close()
    upload.save(tmp.name)
    try:
        return _restore_from(tmp.name)
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def _restore_from(path):
    try:
        zf = zipfile.ZipFile(path)
        names = set(zf.namelist())
        if "settings.json" not in names or "clothes.json" not in names:
            raise ValueError("settings.json oder clothes.json fehlt")
        settings = json.loads(zf.read("settings.json").decode("utf-8"))
        clothes = json.loads(zf.read("clothes.json").decode("utf-8"))
        if not isinstance(settings.get("activities"), list) or not isinstance(clothes.get("items"), list):
            raise ValueError("ungültiger Aufbau")
        images = [n for n in names if n.startswith("images/") and IMAGE_NAME_RE.match(n[7:])]
    except (zipfile.BadZipFile, ValueError, UnicodeDecodeError, KeyError) as exc:
        return jsonify({"ok": False, "errors": [f"Keine gültige Sicherung: {exc}"]}), 400

    safety = auto_backup("vor-wiederherstellung")
    for name in os.listdir(IMAGE_DIR):
        if IMAGE_NAME_RE.match(name):
            remove_image(name)
    for n in images:
        with open(os.path.join(IMAGE_DIR, n[7:]), "wb") as fh:
            fh.write(zf.read(n))
    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, copy.deepcopy(value))
    settings_store.save(settings)
    clothes.setdefault("schema", 1)
    clothes_store.save(clothes)
    zf.close()
    log.info("Sicherung eingespielt (%d Stücke, %d Fotos), vorheriger Stand: %s",
             len(clothes["items"]), len(images), safety)
    return jsonify({"ok": True, "items": len(clothes["items"]), "images": len(images)})


@app.errorhandler(413)
def too_large(_err):
    return jsonify({"ok": False, "errors": [f"Datei zu groß (max. {CONFIG['max_backup_mb']} MB)."]}), 413


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

def main():
    host, port = CONFIG["host"], int(CONFIG["port"])
    log.info("%s v%s startet auf http://%s:%s", APP_NAME, __version__, host, port)
    log.info("Programm: %s", BASE_DIR)
    log.info("Daten:    %s (Konfiguration: %s)", DATA_DIR, CONFIG_PATH)
    try:
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)
    except OSError as exc:
        log.error("Webserver konnte nicht starten (Port %s belegt?): %s", port, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
