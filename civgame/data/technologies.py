"""Tech tree. Each tech has cost, era, prereqs, and units/buildings/improvements it unlocks."""

TECHNOLOGIES = {
    # Ancient
    "agriculture":    {"cost": 20,  "era": "Ancient",     "prereqs": [],                "unlocks": ["granary"]},
    "pottery":        {"cost": 20,  "era": "Ancient",     "prereqs": [],                "unlocks": ["palace"]},
    "mining":         {"cost": 20,  "era": "Ancient",     "prereqs": [],                "unlocks": ["mine_improvement"]},
    "bronze_working": {"cost": 30,  "era": "Ancient",     "prereqs": ["mining"],        "unlocks": ["spearman", "barracks"]},
    "archery":        {"cost": 25,  "era": "Ancient",     "prereqs": [],                "unlocks": ["archer"]},
    "sailing":        {"cost": 30,  "era": "Ancient",     "prereqs": [],                "unlocks": ["galley", "harbor"]},
    "writing":        {"cost": 35,  "era": "Ancient",     "prereqs": ["pottery"],       "unlocks": ["library"]},
    # Classical
    "iron_working":   {"cost": 50,  "era": "Classical",   "prereqs": ["bronze_working"],"unlocks": ["swordsman", "forge"]},
    "mathematics":    {"cost": 50,  "era": "Classical",   "prereqs": ["writing"],       "unlocks": ["catapult"]},
    "construction":   {"cost": 50,  "era": "Classical",   "prereqs": ["mining"],        "unlocks": ["walls", "aqueduct", "colosseum"]},
    "currency":       {"cost": 50,  "era": "Classical",   "prereqs": ["writing"],       "unlocks": ["marketplace"]},
    "horseback":      {"cost": 45,  "era": "Classical",   "prereqs": ["archery"],       "unlocks": ["horseman", "stable"]},
    # Medieval
    "feudalism":      {"cost": 80,  "era": "Medieval",    "prereqs": ["iron_working"],  "unlocks": ["knight"]},
    "engineering":    {"cost": 80,  "era": "Medieval",    "prereqs": ["mathematics", "construction"], "unlocks": ["castle", "workshop"]},
    "theology":       {"cost": 70,  "era": "Medieval",    "prereqs": ["writing"],       "unlocks": ["temple", "monastery"]},
    "education":      {"cost": 90,  "era": "Medieval",    "prereqs": ["theology", "mathematics"], "unlocks": ["university", "school"]},
    # Renaissance
    "gunpowder":      {"cost": 120, "era": "Renaissance", "prereqs": ["engineering"],   "unlocks": ["musketman"]},
    "printing_press": {"cost": 100, "era": "Renaissance", "prereqs": ["education"],     "unlocks": ["bank"]},
    "navigation":     {"cost": 100, "era": "Renaissance", "prereqs": ["sailing", "engineering"], "unlocks": ["caravel"]},
    "astronomy":      {"cost": 110, "era": "Renaissance", "prereqs": ["education"],     "unlocks": ["observatory"]},
    "aesthetics":     {"cost": 90,  "era": "Renaissance", "prereqs": ["theology", "printing_press"], "unlocks": ["museum", "theater"]},
    # Industrial
    "industrialization": {"cost": 160, "era": "Industrial", "prereqs": ["gunpowder", "printing_press"], "unlocks": ["factory", "rifleman", "hospital"]},
    "steam_power":       {"cost": 160, "era": "Industrial", "prereqs": ["industrialization"],           "unlocks": ["ironclad"]},
    "railroad":          {"cost": 150, "era": "Industrial", "prereqs": ["steam_power"],                 "unlocks": ["railroad_improvement"]},
    "dynamite":          {"cost": 170, "era": "Industrial", "prereqs": ["industrialization"],           "unlocks": ["artillery", "infantry"]},
    "military_science":  {"cost": 140, "era": "Industrial", "prereqs": ["gunpowder", "education"],     "unlocks": ["military_academy"]},
    # Modern
    "electricity":    {"cost": 220, "era": "Modern", "prereqs": ["steam_power"],           "unlocks": ["power_plant", "stadium"]},
    "flight":         {"cost": 250, "era": "Modern", "prereqs": ["dynamite"],              "unlocks": ["fighter", "bomber", "airport"]},
    "nuclear_fission":{"cost": 350, "era": "Modern", "prereqs": ["electricity", "flight"], "unlocks": ["nuclear_plant", "bunker"]},
    "rocketry":       {"cost": 400, "era": "Modern", "prereqs": ["flight"],               "unlocks": ["tank"]},
    "space_program":  {"cost": 800, "era": "Modern", "prereqs": ["nuclear_fission", "rocketry"], "unlocks": ["spaceship"]},
}
