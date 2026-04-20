"""JSON serialization + save/load."""
import math
from civgame.hex import hex_neighbors
from civgame.constants import Terrain
from civgame.data import TECHNOLOGIES, UNIT_TYPES, BUILDINGS, IMPROVEMENTS

class SerializationMixin:
    def to_dict(self, for_player=None):
        """Serialize game state. If for_player is set, apply fog of war."""
        visible = None
        if for_player is not None:
            visible = self.get_visible_tiles(for_player)

        # Explored tiles (terrain visible but no units/cities info)
        explored = self.explored.get(for_player, set()) if for_player is not None else None

        # Tiles: show currently visible + previously explored.
        # Also expose tile ownership so the frontend can draw enemy borders
        # even when the owning city itself is hidden by fog of war.
        tiles_data = {}
        tile_owners = {}
        for (q, r), t in self.tiles.items():
            if visible is None or (q, r) in visible or (explored and (q, r) in explored):
                key = f"{q},{r}"
                tiles_data[key] = t.value
                owner = self.get_tile_owner(q, r)
                if owner is not None:
                    tile_owners[key] = owner

        # Units: only show in currently visible tiles
        units_data = []
        for u in self.units.values():
            if visible is None or (u["q"], u["r"]) in visible:
                ud = u.copy()
                # Compute goto path for player's own units with active goto
                if u.get("goto") and for_player is not None and u["player"] == for_player:
                    gpath = self._compute_path(u["q"], u["r"], u["goto"]["q"], u["goto"]["r"], u["player"])
                    ud["goto_path"] = gpath
                    if gpath:
                        ud["goto_turns"] = self._path_turns(gpath, u.get("mov", 1), u.get("moves_left"))
                units_data.append(ud)

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
            "wrap": getattr(self, 'wrap', False),
            "turn": self.turn,
            "current_player": self.current_player,
            "game_over": self.game_over,
            "winner": self.winner,
            "tiles": tiles_data,
            "tile_owners": tile_owners,
            "resources": {f"{q},{r}": v for (q, r), v in self.resources.items()
                          if visible is None or (q, r) in visible or (explored and (q, r) in explored)},
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
                # Strategic resource gating
                ok, missing = self.player_can_build_unit(city["player"], uname)
                if not ok:
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
            "resources": {f"{q},{r}": v for (q, r), v in getattr(self, "resources", {}).items()},
            "agreements": list(getattr(self, "agreements", [])),
            "pending_deals": list(getattr(self, "pending_deals", [])),
        }

    @classmethod

    def load_full(cls, data):
        """Restore game state from saved data."""
        g = cls.__new__(cls)
        g.ai_log = []  # Must init before anything else
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

        # Restore resources (optional for older saves)
        g.resources = {}
        if "resources" in data:
            for key, val in data["resources"].items():
                q, r = map(int, key.split(","))
                g.resources[(q, r)] = val

        # Restore diplomatic state (optional for older saves)
        g.agreements = list(data.get("agreements", []))
        g.pending_deals = list(data.get("pending_deals", []))

        return g

