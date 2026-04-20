"""Tile improvements: worker-built upgrades that add yield or movement bonuses."""

IMPROVEMENTS = {
    "farm":       {"tech": "agriculture",      "turns": 4, "terrain": ["grass", "plains", "desert"],
                   "food": 1, "prod": 0, "gold": 0},
    "mine":       {"tech": "mining",           "turns": 5, "terrain": ["hills"],
                   "food": 0, "prod": 2, "gold": 0},
    "lumber_mill":{"tech": "construction",     "turns": 5, "terrain": ["forest"],
                   "food": 0, "prod": 1, "gold": 0},
    "road":       {"tech": None,               "turns": 3, "terrain": ["grass", "plains", "forest", "hills", "desert"],
                   "food": 0, "prod": 0, "gold": 0},
    "quarry":     {"tech": "mining",           "turns": 5, "terrain": ["mountain"],
                   "food": 0, "prod": 1, "gold": 1},
    "trading_post":{"tech": "currency",        "turns": 4, "terrain": ["grass", "plains", "forest"],
                    "food": 0, "prod": 0, "gold": 2},
    "railroad":   {"tech": "railroad",         "turns": 4, "terrain": ["grass", "plains", "forest", "hills", "desert"],
                   "food": 0, "prod": 0, "gold": 0},
}
