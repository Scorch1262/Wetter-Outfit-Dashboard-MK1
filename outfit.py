"""Stammdaten (Typen, Farben) und die Logik für die Outfit-Zusammenstellung.

Bewertung einer Zusammenstellung:
  * Wetterpassung   – Temperatur- und Niederschlagsbereich jedes Teils
                      gegenüber dem Tageswetter
  * Farbharmonie    – Farbpaare aus Oberteil, Hose und Schuhen
Aus den bestbewerteten Kombinationen wird gewichtet zufällig gezogen,
damit bei jedem Neuladen eine andere, aber trotzdem passende
Zusammenstellung erscheint.
"""

import math
import random

# ---------------------------------------------------------------------------
# Kleidungstypen
# ---------------------------------------------------------------------------

# temp/rain: ob der Typ eine Temperatur- bzw. Niederschlagsangabe hat
TYPES = [
    {"id": "oberteil", "name": "Oberteil", "temp": True, "rain": True},  # Kategorie mit Untertypen
    {"id": "hose", "name": "Hose", "temp": True, "rain": True},
    {"id": "unterwaesche", "name": "Unterwäsche", "temp": False, "rain": False},
    {"id": "schuhe", "name": "Schuhe", "temp": True, "rain": True},
    {"id": "socken", "name": "Socken", "temp": True, "rain": False},
    {"id": "kopfbedeckung", "name": "Kopfbedeckung", "temp": True, "rain": True},
    {"id": "accessoire", "name": "Accessoire", "temp": True, "rain": True},
    {"id": "sonstiges", "name": "Sonstiges", "temp": True, "rain": True},
]
TYPE_BY_ID = {t["id"]: t for t in TYPES}


def has_attr(type_id, kind):
    """Hat dieser Typ eine Angabe für kind ("temp" oder "rain")?"""
    return TYPE_BY_ID.get(type_id, {}).get(kind, True)
# Untertypen der Kategorie Oberteil – von innen nach außen
SUBTYPES = {
    "oberteil": [
        {"id": "tshirt", "name": "T-Shirt"},
        {"id": "pullover", "name": "Pullover"},
        {"id": "jacke", "name": "Jacke"},
    ],
}
SUBTYPE_IDS = {t: {x["id"] for x in subs} for t, subs in SUBTYPES.items()}
DEFAULT_SUBTYPE = {"oberteil": "tshirt"}
TYPE_IDS = {t["id"] for t in TYPES}

# ---------------------------------------------------------------------------
# Farbpalette
#   neutral: passt zu fast allem
#   muted:   gedeckte Farbe, verzeiht mehr Kombinationen
# ---------------------------------------------------------------------------

COLORS = [
    {"id": "schwarz", "name": "Schwarz", "hex": "#141414", "neutral": True},
    {"id": "anthrazit", "name": "Anthrazit", "hex": "#3b3e44", "neutral": True},
    {"id": "grau", "name": "Grau", "hex": "#8d9096", "neutral": True},
    {"id": "weiss", "name": "Weiß", "hex": "#f4f4f1", "neutral": True},
    {"id": "creme", "name": "Creme", "hex": "#efe6d2", "neutral": True},
    {"id": "beige", "name": "Beige", "hex": "#cdb48f", "neutral": True},
    {"id": "braun", "name": "Braun", "hex": "#7a4f2d", "neutral": True},
    {"id": "marine", "name": "Marine", "hex": "#1f2f55", "neutral": True},
    {"id": "denim", "name": "Jeansblau", "hex": "#3d5a80", "neutral": True},
    {"id": "hellblau", "name": "Hellblau", "hex": "#9cc3e6", "hue": 210, "muted": True},
    {"id": "blau", "name": "Blau", "hex": "#2f6fd0", "hue": 216},
    {"id": "tuerkis", "name": "Türkis", "hex": "#2ab7a9", "hue": 175},
    {"id": "gruen", "name": "Grün", "hex": "#3c9a4f", "hue": 132},
    {"id": "oliv", "name": "Oliv", "hex": "#6b6b2e", "hue": 60, "muted": True},
    {"id": "gelb", "name": "Gelb", "hex": "#f2c230", "hue": 45},
    {"id": "orange", "name": "Orange", "hex": "#e8782b", "hue": 25},
    {"id": "rot", "name": "Rot", "hex": "#d0342c", "hue": 3},
    {"id": "bordeaux", "name": "Bordeaux", "hex": "#6e1f2b", "hue": 350, "muted": True},
    {"id": "rosa", "name": "Rosa", "hex": "#f0a3b5", "hue": 345, "muted": True},
    {"id": "lila", "name": "Lila", "hex": "#7b4fa0", "hue": 275},
    {"id": "bunt", "name": "Bunt / Muster", "hex": "linear-gradient(135deg,#d0342c,#f2c230,#3c9a4f,#2f6fd0)",
     "pattern": True},
]
COLOR_BY_ID = {c["id"]: c for c in COLORS}

# bekannte schwierige Paare unter den Neutralen
_NEUTRAL_SPECIAL = {
    frozenset(("schwarz", "marine")): 0.6,
    frozenset(("schwarz", "braun")): 0.55,
    frozenset(("marine", "braun")): 0.8,
    frozenset(("denim", "marine")): 0.7,
}

# ---------------------------------------------------------------------------
# 6 Stufen für Temperatur und Niederschlag
# lo/hi: Grenzen in °C bzw. mm/Tag (unten inklusive, oben exklusiv)
# ---------------------------------------------------------------------------

TEMP_LEVELS = [
    {"level": 1, "name": "Frost", "lo": -20, "hi": 0, "color": "#4fa3ff"},
    {"level": 2, "name": "Kalt", "lo": 0, "hi": 8, "color": "#5fc3e4"},
    {"level": 3, "name": "Kühl", "lo": 8, "hi": 14, "color": "#35d0ba"},
    {"level": 4, "name": "Mild", "lo": 14, "hi": 19, "color": "#9ed36a"},
    {"level": 5, "name": "Warm", "lo": 19, "hi": 25, "color": "#ffb84d"},
    {"level": 6, "name": "Heiß", "lo": 25, "hi": 40, "color": "#ff6b4d"},
]
RAIN_LEVELS = [
    {"level": 1, "name": "Trocken", "lo": 0, "hi": 0.2, "color": "#c9e2ff"},
    {"level": 2, "name": "Vereinzelt", "lo": 0.2, "hi": 1, "color": "#9fcaff"},
    {"level": 3, "name": "Leicht", "lo": 1, "hi": 3, "color": "#74afff"},
    {"level": 4, "name": "Mäßig", "lo": 3, "hi": 8, "color": "#4f8ff0"},
    {"level": 5, "name": "Stark", "lo": 8, "hi": 15, "color": "#3268d0"},
    {"level": 6, "name": "Unwetter", "lo": 15, "hi": 30, "color": "#2347a8"},
]
TEMP_SCALE = (TEMP_LEVELS[0]["lo"], TEMP_LEVELS[-1]["hi"])
RAIN_SCALE = (RAIN_LEVELS[0]["lo"], RAIN_LEVELS[-1]["hi"])

# Standard-Regeln (in den Einstellungen änderbar)
DEFAULT_RULES = {
    "pullover_max_temp": 16,   # ab dieser Temperatur kein Pullover mehr
    "jacket_max_temp": 12,     # ab dieser Temperatur keine Jacke mehr …
    "jacket_rain_level": 4,    # … außer der Niederschlag erreicht diese Stufe
}

# Gewichte der Bewertung
W_TEMP = 0.40
W_RAIN = 0.20
W_COLOR = 0.40


def color_pair_score(a, b):
    """Liefert 0..1 – wie gut zwei Farben zusammenpassen."""
    ca, cb = COLOR_BY_ID.get(a), COLOR_BY_ID.get(b)
    if not ca or not cb:
        return 0.6  # unbekannt: neutral bewerten
    if ca.get("pattern") or cb.get("pattern"):
        if ca.get("pattern") and cb.get("pattern"):
            return 0.15  # Muster zu Muster
        other = cb if ca.get("pattern") else ca
        return 0.85 if other.get("neutral") else 0.4
    na, nb = ca.get("neutral", False), cb.get("neutral", False)
    if a == b:
        return 0.75 if na else 0.45  # Ton in Ton: neutral ok, bunt eher zu viel
    if na and nb:
        return _NEUTRAL_SPECIAL.get(frozenset((a, b)), 0.95)
    if na or nb:
        return 0.9
    # zwei Farbtöne: Farbkreis-Abstand
    d = abs(ca["hue"] - cb["hue"]) % 360
    d = min(d, 360 - d)
    if d <= 35:
        score = 0.75   # analog
    elif 150 <= d <= 210:
        score = 0.7    # komplementär
    elif 105 <= d < 150:
        score = 0.5    # triadisch
    else:
        score = 0.3    # unruhig
    if ca.get("muted") or cb.get("muted"):
        score = min(1.0, score + 0.15)
    return score


def level_of(value, levels):
    """Stufe (1–6) zu einem Messwert."""
    if value is None:
        return None
    for lv in levels:
        if value < lv["hi"]:
            return lv["level"]
    return levels[-1]["level"]


def range_to_levels(lo, hi, levels):
    """Wandelt einen alten Wertebereich (°C/mm) in einen Stufenbereich um."""
    a = level_of(lo, levels)
    b = level_of(hi, levels)
    # liegt die Obergrenze genau auf einer Stufengrenze, zählt die Stufe darüber nicht mit
    if b > a and hi <= levels[b - 1]["lo"]:
        b -= 1
    return a, b


def levels_to_range(a, b, levels):
    return levels[a - 1]["lo"], levels[b - 1]["hi"]


def clamp_level(v, default):
    try:
        return max(1, min(6, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def _level_fit(a, b, level):
    """1.0 innerhalb der Stufen, 1 Stufe daneben 0.55, 2 Stufen 0.2, sonst 0."""
    if level is None:
        return 1.0
    if a <= level <= b:
        return 1.0
    dist = (a - level) if level < a else (level - b)
    return {1: 0.55, 2: 0.2}.get(dist, 0.0)


def temp_fit(item, target, ignore=()):
    if not target or "temp" in ignore or not has_attr(item.get("type"), "temp"):
        return 1.0
    return _level_fit(item.get("temp_level_min", 1), item.get("temp_level_max", 6), target.get("temp_level"))


def rain_fit(item, target, ignore=()):
    if not target or "rain" in ignore or not has_attr(item.get("type"), "rain"):
        return 1.0
    return _level_fit(item.get("rain_level_min", 1), item.get("rain_level_max", 6), target.get("rain_level"))


def enrich_target(target):
    """Ergänzt die Wetter-Zielwerte um ihre Stufen."""
    if not target:
        return None
    t = dict(target)
    t["temp_level"] = level_of(t["temp"], TEMP_LEVELS)
    t["rain_level"] = level_of(t["rain"], RAIN_LEVELS)
    return t


def layer_rules(target, rules):
    """Welche Oberteil-Schichten heute vorgeschlagen werden."""
    r = dict(DEFAULT_RULES)
    r.update(rules or {})
    if not target:
        return {"pullover": False, "jacket": False, "jacket_reason": None, "rules": r,
                "note": "Ohne Wetterdaten werden kein Pullover und keine Jacke vorgeschlagen."}
    pullover = target["temp"] < r["pullover_max_temp"]
    cold = target["temp"] < r["jacket_max_temp"]
    wet = target["rain_level"] >= r["jacket_rain_level"]
    reason = "kalt" if cold else ("regen" if wet else None)
    return {"pullover": pullover, "jacket": cold or wet, "jacket_reason": reason, "rules": r, "note": None}


def _weighted_choice(rng, candidates, sharpness=0.07):
    """candidates: Liste (score, payload). Bessere Scores sind deutlich
    wahrscheinlicher, aber nicht garantiert – sorgt für Abwechslung."""
    if not candidates:
        return None
    best = max(c[0] for c in candidates)
    weights = [math.exp((s - best) / sharpness) for s, _ in candidates]
    return rng.choices([p for _, p in candidates], weights=weights, k=1)[0]


def _by_type(items, type_id, subtype=None):
    return [i for i in items if i.get("type") == type_id and (subtype is None or i.get("subtype") == subtype)]


def _matches_activity(item, activity):
    return activity in (None, "", "alle") or activity in (item.get("activities") or [])


def _weather_score(item, target, ignore=()):
    return W_TEMP * temp_fit(item, target, ignore) + W_RAIN * rain_fit(item, target, ignore)


def _color_vs(item, others):
    ref = [o.get("color") for o in others if o]
    if not ref:
        return 0.8
    return sum(color_pair_score(item.get("color"), c) for c in ref) / len(ref)


def _piece(slot, slot_name, item, target, reason=None, ignore=None):
    if item is None:
        return {"slot": slot, "slot_name": slot_name, "item": None, "reason": reason}
    ignore = ignore or {}
    return {
        "slot": slot,
        "slot_name": slot_name,
        "item": item,
        # ignored: {"temp": "Begründung", "rain": "Begründung"} – Wert zählt heute nicht
        "ignored": ignore,
        "fit": {
            "temp": round(temp_fit(item, target, ignore), 2),
            "rain": round(rain_fit(item, target, ignore), 2),
        },
    }


def build_outfit(items, activity=None, target=None, rng=None, rules=None):
    rng = rng or random.Random()
    target = enrich_target(target)
    layers = layer_rules(target, rules)
    act = lambda lst: [i for i in lst if _matches_activity(i, activity)]

    tshirts_all = _by_type(items, "oberteil", "tshirt")
    pullis_all = _by_type(items, "oberteil", "pullover")
    jackets_all = _by_type(items, "oberteil", "jacke")
    pants_all = _by_type(items, "hose")
    tshirts, pullis, jackets, pants = act(tshirts_all), act(pullis_all), act(jackets_all), act(pants_all)
    under = _by_type(items, "unterwaesche")
    socks_all = _by_type(items, "socken")
    shoes = _by_type(items, "schuhe")

    # Basis-Oberteil: T-Shirt; gibt es keins, ersatzweise ein Pullover (falls erlaubt)
    base_pool = tshirts or (pullis if layers["pullover"] else [])

    # Ausnahmen: was unter einer Schicht liegt, muss das Wetter nicht selbst abdecken
    #  - Pullover (immer wegen Temperatur) darüber -> Temperatur des T-Shirts zählt nicht
    #  - Jacke nur wegen Niederschlag darüber -> Niederschlag von T-Shirt und Pullover zählt nicht
    pulli_on_top = layers["pullover"] and bool(tshirts) and bool(pullis)
    jacket_for_rain = layers["jacket"] and layers["jacket_reason"] == "regen" and bool(jackets)
    ign_shirt, ign_pulli = {}, {}
    if pulli_on_top:
        ign_shirt["temp"] = "Pullover darüber"
    if jacket_for_rain:
        ign_shirt["rain"] = "Jacke wegen Niederschlag"
        ign_pulli["rain"] = "Jacke wegen Niederschlag"

    # --- Basis-Oberteil + Hose gemeinsam bewerten -----------------------
    pairs = [(t, p) for t in base_pool for p in pants]
    if len(pairs) > 5000:
        pairs = rng.sample(pairs, 5000)
    cands = []
    for t, p in pairs:
        w = (_weather_score(t, target, ign_shirt if t.get("subtype") == "tshirt" else ign_pulli)
             + _weather_score(p, target)) / 2
        cands.append((w + W_COLOR * color_pair_score(t.get("color"), p.get("color")), (t, p)))
    base = pant = None
    if cands:
        base, pant = _weighted_choice(rng, cands)
    else:
        if base_pool:
            base = _weighted_choice(rng, [(_weather_score(t, target, ign_shirt if t.get("subtype") == "tshirt"
                                                          else ign_pulli), t) for t in base_pool])
        if pants:
            pant = _weighted_choice(rng, [(_weather_score(p, target), p) for p in pants])

    # --- Pullover über dem T-Shirt ----------------------------------------
    pulli = None
    if layers["pullover"] and base is not None and base.get("subtype") == "tshirt" and pullis:
        pulli = _weighted_choice(rng, [(_weather_score(x, target, ign_pulli) + W_COLOR * _color_vs(x, [base, pant]), x)
                                       for x in pullis])

    # --- Jacke als äußerste Schicht --------------------------------------
    jacket = None
    if layers["jacket"] and jackets:
        jacket = _weighted_choice(rng, [(_weather_score(x, target) + W_COLOR * _color_vs(x, [pulli or base, pant]), x)
                                        for x in jackets])

    # --- Schuhe: Wetter + Farbe (+ Bonus Aktivität) ------------------------
    shoe = None
    if shoes:
        sc = []
        for s in shoes:
            bonus = 0.1 if activity not in (None, "", "alle") and activity in (s.get("activities") or []) else 0.0
            score = (0.35 * temp_fit(s, target) + 0.30 * rain_fit(s, target)
                     + 0.25 * _color_vs(s, [jacket or pulli or base, pant]) + bonus)
            sc.append((score, s))
        shoe = _weighted_choice(rng, sc)

    # --- Socken: Temperatur + Farbe zu Hose und Schuhen (+ Bonus Aktivität) ---
    # (Socken haben keine Niederschlagsangabe)
    sock = None
    if socks_all:
        kc = []
        for k in socks_all:
            bonus = 0.15 if activity not in (None, "", "alle") and activity in (k.get("activities") or []) else 0.0
            kc.append((0.5 * temp_fit(k, target) + 0.3 * _color_vs(k, [pant, shoe]) + bonus, k))
        sock = _weighted_choice(rng, kc)

    # --- Unterwäsche: Temperatur + Bonus Aktivität -------------------------
    undie = None
    if under:
        uc = []
        for u in under:
            bonus = 0.15 if activity not in (None, "", "alle") and activity in (u.get("activities") or []) else 0.0
            uc.append((0.6 + bonus, u))  # Unterwäsche hat keine Wetterwerte
        undie = _weighted_choice(rng, uc, sharpness=0.12)

    # --- Farbharmonie der sichtbaren Teile ---------------------------------
    visible = [x.get("color") for x in (jacket, pulli, base, pant, shoe) if x]
    pair_scores = [color_pair_score(visible[i], visible[j])
                   for i in range(len(visible)) for j in range(i + 1, len(visible))]
    harmony = round(sum(pair_scores) / len(pair_scores), 2) if pair_scores else None

    def missing(name, all_items, filtered):
        if not all_items:
            return f"Noch kein Kleidungsstück „{name}“ angelegt."
        if not filtered:
            return f"Kein Stück „{name}“ mit dieser Aktivität."
        return None

    pieces = []
    if layers["jacket"]:
        pieces.append(_piece("jacke", "Oberteil · Jacke", jacket, target, missing("Jacke", jackets_all, jackets)))
    if layers["pullover"] and (base is None or base.get("subtype") == "tshirt"):
        pieces.append(_piece("pullover", "Oberteil · Pullover", pulli, target,
                             missing("Pullover", pullis_all, pullis), ign_pulli))
    base_is_shirt = base is None or base.get("subtype") == "tshirt"
    base_name = "Oberteil · " + ("T-Shirt" if base_is_shirt else "Pullover")
    pieces.append(_piece("oberteil", base_name, base, target, missing("T-Shirt", tshirts_all, tshirts),
                         ign_shirt if base_is_shirt else ign_pulli))
    pieces += [
        _piece("hose", "Hose", pant, target, missing("Hose", pants_all, pants)),
        _piece("unterwaesche", "Unterwäsche", undie, target, missing("Unterwäsche", under, under)),
        _piece("socken", "Socken", sock, target, missing("Socken", socks_all, socks_all)),
        _piece("schuhe", "Schuhe (Empfehlung)", shoe, target, missing("Schuhe", shoes, shoes)),
    ]
    weather_vals = [p["fit"]["temp"] * 0.67 + p["fit"]["rain"] * 0.33 for p in pieces if p.get("item")]
    weather_score = round(sum(weather_vals) / len(weather_vals), 2) if weather_vals and target else None
    return {
        "pieces": pieces,
        "harmony": harmony,
        "weather_score": weather_score,
        "target": target,
        "layers": layers,
        "activity": activity or "alle",
    }
