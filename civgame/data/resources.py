"""Tile resources: strategic (unit-gating), luxury (happiness), bonus (yield).

Strategic resources gate advanced military production. Luxury resources give
happiness per unique type across the civ. Bonus resources improve tile yield
directly. All are procedurally placed at map-gen time.
"""

RESOURCES = {
    # ---------------- Strategic ----------------
    "iron": {
        "type": "strategic", "tech": "iron_working",
        "terrain": ["hills", "mountain", "plains"],
        "units": ["swordsman", "knight"],
        "icon": "Fe", "color": "#8a8a8a",
    },
    "horse": {
        "type": "strategic", "tech": "horseback",
        "terrain": ["plains", "grass"],
        "units": ["horseman", "knight"],
        "icon": "Hr", "color": "#c88540",
    },
    "coal": {
        "type": "strategic", "tech": "steam_power",
        "terrain": ["hills"],
        "units": ["ironclad"],
        "icon": "Cl", "color": "#202020",
    },
    "oil": {
        "type": "strategic", "tech": "dynamite",
        "terrain": ["desert", "hills"],
        "units": ["tank", "artillery", "fighter", "bomber"],
        "icon": "Ol", "color": "#3a1a1a",
    },
    "uranium": {
        "type": "strategic", "tech": "nuclear_fission",
        "terrain": ["mountain", "hills"],
        "units": [],  # gates nuclear_plant building (handled separately)
        "icon": "U",  "color": "#5ee65e",
    },

    # ---------------- Luxury (+2 happy per unique type per civ) ----------------
    "wine":    {"type": "luxury", "tech": None, "terrain": ["grass", "plains"], "icon": "Wi", "color": "#9c2c5a"},
    "silk":    {"type": "luxury", "tech": None, "terrain": ["forest"],           "icon": "Sk", "color": "#c77ed9"},
    "gems":    {"type": "luxury", "tech": "mining", "terrain": ["hills", "mountain"], "icon": "Gm", "color": "#e05eb0"},
    "gold_ore":{"type": "luxury", "tech": "mining", "terrain": ["hills", "mountain"], "icon": "Au", "color": "#ffd700"},
    "incense": {"type": "luxury", "tech": None, "terrain": ["desert", "plains"], "icon": "In", "color": "#c9a872"},
    "spices":  {"type": "luxury", "tech": None, "terrain": ["grass", "forest"],  "icon": "Sp", "color": "#d06020"},
    "ivory":   {"type": "luxury", "tech": None, "terrain": ["plains", "grass"],  "icon": "Iv", "color": "#eee2c0"},
    "dyes":    {"type": "luxury", "tech": None, "terrain": ["forest", "grass"],  "icon": "Dy", "color": "#7040aa"},

    # ---------------- Bonus (passive tile yield — no tech, no trade) ----------------
    "wheat":  {"type": "bonus", "tech": None, "terrain": ["grass", "plains"],  "yield": {"food": 2},             "icon": "Wh", "color": "#e4c664"},
    "cattle": {"type": "bonus", "tech": None, "terrain": ["grass", "plains"],  "yield": {"food": 1, "prod": 1}, "icon": "Ca", "color": "#b07030"},
    "fish":   {"type": "bonus", "tech": None, "terrain": ["coast", "water"],    "yield": {"food": 2},             "icon": "Fs", "color": "#4fb0ff"},
    "deer":   {"type": "bonus", "tech": None, "terrain": ["forest", "hills"],  "yield": {"food": 1, "prod": 1}, "icon": "De", "color": "#9c6030"},
    "stone":  {"type": "bonus", "tech": None, "terrain": ["hills", "mountain"],"yield": {"prod": 2},             "icon": "St", "color": "#909090"},
}


def strategic_units_requirement(unit_type):
    """Return the strategic resource required to build this unit, or None."""
    for rname, rdata in RESOURCES.items():
        if rdata["type"] == "strategic" and unit_type in rdata.get("units", []):
            return rname
    return None


LUXURY_HAPPINESS_PER_TYPE = 2
