"""GameState — the main object. Combines all mixins and holds per-game state."""
import random

from civgame.constants import Terrain, TERRAIN_YIELDS, GAME_CONFIG
from civgame.hex import hex_neighbors, hex_distance
from civgame.data import CIVILIZATIONS, UNIT_TYPES, RESOURCES
from civgame.mapgen import generate_earth_map, generate_map
from civgame.mixins import (
    VisibilityMixin,
    CityMixin,
    MovementMixin,
    CombatMixin,
    ActionsMixin,
    DiplomacyMixin,
    DealsMixin,
    TurnMixin,
    ResearchMixin,
    SerializationMixin,
    SimulationMixin,
)
from civgame.ai import AIMixin


class GameState(
    VisibilityMixin,
    CityMixin,
    MovementMixin,
    CombatMixin,
    ActionsMixin,
    DiplomacyMixin,
    DealsMixin,
    ResearchMixin,
    TurnMixin,
    SerializationMixin,
    SimulationMixin,
    AIMixin,
):
    def __init__(self, width=40, height=30, num_players=4, seed=None,
                 map_type="random", wrap=False):
        self.width = width
        self.height = height
        self.wrap = wrap  # Globe: left/right edges connect
        self.turn = 1
        self.current_player = 0
        self.ai_log = []  # Debug log for AI decisions
        self.game_over = False
        self.winner = None
        self.victory_type = None
        self.next_unit_id = 1
        self.next_city_id = 1

        # Generate map
        if map_type.startswith("earth"):
            self.tiles = generate_earth_map(width, height, seed)
            self.wrap = True  # Earth maps are always globe
        else:
            self.tiles = generate_map(width, height, seed)

        # Players — unique civilizations, no duplicates
        civ_keys = list(CIVILIZATIONS.keys())
        random.shuffle(civ_keys)
        while len(civ_keys) < num_players:
            base = civ_keys[len(civ_keys) % len(CIVILIZATIONS)]
            civ_keys.append(base)
        self.players = []
        used_civs = set()
        for i in range(num_players):
            civ = civ_keys[i]
            if civ in used_civs:
                for ck in CIVILIZATIONS:
                    if ck not in used_civs:
                        civ = ck
                        break
            used_civs.add(civ)
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
                "diplomacy": {},
                "diplo_cooldown": {},
                "relations": {},
                "trait": CIVILIZATIONS[civ].get("trait", "aggressive"),
                "aggression": CIVILIZATIONS[civ].get("aggression", 0.5),
                "loyalty": CIVILIZATIONS[civ].get("loyalty", 0.5),
                "strategy": CIVILIZATIONS[civ].get("strategy", "balanced"),
            })

        # Init diplomacy + relations
        for p in self.players:
            for other in self.players:
                if p["id"] != other["id"]:
                    p["diplomacy"][other["id"]] = "peace"
                    p["relations"][other["id"]] = 0

        self.units = {}
        self.cities = {}
        self.improvements = {}
        self.roads = {}
        self.explored = {i: set() for i in range(num_players)}

        # Resources: (q, r) -> resource_key (name).
        self.resources = {}
        self._place_resources(seed)

        # Diplomacy extras: agreements list and per-player memory/grievances.
        self.agreements = []   # list of {type, players, turns_left, params}
        self.pending_deals = []  # list of proposals awaiting decision

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

            min_dist = 999
            for tq, tr in taken_positions:
                d = hex_distance(q, r, tq, tr)
                min_dist = min(min_dist, d)

            if min_dist < 6:
                continue

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

            self._create_unit(p["id"], "settler", pos[0], pos[1])
            wq, wr = pos
            used_tiles = [pos]
            for nq, nr in hex_neighbors(wq, wr):
                if self.tiles.get((nq, nr)) not in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                    wq, wr = nq, nr
                    break
            self._create_unit(p["id"], "warrior", wq, wr)
            used_tiles.append((wq, wr))
            for nq, nr in hex_neighbors(pos[0], pos[1]):
                if (nq, nr) not in used_tiles and self.tiles.get((nq, nr)) not in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                    self._create_unit(p["id"], "worker", nq, nr)
                    break

    def wrap_q(self, q):
        """Wrap horizontal coordinate for globe maps."""
        if getattr(self, "wrap", False):
            return q % self.width
        return q

    def _place_resources(self, seed=None):
        """Procedurally place resources on matching terrain.

        Each tile has a small chance (~3%) of getting a resource, weighted by
        whether its terrain is valid for any resource. Bonus resources are
        slightly more common than strategic/luxury.
        """
        import random as _r
        rng = _r.Random(seed if seed is not None else self.width * self.height)
        # Build terrain -> possible resources index
        by_terrain = {}
        for rname, rdata in RESOURCES.items():
            for t in rdata["terrain"]:
                by_terrain.setdefault(t, []).append((rname, rdata))
        spawn_chance = GAME_CONFIG.get("resource_spawn_chance", 0.035)
        for (q, r), terrain in list(self.tiles.items()):
            if rng.random() > spawn_chance:
                continue
            t_val = terrain.value
            candidates = by_terrain.get(t_val, [])
            if not candidates:
                continue
            # Weight bonus twice as likely as strategic/luxury
            weighted = []
            for name, data in candidates:
                w = 2 if data["type"] == "bonus" else 1
                weighted.extend([name] * w)
            self.resources[(q, r)] = rng.choice(weighted)

    def _create_unit(self, player_id, unit_type, q, r):
        uid = self.next_unit_id
        self.next_unit_id += 1
        stats = UNIT_TYPES[unit_type]
        home_city = None
        best_dist = 999
        for c in self.cities.values():
            if c["player"] == player_id:
                d = hex_distance(c["q"], c["r"], q, r)
                if d < best_dist:
                    best_dist = d
                    home_city = c["id"]
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
            "building": None,
            "goto": None,
            "born_turn": self.turn,
            "home_city": home_city,
        }
        return uid

    def _create_city(self, player_id, name, q, r):
        cid = self.next_city_id
        self.next_city_id += 1
        is_first = len([c for c in self.cities.values() if c["player"] == player_id]) == 0
        self.cities[cid] = {
            "id": cid,
            "player": player_id,
            "name": name,
            "q": q, "r": r,
            "population": 1,
            "food_store": 0,
            "culture": 0,
            "border_radius": 1,
            "buildings": ["palace"] if is_first else [],
            "producing": None,
            "prod_progress": 0,
            "prod_queue": [],
            "auto_produce": None,
            "hp": 200,
            "max_hp": 200,
        }
        return cid
