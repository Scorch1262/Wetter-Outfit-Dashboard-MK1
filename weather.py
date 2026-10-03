"""Wetterabfrage über Open-Meteo (kostenlos, kein API-Schlüssel nötig).

Nur Python-Standardbibliothek (urllib), damit auf OpenWrt keine
zusätzlichen Pakete wie "requests" installiert werden müssen.
Wetterdaten: Open-Meteo.com, Lizenz CC BY 4.0.
"""

import json
import ssl
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

from version import APP_NAME, __version__

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
USER_AGENT = f"{APP_NAME}/{__version__}"

WMO_TEXT = {
    0: "Klar", 1: "Überwiegend klar", 2: "Teilweise bewölkt", 3: "Bedeckt",
    45: "Nebel", 48: "Reifnebel",
    51: "Leichter Nieselregen", 53: "Nieselregen", 55: "Starker Nieselregen",
    56: "Gefrierender Nieselregen", 57: "Starker gefrierender Nieselregen",
    61: "Leichter Regen", 63: "Regen", 65: "Starker Regen",
    66: "Gefrierender Regen", 67: "Starker gefrierender Regen",
    71: "Leichter Schneefall", 73: "Schneefall", 75: "Starker Schneefall",
    77: "Schneegriesel",
    80: "Leichte Regenschauer", 81: "Regenschauer", 82: "Heftige Regenschauer",
    85: "Leichte Schneeschauer", 86: "Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Schweres Gewitter mit Hagel",
}


def wmo_icon(code):
    if code is None:
        return "cloud"
    if code in (0, 1):
        return "sun"
    if code == 2:
        return "partly"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code >= 95:
        return "storm"
    return "rain"


_cache = {}
_cache_lock = threading.Lock()
_fetch_lock = threading.Lock()


def _ssl_context(verify=True):
    if verify:
        return ssl.create_default_context()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _get_json(url, params, timeout=8, verify_ssl=True):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context(verify_ssl)) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _first(values, default=None):
    if isinstance(values, list) and values:
        return values[0]
    return default


def _round(value, digits=1):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _parse_forecast(raw):
    cur = raw.get("current", {}) or {}
    day = raw.get("daily", {}) or {}
    cur_code = cur.get("weather_code")
    day_code = _first(day.get("weather_code"))
    t_max = _round(_first(day.get("temperature_2m_max")))
    t_min = _round(_first(day.get("temperature_2m_min")))
    precip = _round(_first(day.get("precipitation_sum"), 0.0)) or 0.0
    prob = _first(day.get("precipitation_probability_max"))
    return {
        "current": {
            "temp": _round(cur.get("temperature_2m")),
            "apparent": _round(cur.get("apparent_temperature")),
            "precipitation": _round(cur.get("precipitation")),
            "wind": _round(cur.get("wind_speed_10m")),
            "code": cur_code,
            "text": WMO_TEXT.get(cur_code, "Unbekannt"),
            "icon": wmo_icon(cur_code),
        },
        "today": {
            "date": _first(day.get("time")),
            "temp_max": t_max,
            "temp_min": t_min,
            "precip_sum": precip,
            "precip_prob": prob,
            "code": day_code,
            "text": WMO_TEXT.get(day_code, "Unbekannt"),
            "icon": wmo_icon(day_code),
        },
        "timezone": raw.get("timezone"),
    }


def target_values(weather):
    """Ziel-Temperatur und -Niederschlag für die Outfit-Auswahl.

    Die Temperatur wird zur Tageshöchsttemperatur hin gewichtet, weil man
    tagsüber unterwegs ist. Fehlen Tageswerte, gilt die aktuelle Temperatur.
    """
    if not weather or not weather.get("ok"):
        return None
    today = weather["today"]
    t_max, t_min = today.get("temp_max"), today.get("temp_min")
    if t_max is not None and t_min is not None:
        temp = t_min + 0.65 * (t_max - t_min)
    else:
        temp = weather["current"].get("temp")
    if temp is None:
        return None
    return {"temp": round(temp, 1), "rain": float(today.get("precip_sum") or 0.0)}


def get_weather(lat, lon, cache_minutes=15, verify_ssl=True):
    if lat is None or lon is None:
        return {"ok": False, "error": "no_location",
                "message": "Kein Standort festgelegt – bitte unter Einstellungen wählen."}
    key = f"{float(lat):.3f},{float(lon):.3f}"
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
    if hit and now - hit["ts"] < cache_minutes * 60 and hit["day"] == datetime.now().date().isoformat():
        return hit["data"]

    with _fetch_lock:
        # nach Warten auf den Lock prüfen, ob ein anderer Thread schon geholt hat
        with _cache_lock:
            hit = _cache.get(key)
        if hit and time.time() - hit["ts"] < cache_minutes * 60 and hit["day"] == datetime.now().date().isoformat():
            return hit["data"]
        params = {
            "latitude": f"{float(lat):.4f}",
            "longitude": f"{float(lon):.4f}",
            "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                     "precipitation_probability_max,weather_code",
            "timezone": "auto",
            "forecast_days": 1,
        }
        try:
            raw = _get_json(FORECAST_URL, params, verify_ssl=verify_ssl)
            data = _parse_forecast(raw)
            data.update({"ok": True, "stale": False,
                         "fetched_at": datetime.now().strftime("%H:%M")})
            data["target"] = target_values(data)
            with _cache_lock:
                _cache[key] = {"ts": time.time(), "day": datetime.now().date().isoformat(), "data": data}
            return data
        except Exception as exc:  # Netzwerk, SSL, JSON …
            if hit:
                stale = dict(hit["data"])
                stale["stale"] = True
                return stale
            return {"ok": False, "error": "fetch_failed",
                    "message": f"Wetterdaten nicht abrufbar ({exc.__class__.__name__}: {exc})"}


def geocode(query, verify_ssl=True):
    query = (query or "").strip()
    if len(query) < 2:
        return []
    raw = _get_json(GEOCODE_URL, {"name": query, "count": 8, "language": "de", "format": "json"},
                    verify_ssl=verify_ssl)
    results = []
    for r in raw.get("results", []) or []:
        parts = []
        for p in (r.get("name"), r.get("admin1"), r.get("country")):
            if p and p not in parts:
                parts.append(p)
        results.append({
            "name": r.get("name"),
            "label": ", ".join(parts),
            "lat": r.get("latitude"),
            "lon": r.get("longitude"),
        })
    return results
