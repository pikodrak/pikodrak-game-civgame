"""
Civilization-like game engine - core game logic
"""
import random
from enum import Enum

# Game config — overridden by config_loader from game_config.ini
GAME_CONFIG = {}

# ============================================================
# TERRAIN & MAP
# ============================================================

class Terrain(str, Enum):
    GRASS = "grass"
    PLAINS = "plains"
    FOREST = "forest"
    HILLS = "hills"
    MOUNTAIN = "mountain"
    DESERT = "desert"
    WATER = "water"
    COAST = "coast"

TERRAIN_YIELDS = {
    Terrain.GRASS:    {"food": 2, "prod": 1, "gold": 0},
    Terrain.PLAINS:   {"food": 1, "prod": 2, "gold": 0},
    Terrain.FOREST:   {"food": 1, "prod": 2, "gold": 0},
    Terrain.HILLS:    {"food": 0, "prod": 3, "gold": 0},
    Terrain.MOUNTAIN: {"food": 0, "prod": 1, "gold": 1},
    Terrain.DESERT:   {"food": 0, "prod": 1, "gold": 1},
    Terrain.WATER:    {"food": 2, "prod": 0, "gold": 1},
    Terrain.COAST:    {"food": 1, "prod": 0, "gold": 2},
}

TERRAIN_MOVE_COST = {
    Terrain.GRASS: 1, Terrain.PLAINS: 1, Terrain.FOREST: 2,
    Terrain.HILLS: 2, Terrain.MOUNTAIN: 99, Terrain.DESERT: 1,
    Terrain.WATER: 99, Terrain.COAST: 99,
}

TERRAIN_DEFENSE = {
    Terrain.GRASS: 0, Terrain.PLAINS: 0, Terrain.FOREST: 25,
    Terrain.HILLS: 50, Terrain.MOUNTAIN: 0, Terrain.DESERT: -10,
    Terrain.WATER: 0, Terrain.COAST: 0,
}

# ============================================================
# HEX MATH (offset coordinates, odd-r pointy-top)
# ============================================================

def hex_neighbors(q, r):
    """Return the 6 neighbors of hex (q, r) in odd-r offset coords."""
    if r & 1:  # odd row
        return [
            (q, r-1), (q+1, r-1), (q+1, r),
            (q, r+1), (q+1, r+1), (q-1, r)
        ]
    else:  # even row
        return [
            (q-1, r-1), (q, r-1), (q+1, r),
            (q, r+1), (q-1, r+1), (q-1, r)
        ]

def hex_distance(q1, r1, q2, r2):
    """Hex distance using cube coordinates (odd-r offset)."""
    def offset_to_cube(q, r):
        x = q - (r - (r & 1)) // 2
        z = r
        y = -x - z
        return x, y, z
    x1, y1, z1 = offset_to_cube(q1, r1)
    x2, y2, z2 = offset_to_cube(q2, r2)
    return max(abs(x1-x2), abs(y1-y2), abs(z1-z2))

# ============================================================
# TECH TREE
# ============================================================

TECHNOLOGIES = {
    # Ancient
    "agriculture":    {"cost": 20,  "era": "Ancient",     "prereqs": [],                "unlocks": ["granary"]},
    "pottery":        {"cost": 20,  "era": "Ancient",     "prereqs": [],                "unlocks": ["palace"]},
    "mining":         {"cost": 20,  "era": "Ancient",     "prereqs": [],                "unlocks": ["mine_improvement"]},
    "bronze_working": {"cost": 30,  "era": "Ancient",     "prereqs": ["mining"],        "unlocks": ["spearman"]},
    "archery":        {"cost": 25,  "era": "Ancient",     "prereqs": [],                "unlocks": ["archer"]},
    "sailing":        {"cost": 30,  "era": "Ancient",     "prereqs": [],                "unlocks": ["galley"]},
    "writing":        {"cost": 35,  "era": "Ancient",     "prereqs": ["pottery"],       "unlocks": ["library"]},
    # Classical
    "iron_working":   {"cost": 50,  "era": "Classical",   "prereqs": ["bronze_working"],"unlocks": ["swordsman"]},
    "mathematics":    {"cost": 50,  "era": "Classical",   "prereqs": ["writing"],       "unlocks": ["catapult"]},
    "construction":   {"cost": 50,  "era": "Classical",   "prereqs": ["mining"],        "unlocks": ["walls", "aqueduct"]},
    "currency":       {"cost": 50,  "era": "Classical",   "prereqs": ["writing"],       "unlocks": ["marketplace"]},
    "horseback":      {"cost": 45,  "era": "Classical",   "prereqs": ["archery"],       "unlocks": ["horseman"]},
    # Medieval
    "feudalism":      {"cost": 80,  "era": "Medieval",    "prereqs": ["iron_working"],  "unlocks": ["knight"]},
    "engineering":    {"cost": 80,  "era": "Medieval",    "prereqs": ["mathematics", "construction"], "unlocks": ["castle"]},
    "theology":       {"cost": 70,  "era": "Medieval",    "prereqs": ["writing"],       "unlocks": ["temple", "monastery"]},
    "education":      {"cost": 90,  "era": "Medieval",    "prereqs": ["theology", "mathematics"], "unlocks": ["university"]},
    # Renaissance
    "gunpowder":      {"cost": 120, "era": "Renaissance", "prereqs": ["engineering"],   "unlocks": ["musketman"]},
    "printing_press": {"cost": 100, "era": "Renaissance", "prereqs": ["education"],     "unlocks": ["bank"]},
    "navigation":     {"cost": 100, "era": "Renaissance", "prereqs": ["sailing", "engineering"], "unlocks": ["caravel"]},
    "astronomy":      {"cost": 110, "era": "Renaissance", "prereqs": ["education"],     "unlocks": ["observatory"]},
    # Industrial
    "industrialization": {"cost": 160, "era": "Industrial", "prereqs": ["gunpowder", "printing_press"], "unlocks": ["factory", "rifleman"]},
    "steam_power":       {"cost": 160, "era": "Industrial", "prereqs": ["industrialization"],           "unlocks": ["ironclad"]},
    "railroad":          {"cost": 150, "era": "Industrial", "prereqs": ["steam_power"],                 "unlocks": ["railroad_improvement"]},
    "dynamite":          {"cost": 170, "era": "Industrial", "prereqs": ["industrialization"],           "unlocks": ["artillery", "infantry"]},
    # Modern
    "electricity":    {"cost": 220, "era": "Modern", "prereqs": ["steam_power"],           "unlocks": ["power_plant"]},
    "flight":         {"cost": 250, "era": "Modern", "prereqs": ["dynamite"],              "unlocks": ["fighter", "bomber"]},
    "nuclear_fission":{"cost": 350, "era": "Modern", "prereqs": ["electricity", "flight"], "unlocks": ["nuclear_plant"]},
    "rocketry":       {"cost": 400, "era": "Modern", "prereqs": ["flight"],               "unlocks": ["tank"]},
    "space_program":  {"cost": 800, "era": "Modern", "prereqs": ["nuclear_fission", "rocketry"], "unlocks": ["spaceship"]},
}

# ============================================================
# UNIT DEFINITIONS
# ============================================================

UNIT_TYPES = {
    # name:          (attack, defense, movement, cost, prereq_tech, category)
    "settler":       {"atk": 0,  "def": 1,  "mov": 2, "cost": 40, "tech": None,              "cat": "civilian"},
    "worker":        {"atk": 0,  "def": 0,  "mov": 2, "cost": 25, "tech": None,              "cat": "civilian"},
    "spy":           {"atk": 0,  "def": 0,  "mov": 3, "cost": 40, "tech": "writing",         "cat": "civilian"},
    "caravan":       {"atk": 0,  "def": 0,  "mov": 3, "cost": 30, "tech": "currency",        "cat": "civilian"},
    "warrior":       {"atk": 2,  "def": 1,  "mov": 2, "cost": 15, "tech": None,              "cat": "melee"},
    "spearman":      {"atk": 2,  "def": 3,  "mov": 2, "cost": 20, "tech": "bronze_working",  "cat": "melee"},
    "archer":        {"atk": 3,  "def": 1,  "mov": 2, "cost": 20, "tech": "archery",         "cat": "ranged"},
    "horseman":      {"atk": 4,  "def": 2,  "mov": 3, "cost": 30, "tech": "horseback",       "cat": "mounted"},
    "swordsman":     {"atk": 5,  "def": 3,  "mov": 2, "cost": 30, "tech": "iron_working",    "cat": "melee"},
    "catapult":      {"atk": 6,  "def": 1,  "mov": 1, "cost": 35, "tech": "mathematics",     "cat": "siege"},
    "knight":        {"atk": 7,  "def": 4,  "mov": 3, "cost": 45, "tech": "feudalism",       "cat": "mounted"},
    "musketman":     {"atk": 8,  "def": 5,  "mov": 2, "cost": 50, "tech": "gunpowder",       "cat": "melee"},
    "rifleman":      {"atk": 12, "def": 8,  "mov": 2, "cost": 60, "tech": "industrialization","cat": "melee"},
    "artillery":     {"atk": 14, "def": 2,  "mov": 1, "cost": 55, "tech": "dynamite",        "cat": "siege"},
    "infantry":      {"atk": 16, "def": 12, "mov": 2, "cost": 70, "tech": "dynamite",        "cat": "melee"},
    "tank":          {"atk": 24, "def": 15, "mov": 3, "cost": 90, "tech": "rocketry",        "cat": "mounted"},
    "fighter":       {"atk": 18, "def": 10, "mov": 5, "cost": 80, "tech": "flight",          "cat": "air"},
    "bomber":        {"atk": 25, "def": 5,  "mov": 5, "cost": 90, "tech": "flight",          "cat": "air"},
    "galley":        {"atk": 2,  "def": 2,  "mov": 3, "cost": 25, "tech": "sailing",         "cat": "naval"},
    "caravel":       {"atk": 4,  "def": 3,  "mov": 4, "cost": 40, "tech": "navigation",      "cat": "naval"},
    "ironclad":      {"atk": 10, "def": 8,  "mov": 4, "cost": 60, "tech": "steam_power",     "cat": "naval"},
}

# ============================================================
# BUILDING DEFINITIONS
# ============================================================

BUILDINGS = {
    "palace":      {"cost": 1,   "tech": None,            "food": 0, "prod": 2, "gold": 2, "science": 3, "culture": 1, "defense": 10, "happiness": 0},
    "granary":     {"cost": 30,  "tech": "agriculture",   "food": 3, "prod": 0, "gold": 0, "science": 0, "culture": 0, "defense": 0,  "happiness": 0},
    "library":     {"cost": 40,  "tech": "writing",       "food": 0, "prod": 0, "gold": 0, "science": 3, "culture": 1, "defense": 0,  "happiness": 0},
    "walls":       {"cost": 35,  "tech": "construction",  "food": 0, "prod": 0, "gold": 0, "science": 0, "culture": 0, "defense": 50, "happiness": 0},
    "marketplace": {"cost": 45,  "tech": "currency",      "food": 0, "prod": 0, "gold": 4, "science": 0, "culture": 0, "defense": 0,  "happiness": 1},
    "aqueduct":    {"cost": 50,  "tech": "construction",  "food": 3, "prod": 0, "gold": 0, "science": 0, "culture": 0, "defense": 0,  "happiness": 0},
    "temple":      {"cost": 40,  "tech": "theology",      "food": 0, "prod": 0, "gold": 0, "science": 0, "culture": 3, "defense": 0,  "happiness": 2},
    "monastery":   {"cost": 50,  "tech": "theology",      "food": 0, "prod": 0, "gold": 0, "science": 2, "culture": 2, "defense": 0,  "happiness": 1},
    "castle":      {"cost": 60,  "tech": "engineering",   "food": 0, "prod": 0, "gold": 0, "science": 0, "culture": 1, "defense": 80, "happiness": 0},
    "university":  {"cost": 80,  "tech": "education",     "food": 0, "prod": 0, "gold": 0, "science": 5, "culture": 2, "defense": 0,  "happiness": 0},
    "bank":        {"cost": 70,  "tech": "printing_press","food": 0, "prod": 0, "gold": 5, "science": 0, "culture": 0, "defense": 0,  "happiness": 1},
    "observatory": {"cost": 90,  "tech": "astronomy",     "food": 0, "prod": 0, "gold": 0, "science": 5, "culture": 0, "defense": 0,  "happiness": 0},
    "factory":     {"cost": 100, "tech": "industrialization","food": 0, "prod": 5, "gold": 0, "science": 0, "culture": 0, "defense": 0, "happiness": -1},
    "power_plant": {"cost": 120, "tech": "electricity",   "food": 0, "prod": 5, "gold": 0, "science": 0, "culture": 0, "defense": 0,  "happiness": -1},
    "nuclear_plant":{"cost": 160,"tech": "nuclear_fission","food": 0, "prod": 8, "gold": 0, "science": 3, "culture": 0, "defense": 0, "happiness": -2},
}

# ============================================================
# CIVILIZATIONS
# ============================================================

CIVILIZATIONS = {
    "rome":     {"name": "Roman Empire",     "color": "#e74c3c", "bonus": "prod",    "leader": "Caesar",
                 "trait": "industrious", "aggression": 0.5, "loyalty": 0.7,
                 "strategy": "builder"},      # focus: production buildings, wonders, infrastructure
    "egypt":    {"name": "Egypt",            "color": "#f1c40f", "bonus": "culture",  "leader": "Cleopatra",
                 "trait": "creative",   "aggression": 0.3, "loyalty": 0.8,
                 "strategy": "culturalist"},   # focus: culture, temples, borders, peaceful
    "greece":   {"name": "Greece",           "color": "#3498db", "bonus": "science",  "leader": "Alexander",
                 "trait": "aggressive", "aggression": 0.8, "loyalty": 0.5,
                 "strategy": "conqueror"},     # focus: military rush, conquer neighbors early
    "china":    {"name": "China",            "color": "#e67e22", "bonus": "food",     "leader": "Qin Shi Huang",
                 "trait": "expansive",  "aggression": 0.3, "loyalty": 0.7,
                 "strategy": "expansionist"},  # focus: settlers, many cities, food
    "persia":   {"name": "Persia",           "color": "#9b59b6", "bonus": "gold",     "leader": "Cyrus",
                 "trait": "financial",  "aggression": 0.5, "loyalty": 0.5,
                 "strategy": "builder"},       # focus: gold economy + production → space race
    "aztec":    {"name": "Aztec Empire",     "color": "#2ecc71", "bonus": "military", "leader": "Montezuma",
                 "trait": "aggressive", "aggression": 0.85, "loyalty": 0.35,
                 "strategy": "conqueror"},     # focus: conquest victory via military
    "japan":    {"name": "Japan",            "color": "#ecf0f1", "bonus": "defense",  "leader": "Tokugawa",
                 "trait": "protective", "aggression": 0.4, "loyalty": 0.9,
                 "strategy": "turtle"},        # focus: defense, walls, castles, tech
    "czech":    {"name": "Czech Kingdom",    "color": "#d35400", "bonus": "science",  "leader": "Jan Zizka",
                 "trait": "industrious", "aggression": 0.35, "loyalty": 0.85,
                 "strategy": "turtle"},        # focus: defense (Hussite wagons), science, industry
    "mongol":   {"name": "Mongol Empire",    "color": "#1abc9c", "bonus": "movement", "leader": "Genghis Khan",
                 "trait": "aggressive", "aggression": 1.0, "loyalty": 0.2,
                 "strategy": "conqueror"},     # focus: fast units, conquest, nomadic
}

# Leader traits:
#   aggressive  — needs fewer military to attack (3 instead of 5), wider attack range
#   creative    — +2 culture per city, borders expand faster
#   expansive   — settlers cost 25% less, +1 food in cities
#   financial   — +1 gold from tiles with 2+ gold
#   protective  — +25% city defense, prefers defense over offense

# ============================================================
# TILE IMPROVEMENTS
# ============================================================

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

# ============================================================
# MAP GENERATOR
# ============================================================

def generate_map(width, height, seed=None):
    """Generate a hex map with continents and varied terrain."""
    if seed is not None:
        random.seed(seed)

    tiles = {}
    # Start with all water
    for q in range(width):
        for r in range(height):
            tiles[(q, r)] = Terrain.WATER

    # Generate continents using random walk
    num_land = int(width * height * 0.55)
    land_tiles = set()

    # Scale continent count with map size
    area = width * height
    num_continents = max(3, min(15, int(area / 300)))
    seeds = []
    for _ in range(num_continents):
        sq = random.randint(2, width - 3)
        sr = random.randint(2, height - 3)
        seeds.append((sq, sr))
        land_tiles.add((sq, sr))

    # Grow continents
    while len(land_tiles) < num_land:
        seed_tile = random.choice(list(land_tiles))
        neighbors = hex_neighbors(*seed_tile)
        valid = [(nq, nr) for nq, nr in neighbors
                 if 0 <= nq < width and 0 <= nr < height]
        if valid:
            chosen = random.choice(valid)
            land_tiles.add(chosen)

    # Assign terrain types to land
    for (q, r) in land_tiles:
        # Use position-based biomes
        lat = r / height  # 0=top, 1=bottom
        rand = random.random()

        if lat < 0.15 or lat > 0.85:  # Polar-ish
            if rand < 0.4:
                tiles[(q, r)] = Terrain.HILLS
            elif rand < 0.7:
                tiles[(q, r)] = Terrain.PLAINS
            else:
                tiles[(q, r)] = Terrain.MOUNTAIN
        elif 0.35 < lat < 0.65:  # Equatorial
            if rand < 0.3:
                tiles[(q, r)] = Terrain.DESERT
            elif rand < 0.5:
                tiles[(q, r)] = Terrain.PLAINS
            elif rand < 0.8:
                tiles[(q, r)] = Terrain.GRASS
            else:
                tiles[(q, r)] = Terrain.HILLS
        else:  # Temperate
            if rand < 0.3:
                tiles[(q, r)] = Terrain.GRASS
            elif rand < 0.55:
                tiles[(q, r)] = Terrain.FOREST
            elif rand < 0.75:
                tiles[(q, r)] = Terrain.PLAINS
            elif rand < 0.9:
                tiles[(q, r)] = Terrain.HILLS
            else:
                tiles[(q, r)] = Terrain.MOUNTAIN

    # Create coastal tiles
    for q in range(width):
        for r in range(height):
            if tiles[(q, r)] == Terrain.WATER:
                neighbors = hex_neighbors(q, r)
                for nq, nr in neighbors:
                    if (nq, nr) in tiles and tiles[(nq, nr)] not in (Terrain.WATER, Terrain.COAST):
                        tiles[(q, r)] = Terrain.COAST
                        break

    return tiles

# ============================================================
# GAME STATE
# ============================================================

class GameState:
    def __init__(self, width=40, height=30, num_players=4, seed=None):
        self.width = width
        self.height = height
        self.turn = 1
        self.current_player = 0
        self.ai_log = []  # Debug log for AI decisions
        self.game_over = False
        self.winner = None
        self.next_unit_id = 1
        self.next_city_id = 1

        # Generate map
        self.tiles = generate_map(width, height, seed)

        # Players
        civ_keys = list(CIVILIZATIONS.keys())
        random.shuffle(civ_keys)
        self.players = []
        for i in range(num_players):
            civ = civ_keys[i % len(civ_keys)]
            self.players.append({
                "id": i,
                "civ": civ,
                "name": CIVILIZATIONS[civ]["name"],
                "color": CIVILIZATIONS[civ]["color"],
                "leader": CIVILIZATIONS[civ]["leader"],
                "gold": GAME_CONFIG.get("starting_gold", 30),
                "science_pool": 0,
                "culture_pool": 0,
                "researching": None,
                "techs": [],
                "alive": True,
                "score": 0,
                "is_human": (i == 0),
                "diplomacy": {},  # player_id -> "peace"/"war"/"neutral"
                "diplo_cooldown": {},  # player_id -> turns until can change again
                "trait": CIVILIZATIONS[civ].get("trait", "aggressive"),
                "aggression": CIVILIZATIONS[civ].get("aggression", 0.5),
                "loyalty": CIVILIZATIONS[civ].get("loyalty", 0.5),
                "strategy": CIVILIZATIONS[civ].get("strategy", "balanced"),
            })

        # Init diplomacy
        for p in self.players:
            for other in self.players:
                if p["id"] != other["id"]:
                    p["diplomacy"][other["id"]] = "peace"

        self.units = {}   # unit_id -> unit dict
        self.cities = {}  # city_id -> city dict
        self.improvements = {}  # (q,r) -> {"type": str, "player": int} (farm/mine/etc)
        self.roads = {}        # (q,r) -> {"type": "road"/"railroad", "player": int}
        self.explored = {i: set() for i in range(num_players)}  # player_id -> set of (q,r)

        # Place starting units
        self._place_starting_units()

    def _find_good_start(self, taken_positions):
        """Find a good starting position away from others."""
        best = None
        best_score = -1

        attempts = max(200, self.width * self.height // 6)
        for _ in range(attempts):
            q = random.randint(3, self.width - 4)
            r = random.randint(3, self.height - 4)

            if self.tiles.get((q, r)) in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                continue

            # Check distance from others
            min_dist = 999
            for tq, tr in taken_positions:
                d = hex_distance(q, r, tq, tr)
                min_dist = min(min_dist, d)

            if min_dist < 6:
                continue

            # Score: count good tiles nearby
            score = min_dist * 2
            for nq, nr in hex_neighbors(q, r):
                t = self.tiles.get((nq, nr))
                if t and t not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                    score += TERRAIN_YIELDS[t]["food"] + TERRAIN_YIELDS[t]["prod"]

            if score > best_score:
                best_score = score
                best = (q, r)

        return best or (self.width // 2, self.height // 2)

    def _place_starting_units(self):
        taken = []
        for p in self.players:
            pos = self._find_good_start(taken)
            taken.append(pos)

            # Create settler
            self._create_unit(p["id"], "settler", pos[0], pos[1])
            # Create warrior on adjacent tile
            wq, wr = pos
            used_tiles = [pos]
            for nq, nr in hex_neighbors(wq, wr):
                if self.tiles.get((nq, nr)) not in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                    wq, wr = nq, nr
                    break
            self._create_unit(p["id"], "warrior", wq, wr)
            used_tiles.append((wq, wr))
            # Create worker on another adjacent tile
            for nq, nr in hex_neighbors(pos[0], pos[1]):
                if (nq, nr) not in used_tiles and self.tiles.get((nq, nr)) not in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                    self._create_unit(p["id"], "worker", nq, nr)
                    break

    def _create_unit(self, player_id, unit_type, q, r):
        uid = self.next_unit_id
        self.next_unit_id += 1
        stats = UNIT_TYPES[unit_type]
        self.units[uid] = {
            "id": uid,
            "player": player_id,
            "type": unit_type,
            "q": q, "r": r,
            "hp": 100,
            "atk": stats["atk"],
            "def": stats["def"],
            "mov": stats["mov"],
            "moves_left": stats["mov"],
            "cat": stats["cat"],
            "xp": 0,
            "level": 1,
            "fortified": False,
            "exploring": False,
            "sentry": False,
            "building": None,      # {"type": str, "turns_left": int} for workers
            "goto": None,          # {"q": int, "r": int} auto-move target
            "born_turn": self.turn,
        }
        return uid

    def _create_city(self, player_id, name, q, r):
        cid = self.next_city_id
        self.next_city_id += 1
        self.cities[cid] = {
            "id": cid,
            "player": player_id,
            "name": name,
            "q": q, "r": r,
            "population": 1,
            "food_store": 0,
            "culture": 0,
            "border_radius": 1,
            "buildings": ["palace"] if len([c for c in self.cities.values() if c["player"] == player_id]) == 0 else [],
            "producing": None,
            "prod_progress": 0,
            "hp": 200,
            "max_hp": 200,
        }
        return cid

    # --------------------------------------------------------
    # YIELDS
    # --------------------------------------------------------

    def get_city_yields(self, city_id):
        city = self.cities[city_id]
        player = self.players[city["player"]]
        civ_bonus = CIVILIZATIONS[player["civ"]]["bonus"]

        food = 2  # base
        prod = 1  # base
        gold = 0
        science = 0
        culture = 1  # base

        # Tile yields (work radius = border_radius) + improvements
        brd = city.get("border_radius", 1)
        max_work = city["population"] + 1  # +1 for city center
        tiles_by_value = []
        for dq in range(-brd, brd + 1):
            for dr in range(-brd, brd + 1):
                tq, tr = city["q"] + dq, city["r"] + dr
                if hex_distance(city["q"], city["r"], tq, tr) <= brd:
                    t = self.tiles.get((tq, tr))
                    if t:
                        y = TERRAIN_YIELDS[t]
                        tf, tp, tg = y["food"], y["prod"], y["gold"]
                        # Add improvement yields (farm, mine, etc)
                        imp = self.improvements.get((tq, tr))
                        if imp:
                            idata = IMPROVEMENTS.get(imp["type"], {})
                            tf += idata.get("food", 0)
                            tp += idata.get("prod", 0)
                            tg += idata.get("gold", 0)
                        # Road/railroad layer — railroad gives +1 prod
                        road = self.roads.get((tq, tr))
                        if road and road["type"] == "railroad":
                            tp += 1
                        tiles_by_value.append((tf + tp + tg, {"food": tf, "prod": tp, "gold": tg}))

        tiles_by_value.sort(key=lambda x: -x[0])
        for _, y in tiles_by_value[:max_work]:
            food += y["food"]
            prod += y["prod"]
            gold += y["gold"]

        # Leader trait bonuses
        trait = player.get("trait", "")
        if trait == "creative":
            culture += 4  # strong culture for culture victory
        elif trait == "expansive":
            food += 1  # nerfed from 2
        elif trait == "financial":
            gold += max(2, gold // 3)  # buffed: +33% gold
        elif trait == "industrious":
            prod += max(1, prod // 5)  # nerfed from +25% to +20%
        elif trait == "aggressive":
            prod += 1
        elif trait == "protective":
            science += max(1, science // 5)  # +20% science (turtle = tech victory)

        # Building bonuses
        for bname in city["buildings"]:
            b = BUILDINGS[bname]
            food += b["food"]
            prod += b["prod"]
            gold += b["gold"]
            science += b["science"]
            culture += b["culture"]

        # Population contributes science
        science += city["population"]

        # Civ bonuses
        if civ_bonus == "food":
            food = int(food * 1.15)
        elif civ_bonus == "prod":
            prod = int(prod * 1.15)
        elif civ_bonus == "gold":
            gold = int(gold * 1.15)
        elif civ_bonus == "science":
            science = int(science * 1.15)
        elif civ_bonus == "culture":
            culture = int(culture * 1.15)

        # Food consumed by population
        food_surplus = food - city["population"] * 2

        return {
            "food": food, "food_surplus": food_surplus,
            "prod": prod, "gold": gold,
            "science": science, "culture": culture
        }

    def get_city_defense(self, city_id):
        city = self.cities[city_id]
        defense = 10  # base
        for bname in city["buildings"]:
            defense += BUILDINGS[bname]["defense"]
        return defense

    # --------------------------------------------------------
    # TERRITORY
    # --------------------------------------------------------

    def get_tile_owner(self, q, r):
        """Return player_id who owns this tile via city border, or None."""
        for c in self.cities.values():
            br = c.get("border_radius", 1)
            if hex_distance(c["q"], c["r"], q, r) <= br:
                return c["player"]
        return None

    # --------------------------------------------------------
    # VISIBILITY / FOG OF WAR
    # --------------------------------------------------------

    def get_visible_tiles(self, player_id):
        """Return set of (q,r) currently visible to player."""
        visible = set()
        sight = 2

        for u in self.units.values():
            if u["player"] == player_id:
                for dq in range(-sight-1, sight+2):
                    for dr in range(-sight-1, sight+2):
                        tq, tr = u["q"] + dq, u["r"] + dr
                        if hex_distance(u["q"], u["r"], tq, tr) <= sight:
                            if 0 <= tq < self.width and 0 <= tr < self.height:
                                visible.add((tq, tr))

        for c in self.cities.values():
            if c["player"] == player_id:
                br = c.get("border_radius", 1) + 1  # see 1 beyond borders
                for dq in range(-br - 1, br + 2):
                    for dr in range(-br - 1, br + 2):
                        tq, tr = c["q"] + dq, c["r"] + dr
                        if hex_distance(c["q"], c["r"], tq, tr) <= br:
                            if 0 <= tq < self.width and 0 <= tr < self.height:
                                visible.add((tq, tr))

        # Update explored memory
        if player_id in self.explored:
            self.explored[player_id].update(visible)

        return visible

    # --------------------------------------------------------
    # ACTIONS
    # --------------------------------------------------------

    def move_unit(self, unit_id, target_q, target_r):
        """Move unit to target hex. Returns result dict."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}

        if unit["moves_left"] <= 0:
            return {"ok": False, "msg": "No moves left"}

        dist = hex_distance(unit["q"], unit["r"], target_q, target_r)
        if dist != 1:
            return {"ok": False, "msg": "Can only move to adjacent hex"}

        terrain = self.tiles.get((target_q, target_r))
        if not terrain:
            return {"ok": False, "msg": "Off map"}

        # Water/coast check (only naval units)
        if terrain in (Terrain.WATER, Terrain.COAST) and unit["cat"] not in ("naval", "air"):
            return {"ok": False, "msg": "Cannot cross water"}

        if terrain == Terrain.MOUNTAIN and unit["cat"] != "air":
            return {"ok": False, "msg": "Cannot enter mountains"}

        # Land check for naval
        if terrain not in (Terrain.WATER, Terrain.COAST) and unit["cat"] == "naval":
            return {"ok": False, "msg": "Naval units stay in water"}

        move_cost = TERRAIN_MOVE_COST.get(terrain, 1)
        if unit["moves_left"] < move_cost and unit["moves_left"] < unit["mov"]:
            return {"ok": False, "msg": "Not enough movement"}

        # Territory check — only alliance allows passage
        territory_owner = self.get_tile_owner(target_q, target_r)
        if territory_owner is not None and territory_owner != unit["player"]:
            rel = self.players[unit["player"]]["diplomacy"].get(territory_owner, "peace")
            if rel == "alliance":
                pass  # allied, free passage
            elif rel == "war":
                pass  # already at war, enter to fight
            else:
                # Human player: block and ask for confirmation
                if self.players[unit["player"]].get("is_human"):
                    return {"ok": False, "needs_war": True,
                            "war_target": territory_owner,
                            "war_target_name": self.players[territory_owner]["name"],
                            "msg": f"Enter {self.players[territory_owner]['name']} territory? This means WAR!"}
                # AI: auto-declare war
                self.declare_war(unit["player"], territory_owner)
                self._log_ai(unit["player"], f"DIPLO: entered {self.players[territory_owner]['name']} territory — WAR!")

        # Check for enemy units
        enemy_units = [u for u in self.units.values()
                       if u["q"] == target_q and u["r"] == target_r and u["player"] != unit["player"]]

        if enemy_units:
            defender = enemy_units[0]
            rel = self.players[unit["player"]]["diplomacy"].get(defender["player"], "peace")
            if rel != "war":
                if self.players[unit["player"]].get("is_human"):
                    return {"ok": False, "needs_war": True,
                            "war_target": defender["player"],
                            "war_target_name": self.players[defender["player"]]["name"],
                            "msg": f"Attack {self.players[defender['player']]['name']}? This means WAR!"}
                self.declare_war(unit["player"], defender["player"])
            return self._combat(unit, defender)

        # Check for enemy cities
        enemy_cities = [c for c in self.cities.values()
                        if c["q"] == target_q and c["r"] == target_r and c["player"] != unit["player"]]
        if enemy_cities and unit["cat"] != "civilian":
            city = enemy_cities[0]
            rel = self.players[unit["player"]]["diplomacy"].get(city["player"], "peace")
            if rel != "war":
                if self.players[unit["player"]].get("is_human"):
                    return {"ok": False, "needs_war": True,
                            "war_target": city["player"],
                            "war_target_name": self.players[city["player"]]["name"],
                            "msg": f"Attack {city['name']}? This means WAR with {self.players[city['player']]['name']}!"}
                self.declare_war(unit["player"], city["player"])
            return self._attack_city(unit, city)

        # Move
        unit["q"] = target_q
        unit["r"] = target_r
        unit["moves_left"] = max(0, unit["moves_left"] - move_cost)
        unit["fortified"] = False
        unit["sentry"] = False

        return {"ok": True, "msg": "Moved"}

    def _combat(self, attacker, defender):
        """Resolve combat between two units."""
        terrain = self.tiles.get((defender["q"], defender["r"]), Terrain.GRASS)
        terrain_def = TERRAIN_DEFENSE.get(terrain, 0)

        atk_str = attacker["atk"] * (attacker["hp"] / 100)
        # Aggressive trait: +15% attack strength
        atk_player = self.players[attacker["player"]]
        if atk_player.get("trait") == "aggressive":
            atk_str *= 1.15
        def_str = defender["def"] * (defender["hp"] / 100) * (1 + terrain_def / 100)
        # Protective trait: +15% defense in own territory
        def_player = self.players[defender["player"]]
        if def_player.get("trait") == "protective":
            near_own_city = any(c["player"] == defender["player"]
                                and hex_distance(c["q"], c["r"], defender["q"], defender["r"]) <= 3
                                for c in self.cities.values())
            if near_own_city:
                def_str *= 1.15

        if defender["fortified"]:
            def_str *= 1.25

        # Random factor
        atk_roll = atk_str * (0.8 + random.random() * 0.4)
        def_roll = def_str * (0.8 + random.random() * 0.4)

        total = atk_roll + def_roll
        if total == 0:
            total = 1

        dmg_to_def = int(50 * atk_roll / total + 15)
        dmg_to_atk = int(40 * def_roll / total + 10)

        defender["hp"] -= dmg_to_def
        attacker["hp"] -= dmg_to_atk
        attacker["moves_left"] = 0

        result = {"ok": True, "combat": True, "atk_dmg": dmg_to_atk, "def_dmg": dmg_to_def}

        atk_name = self.players[attacker["player"]]["name"]
        def_name = self.players[defender["player"]]["name"]

        if defender["hp"] <= 0:
            result["defender_killed"] = True
            result["msg"] = f"Victory! Enemy {defender['type']} destroyed"
            self._log_ai(attacker["player"],
                f"BATTLE WON: {attacker['type']}(hp={attacker['hp']}) killed {def_name} {defender['type']} | dealt {dmg_to_def} took {dmg_to_atk}")
            attacker["q"] = defender["q"]
            attacker["r"] = defender["r"]
            attacker["xp"] += 5
            del self.units[defender["id"]]
        elif attacker["hp"] <= 0:
            result["attacker_killed"] = True
            result["msg"] = f"Defeat! Your {attacker['type']} was destroyed"
            self._log_ai(defender["player"],
                f"BATTLE WON: {defender['type']}(hp={defender['hp']}) killed {atk_name} {attacker['type']} | dealt {dmg_to_atk} took {dmg_to_def}")
            del self.units[attacker["id"]]
        else:
            result["msg"] = f"Battle: dealt {dmg_to_def} dmg, took {dmg_to_atk} dmg"
            self._log_ai(attacker["player"],
                f"BATTLE DRAW: {attacker['type']}(hp={attacker['hp']}) vs {def_name} {defender['type']}(hp={defender['hp']}) | dealt {dmg_to_def} took {dmg_to_atk}")

        self._check_elimination()
        return result

    def _attack_city(self, attacker, city):
        """Attack an enemy city."""
        city_def = self.get_city_defense(city["id"])

        atk_str = attacker["atk"] * (attacker["hp"] / 100)
        def_str = city_def / 10

        atk_roll = atk_str * (0.8 + random.random() * 0.4)
        def_roll = def_str * (0.8 + random.random() * 0.4)

        dmg_to_city = int(25 * atk_roll / (atk_roll + def_roll + 1) + 5)
        dmg_to_atk = int(15 * def_roll / (atk_roll + def_roll + 1) + 3)

        city["hp"] -= dmg_to_city
        attacker["hp"] -= dmg_to_atk
        attacker["moves_left"] = 0

        result = {"ok": True, "combat": True, "city_attack": True}

        if city["hp"] <= 0:
            # City captured!
            old_owner = self.players[city["player"]]["name"]
            city["player"] = attacker["player"]
            city["hp"] = city["max_hp"] // 2
            if city["population"] > 1:
                city["population"] = max(1, city["population"] - 1)
            attacker["q"] = city["q"]
            attacker["r"] = city["r"]
            result["msg"] = f"City {city['name']} captured!"
            result["captured"] = True
            self._log_ai(attacker["player"],
                f"CITY CAPTURED: {city['name']} from {old_owner} by {attacker['type']}(hp={attacker['hp']})")
            self._check_elimination()
        elif attacker["hp"] <= 0:
            self._log_ai(attacker["player"],
                f"SIEGE FAILED: {attacker['type']} destroyed attacking {city['name']}(hp={city['hp']}/{city['max_hp']})")
            del self.units[attacker["id"]]
            result["msg"] = f"Attack failed! {attacker['type']} destroyed"
            result["attacker_killed"] = True
        else:
            result["msg"] = f"City attacked: dealt {dmg_to_city} dmg, took {dmg_to_atk} dmg (City HP: {city['hp']}/{city['max_hp']})"

        return result

    def found_city(self, unit_id, name):
        """Found a city with a settler."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        if unit["type"] != "settler":
            return {"ok": False, "msg": "Only settlers can found cities"}

        # Check no city nearby
        for c in self.cities.values():
            if hex_distance(c["q"], c["r"], unit["q"], unit["r"]) < 3:
                return {"ok": False, "msg": "Too close to another city"}

        terrain = self.tiles.get((unit["q"], unit["r"]))
        if terrain in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
            return {"ok": False, "msg": "Cannot build city here"}

        cid = self._create_city(unit["player"], name, unit["q"], unit["r"])
        city_player = unit["player"]
        del self.units[unit_id]

        # Push foreign units out of new city borders
        city = self.cities[cid]
        br = city.get("border_radius", 1)
        pushed = []
        for uid, u in list(self.units.items()):
            if u["player"] != city_player and hex_distance(city["q"], city["r"], u["q"], u["r"]) <= br:
                # Find nearest tile outside borders
                best_exit = None
                best_d = 999
                for nq, nr in hex_neighbors(u["q"], u["r"]):
                    t = self.tiles.get((nq, nr))
                    if not t or t in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                        continue
                    if hex_distance(city["q"], city["r"], nq, nr) > br:
                        d = hex_distance(u["q"], u["r"], nq, nr)
                        if d < best_d:
                            best_d = d
                            best_exit = (nq, nr)
                if best_exit:
                    u["q"], u["r"] = best_exit
                    pushed.append(u["type"])

        msg = f"City {name} founded!"
        if pushed:
            msg += f" ({len(pushed)} foreign unit(s) expelled)"
        return {"ok": True, "msg": msg, "city_id": cid}

    def set_production(self, city_id, item_type, item_name):
        """Set what a city is producing. item_type: 'unit' or 'building'."""
        city = self.cities.get(city_id)
        if not city or city["player"] != self.current_player:
            return {"ok": False, "msg": "Not your city"}

        player = self.players[city["player"]]

        if item_type == "unit":
            if item_name not in UNIT_TYPES:
                return {"ok": False, "msg": "Unknown unit type"}
            udef = UNIT_TYPES[item_name]
            if udef["tech"] and udef["tech"] not in player["techs"]:
                return {"ok": False, "msg": f"Need tech: {udef['tech']}"}
            city["producing"] = {"type": "unit", "name": item_name, "cost": udef["cost"]}
        elif item_type == "building":
            if item_name not in BUILDINGS:
                return {"ok": False, "msg": "Unknown building"}
            bdef = BUILDINGS[item_name]
            if bdef["tech"] and bdef["tech"] not in player["techs"]:
                return {"ok": False, "msg": f"Need tech: {bdef['tech']}"}
            if item_name in city["buildings"]:
                return {"ok": False, "msg": "Already built"}
            city["producing"] = {"type": "building", "name": item_name, "cost": bdef["cost"]}
        else:
            return {"ok": False, "msg": "Invalid type"}

        city["prod_progress"] = 0
        return {"ok": True, "msg": f"Now producing: {item_name}"}

    def set_research(self, player_id, tech_name):
        """Set current research for a player."""
        if player_id != self.current_player:
            return {"ok": False, "msg": "Not your turn"}

        player = self.players[player_id]

        if tech_name not in TECHNOLOGIES:
            return {"ok": False, "msg": "Unknown technology"}

        tech = TECHNOLOGIES[tech_name]
        if tech_name in player["techs"]:
            return {"ok": False, "msg": "Already researched"}

        for prereq in tech["prereqs"]:
            if prereq not in player["techs"]:
                return {"ok": False, "msg": f"Need prerequisite: {prereq}"}

        player["researching"] = {"name": tech_name, "cost": tech["cost"], "progress": 0}
        return {"ok": True, "msg": f"Researching: {tech_name}"}

    def worker_build(self, unit_id, improvement_type):
        """Order a worker to build a tile improvement."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        if unit["type"] != "worker":
            return {"ok": False, "msg": "Only workers can build improvements"}
        if improvement_type not in IMPROVEMENTS:
            return {"ok": False, "msg": "Unknown improvement"}

        imp = IMPROVEMENTS[improvement_type]
        player = self.players[unit["player"]]
        terrain = self.tiles.get((unit["q"], unit["r"]))

        # Tech check
        if imp["tech"] and imp["tech"] not in player["techs"]:
            return {"ok": False, "msg": f"Need tech: {imp['tech']}"}

        # Terrain check (roads/railroads go anywhere land, others specific)
        if terrain is None or terrain.value not in imp["terrain"]:
            return {"ok": False, "msg": f"Cannot build {improvement_type} here"}

        # Check existing — improvements and roads are separate layers
        pos = (unit["q"], unit["r"])
        if improvement_type in ("road", "railroad"):
            existing_road = self.roads.get(pos)
            if existing_road and existing_road["type"] == improvement_type:
                return {"ok": False, "msg": f"Already has {improvement_type}"}
        else:
            existing_imp = self.improvements.get(pos)
            if existing_imp:
                return {"ok": False, "msg": "Tile already improved"}

        unit["building"] = {"type": improvement_type, "turns_left": imp["turns"]}
        unit["moves_left"] = 0
        return {"ok": True, "msg": f"Building {improvement_type} ({imp['turns']} turns)"}

    def disband_unit(self, unit_id):
        """Disband (delete) a unit."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        utype = unit["type"]
        del self.units[unit_id]
        return {"ok": True, "msg": f"{utype} disbanded"}

    def auto_worker(self, unit_id):
        """Set worker to auto-build mode."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        if unit["type"] != "worker":
            return {"ok": False, "msg": "Only workers can auto-build"}
        unit["exploring"] = True  # reuse exploring flag for auto-worker
        unit["moves_left"] = 0
        return {"ok": True, "msg": "Worker set to auto-build"}

    def fortify_unit(self, unit_id):
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        unit["fortified"] = True
        unit["exploring"] = False
        unit["moves_left"] = 0
        return {"ok": True, "msg": "Unit fortified (+25% defense)"}

    def explore_unit(self, unit_id):
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        if unit["cat"] == "civilian":
            return {"ok": False, "msg": "Civilian units cannot explore"}
        unit["exploring"] = not unit.get("exploring", False)
        unit["fortified"] = False
        unit["sentry"] = False
        msg = "Unit set to auto-explore" if unit["exploring"] else "Auto-explore cancelled"
        return {"ok": True, "msg": msg}

    def sentry_unit(self, unit_id):
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        unit["sentry"] = True
        unit["fortified"] = False
        unit["exploring"] = False
        unit["moves_left"] = 0
        return {"ok": True, "msg": "Unit on sentry duty"}

    def set_goto(self, unit_id, q, r):
        """Set auto-move target for unit."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        unit["goto"] = {"q": q, "r": r}
        unit["fortified"] = False
        unit["sentry"] = False
        unit["exploring"] = False
        return {"ok": True, "msg": f"Moving to ({q},{r})"}

    def skip_unit(self, unit_id):
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        unit["moves_left"] = 0
        return {"ok": True, "msg": "Unit skipped"}

    def declare_war(self, player_a, player_b):
        self.players[player_a]["diplomacy"][player_b] = "war"
        self.players[player_b]["diplomacy"][player_a] = "war"
        cd = GAME_CONFIG.get("diplo_war_cooldown", 10)
        self.players[player_a].setdefault("diplo_cooldown", {})[player_b] = cd
        self.players[player_b].setdefault("diplo_cooldown", {})[player_a] = cd

    def make_peace(self, player_a, player_b):
        # Check cooldown
        cd_a = self.players[player_a].get("diplo_cooldown", {}).get(player_b, 0)
        cd_b = self.players[player_b].get("diplo_cooldown", {}).get(player_a, 0)
        if cd_a > 0 or cd_b > 0:
            return  # can't make peace yet
        self.players[player_a]["diplomacy"][player_b] = "peace"
        self.players[player_b]["diplomacy"][player_a] = "peace"
        cd = GAME_CONFIG.get("diplo_peace_cooldown", 15)
        self.players[player_a].setdefault("diplo_cooldown", {})[player_b] = cd
        self.players[player_b].setdefault("diplo_cooldown", {})[player_a] = cd

    def form_alliance(self, player_a, player_b):
        """Form alliance — mutual free passage + shared vision."""
        # Must be at peace first
        rel_a = self.players[player_a]["diplomacy"].get(player_b, "peace")
        if rel_a == "war":
            return
        self.players[player_a]["diplomacy"][player_b] = "alliance"
        self.players[player_b]["diplomacy"][player_a] = "alliance"

    def break_alliance(self, player_a, player_b):
        """Break alliance — reverts to peace."""
        self.players[player_a]["diplomacy"][player_b] = "peace"
        self.players[player_b]["diplomacy"][player_a] = "peace"
        cd = GAME_CONFIG.get("diplo_peace_cooldown", 15)
        self.players[player_a].setdefault("diplo_cooldown", {})[player_b] = cd
        self.players[player_b].setdefault("diplo_cooldown", {})[player_a] = cd

    # --------------------------------------------------------
    # END TURN
    # --------------------------------------------------------

    def end_turn(self):
        """Process end of turn for current player."""
        pid = self.current_player
        player = self.players[pid]

        if not player["alive"]:
            self._advance_turn()
            return {"ok": True, "msg": "Skipped (eliminated)"}

        # Tick diplomacy cooldowns
        for k in list(player.get("diplo_cooldown", {}).keys()):
            if player["diplo_cooldown"][k] > 0:
                player["diplo_cooldown"][k] -= 1

        # Wake sentry units if enemies nearby
        woken = []
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("sentry"):
                for eu in self.units.values():
                    if eu["player"] != pid and hex_distance(u["q"], u["r"], eu["q"], eu["r"]) <= 2:
                        u["sentry"] = False
                        woken.append(u["type"])
                        break

        # Auto-explore units
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("exploring") and u.get("moves_left", 0) > 0:
                while u["id"] in self.units and u.get("exploring") and u.get("moves_left", 0) > 0:
                    old_q, old_r = u["q"], u["r"]
                    self._auto_explore_step(u, pid)
                    if u["id"] not in self.units or (u["q"] == old_q and u["r"] == old_r):
                        break

        # Auto-move units with goto targets
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("goto") and u.get("moves_left", 0) > 0:
                tgt = u["goto"]
                # Check for non-peace enemy adjacent — cancel goto
                enemy_near = False
                for nq, nr in hex_neighbors(u["q"], u["r"]):
                    for eu in self.units.values():
                        if eu["player"] != pid and eu["q"] == nq and eu["r"] == nr:
                            rel = player["diplomacy"].get(eu["player"], "peace")
                            if rel != "peace":
                                enemy_near = True
                                break
                    if enemy_near:
                        break
                if enemy_near:
                    u["goto"] = None
                    continue
                # Move toward target using all movement
                while u["id"] in self.units and u.get("goto") and u.get("moves_left", 0) > 0:
                    if u["q"] == tgt["q"] and u["r"] == tgt["r"]:
                        u["goto"] = None
                        break
                    # BFS pathfinding toward target
                    best = self._find_path_next(u, tgt["q"], tgt["r"])
                    if not best:
                        u["goto"] = None
                        break
                    old_q, old_r = u["q"], u["r"]
                    self.move_unit(u["id"], best[0], best[1])
                    if u["id"] not in self.units or (u["q"] == old_q and u["r"] == old_r):
                        u["goto"] = None
                        break

        total_gold = 0
        total_science = 0
        total_culture = 0
        events = []
        for w in woken:
            events.append(f"Sentry {w} spotted enemy!")

        # Process cities
        for city in list(self.cities.values()):
            if city["player"] != pid:
                continue

            yields = self.get_city_yields(city["id"])
            total_gold += yields["gold"]
            total_science += yields["science"]
            total_culture += yields["culture"]

            # Food & growth
            city["food_store"] += yields["food_surplus"]
            growth_needed = 10 + city["population"] * 5
            if city["food_store"] >= growth_needed:
                city["population"] += 1
                city["food_store"] = 0
                events.append(f"{city['name']} grew to pop {city['population']}")
            elif city["food_store"] < 0:
                if city["population"] > 1:
                    city["population"] -= 1
                    city["food_store"] = 0
                    events.append(f"{city['name']} lost population (starvation)")

            # Production
            if city["producing"]:
                city["prod_progress"] += yields["prod"]
                if city["prod_progress"] >= city["producing"]["cost"]:
                    item = city["producing"]
                    if item["type"] == "unit":
                        self._create_unit(pid, item["name"], city["q"], city["r"])
                        events.append(f"{city['name']} produced {item['name']}")
                    elif item["type"] == "building":
                        city["buildings"].append(item["name"])
                        events.append(f"{city['name']} built {item['name']}")
                    city["producing"] = None
                    city["prod_progress"] = 0
                    # AI: immediately pick next production (bypass validation)
                    if not player["is_human"]:
                        self._ai_auto_produce(city, player, pid)

            # City culture & border expansion
            city["culture"] = city.get("culture", 0) + yields["culture"]
            old_br = city.get("border_radius", 1)
            # Thresholds: 0->1, 10->2, 50->3, 150->4, 400->5
            thresholds = [(400, 5), (150, 4), (50, 3), (10, 2)]
            new_br = 1
            for threshold, radius in thresholds:
                if city["culture"] >= threshold:
                    new_br = radius
                    break
            city["border_radius"] = new_br
            if new_br > old_br:
                events.append(f"{city['name']} borders expanded! (radius {new_br})")

            # City healing
            if city["hp"] < city["max_hp"]:
                city["hp"] = min(city["max_hp"], city["hp"] + 10)

        # Worker building progress
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("building"):
                u["building"]["turns_left"] -= 1
                if u["building"]["turns_left"] <= 0:
                    imp_type = u["building"]["type"]
                    pos = (u["q"], u["r"])
                    if imp_type in ("road", "railroad"):
                        self.roads[pos] = {"type": imp_type, "player": pid}
                    else:
                        self.improvements[pos] = {"type": imp_type, "player": pid}
                    events.append(f"Worker built {imp_type}")
                    u["building"] = None

        # Spy actions — sabotage or steal tech if in enemy city
        for u in list(self.units.values()):
            if u["player"] == pid and u["type"] == "spy":
                for ec in self.cities.values():
                    if ec["player"] != pid and ec["q"] == u["q"] and ec["r"] == u["r"]:
                        enemy = self.players[ec["player"]]
                        if random.random() < 0.3:  # 30% chance per turn
                            # Steal tech
                            stealable = [t for t in enemy["techs"] if t not in player["techs"]]
                            if stealable:
                                stolen = random.choice(stealable)
                                player["techs"].append(stolen)
                                events.append(f"Spy stole {stolen} from {ec['name']}!")
                            else:
                                # Sabotage production
                                ec["prod_progress"] = max(0, ec.get("prod_progress", 0) - 10)
                                events.append(f"Spy sabotaged {ec['name']}!")
                            # Spy has 40% chance of being caught and killed
                            if random.random() < 0.4:
                                del self.units[u["id"]]
                                events.append(f"Spy was caught and executed!")
                        break

        # Caravan trade — earn gold when in foreign city
        for u in list(self.units.values()):
            if u["player"] == pid and u["type"] == "caravan":
                for fc in self.cities.values():
                    if fc["player"] != pid and fc["q"] == u["q"] and fc["r"] == u["r"]:
                        rel = player["diplomacy"].get(fc["player"], "neutral")
                        if rel != "war":
                            trade_gold = 5 + hex_distance(
                                u["q"], u["r"],
                                min((c for c in self.cities.values() if c["player"] == pid),
                                    key=lambda c: hex_distance(c["q"], c["r"], u["q"], u["r"]),
                                    default={"q": 0, "r": 0})["q"],
                                min((c for c in self.cities.values() if c["player"] == pid),
                                    key=lambda c: hex_distance(c["q"], c["r"], u["q"], u["r"]),
                                    default={"q": 0, "r": 0})["r"])
                            total_gold += trade_gold
                            events.append(f"Caravan earned {trade_gold} gold from {fc['name']}")
                            # Caravan is consumed after delivery
                            del self.units[u["id"]]
                        break

        # Gold
        # Unit maintenance
        unit_count = sum(1 for u in self.units.values() if u["player"] == pid)
        free = GAME_CONFIG.get("unit_maintenance_free", 2)
        mcost = GAME_CONFIG.get("unit_maintenance_cost", 1)
        maintenance = max(0, unit_count - free) * mcost
        total_gold -= maintenance
        player["gold"] += total_gold

        # Bankruptcy — disband units aggressively when gold negative
        if player["gold"] < GAME_CONFIG.get("bankruptcy_threshold", -50) and not player["is_human"]:
            mil_units = [u for u in self.units.values()
                         if u["player"] == pid and u["cat"] != "civilian"]
            # Disband multiple units if deeply in debt
            disband_count = max(1, abs(player["gold"]) // 50)
            mil_units.sort(key=lambda u: u["hp"])
            for i in range(min(disband_count, len(mil_units))):
                u = mil_units[i]
                if u["id"] in self.units:
                    del self.units[u["id"]]
                    player["gold"] += 20
                    events.append(f"Disbanded {u['type']} (bankrupt)")

        # Research
        if player["researching"]:
            player["researching"]["progress"] += total_science
            if player["researching"]["progress"] >= player["researching"]["cost"]:
                tech_name = player["researching"]["name"]
                player["techs"].append(tech_name)
                events.append(f"Discovered: {tech_name}!")
                player["researching"] = None

        # Culture
        player["culture_pool"] += total_culture

        # Heal units
        for u in self.units.values():
            if u["player"] == pid and u["hp"] < 100:
                # In friendly city: +15, in friendly territory: +10, else: +5
                in_city = any(c["q"] == u["q"] and c["r"] == u["r"] and c["player"] == pid
                             for c in self.cities.values())
                if in_city:
                    u["hp"] = min(100, u["hp"] + 15)
                elif u["fortified"]:
                    u["hp"] = min(100, u["hp"] + 10)
                else:
                    u["hp"] = min(100, u["hp"] + 5)

        # Calculate score
        player["score"] = (
            len([c for c in self.cities.values() if c["player"] == pid]) * 100 +
            sum(c["population"] for c in self.cities.values() if c["player"] == pid) * 20 +
            len(player["techs"]) * 30 +
            player["culture_pool"] // 10
        )

        # --- VICTORY CONDITIONS ---

        # Space victory — 3 end-game techs + 2000 accumulated production
        space_techs = ["space_program", "rocketry", "nuclear_fission"]
        if all(t in player["techs"] for t in space_techs):
            player["space_progress"] = player.get("space_progress", 0) + sum(
                self.get_city_yields(c["id"])["prod"] for c in self.cities.values() if c["player"] == pid)
            if player.get("space_progress", 0) >= GAME_CONFIG.get("space_victory_production", 2000):
                self.game_over = True
                self.winner = pid
                events.append(f"{player['name']} achieves SPACE victory!")

        # Culture victory — accumulate 5000 culture
        if not self.game_over and player["culture_pool"] >= GAME_CONFIG.get("culture_victory_threshold", 3000):
            self.game_over = True
            self.winner = pid
            events.append(f"{player['name']} achieves CULTURE victory!")

        # Domination victory — control 60%+ of all cities
        if not self.game_over:
            total_cities = len(self.cities)
            my_city_count = len([c for c in self.cities.values() if c["player"] == pid])
            if total_cities >= 4 and my_city_count >= total_cities * GAME_CONFIG.get("domination_city_percent", 0.6):
                self.game_over = True
                self.winner = pid
                events.append(f"{player['name']} achieves DOMINATION victory!")

        # Advance to next player
        self._advance_turn()

        return {"ok": True, "events": events, "gold": total_gold, "science": total_science}

    def _advance_turn(self):
        """Move to next alive player, or next turn."""
        start = self.current_player
        while True:
            self.current_player = (self.current_player + 1) % len(self.players)
            if self.current_player == 0:
                self.turn += 1
            if self.players[self.current_player]["alive"]:
                break
            if self.current_player == start:
                break

        # Reset movement for new current player
        for u in self.units.values():
            if u["player"] == self.current_player:
                u["moves_left"] = u["mov"]

        # Run AI turns
        if not self.players[self.current_player]["is_human"] and not self.game_over:
            self._run_ai(self.current_player)
            self.end_turn()

    def _check_elimination(self):
        """Check if any player is eliminated."""
        for p in self.players:
            if not p["alive"]:
                continue
            has_cities = any(c["player"] == p["id"] for c in self.cities.values())
            has_settlers = any(u["player"] == p["id"] and u["type"] == "settler" for u in self.units.values())
            if not has_cities and not has_settlers:
                p["alive"] = False
                remaining = len([u for u in self.units.values() if u["player"] == p["id"]])
                self._log_ai(p["id"], f"ELIMINATED: {p['name']} destroyed! (had {remaining} units remaining, turn {self.turn})")
                to_remove = [uid for uid, u in self.units.items() if u["player"] == p["id"]]
                for uid in to_remove:
                    del self.units[uid]

        alive = [p for p in self.players if p["alive"]]
        if len(alive) == 1:
            self.game_over = True
            self.winner = alive[0]["id"]

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    def _log_ai(self, pid, msg):
        """Add AI debug message to log."""
        if hasattr(self, 'ai_log'):
            pname = self.players[pid]["name"] if pid < len(self.players) else f"P{pid}"
            self.ai_log.append(f"[{pname}] {msg}")

    def _run_ai(self, pid):
        """AI logic with personality-driven priorities."""
        player = self.players[pid]
        my_cities = [c for c in self.cities.values() if c["player"] == pid]
        my_units = [u for u in self.units.values() if u["player"] == pid]
        my_settlers = [u for u in my_units if u["type"] == "settler"]
        my_military = [u for u in my_units if u["cat"] not in ("civilian",)]
        aggression = player.get("aggression", 0.5)
        loyalty = player.get("loyalty", 0.5)

        # Diplomacy AI — personality-driven (respect cooldowns)
        for other in self.players:
            if other["id"] == pid or not other["alive"]:
                continue
            rel = player["diplomacy"].get(other["id"], "peace")
            other_military = len([u for u in self.units.values() if u["player"] == other["id"] and u["cat"] != "civilian"])
            cd = player.get("diplo_cooldown", {}).get(other["id"], 0)
            if cd > 0:
                continue  # skip — cooldown active

            if rel == "war":
                if len(my_military) < 2 and random.random() > loyalty:
                    self.make_peace(pid, other["id"])
                    self._log_ai(pid, f"DIPLO: peace with {other['name']} (too weak, mil={len(my_military)})")
                elif other_military > len(my_military) * 1.5 and random.random() > loyalty * 0.7:
                    self.make_peace(pid, other["id"])
                    self._log_ai(pid, f"DIPLO: peace with {other['name']} (outmatched {len(my_military)} vs {other_military})")
            elif rel == "neutral":
                war_chance = aggression * 0.08
                if player.get("strategy") == "conqueror":
                    war_chance = aggression * 0.15  # conquerors are more warlike
                if len(my_military) > other_military * 1.3 and random.random() < war_chance:
                    self.declare_war(pid, other["id"])
                    self._log_ai(pid, f"DIPLO: WAR on {other['name']} (stronger {len(my_military)} vs {other_military}, aggr={aggression})")
            elif rel == "peace":
                if random.random() < aggression * (1 - loyalty) * 0.03:
                    if len(my_military) > other_military * 1.5:
                        self.declare_war(pid, other["id"])
                        self._log_ai(pid, f"DIPLO: BETRAYAL of {other['name']}! (aggr={aggression}, loyal={loyalty})")

        # Gang up on the leader — if someone is way ahead, declare war
        alive_players = [p for p in self.players if p["alive"] and p["id"] != pid]
        if alive_players:
            leader = max(alive_players, key=lambda p: p["score"])
            gang_ratio = GAME_CONFIG.get("gang_up_score_ratio", 1.3)
            gang_min = GAME_CONFIG.get("gang_up_min_score", 800)
            gang_chance = GAME_CONFIG.get("gang_up_chance", 0.15)
            if leader["score"] > player["score"] * gang_ratio and leader["score"] > gang_min:
                rel = player["diplomacy"].get(leader["id"], "neutral")
                if rel != "war" and random.random() < gang_chance:
                    self.declare_war(pid, leader["id"])
                    self._log_ai(pid, f"DIPLO: gang-up WAR on leader {leader['name']} (score {leader['score']} vs my {player['score']})")

        # Alliance AI — loyal/peaceful civs seek alliances against common enemies
        for other in self.players:
            if other["id"] == pid or not other["alive"]:
                continue
            rel = player["diplomacy"].get(other["id"], "peace")
            # Form alliance: both at peace AND share a common enemy
            if rel == "peace" and loyalty > 0.5:
                common_enemy = any(
                    player["diplomacy"].get(e["id"]) == "war" and other["diplomacy"].get(e["id"]) == "war"
                    for e in self.players if e["id"] != pid and e["id"] != other["id"] and e["alive"]
                )
                if common_enemy and random.random() < loyalty * 0.2:
                    self.form_alliance(pid, other["id"])
                    self._log_ai(pid, f"DIPLO: ALLIANCE with {other['name']} (common enemy, loyalty={loyalty})")
            # Break alliance if disloyal and strong enough
            elif rel == "alliance" and random.random() < (1 - loyalty) * aggression * 0.02:
                self.break_alliance(pid, other["id"])
                self._log_ai(pid, f"DIPLO: broke alliance with {other['name']} (disloyal)")

        # Upgrade obsolete units
        self._ai_upgrade_units(pid)

        # Research: strategy-weighted tech selection
        if not player["researching"]:
            strategy = player.get("strategy", "balanced")
            available = []
            # Priority techs by strategy
            priority_techs = {
                "conqueror": ["bronze_working", "iron_working", "horseback", "feudalism", "gunpowder", "dynamite", "industrialization", "flight"],
                "warmonger": ["archery", "bronze_working", "iron_working", "gunpowder", "dynamite", "flight"],
                "turtle": ["construction", "engineering", "education", "astronomy", "electricity", "nuclear_fission", "rocketry", "space_program"],
                "builder": ["mining", "construction", "engineering", "industrialization", "steam_power", "railroad", "rocketry", "space_program"],
                "culturalist": ["pottery", "writing", "theology", "education", "printing_press"],
                "economist": ["pottery", "writing", "currency", "printing_press", "navigation"],
                "expansionist": ["agriculture", "pottery", "writing", "construction"],
            }
            prio_list = priority_techs.get(strategy, [])
            # Dynamic priority: if close to space victory, rush remaining space techs
            space_techs_needed = ["space_program", "rocketry", "nuclear_fission"]
            space_done = sum(1 for t in space_techs_needed if t in player["techs"])
            for tname, tdata in TECHNOLOGIES.items():
                if tname in player["techs"]:
                    continue
                if all(p in player["techs"] for p in tdata["prereqs"]):
                    cost = tdata["cost"]
                    # Discount priority techs
                    if tname in prio_list:
                        cost = int(cost * 0.5)
                    # Rush remaining space techs if close to space victory
                    if space_done >= 1 and tname in space_techs_needed:
                        cost = int(cost * 0.3)  # massive discount
                    available.append((cost, tname))
            if available:
                available.sort()
                self.current_player = pid
                self.set_research(pid, available[0][1])
                self._log_ai(pid, f"RESEARCH: {available[0][1]} (effective_cost {available[0][0]}, {len(available)} options, strategy={strategy})")

        # City production — smarter priorities
        for city in my_cities:
            if not city["producing"]:
                self.current_player = pid
                self._ai_choose_production(city, player, my_cities, my_military, my_settlers, pid)

        # Move units — workers, settlers, spies, caravans, then military
        for unit in list(my_units):
            if unit["id"] not in self.units:
                continue
            if unit["type"] == "worker":
                self._ai_worker_move(unit, pid)

        for unit in list(my_units):
            if unit["id"] not in self.units:
                continue
            if unit["type"] == "spy":
                self._ai_spy_move(unit, pid)

        for unit in list(my_units):
            if unit["id"] not in self.units:
                continue
            if unit["type"] == "caravan":
                self._ai_caravan_move(unit, pid)

        for unit in list(my_units):
            if unit["id"] not in self.units:
                continue
            if unit["type"] == "settler":
                self._ai_settler_move(unit, pid)

        for unit in list(my_units):
            if unit["id"] not in self.units:
                continue
            if unit["cat"] in ("melee", "ranged", "mounted", "siege"):
                self._ai_military_move(unit, pid)

    def _ai_choose_production(self, city, player, my_cities, my_military, my_settlers, pid):
        """Score-based production: every option gets points based on context."""
        trait = player.get("trait", "")
        aggression = player.get("aggression", 0.5)
        my_workers = [u for u in self.units.values() if u["player"] == pid and u["type"] == "worker"]
        my_spies = [u for u in self.units.values() if u["player"] == pid and u["type"] == "spy"]
        my_caravans = [u for u in self.units.values() if u["player"] == pid and u["type"] == "caravan"]
        at_war = any(player["diplomacy"].get(p["id"]) == "war" for p in self.players if p["id"] != pid and p["alive"])
        nearby_enemies = sum(1 for u in self.units.values()
                             if u["player"] != pid and any(
                                 hex_distance(u["q"], u["r"], c["q"], c["r"]) < 6 for c in my_cities))
        num_players = len([p for p in self.players if p["alive"]])
        land_per_player = (self.width * self.height) // max(1, num_players)
        base_max = max(4, land_per_player // 35)
        max_cities = base_max + 3 if trait == "expansive" else base_max
        game_phase = min(1.0, self.turn / 120)  # 0=early, 1=late

        strategy = player.get("strategy", "balanced")
        candidates = []  # (score, type, name, reason)

        # --- UNITS ---

        # Worker — 1 per city, max 4
        needed_workers = min(4, max(1, len(my_cities)))
        if len(my_workers) < needed_workers:
            urgency = 80 if len(my_workers) == 0 else 40
            candidates.append((urgency, "unit", "worker", f"need workers ({len(my_workers)}/{needed_workers})"))

        # Settler
        max_settlers = min(3, max(1, max_cities // 3))
        if len(my_cities) + len(my_settlers) < max_cities and len(my_settlers) < max_settlers:
            has_spot = any(
                self.tiles.get((q, r)) not in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN)
                and not any(hex_distance(c["q"], c["r"], q, r) < 4 for c in self.cities.values())
                for q in range(0, self.width, 3) for r in range(0, self.height, 3)
            )
            if has_spot:
                score = 55 - len(my_cities) * 4
                if trait == "expansive":
                    score += 15
                if strategy == "expansionist":
                    score += 25  # China loves expanding
                elif strategy == "warmonger":
                    score -= 10  # Aztec prefers fighting over settling
                if game_phase < 0.4:
                    score += 15
                candidates.append((score, "unit", "settler", f"expand ({len(my_cities)}/{max_cities})"))

        # Military
        mil_ratio = len(my_military) / max(1, len(my_cities))
        desired_ratio = 3.0 if trait == "aggressive" else 1.5 if trait == "protective" else 2.0
        best_mil = self._ai_best_military(player)
        mil_score = 0
        if mil_ratio < desired_ratio:
            mil_score = int((desired_ratio - mil_ratio) * 30)
        if at_war:
            mil_score += 35
        if nearby_enemies > 0:
            mil_score += 20
        if trait == "aggressive":
            mil_score += 10
        if strategy in ("warmonger", "conqueror"):
            mil_score += 20  # always want more military
        elif strategy == "turtle":
            mil_score -= 5   # Japan prefers buildings over units
        if game_phase > 0.6:
            mil_score += 10
        # Domination urgency — boost military if close to domination victory
        total_cities_all = len(self.cities)
        my_city_count_now = len(my_cities)
        if total_cities_all >= 4:
            domin_pct = my_city_count_now / total_cities_all
            if domin_pct >= 0.4:
                mil_score += 25
            if strategy in ("conqueror",) and domin_pct >= 0.3:
                mil_score += 20  # conquerors push earlier for domination
        # Diminishing returns: strong penalty when already have lots of units
        mil_per_city = len(my_military) / max(1, len(my_cities))
        if mil_per_city > 3:
            mil_score -= int((mil_per_city - 3) * 12)
        if mil_per_city > 5:
            mil_score -= int((mil_per_city - 5) * 20)  # very harsh above 5 per city
        # Don't build military when bankrupt
        if player["gold"] < -30:
            mil_score -= 30
        if mil_score > 0:
            candidates.append((mil_score, "unit", best_mil, f"military (ratio={mil_ratio:.1f}/{desired_ratio:.1f}, war={at_war})"))

        # Spy
        if "writing" in player["techs"] and len(my_spies) < max(1, len(my_cities) // 3):
            score = 25
            if aggression > 0.6:
                score += 15
            if strategy in ("warmonger", "conqueror"):
                score += 15  # spies complement military strategy
            if game_phase > 0.3:
                score += 10
            candidates.append((score, "unit", "spy", f"espionage (have {len(my_spies)})"))

        # Caravan
        if "currency" in player["techs"] and len(my_caravans) < max(1, len(my_cities) // 3):
            score = 20
            if trait == "financial":
                score += 20
            if strategy == "economist":
                score += 25  # Persia loves trade
            if not at_war:
                score += 10
            candidates.append((score, "unit", "caravan", f"trade (have {len(my_caravans)})"))

        # --- BUILDINGS ---
        for bname, bdata in BUILDINGS.items():
            if bname in city["buildings"]:
                continue
            if bname == "palace":
                continue
            if bdata["tech"] and bdata["tech"] not in player["techs"]:
                continue

            score = 0
            reason_parts = []

            # Base: buildings get bonus in mid/late game
            phase_mult = 1.0 + game_phase * 0.5  # 1.0 early → 1.5 late
            # Food buildings — more valuable when city is small
            if bdata["food"] > 0:
                score += int(bdata["food"] * (10 if city["population"] < 5 else 5) * phase_mult)
                reason_parts.append(f"+{bdata['food']}f")
            # Production buildings
            if bdata["prod"] > 0:
                score += int(bdata["prod"] * 7 * phase_mult)
                if trait == "industrious":
                    score += bdata["prod"] * 3
                reason_parts.append(f"+{bdata['prod']}p")
            # Gold buildings — critical for economy
            if bdata["gold"] > 0:
                score += int(bdata["gold"] * 6 * phase_mult)
                if trait == "financial":
                    score += bdata["gold"] * 4
                # Extra bonus if gold is negative
                if player["gold"] < 0:
                    score += bdata["gold"] * 5
                reason_parts.append(f"+{bdata['gold']}g")
            # Science buildings
            if bdata["science"] > 0:
                score += int(bdata["science"] * 7 * phase_mult)
                reason_parts.append(f"+{bdata['science']}s")
            # Culture buildings
            if bdata["culture"] > 0:
                score += int(bdata["culture"] * 5 * phase_mult)
                if trait == "creative":
                    score += bdata["culture"] * 4
                reason_parts.append(f"+{bdata['culture']}c")
            # Defense buildings — more valuable when threatened
            if bdata["defense"] > 0:
                score += bdata["defense"] // 8
                if at_war or nearby_enemies > 0:
                    score += bdata["defense"] // 4
                if trait == "protective":
                    score += bdata["defense"] // 6
                reason_parts.append(f"+{bdata['defense']}def")
            # Happiness
            if bdata["happiness"] < 0:
                score -= abs(bdata["happiness"]) * 5  # penalty for unhappiness
            elif bdata["happiness"] > 0:
                score += bdata["happiness"] * 4

            # Penalize expensive buildings early game
            score -= bdata["cost"] // 15

            # Strategy bonuses for buildings
            if strategy == "builder" and bdata["prod"] > 0:
                score += 10
            if strategy == "culturalist" and bdata["culture"] > 0:
                score += 12
            if strategy == "turtle" and bdata["defense"] > 0:
                score += 15
            if strategy == "economist" and bdata["gold"] > 0:
                score += 10
            # ALL strategies: core infrastructure is essential
            if bname == "granary":
                score += 25 if city["population"] < 5 else 10
            elif bname == "library":
                score += 20
            elif bname == "marketplace":
                score += 18
            elif bname == "walls" and (at_war or nearby_enemies > 0):
                score += 20

            if score > 0:
                candidates.append((score, "building", bname, " ".join(reason_parts)))

        # Pick the best option
        if not candidates:
            self.set_production(city["id"], "unit", best_mil)
            return

        candidates.sort(key=lambda x: -x[0])
        best = candidates[0]
        self.set_production(city["id"], best[1], best[2])
        self._log_ai(pid, f"PROD-SCORE: {city['name']} -> {best[2]} (score={best[0]}, reason={best[3]}) | top3: {[(c[2],c[0]) for c in candidates[:3]]}")

    def _ai_auto_produce(self, city, player, pid):
        """Directly set production for AI city, bypassing current_player check."""
        my_cities = [c for c in self.cities.values() if c["player"] == pid]
        my_military = [u for u in self.units.values() if u["player"] == pid and u["cat"] != "civilian"]
        my_settlers = [u for u in self.units.values() if u["player"] == pid and u["type"] == "settler"]
        saved = self.current_player
        self.current_player = pid
        self._ai_choose_production(city, player, my_cities, my_military, my_settlers, pid)
        self.current_player = saved

    def _ai_best_military(self, player):
        """Pick best available military unit."""
        for uname in ["infantry", "rifleman", "musketman", "knight", "swordsman", "spearman", "archer", "warrior"]:
            udata = UNIT_TYPES[uname]
            if not udata["tech"] or udata["tech"] in player["techs"]:
                return uname
        return "warrior"

    def _ai_upgrade_units(self, pid):
        """Upgrade obsolete units in cities (costs gold)."""
        player = self.players[pid]
        if player["gold"] < 50:
            return
        upgrade_path = {
            "warrior": "swordsman", "swordsman": "musketman", "musketman": "rifleman",
            "rifleman": "infantry", "spearman": "musketman",
            "archer": "musketman", "horseman": "knight", "knight": "tank",
            "catapult": "artillery", "galley": "caravel", "caravel": "ironclad",
        }
        for u in list(self.units.values()):
            if u["player"] != pid or u["cat"] == "civilian":
                continue
            upgrade_to = upgrade_path.get(u["type"])
            if not upgrade_to or upgrade_to not in UNIT_TYPES:
                continue
            udata = UNIT_TYPES[upgrade_to]
            if udata["tech"] and udata["tech"] not in player["techs"]:
                continue
            # Must be in own city to upgrade
            in_city = any(c["q"] == u["q"] and c["r"] == u["r"] and c["player"] == pid
                          for c in self.cities.values())
            if not in_city:
                continue
            cost = udata["cost"] // 2  # half price for upgrade
            if player["gold"] >= cost:
                player["gold"] -= cost
                old_type = u["type"]
                u["type"] = upgrade_to
                u["atk"] = udata["atk"]
                u["def"] = udata["def"]
                u["mov"] = udata["mov"]
                u["cat"] = udata["cat"]
                self._log_ai(pid, f"UPGRADE: {old_type} → {upgrade_to} at ({u['q']},{u['r']}) cost={cost}g")

    def _ai_spy_move(self, unit, pid):
        """Move spy toward nearest enemy city."""
        if unit["moves_left"] <= 0:
            return
        # Already in enemy city? Stay put
        for c in self.cities.values():
            if c["player"] != pid and c["q"] == unit["q"] and c["r"] == unit["r"]:
                unit["moves_left"] = 0
                return
        # Move toward nearest enemy city
        enemy_cities = [c for c in self.cities.values() if c["player"] != pid]
        if enemy_cities:
            target = min(enemy_cities, key=lambda c: hex_distance(unit["q"], unit["r"], c["q"], c["r"]))
            for _ in range(unit["mov"]):
                if unit["moves_left"] <= 0 or unit["id"] not in self.units:
                    break
                old_q, old_r = unit["q"], unit["r"]
                self._ai_step_toward(unit, target["q"], target["r"])
                if unit["q"] == old_q and unit["r"] == old_r:
                    break

    def _ai_caravan_move(self, unit, pid):
        """Move caravan toward nearest foreign non-enemy city for trade."""
        if unit["moves_left"] <= 0:
            return
        trade_cities = [c for c in self.cities.values()
                        if c["player"] != pid
                        and self.players[pid]["diplomacy"].get(c["player"], "neutral") != "war"]
        if trade_cities:
            target = min(trade_cities, key=lambda c: hex_distance(unit["q"], unit["r"], c["q"], c["r"]))
            for _ in range(unit["mov"]):
                if unit["moves_left"] <= 0 or unit["id"] not in self.units:
                    break
                old_q, old_r = unit["q"], unit["r"]
                self._ai_step_toward(unit, target["q"], target["r"])
                if unit["q"] == old_q and unit["r"] == old_r:
                    break

    def _ai_worker_move(self, unit, pid):
        """Smart auto-worker: improve cities, connect with roads, then help neighbors."""
        if unit["id"] not in self.units or unit.get("building"):
            return

        player = self.players[pid]
        my_cities = [c for c in self.cities.values() if c["player"] == pid]
        if not my_cities:
            return

        has_railroad = "railroad" in player["techs"]
        pos = (unit["q"], unit["r"])
        terrain = self.tiles.get(pos)

        # --- CAN WE BUILD ON CURRENT TILE? ---
        if terrain and terrain.value not in ("water", "coast", "mountain"):
            existing_imp = self.improvements.get(pos)
            existing_road = self.roads.get(pos)

            # Near any own city?
            near_city = any(hex_distance(c["q"], c["r"], unit["q"], unit["r"]) <= c.get("border_radius", 1) + 1
                           for c in my_cities)

            # On a road between cities? (not near city but on road path)
            on_road_path = existing_road is not None

            if near_city:
                # Priority 1: Terrain improvement (farm/mine/lumber_mill)
                if not existing_imp:
                    imp_type = self._ai_pick_improvement(terrain.value, player)
                    if imp_type:
                        idata = IMPROVEMENTS.get(imp_type, {})
                        bonus = f"+{idata.get('food',0)}f +{idata.get('prod',0)}p +{idata.get('gold',0)}g"
                        self.current_player = pid
                        self.worker_build(unit["id"], imp_type)
                        self._log_ai(pid, f"WORKER: {imp_type} at ({unit['q']},{unit['r']}) [{bonus}] terrain={terrain.value}")
                        return

                # Priority 2: Road
                if not existing_road:
                    self.current_player = pid
                    self.worker_build(unit["id"], "road")
                    self._log_ai(pid, f"WORKER: road at ({unit['q']},{unit['r']})")
                    return

                # Priority 3: Upgrade to railroad
                if has_railroad and existing_road and existing_road["type"] == "road":
                    self.current_player = pid
                    self.worker_build(unit["id"], "railroad")
                    self._log_ai(pid, f"WORKER: railroad at ({unit['q']},{unit['r']})")
                    return

            elif on_road_path or not existing_road:
                # Between cities — build road to connect
                if not existing_road:
                    self.current_player = pid
                    self.worker_build(unit["id"], "road")
                    self._log_ai(pid, f"WORKER: connecting road at ({unit['q']},{unit['r']})")
                    return
                # Upgrade road between cities to railroad
                if has_railroad and existing_road and existing_road["type"] == "road":
                    self.current_player = pid
                    self.worker_build(unit["id"], "railroad")
                    self._log_ai(pid, f"WORKER: railroad link at ({unit['q']},{unit['r']})")
                    return

        # --- WHERE TO MOVE? ---
        task = self._ai_worker_find_task(unit, pid, my_cities, has_railroad)
        if task:
            self._ai_step_toward(unit, task[0], task[1])

    def _ai_worker_find_task(self, unit, pid, my_cities, has_railroad):
        """Find best tile for worker to move to. Returns (q,r) or None."""
        player = self.players[pid]
        candidates = []  # (priority, q, r, reason)

        # Task 1: Unimproved tiles near cities (improvements — highest priority)
        for city in my_cities:
            br = city.get("border_radius", 1) + 1
            for dq in range(-br, br + 1):
                for dr in range(-br, br + 1):
                    tq, tr = city["q"] + dq, city["r"] + dr
                    if hex_distance(city["q"], city["r"], tq, tr) > br:
                        continue
                    t = self.tiles.get((tq, tr))
                    if not t or t in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                        continue
                    d = hex_distance(unit["q"], unit["r"], tq, tr)
                    if d > 20:
                        continue
                    needs_imp = (tq, tr) not in self.improvements and self._ai_pick_improvement(t.value, player)
                    needs_road = (tq, tr) not in self.roads
                    needs_rr = has_railroad and (tq, tr) in self.roads and self.roads[(tq, tr)]["type"] == "road"
                    if needs_imp:
                        candidates.append((d, tq, tr, "improve"))
                    elif needs_road:
                        candidates.append((d + 10, tq, tr, "road"))
                    elif needs_rr:
                        candidates.append((d + 20, tq, tr, "railroad"))

        # Task 2: Build road connecting two cities
        if len(my_cities) >= 2:
            for i, c1 in enumerate(my_cities):
                for c2 in my_cities[i+1:]:
                    # Check if cities are already connected (road exists on path between them)
                    dist = hex_distance(c1["q"], c1["r"], c2["q"], c2["r"])
                    if dist > 15:
                        continue
                    # Find midpoint — crude but effective
                    mid_q = (c1["q"] + c2["q"]) // 2
                    mid_r = (c1["r"] + c2["r"]) // 2
                    if (mid_q, mid_r) not in self.roads:
                        t = self.tiles.get((mid_q, mid_r))
                        if t and t not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                            d = hex_distance(unit["q"], unit["r"], mid_q, mid_r)
                            candidates.append((d + 8, mid_q, mid_r, "connect"))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])
        best = candidates[0]
        self._log_ai(pid, f"WORKER: moving to ({best[1]},{best[2]}) for {best[3]} (dist={best[0]:.0f})")
        return (best[1], best[2])

    def _ai_pick_improvement(self, terrain_val, player):
        """Pick the best improvement for a terrain type."""
        # If gold is negative, prefer trading posts on suitable terrain
        if player["gold"] < -20 and terrain_val in ("grass", "plains", "forest") and "currency" in player["techs"]:
            return "trading_post"
        options = {
            "grass": "farm", "plains": "farm", "desert": "farm",
            "hills": "mine", "forest": "lumber_mill",
        }
        imp_type = options.get(terrain_val)
        if imp_type and imp_type in IMPROVEMENTS:
            tech = IMPROVEMENTS[imp_type]["tech"]
            if not tech or tech in player["techs"]:
                return imp_type
        return None

    def _ai_settler_move(self, unit, pid):
        """Settler AI: find good spot and settle. Uses all movement."""
        if unit["id"] not in self.units:
            return

        # Find target spot once
        target = self._ai_find_settle_spot(unit, pid)

        # Use all movement to get there or settle
        for _ in range(unit["mov"]):
            if unit["id"] not in self.units or unit["moves_left"] <= 0:
                break
            # Can we settle here?
            terrain = self.tiles.get((unit["q"], unit["r"]))
            too_close = any(hex_distance(c["q"], c["r"], unit["q"], unit["r"]) < 3 for c in self.cities.values())
            if not too_close and terrain not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                city_names = ["Nova Roma", "Alexandria", "Persepolis", "Kyoto", "Tenochtitlan",
                              "Constantinople", "Carthage", "Babylon", "Memphis", "Sparta",
                              "Athens", "Thebes", "Troy", "Corinth", "Delhi",
                              "Luxor", "Olympia", "Syracuse", "Antioch", "Samarkand"]
                used = {c["name"] for c in self.cities.values()}
                name = next((n for n in city_names if n not in used), f"City {self.next_city_id}")
                self.current_player = pid
                wander_turns = self.turn - unit.get("born_turn", self.turn)
                self._log_ai(pid, f"SETTLE: founding {name} at ({unit['q']},{unit['r']}) terrain={terrain.value} wandered={wander_turns}t")
                self.found_city(unit["id"], name)
                return

            if target:
                old_q, old_r = unit["q"], unit["r"]
                self._ai_step_toward(unit, target[0], target[1])
                if unit["q"] == old_q and unit["r"] == old_r:
                    # Stuck — try settling here if possible
                    terrain_here = self.tiles.get((unit["q"], unit["r"]))
                    too_close = any(hex_distance(c["q"], c["r"], unit["q"], unit["r"]) < 3 for c in self.cities.values())
                    if not too_close and terrain_here and terrain_here not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                        # Settle here instead of target
                        self._log_ai(pid, f"SETTLER: stuck, settling here instead at ({unit['q']},{unit['r']})")
                    else:
                        # Try random adjacent move to get unstuck
                        neighbors = hex_neighbors(unit["q"], unit["r"])
                        valid = [(nq, nr) for nq, nr in neighbors
                                 if self.tiles.get((nq, nr)) not in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN)]
                        if valid:
                            nq, nr = random.choice(valid)
                            self.current_player = pid
                            self.move_unit(unit["id"], nq, nr)
                    break
            else:
                break

    def _ai_find_settle_spot(self, unit, pid):
        """Find best settlement location — weighs food heavily, considers 2-ring radius."""
        player = self.players[pid]
        strategy = player.get("strategy", "balanced")
        best = None
        best_score = -999
        for q in range(0, self.width, 2):
            for r in range(0, self.height, 2):
                t = self.tiles.get((q, r))
                if t in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                    continue
                if any(hex_distance(c["q"], c["r"], q, r) < 4 for c in self.cities.values()):
                    continue
                # Avoid spots where another settler is already heading
                if any(u["player"] == pid and u["type"] == "settler" and u["id"] != unit["id"]
                       and hex_distance(u["q"], u["r"], q, r) < 4 for u in self.units.values()):
                    continue
                d = hex_distance(unit["q"], unit["r"], q, r)
                if d > 20:
                    continue
                # Score all tiles in 2-ring radius
                score = 0
                food_total = 0
                for dq in range(-2, 3):
                    for dr in range(-2, 3):
                        if hex_distance(q, r, q + dq, r + dr) > 2:
                            continue
                        nt = self.tiles.get((q + dq, r + dr))
                        if nt and nt not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                            y = TERRAIN_YIELDS[nt]
                            food_total += y["food"]
                            # Weight: food most important for city growth
                            score += y["food"] * 3 + y["prod"] * 2 + y["gold"]
                # City tile itself
                cy = TERRAIN_YIELDS.get(t, {})
                score += cy.get("food", 0) * 2

                # Strategy preferences
                if strategy == "expansionist" and food_total >= 6:
                    score += 5  # China loves food-rich spots
                # Coastal bonus (for future naval)
                has_coast = any(self.tiles.get((q + dq, r + dr)) in (Terrain.COAST, Terrain.WATER)
                                for dq in range(-1, 2) for dr in range(-1, 2)
                                if hex_distance(q, r, q + dq, r + dr) <= 1)
                if has_coast:
                    score += 3

                score -= d  # Prefer closer
                if score > best_score:
                    best_score = score
                    best = (q, r)
        if best:
            self._log_ai(pid, f"SETTLER: target ({best[0]},{best[1]}) score={best_score} dist={hex_distance(unit['q'],unit['r'],best[0],best[1])}")
        else:
            self._log_ai(pid, f"SETTLER: no good spot from ({unit['q']},{unit['r']})")
        return best

    def _ai_military_move(self, unit, pid):
        """Personality-driven military AI."""
        if unit["moves_left"] <= 0:
            return
        player = self.players[pid]
        aggression = player.get("aggression", 0.5)
        trait = player.get("trait", "")
        my_military = [u for u in self.units.values() if u["player"] == pid and u["cat"] != "civilian"]
        my_cities = [c for c in self.cities.values() if c["player"] == pid]

        # Adjacent enemies — attack military units, or any unit if at war
        for nq, nr in hex_neighbors(unit["q"], unit["r"]):
            for eu in list(self.units.values()):
                if eu["player"] != pid and eu["q"] == nq and eu["r"] == nr:
                    rel = self.players[pid]["diplomacy"].get(eu["player"], "peace")
                    # Only attack: military units when not at peace, or any unit when at war
                    if rel == "war":
                        self._log_ai(pid, f"COMBAT: {unit['type']}(hp={unit['hp']}) attacks {eu['type']}(hp={eu['hp']}) at ({nq},{nr})")
                        self.current_player = pid
                        self.move_unit(unit["id"], nq, nr)
                        return
                    elif eu["cat"] != "civilian" and random.random() < aggression * 0.3:
                        # Attack enemy military (not civilians) — triggers war
                        self.declare_war(pid, eu["player"])
                        self._log_ai(pid, f"COMBAT: {unit['type']} attacks {eu['type']} — WAR declared!")
                        self.current_player = pid
                        self.move_unit(unit["id"], nq, nr)
                        return

        # Adjacent enemy city — attack if at war
        for nq, nr in hex_neighbors(unit["q"], unit["r"]):
            for ec in list(self.cities.values()):
                if ec["player"] != pid and ec["q"] == nq and ec["r"] == nr:
                    rel = self.players[pid]["diplomacy"].get(ec["player"], "neutral")
                    if rel == "war":
                        self._log_ai(pid, f"SIEGE: {unit['type']}(hp={unit['hp']}) attacks city {ec['name']}(hp={ec['hp']}/{ec['max_hp']})")
                        self.current_player = pid
                        self.move_unit(unit["id"], nq, nr)
                        return

        # Personality-driven war decisions
        min_military_for_attack = 2 if trait == "aggressive" else 4 if trait == "protective" else 3
        attack_range = 25 if trait == "aggressive" else 12 if trait == "protective" else 18

        # Chase enemies at war
        war_enemies = [u for u in self.units.values()
                       if u["player"] != pid
                       and self.players[pid]["diplomacy"].get(u["player"], "neutral") == "war"
                       and hex_distance(unit["q"], unit["r"], u["q"], u["r"]) <= 8]
        if war_enemies:
            target = min(war_enemies, key=lambda e: hex_distance(unit["q"], unit["r"], e["q"], e["r"]))
            self._ai_step_toward(unit, target["q"], target["r"])
            return

        # Offensive: consider starting wars based on personality
        if len(my_military) >= min_military_for_attack:
            # Aggressive leaders pick fights, protective ones don't
            if random.random() < aggression * 0.15:
                enemy_cities = [c for c in self.cities.values()
                                if c["player"] != pid
                                and self.players[pid]["diplomacy"].get(c["player"], "neutral") != "peace"]
                if enemy_cities:
                    target = min(enemy_cities, key=lambda c: hex_distance(unit["q"], unit["r"], c["q"], c["r"]))
                    d = hex_distance(unit["q"], unit["r"], target["q"], target["r"])
                    if d < attack_range:
                        self.declare_war(pid, target["player"])
                        self._ai_step_toward(unit, target["q"], target["r"])
                        return

        # Always march toward cities we're at war with (regardless of military count)
        war_cities = [c for c in self.cities.values()
                      if c["player"] != pid
                      and self.players[pid]["diplomacy"].get(c["player"], "neutral") == "war"]
        if war_cities:
            target = min(war_cities, key=lambda c: hex_distance(unit["q"], unit["r"], c["q"], c["r"]))
            if hex_distance(unit["q"], unit["r"], target["q"], target["r"]) < attack_range:
                self._ai_step_toward(unit, target["q"], target["r"])
                return

        # Obsolete unit — go to nearest city for upgrade
        upgrade_path = {"warrior": "swordsman", "swordsman": "musketman", "musketman": "rifleman",
                        "spearman": "musketman", "archer": "musketman", "horseman": "knight"}
        upgrade_to = upgrade_path.get(unit["type"])
        if upgrade_to and upgrade_to in UNIT_TYPES:
            udata = UNIT_TYPES[upgrade_to]
            if udata["tech"] and udata["tech"] in player.get("techs", []):
                # Has tech for upgrade — go to nearest own city
                in_city = any(c["q"] == unit["q"] and c["r"] == unit["r"] and c["player"] == pid
                              for c in self.cities.values())
                any_war = any(player["diplomacy"].get(p["id"]) == "war" for p in self.players if p["id"] != pid and p["alive"])
                if not in_city and my_cities and not any_war:
                    nearest_city = min(my_cities, key=lambda c: hex_distance(unit["q"], unit["r"], c["q"], c["r"]))
                    if hex_distance(unit["q"], unit["r"], nearest_city["q"], nearest_city["r"]) <= 6:
                        self._ai_step_toward(unit, nearest_city["q"], nearest_city["r"])
                        return

        # Defend threatened cities — only if not enough defenders
        for city in my_cities:
            enemies_near_city = [u for u in self.units.values()
                                 if u["player"] != pid and u["cat"] != "civilian"
                                 and hex_distance(u["q"], u["r"], city["q"], city["r"]) <= 3]
            defenders_near = [u for u in self.units.values()
                              if u["player"] == pid and u["cat"] != "civilian" and u["id"] != unit["id"]
                              and hex_distance(u["q"], u["r"], city["q"], city["r"]) <= 2]
            if enemies_near_city and len(defenders_near) < len(enemies_near_city):
                d = hex_distance(unit["q"], unit["r"], city["q"], city["r"])
                if d <= 6:
                    self._ai_step_toward(unit, city["q"], city["r"])
                    return

        # Default: patrol near own cities
        if my_cities:
            nearest = min(my_cities, key=lambda c: hex_distance(unit["q"], unit["r"], c["q"], c["r"]))
            d = hex_distance(unit["q"], unit["r"], nearest["q"], nearest["r"])
            if d > 3:
                self._ai_step_toward(unit, nearest["q"], nearest["r"])
            elif random.random() > 0.5:
                neighbors = hex_neighbors(unit["q"], unit["r"])
                valid = [(nq, nr) for nq, nr in neighbors
                         if self.tiles.get((nq, nr)) not in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN)]
                if valid:
                    nq, nr = random.choice(valid)
                    self.current_player = pid
                    self.move_unit(unit["id"], nq, nr)

    def _auto_explore_step(self, unit, pid):
        """BFS explore — find nearest REACHABLE unexplored tile and move toward it."""
        if unit["id"] not in self.units:
            return
        from collections import deque
        explored = self.explored.get(pid, set())
        is_naval = unit["cat"] == "naval"
        is_air = unit["cat"] == "air"
        start = (unit["q"], unit["r"])

        # BFS from unit position — first unexplored reachable tile is target
        visited = {start}
        queue = deque([(start, [start])])
        target_path = None
        max_search = min(500, self.width * self.height // 2)
        steps = 0

        while queue and steps < max_search:
            (cq, cr), path = queue.popleft()
            steps += 1

            # Is this tile unexplored?
            if (cq, cr) not in explored and (cq, cr) != start:
                target_path = path
                break

            for nq, nr in hex_neighbors(cq, cr):
                if (nq, nr) in visited:
                    continue
                t = self.tiles.get((nq, nr))
                if t is None:
                    continue
                if not is_air:
                    if is_naval and t not in (Terrain.WATER, Terrain.COAST):
                        continue
                    if not is_naval and t == Terrain.MOUNTAIN:
                        continue
                    if not is_naval and t in (Terrain.WATER, Terrain.COAST):
                        continue
                visited.add((nq, nr))
                queue.append(((nq, nr), path + [(nq, nr)]))

        if not target_path or len(target_path) < 2:
            unit["exploring"] = False
            return

        # Move to next hex in path
        next_hex = target_path[1]
        result = self.move_unit(unit["id"], next_hex[0], next_hex[1])
        if result.get("combat") and unit["id"] in self.units:
            self.units[unit["id"]]["exploring"] = False

    def _find_path_next(self, unit, tq, tr):
        """BFS pathfinding — returns next hex to move to, or None."""
        from collections import deque
        start = (unit["q"], unit["r"])
        target = (tq, tr)
        if start == target:
            return None

        is_naval = unit["cat"] in ("naval",)
        is_air = unit["cat"] == "air"

        visited = {start}
        queue = deque([(start, [start])])
        max_search = min(200, self.width * self.height // 4)
        steps = 0

        while queue and steps < max_search:
            (cq, cr), path = queue.popleft()
            steps += 1
            for nq, nr in hex_neighbors(cq, cr):
                if (nq, nr) in visited:
                    continue
                t = self.tiles.get((nq, nr))
                if t is None:
                    continue
                # Passability
                if not is_air:
                    if is_naval and t not in (Terrain.WATER, Terrain.COAST):
                        continue
                    if not is_naval and t == Terrain.MOUNTAIN:
                        continue
                    if not is_naval and t in (Terrain.WATER, Terrain.COAST):
                        continue
                visited.add((nq, nr))
                new_path = path + [(nq, nr)]
                if (nq, nr) == target:
                    return new_path[1] if len(new_path) > 1 else None
                queue.append(((nq, nr), new_path))

        # BFS failed — fallback to greedy step
        return self._greedy_step(unit, tq, tr)

    def _greedy_step(self, unit, tq, tr):
        """Simple greedy step toward target (fallback)."""
        best = None
        best_dist = hex_distance(unit["q"], unit["r"], tq, tr)
        for nq, nr in hex_neighbors(unit["q"], unit["r"]):
            t = self.tiles.get((nq, nr))
            if t is None or t == Terrain.MOUNTAIN:
                continue
            if t in (Terrain.WATER, Terrain.COAST) and unit["cat"] not in ("naval", "air"):
                continue
            d = hex_distance(nq, nr, tq, tr)
            if d < best_dist or d == 0:
                best_dist = d
                best = (nq, nr)
        return best

    def _ai_step_toward(self, unit, tq, tr):
        """Move unit one step toward target using BFS pathfinding."""
        next_hex = self._find_path_next(unit, tq, tr)
        if next_hex:
            self.current_player = unit["player"]
            self.move_unit(unit["id"], next_hex[0], next_hex[1])

    # --------------------------------------------------------
    # SERIALIZATION
    # --------------------------------------------------------

    def to_dict(self, for_player=None):
        """Serialize game state. If for_player is set, apply fog of war."""
        visible = None
        if for_player is not None:
            visible = self.get_visible_tiles(for_player)

        # Explored tiles (terrain visible but no units/cities info)
        explored = self.explored.get(for_player, set()) if for_player is not None else None

        # Tiles: show currently visible + previously explored
        tiles_data = {}
        for (q, r), t in self.tiles.items():
            if visible is None or (q, r) in visible or (explored and (q, r) in explored):
                tiles_data[f"{q},{r}"] = t.value

        # Units: only show in currently visible tiles
        units_data = []
        for u in self.units.values():
            if visible is None or (u["q"], u["r"]) in visible:
                units_data.append(u.copy())

        # Cities
        cities_data = []
        for c in self.cities.values():
            if visible is None or (c["q"], c["r"]) in visible:
                cd = c.copy()
                if for_player is not None and c["player"] != for_player:
                    # Hide production info for enemy cities
                    cd.pop("producing", None)
                    cd.pop("prod_progress", None)
                    cd.pop("food_store", None)
                cities_data.append(cd)

        players_data = []
        for p in self.players:
            pd = {
                "id": p["id"],
                "name": p["name"],
                "civ": p["civ"],
                "color": p["color"],
                "leader": p["leader"],
                "alive": p["alive"],
                "score": p["score"],
            }
            if for_player is not None and p["id"] == for_player:
                pd.update({
                    "gold": p["gold"],
                    "techs": p["techs"],
                    "researching": p["researching"],
                    "diplomacy": p["diplomacy"],
                    "science_pool": p["science_pool"],
                    "culture_pool": p["culture_pool"],
                })
            players_data.append(pd)

        # Build visible set for fog of war rendering
        visible_keys = []
        if visible is not None:
            visible_keys = [f"{q},{r}" for q, r in visible]

        return {
            "width": self.width,
            "height": self.height,
            "turn": self.turn,
            "current_player": self.current_player,
            "game_over": self.game_over,
            "winner": self.winner,
            "tiles": tiles_data,
            "visible": visible_keys,
            "improvements": {f"{q},{r}": v for (q, r), v in self.improvements.items()
                             if visible is None or (q, r) in visible or (explored and (q, r) in explored)},
            "roads": {f"{q},{r}": v for (q, r), v in self.roads.items()
                      if visible is None or (q, r) in visible or (explored and (q, r) in explored)},
            "units": units_data,
            "cities": cities_data,
            "players": players_data,
        }

    def get_available_productions(self, city_id):
        """Get list of units and buildings a city can produce."""
        city = self.cities.get(city_id)
        if not city:
            return {"units": [], "buildings": []}

        player = self.players[city["player"]]

        # Check if city has adjacent water (for naval units)
        has_water = any(self.tiles.get((nq, nr)) in (Terrain.WATER, Terrain.COAST)
                        for nq, nr in hex_neighbors(city["q"], city["r"]))

        units = []
        for uname, udata in UNIT_TYPES.items():
            if not udata["tech"] or udata["tech"] in player["techs"]:
                # Naval units only in coastal cities
                if udata["cat"] == "naval" and not has_water:
                    continue
                units.append({"name": uname, "cost": udata["cost"], "atk": udata["atk"],
                            "def": udata["def"], "mov": udata["mov"], "cat": udata["cat"]})

        buildings = []
        for bname, bdata in BUILDINGS.items():
            if bname in city["buildings"]:
                continue
            if not bdata["tech"] or bdata["tech"] in player["techs"]:
                buildings.append({"name": bname, "cost": bdata["cost"],
                                "food": bdata["food"], "prod": bdata["prod"], "gold": bdata["gold"],
                                "science": bdata["science"], "culture": bdata["culture"],
                                "defense": bdata["defense"]})

        return {"units": units, "buildings": buildings}

    def get_available_techs(self, player_id):
        """Get list of researchable technologies."""
        player = self.players[player_id]
        available = []
        for tname, tdata in TECHNOLOGIES.items():
            if tname in player["techs"]:
                continue
            can_research = all(p in player["techs"] for p in tdata["prereqs"])
            available.append({
                "name": tname,
                "cost": tdata["cost"],
                "era": tdata["era"],
                "prereqs": tdata["prereqs"],
                "unlocks": tdata["unlocks"],
                "available": can_research,
            })
        return available

    # --------------------------------------------------------
    # SIMULATION / DEBUG
    # --------------------------------------------------------

    @classmethod
    def simulate(cls, width=40, height=30, num_players=4, num_turns=100, seed=None):
        """Run a full AI-only game and return detailed log."""
        game = cls(width=width, height=height, num_players=num_players, seed=seed)
        # Make all players AI
        for p in game.players:
            p["is_human"] = False

        log = {
            "settings": {"width": width, "height": height, "players": num_players, "seed": seed, "turns": num_turns},
            "players": [{"id": p["id"], "name": p["name"], "civ": p["civ"]} for p in game.players],
            "turns": [],
            "result": None,
        }

        for turn_num in range(num_turns):
            if game.game_over:
                break

            turn_log = {"turn": game.turn, "events": []}

            # Snapshot before turn
            for p in game.players:
                if not p["alive"]:
                    continue
                pid = p["id"]
                my_cities = [c for c in game.cities.values() if c["player"] == pid]
                my_units = [u for u in game.units.values() if u["player"] == pid]
                # Economy breakdown
                total_income = sum(game.get_city_yields(c["id"])["gold"] for c in my_cities)
                unit_count = len(my_units)
                free = GAME_CONFIG.get("unit_maintenance_free", 2)
                maint = max(0, unit_count - free) * GAME_CONFIG.get("unit_maintenance_cost", 1)
                total_prod_out = sum(game.get_city_yields(c["id"])["prod"] for c in my_cities)
                total_science_out = sum(game.get_city_yields(c["id"])["science"] for c in my_cities)
                total_culture_out = sum(game.get_city_yields(c["id"])["culture"] for c in my_cities)
                total_food_out = sum(game.get_city_yields(c["id"])["food"] for c in my_cities)

                # Territory
                territory = sum(1 for q in range(game.width) for r in range(game.height)
                                if game.get_tile_owner(q, r) == pid) if game.turn % 10 == 0 else 0

                # Victory progress
                space_techs = ["space_program", "rocketry", "nuclear_fission"]
                space_tech_done = sum(1 for t in space_techs if t in p["techs"])
                space_prog = p.get("space_progress", 0)
                space_need = GAME_CONFIG.get("space_victory_production", 2000)
                culture_prog = p["culture_pool"]
                culture_need = GAME_CONFIG.get("culture_victory_threshold", 3000)
                total_cities_all = len(game.cities)
                my_city_count = len(my_cities)
                domin_pct = my_city_count / max(1, total_cities_all)

                # Improvements on my territory
                my_imps = sum(1 for pos in game.improvements if game.get_tile_owner(*pos) == pid)
                my_roads = sum(1 for pos in game.roads if game.get_tile_owner(*pos) == pid)

                plog = {
                    "player": p["name"],
                    "gold": p["gold"],
                    "score": p["score"],
                    "techs": len(p["techs"]),
                    "researching": p["researching"]["name"] if p["researching"] else None,
                    "economy": {"income": total_income, "maintenance": maint, "net": total_income - maint},
                    "yields": {"food": total_food_out, "prod": total_prod_out, "science": total_science_out, "culture": total_culture_out},
                    "victory": {
                        "space": f"{space_tech_done}/3 techs, {space_prog}/{space_need} prod ({int(space_prog/space_need*100)}%)" if space_tech_done > 0 else "0/3 techs",
                        "culture": f"{culture_prog}/{culture_need} ({int(culture_prog/culture_need*100)}%)",
                        "domination": f"{my_city_count}/{total_cities_all} ({int(domin_pct*100)}%)",
                    },
                    "territory": territory,
                    "improvements": my_imps,
                    "roads": my_roads,
                    "cities": [{
                        "name": c["name"],
                        "pop": c["population"],
                        "producing": c["producing"]["name"] if c.get("producing") else "IDLE",
                        "buildings": len(c["buildings"]),
                    } for c in my_cities],
                    "units": {},
                }
                for u in my_units:
                    utype = u["type"]
                    plog["units"][utype] = plog["units"].get(utype, 0) + 1
                turn_log["events"].append(plog)

            log["turns"].append(turn_log)

            # Run one full round (all players)
            start_turn = game.turn
            # Process each player's turn
            for pid in range(num_players):
                if not game.players[pid]["alive"] or game.game_over:
                    continue
                game.current_player = pid
                pname = game.players[pid]["name"]
                # Snapshot before AI
                units_before = set(game.units.keys())
                cities_before = {c["id"]: c["player"] for c in game.cities.values()}
                # Reset movement
                for u in game.units.values():
                    if u["player"] == pid:
                        u["moves_left"] = u["mov"]
                # Run AI (clear log before, collect after)
                game.ai_log = []
                game._run_ai(pid)
                # Add AI decisions to turn log
                if game.ai_log:
                    turn_log["events"].extend(game.ai_log)
                # Detect combat results
                units_after = set(game.units.keys())
                killed = units_before - units_after
                if killed:
                    turn_log["events"].append(f"[{pname}] {len(killed)} unit(s) destroyed in combat")
                for cid, cdata in game.cities.items():
                    old_owner = cities_before.get(cid)
                    if old_owner is not None and old_owner != cdata["player"]:
                        turn_log["events"].append(f"[{pname}] captured {cdata['name']}!")
                # Check new cities founded
                for cid in game.cities:
                    if cid not in cities_before:
                        turn_log["events"].append(f"[{pname}] founded {game.cities[cid]['name']}")
                # Process end of turn (cities, research, etc.)
                result = game._process_turn(pid)
                if result.get("events"):
                    turn_log["events"].extend([f"[{pname}] {e}" for e in result["events"]])

            game.turn += 1

        # Score victory — if no winner, highest score wins
        if not game.game_over:
            alive = [p for p in game.players if p["alive"]]
            if alive:
                best = max(alive, key=lambda p: p["score"])
                game.game_over = True
                game.winner = best["id"]
                log["turns"][-1]["events"].append(f"{best['name']} achieves SCORE victory! ({best['score']} pts)")

        # Final result
        log["result"] = {
            "game_over": game.game_over,
            "winner": game.players[game.winner]["name"] if game.winner is not None else None,
            "final_turn": game.turn,
            "scores": [{
                "name": p["name"],
                "score": p["score"],
                "alive": p["alive"],
                "techs": len(p["techs"]),
                "cities": len([c for c in game.cities.values() if c["player"] == p["id"]]),
                "units": len([u for u in game.units.values() if u["player"] == p["id"]]),
            } for p in game.players],
        }
        return log

    def _process_turn(self, pid):
        """Process yields, production, research for one player. Returns events."""
        player = self.players[pid]
        if not player["alive"]:
            return {"events": []}

        # Tick diplomacy cooldowns
        for k in list(player.get("diplo_cooldown", {}).keys()):
            if player["diplo_cooldown"][k] > 0:
                player["diplo_cooldown"][k] -= 1

        total_gold = 0
        total_science = 0
        total_culture = 0
        events = []

        for city in list(self.cities.values()):
            if city["player"] != pid:
                continue
            yields = self.get_city_yields(city["id"])
            total_gold += yields["gold"]
            total_science += yields["science"]
            total_culture += yields["culture"]

            city["food_store"] += yields["food_surplus"]
            growth_needed = 10 + city["population"] * 5
            if city["food_store"] >= growth_needed:
                city["population"] += 1
                city["food_store"] = 0
                events.append(f"{city['name']} grew to pop {city['population']}")
            elif city["food_store"] < 0:
                if city["population"] > 1:
                    city["population"] -= 1
                    city["food_store"] = 0

            if city["producing"]:
                city["prod_progress"] += yields["prod"]
                if city["prod_progress"] >= city["producing"]["cost"]:
                    item = city["producing"]
                    if item["type"] == "unit":
                        self._create_unit(pid, item["name"], city["q"], city["r"])
                        events.append(f"{city['name']} produced {item['name']}")
                    elif item["type"] == "building":
                        city["buildings"].append(item["name"])
                        events.append(f"{city['name']} built {item['name']}")
                    city["producing"] = None
                    city["prod_progress"] = 0
                    self._ai_auto_produce(city, player, pid)

            city["culture"] = city.get("culture", 0) + yields["culture"]
            old_br = city.get("border_radius", 1)
            thresholds = [(400, 5), (150, 4), (50, 3), (10, 2)]
            new_br = 1
            for threshold, radius in thresholds:
                if city["culture"] >= threshold:
                    new_br = radius
                    break
            city["border_radius"] = new_br

            if city["hp"] < city["max_hp"]:
                city["hp"] = min(city["max_hp"], city["hp"] + 10)

        # Worker building progress (simulation)
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("building"):
                u["building"]["turns_left"] -= 1
                if u["building"]["turns_left"] <= 0:
                    imp_type = u["building"]["type"]
                    pos = (u["q"], u["r"])
                    if imp_type in ("road", "railroad"):
                        self.roads[pos] = {"type": imp_type, "player": pid}
                    else:
                        self.improvements[pos] = {"type": imp_type, "player": pid}
                    events.append(f"Worker built {imp_type}")
                    u["building"] = None

        # Spy/caravan processing (simulation)
        for u in list(self.units.values()):
            if u["player"] == pid and u["type"] == "spy":
                for ec in self.cities.values():
                    if ec["player"] != pid and ec["q"] == u["q"] and ec["r"] == u["r"]:
                        if random.random() < 0.3:
                            enemy = self.players[ec["player"]]
                            stealable = [t for t in enemy["techs"] if t not in player["techs"]]
                            if stealable:
                                stolen = random.choice(stealable)
                                player["techs"].append(stolen)
                                events.append(f"Spy stole {stolen}")
                            else:
                                ec["prod_progress"] = max(0, ec.get("prod_progress", 0) - 10)
                                events.append(f"Spy sabotaged {ec['name']}")
                            if random.random() < 0.4:
                                del self.units[u["id"]]
                                events.append(f"Spy caught!")
                        break
            elif u["player"] == pid and u["type"] == "caravan":
                for fc in self.cities.values():
                    if fc["player"] != pid and fc["q"] == u["q"] and fc["r"] == u["r"]:
                        rel = player["diplomacy"].get(fc["player"], "neutral")
                        if rel != "war":
                            total_gold += 8
                            events.append(f"Caravan trade +8 gold")
                            del self.units[u["id"]]
                        break

        unit_count = sum(1 for u in self.units.values() if u["player"] == pid)
        maintenance = max(0, unit_count - 2) * 1
        total_gold -= maintenance
        player["gold"] += total_gold

        # Bankruptcy
        if player["gold"] < -50:
            mil_units = [u for u in self.units.values()
                         if u["player"] == pid and u["cat"] != "civilian"]
            if mil_units:
                weakest = min(mil_units, key=lambda u: u["hp"])
                del self.units[weakest["id"]]
                player["gold"] += 20
                events.append(f"Disbanded {weakest['type']} (bankrupt)")

        if player["researching"]:
            player["researching"]["progress"] += total_science
            if player["researching"]["progress"] >= player["researching"]["cost"]:
                tech_name = player["researching"]["name"]
                player["techs"].append(tech_name)
                events.append(f"Discovered: {tech_name}")
                player["researching"] = None

        player["culture_pool"] += total_culture

        for u in self.units.values():
            if u["player"] == pid and u["hp"] < 100:
                in_city = any(c["q"] == u["q"] and c["r"] == u["r"] and c["player"] == pid
                             for c in self.cities.values())
                if in_city:
                    u["hp"] = min(100, u["hp"] + 15)
                elif u.get("fortified"):
                    u["hp"] = min(100, u["hp"] + 10)
                else:
                    u["hp"] = min(100, u["hp"] + 5)

        player["score"] = (
            len([c for c in self.cities.values() if c["player"] == pid]) * 100 +
            sum(c["population"] for c in self.cities.values() if c["player"] == pid) * 20 +
            len(player["techs"]) * 30 +
            player["culture_pool"] // 10
        )

        space_techs = ["space_program", "rocketry", "nuclear_fission"]
        if all(t in player["techs"] for t in space_techs):
            player["space_progress"] = player.get("space_progress", 0) + sum(
                self.get_city_yields(c["id"])["prod"] for c in self.cities.values() if c["player"] == pid)
            if player.get("space_progress", 0) >= GAME_CONFIG.get("space_victory_production", 2000):
                self.game_over = True
                self.winner = pid
                events.append(f"{player['name']} achieves SPACE victory!")
        if not self.game_over and player["culture_pool"] >= GAME_CONFIG.get("culture_victory_threshold", 3000):
            self.game_over = True
            self.winner = pid
            events.append(f"{player['name']} achieves CULTURE victory!")
        if not self.game_over:
            total_cities = len(self.cities)
            my_city_count = len([c for c in self.cities.values() if c["player"] == pid])
            if total_cities >= 4 and my_city_count >= total_cities * GAME_CONFIG.get("domination_city_percent", 0.6):
                self.game_over = True
                self.winner = pid
                events.append(f"{player['name']} achieves DOMINATION victory!")

        self._check_elimination()
        return {"events": events}

    # --------------------------------------------------------
    # SAVE / LOAD
    # --------------------------------------------------------

    def save_full(self):
        """Serialize complete game state for saving (no fog of war)."""
        tiles_data = {}
        for (q, r), t in self.tiles.items():
            tiles_data[f"{q},{r}"] = t.value

        return {
            "version": 1,
            "width": self.width,
            "height": self.height,
            "turn": self.turn,
            "current_player": self.current_player,
            "game_over": self.game_over,
            "winner": self.winner,
            "next_unit_id": self.next_unit_id,
            "next_city_id": self.next_city_id,
            "tiles": tiles_data,
            "units": {str(k): v.copy() for k, v in self.units.items()},
            "cities": {str(k): v.copy() for k, v in self.cities.items()},
            "players": [p.copy() for p in self.players],
            "explored": {str(k): [f"{q},{r}" for q, r in v] for k, v in self.explored.items()},
            "improvements": {f"{q},{r}": v for (q, r), v in self.improvements.items()},
            "roads": {f"{q},{r}": v for (q, r), v in self.roads.items()},
        }

    @classmethod
    def load_full(cls, data):
        """Restore game state from saved data."""
        g = cls.__new__(cls)
        g.width = data["width"]
        g.height = data["height"]
        g.turn = data["turn"]
        g.current_player = data["current_player"]
        g.game_over = data["game_over"]
        g.winner = data["winner"]
        g.next_unit_id = data["next_unit_id"]
        g.next_city_id = data["next_city_id"]

        # Restore tiles
        g.tiles = {}
        for key, val in data["tiles"].items():
            q, r = map(int, key.split(","))
            g.tiles[(q, r)] = Terrain(val)

        # Restore units
        g.units = {}
        for key, val in data["units"].items():
            g.units[int(key)] = val

        # Restore cities
        g.cities = {}
        for key, val in data["cities"].items():
            g.cities[int(key)] = val

        # Restore players
        g.players = data["players"]
        # Ensure diplomacy keys are ints
        for p in g.players:
            if "diplomacy" in p:
                p["diplomacy"] = {int(k): v for k, v in p["diplomacy"].items()}

        # Restore explored tiles
        g.explored = {}
        if "explored" in data:
            for k, coords in data["explored"].items():
                g.explored[int(k)] = {(int(c.split(",")[0]), int(c.split(",")[1])) for c in coords}
        else:
            g.explored = {i: set() for i in range(len(g.players))}

        # Restore improvements
        g.improvements = {}
        if "improvements" in data:
            for key, val in data["improvements"].items():
                q, r = map(int, key.split(","))
                g.improvements[(q, r)] = val

        # Restore roads
        g.roads = {}
        if "roads" in data:
            for key, val in data["roads"].items():
                q, r = map(int, key.split(","))
                g.roads[(q, r)] = val

        return g
