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

TYPES = [
    {"id": "oberteil", "name": "Oberteil"},
    {"id": "hose", "name": "Hose"},
    {"id": "unterwaesche", "name": "Unterwäsche"},
    {"id": "schuhe", "name": "Schuhe"},
    {"id": "jacke", "name": "Jacke"},
    {"id": "socken", "name": "Socken"},
    {"id": "kopfbedeckung", "name": "Kopfbedeckung"},
    {"id": "accessoire", "name": "Accessoire"},
    {"id": "sonstiges", "name": "Sonstiges"},
]
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

# Gewichte der Bewertung
W_TEMP = 0.40
W_RAIN = 0.20
W_COLOR = 0.40

TEMP_SCALE = (-20, 40)   # °C – Darstellung und Eingabebereich
RAIN_SCALE = (0, 30)     # mm/Tag


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


def _range_fit(lo, hi, value, softness):
    if value is None:
        return 1.0
    if lo <= value <= hi:
        return 1.0
    dist = (lo - value) if value < lo else (value - hi)
    return max(0.0, 1.0 - dist / softness)


def temp_fit(item, target):
    if not target:
        return 1.0
    return _range_fit(item.get("temp_min", -20), item.get("temp_max", 40), target["temp"], 10.0)


def rain_fit(item, target):
    if not target:
        return 1.0
    return _range_fit(item.get("rain_min", 0), item.get("rain_max", 30), target["rain"], 6.0)


def _weighted_choice(rng, candidates, sharpness=0.07):
    """candidates: Liste (score, payload). Bessere Scores sind deutlich
    wahrscheinlicher, aber nicht garantiert – sorgt für Abwechslung."""
    if not candidates:
        return None
    best = max(c[0] for c in candidates)
    weights = [math.exp((s - best) / sharpness) for s, _ in candidates]
    return rng.choices([p for _, p in candidates], weights=weights, k=1)[0]


def _by_type(items, type_id):
    return [i for i in items if i.get("type") == type_id]


def _matches_activity(item, activity):
    return activity in (None, "", "alle") or activity in (item.get("activities") or [])


def _piece(slot, slot_name, item, target, reason=None):
    if item is None:
        return {"slot": slot, "slot_name": slot_name, "item": None, "reason": reason}
    return {
        "slot": slot,
        "slot_name": slot_name,
        "item": item,
        "fit": {
            "temp": round(temp_fit(item, target), 2),
            "rain": round(rain_fit(item, target), 2),
        },
    }


def build_outfit(items, activity=None, target=None, rng=None):
    rng = rng or random.Random()
    tops_all = _by_type(items, "oberteil")
    pants_all = _by_type(items, "hose")
    tops = [i for i in tops_all if _matches_activity(i, activity)]
    pants = [i for i in pants_all if _matches_activity(i, activity)]
    under = _by_type(items, "unterwaesche")
    shoes = _by_type(items, "schuhe")

    # --- Oberteil + Hose gemeinsam bewerten -----------------------------
    pairs = [(t, p) for t in tops for p in pants]
    if len(pairs) > 5000:  # Schutz für sehr große Kleiderschränke
        pairs = rng.sample(pairs, 5000)
    combo_candidates = []
    for t, p in pairs:
        w_temp = (temp_fit(t, target) + temp_fit(p, target)) / 2
        w_rain = (rain_fit(t, target) + rain_fit(p, target)) / 2
        col = color_pair_score(t.get("color"), p.get("color"))
        combo_candidates.append((W_TEMP * w_temp + W_RAIN * w_rain + W_COLOR * col, (t, p)))

    top = pant = None
    if combo_candidates:
        top, pant = _weighted_choice(rng, combo_candidates)
    else:
        # nur eines der beiden vorhanden → einzeln nach Wetter auswählen
        if tops:
            top = _weighted_choice(rng, [(W_TEMP * temp_fit(t, target) + W_RAIN * rain_fit(t, target), t)
                                         for t in tops])
        if pants:
            pant = _weighted_choice(rng, [(W_TEMP * temp_fit(p, target) + W_RAIN * rain_fit(p, target), p)
                                          for p in pants])

    # --- Schuhe: Wetter + Farbe zu Oberteil/Hose (+ Bonus Aktivität) ----
    shoe = None
    if shoes:
        cands = []
        for s in shoes:
            ref = [x.get("color") for x in (top, pant) if x]
            col = sum(color_pair_score(s.get("color"), c) for c in ref) / len(ref) if ref else 0.8
            bonus = 0.1 if activity not in (None, "", "alle") and activity in (s.get("activities") or []) else 0.0
            score = 0.35 * temp_fit(s, target) + 0.30 * rain_fit(s, target) + 0.25 * col + bonus
            cands.append((score, s))
        shoe = _weighted_choice(rng, cands)

    # --- Unterwäsche: Temperatur + Bonus Aktivität, sonst zufällig -------
    undie = None
    if under:
        cands = []
        for u in under:
            bonus = 0.15 if activity not in (None, "", "alle") and activity in (u.get("activities") or []) else 0.0
            cands.append((0.6 * temp_fit(u, target) + bonus, u))
        undie = _weighted_choice(rng, cands, sharpness=0.12)

    # --- Gesamt-Farbharmonie der sichtbaren Teile ------------------------
    visible = [x.get("color") for x in (top, pant, shoe) if x]
    pair_scores = [color_pair_score(visible[i], visible[j])
                   for i in range(len(visible)) for j in range(i + 1, len(visible))]
    harmony = round(sum(pair_scores) / len(pair_scores), 2) if pair_scores else None

    def missing(type_name, all_items, filtered):
        if not all_items:
            return f"Noch kein Kleidungsstück vom Typ „{type_name}“ angelegt."
        if not filtered:
            return f"Kein Stück vom Typ „{type_name}“ mit dieser Aktivität."
        return None

    pieces = [
        _piece("oberteil", "Oberteil", top, target, missing("Oberteil", tops_all, tops)),
        _piece("hose", "Hose", pant, target, missing("Hose", pants_all, pants)),
        _piece("unterwaesche", "Unterwäsche", undie, target, missing("Unterwäsche", under, under)),
        _piece("schuhe", "Schuhe (Empfehlung)", shoe, target, missing("Schuhe", shoes, shoes)),
    ]
    weather_vals = [p["fit"]["temp"] * 0.67 + p["fit"]["rain"] * 0.33 for p in pieces if p.get("item")]
    weather_score = round(sum(weather_vals) / len(weather_vals), 2) if weather_vals and target else None
    return {
        "pieces": pieces,
        "harmony": harmony,
        "weather_score": weather_score,
        "target": target,
        "activity": activity or "alle",
    }
