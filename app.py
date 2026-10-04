#!/usr/bin/env python3
"""Outfit-Dashboard-MK1

Lokales Web-Dashboard, das aus dem eigenen Kleiderschrank passend zum
Tageswetter und zur gewählten Aktivität ein farblich stimmiges Outfit
zusammenstellt. Läuft auf PC, Raspberry Pi und GL.iNet-Routern (OpenWrt)
sowie als eigenständige Windows-EXE bzw. macOS-App (PyInstaller).

Start:  python3 app.py
"""

import copy
import json
import logging
import os
import random
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
import webbrowser
import zipfile

from flask import Flask, abort, jsonify, render_template, request, send_file, send_from_directory

import outfit as ofit
import weather as wx
from storage import JsonStore
from version import APP_NAME, __version__

# Als EXE/App (PyInstaller) liegen Vorlagen und statische Dateien im
# entpackten Bundle (sys._MEIPASS), die Nutzerdaten dagegen außerhalb.
FROZEN = bool(getattr(sys, "frozen", False))
IS_MAC_APP = FROZEN and sys.platform == "darwin"


def _program_dir():
    """Ordner, in dem das Programm für den Nutzer sichtbar liegt.

    Python:     Ordner von app.py
    EXE:        Ordner der .exe
    macOS-App:  Ordner, in dem die .app liegt (nicht das Innere des Bundles)
    """
    if not FROZEN:
        return os.path.dirname(os.path.abspath(__file__))
    exe = os.path.abspath(sys.executable)
    if sys.platform == "darwin" and ".app/Contents/MacOS" in exe:
        bundle = exe[:exe.index(".app/Contents/MacOS") + 4]   # …/Outfit-Dashboard.app
        return os.path.dirname(bundle)
    return os.path.dirname(exe)


BASE_DIR = _program_dir()
RESOURCE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8095,
    "data_dir": ".",
    "max_upload_mb": 12,
    "max_backup_mb": 300,
    "weather_cache_minutes": 15,
    "weather_verify_ssl": True,
}

DEFAULT_SETTINGS = {
    "schema": 2,
    "rules": dict(ofit.DEFAULT_RULES),
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

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
_log_handlers = []
if sys.stdout is not None:  # macOS-App ohne Terminal hat kein stdout
    _log_handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=_log_handlers or None)
log = logging.getLogger("outfit")


# ---------------------------------------------------------------------------
# Ordneraufbau – alles in EINEM Ordner (z. B. /root/Outfit-Dashboard)
#
#   Outfit-Dashboard/
#   ├── app.py, outfit.py, …, templates/, static/, openwrt/   Programm
#   └── daten/                                                Nutzerdaten
#       ├── config.json
#       ├── settings.json      Standort, Aktivitäten
#       ├── clothes.json       Kleidungsstücke mit Labels
#       ├── images/            Fotos
#       └── backups/           automatische Sicherungen
#
# Bei einem Update werden nur die Programmdateien ersetzt, "daten/" bleibt
# unverändert. Abweichender Datenordner: Umgebungsvariable OUTFIT_HOME.
# ---------------------------------------------------------------------------

DATA_FOLDER_NAME = "daten"
APP_SUPPORT_DIR = os.path.expanduser("~/Library/Application Support/Outfit-Dashboard/" + DATA_FOLDER_NAME)
LOCALAPPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                                "Outfit-Dashboard", DATA_FOLDER_NAME)
# frühere Speicherorte: (Ordner, Standard für data_dir ohne config.json)
LEGACY_HOMES = [
    ("/srv/outfit-dashboard", "data"),                                        # v1.1.0 Router
    (os.path.join(os.path.expanduser("~"), ".outfit-dashboard"), "data"),     # v1.1.0 PC
    (APP_SUPPORT_DIR, "."),                                                   # v1.3.0 Mac-App
    (LOCALAPPDATA_DIR, "."),                                                  # v1.3.0 EXE-Rückfall
]

# Hinweis für die Oberfläche, falls nicht neben dem Programm gespeichert werden kann
STORAGE_WARNING = None


def _writable(folder):
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".schreibtest")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def resolve_home():
    """Datenordner: immer "daten/" direkt neben app.py, der EXE bzw. der Mac-App.

        Outfit-Dashboard.exe          Outfit-Dashboard.app          app.py
        daten/                        daten/                        daten/

    Nur wenn dort nicht geschrieben werden kann (z. B. "Programme"-Ordner unter
    Windows oder eine von macOS isoliert gestartete App), wird ersatzweise ein
    Benutzerordner verwendet und in den Einstellungen ein Hinweis angezeigt.
    """
    global STORAGE_WARNING
    env = os.environ.get("OUTFIT_HOME")
    if env:
        home = os.path.abspath(env)
        if _writable(home):
            return home
        log.error("Datenordner %s (OUTFIT_HOME) nicht beschreibbar.", home)
        sys.exit(1)

    home = os.path.join(BASE_DIR, DATA_FOLDER_NAME)
    translocated = IS_MAC_APP and "/AppTranslocation/" in BASE_DIR
    if not translocated and _writable(home):
        return home

    if translocated:
        STORAGE_WARNING = ("macOS startet die App aus einem isolierten Ordner, deshalb können die Daten "
                           "nicht neben der App liegen. Abhilfe: App beenden, im Terminal "
                           "„xattr -cr <Pfad>/Outfit-Dashboard.app“ ausführen und neu starten.")
    else:
        STORAGE_WARNING = (f"Der Ordner neben dem Programm ({BASE_DIR}) ist nicht beschreibbar. "
                           "Programm am besten in einen eigenen Ordner verschieben, z. B. "
                           "Dokumente\\Outfit-Dashboard bzw. ~/Outfit-Dashboard.")
    fallback = APP_SUPPORT_DIR if sys.platform == "darwin" else LOCALAPPDATA_DIR
    log.warning("%s Ersatzweise genutzt: %s", STORAGE_WARNING, fallback)
    if _writable(fallback):
        return os.path.abspath(fallback)
    log.error("Kein beschreibbarer Datenordner gefunden.")
    sys.exit(1)


HOME_DIR = resolve_home()
BACKUP_DIR = os.path.join(HOME_DIR, "backups")
CONFIG_PATH = os.path.abspath(os.environ.get("OUTFIT_CONFIG") or os.path.join(HOME_DIR, "config.json"))


def _has_data(folder):
    return any(os.path.isfile(os.path.join(folder, f)) for f in ("clothes.json", "settings.json"))


def _legacy_sources():
    """Mögliche Altbestände: (Konfigurationsdatei, Basisordner, data_dir-Standard)."""
    sources = []
    for home, default_dd in LEGACY_HOMES:
        if os.path.realpath(home) != os.path.realpath(HOME_DIR):
            sources.append((os.path.join(home, "config.json"), home, default_dd))
    # v1.0.0: config.json und data/ direkt im Programmordner
    if not FROZEN:
        sources.append((os.path.join(BASE_DIR, "config.json"), BASE_DIR, "data"))
    return sources


def migrate_legacy():
    """Übernimmt Daten früherer Versionen einmalig in den Ordner daten/."""
    if _has_data(HOME_DIR):
        return
    for cfg_path, base, default_dd in _legacy_sources():
        old_cfg = {}
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as fh:
                    old_cfg = json.load(fh)
            except (OSError, ValueError):
                old_cfg = {}
        dd = old_cfg.get("data_dir", default_dd)
        src = dd if os.path.isabs(dd) else os.path.join(base, dd)
        if not _has_data(src) or os.path.realpath(src) == os.path.realpath(HOME_DIR):
            continue
        try:
            for name in ("settings.json", "clothes.json"):
                if os.path.isfile(os.path.join(src, name)):
                    shutil.copy2(os.path.join(src, name), os.path.join(HOME_DIR, name))
            if os.path.isdir(os.path.join(src, "images")):
                shutil.copytree(os.path.join(src, "images"), os.path.join(HOME_DIR, "images"),
                                dirs_exist_ok=True)
            if old_cfg and not os.path.exists(CONFIG_PATH):
                old_cfg["data_dir"] = "."
                with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
                    json.dump(old_cfg, fh, indent=2)
            log.info("Daten übernommen: %s -> %s (der alte Ordner kann gelöscht werden)", src, HOME_DIR)
            return
        except OSError as exc:
            log.error("Datenübernahme aus %s fehlgeschlagen: %s", src, exc)


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
    DATA_DIR = os.path.normpath(os.path.join(HOME_DIR, DATA_DIR))
IMAGE_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

settings_store = JsonStore(os.path.join(DATA_DIR, "settings.json"), DEFAULT_SETTINGS)
clothes_store = JsonStore(os.path.join(DATA_DIR, "clothes.json"), DEFAULT_CLOTHES)


def normalize_item(item):
    """Ergänzt fehlende Felder – ältere oder künftige Datenstände bleiben lesbar."""
    item.setdefault("name", "Ohne Namen")
    # bis v1.4.0 war "Jacke" ein eigener Typ – jetzt Untertyp von Oberteil
    if item.get("type") == "jacke":
        item["type"], item["subtype"] = "oberteil", "jacke"
    if item.get("type") not in ofit.TYPE_IDS:
        item["type"] = "sonstiges"
    subs = ofit.SUBTYPE_IDS.get(item["type"])
    if subs:
        if item.get("subtype") not in subs:
            item["subtype"] = ofit.DEFAULT_SUBTYPE[item["type"]]
    else:
        item.pop("subtype", None)
    if item.get("color") not in ofit.COLOR_BY_ID:
        item["color"] = "grau"
    if not isinstance(item.get("activities"), list):
        item["activities"] = []

    # bis v1.4.0: freie °C-/mm-Bereiche → jetzt 6 Stufen
    for kind, levels, dmin, dmax in (("temp", ofit.TEMP_LEVELS, 5, 25), ("rain", ofit.RAIN_LEVELS, 0, 5)):
        kmin, kmax = f"{kind}_level_min", f"{kind}_level_max"
        if not ofit.has_attr(item["type"], kind):
            # z. B. Unterwäsche (keine Werte) oder Socken (kein Niederschlag)
            for k in (kmin, kmax, f"{kind}_min", f"{kind}_max"):
                item.pop(k, None)
            continue
        if kmin not in item or kmax not in item:
            try:
                lo, hi = float(item.get(f"{kind}_min", dmin)), float(item.get(f"{kind}_max", dmax))
            except (TypeError, ValueError):
                lo, hi = dmin, dmax
            item[kmin], item[kmax] = ofit.range_to_levels(min(lo, hi), max(lo, hi), levels)
        a = ofit.clamp_level(item[kmin], 1)
        b = ofit.clamp_level(item[kmax], 6)
        if a > b:
            a, b = b, a
        item[kmin], item[kmax] = a, b
        # °C/mm-Grenzen der Stufen mitschreiben (lesbar für ältere Versionen)
        item[f"{kind}_min"], item[f"{kind}_max"] = ofit.levels_to_range(a, b, levels)
    item.setdefault("image", "")
    item.setdefault("created", 0)
    return item


def load_items():
    return [normalize_item(i) for i in clothes_store.load()["items"] if isinstance(i, dict) and i.get("id")]


# Protokoll zusätzlich in daten/outfit.log (wichtig für die macOS-App ohne Terminal)
try:
    _fh = logging.FileHandler(os.path.join(HOME_DIR, "outfit.log"), encoding="utf-8")
    _fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger().addHandler(_fh)
except OSError:
    pass

app = Flask(__name__,
            template_folder=os.path.join(RESOURCE_DIR, "templates"),
            static_folder=os.path.join(RESOURCE_DIR, "static"))
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
    subs = ofit.SUBTYPE_IDS.get(typ)
    if subs:
        sub = form.get("subtype")
        if sub not in subs:
            errors.append("Bitte die Art des Oberteils wählen (T-Shirt, Pullover oder Jacke).")
        item["subtype"] = sub
    else:
        item.pop("subtype", None)

    color = form.get("color")
    if color not in ofit.COLOR_BY_ID:
        errors.append("Bitte eine Farbe wählen.")
    item["color"] = color

    valid_acts = {a["id"] for a in settings_store.load()["activities"]}
    acts = form.getlist("activities") if hasattr(form, "getlist") else form.get("activities", [])
    item["activities"] = [a for a in acts if a in valid_acts]

    # Temperatur und Niederschlag in 6 Stufen
    for kind, d_a, d_b in (("temp", 2, 5), ("rain", 1, 3)):
        if not ofit.has_attr(typ, kind):
            continue  # Wert gibt es für diesen Typ nicht (normalize_item räumt auf)
        a = ofit.clamp_level(form.get(f"{kind}_level_min"), d_a)
        b = ofit.clamp_level(form.get(f"{kind}_level_max"), d_b)
        if a > b:
            a, b = b, a
        item[f"{kind}_level_min"], item[f"{kind}_level_max"] = a, b
    if errors:
        return item, errors
    return normalize_item(item), errors


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

def _is_local_request():
    return request.remote_addr in ("127.0.0.1", "::1", "::ffff:127.0.0.1")


@app.get("/api/meta")
def api_meta():
    s = settings_store.load()
    return jsonify({
        "app": APP_NAME,
        "version": __version__,
        "can_shutdown": FROZEN and _is_local_request(),
        "types": ofit.TYPES,
        "subtypes": ofit.SUBTYPES,
        "colors": ofit.COLORS,
        "temp_levels": ofit.TEMP_LEVELS,
        "rain_levels": ofit.RAIN_LEVELS,
        "rules": current_rules(s),
        "activities": s["activities"],
        "location": s["location"],
    })


def current_rules(settings=None):
    s = settings or settings_store.load()
    r = dict(ofit.DEFAULT_RULES)
    r.update({k: v for k, v in (s.get("rules") or {}).items() if k in r})
    return r


@app.post("/api/settings/rules")
def api_settings_rules():
    body = request.get_json(silent=True) or {}
    r = current_rules()
    for key in ("pullover_max_temp", "jacket_max_temp"):
        if key in body:
            r[key] = clamp_num(body[key], -20, 40, r[key])
    if "jacket_rain_level" in body:
        r["jacket_rain_level"] = ofit.clamp_level(body["jacket_rain_level"], r["jacket_rain_level"])

    def apply(data):
        data["rules"] = r
    settings_store.update(apply)
    log.info("Regeln gespeichert: %s", r)
    return jsonify({"ok": True, "rules": r})


@app.get("/api/weather")
def api_weather():
    return jsonify(current_weather())


@app.get("/api/outfit")
def api_outfit():
    activity = request.args.get("activity") or "alle"
    items = load_items()
    w = current_weather()
    target = w.get("target") if w.get("ok") else None
    result = ofit.build_outfit(items, activity=activity, target=target, rng=random.SystemRandom(),
                               rules=current_rules())
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
        "warning": STORAGE_WARNING,
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


@app.post("/api/shutdown")
def api_shutdown():
    """Beendet die Desktop-Version (EXE/App) – nur vom eigenen Rechner aus."""
    if not FROZEN or not _is_local_request():
        return jsonify({"ok": False, "errors": ["Nur in der Desktop-Version vom eigenen Rechner möglich."]}), 403
    log.info("Beenden über die Weboberfläche angefordert")
    threading.Timer(0.6, lambda: os._exit(0)).start()
    return jsonify({"ok": True})


@app.errorhandler(413)
def too_large(_err):
    return jsonify({"ok": False, "errors": [f"Datei zu groß (max. {CONFIG['max_backup_mb']} MB)."]}), 413


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

def _env_flag(name):
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip().lower() in ("1", "true", "ja", "yes", "on")


def _port_free(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform != "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _already_running(port):
    """Läuft auf dem Port schon ein Outfit-Dashboard?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/meta", timeout=1.5) as resp:
            return json.loads(resp.read().decode("utf-8")).get("app") == APP_NAME
    except Exception:
        return False


def _lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))  # kein echter Verkehr, nur Routenwahl
            return sock.getsockname()[0]
    except OSError:
        return None


def main():
    host = CONFIG["host"]
    port = int(os.environ.get("OUTFIT_PORT") or CONFIG["port"])
    open_browser = _env_flag("OUTFIT_OPEN_BROWSER")
    if open_browser is None:
        open_browser = bool(CONFIG.get("open_browser", FROZEN))

    if not _port_free(host, port):
        if _already_running(port):
            log.info("Outfit-Dashboard läuft bereits auf Port %s – öffne nur den Browser.", port)
            if open_browser:
                webbrowser.open(f"http://127.0.0.1:{port}/")
            return
        for alt in range(port + 1, port + 11):
            if _port_free(host, alt):
                log.warning("Port %s ist belegt – weiche auf Port %s aus.", port, alt)
                port = alt
                break
        else:
            log.error("Port %s und die 10 folgenden Ports sind belegt.", port)
            sys.exit(1)

    log.info("%s v%s", APP_NAME, __version__)
    log.info("Programm: %s", BASE_DIR)
    log.info("Daten:    %s (Konfiguration: %s)", DATA_DIR, CONFIG_PATH)
    log.info("Lokal:    http://127.0.0.1:%s", port)
    ip = _lan_ip()
    if ip and host in ("0.0.0.0", "::"):
        log.info("Netzwerk: http://%s:%s  (z. B. für das iPhone)", ip, port)
    if open_browser:
        threading.Timer(1.2, webbrowser.open, [f"http://127.0.0.1:{port}/"]).start()
    try:
        app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)
    except OSError as exc:
        log.error("Webserver konnte nicht starten (Port %s): %s", port, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
