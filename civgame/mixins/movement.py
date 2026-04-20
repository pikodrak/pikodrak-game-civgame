"""Unit movement and pathfinding (A*)."""
import heapq
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain, TERRAIN_MOVE_COST, TERRAIN_DEFENSE, GAME_CONFIG
from civgame.data import UNIT_TYPES, CIVILIZATIONS

class MovementMixin:
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

        move_cost = float(TERRAIN_MOVE_COST.get(terrain, 1))
        # Roads halve cost, railroads quarter it (fractional MP allowed)
        road = self.roads.get((target_q, target_r))
        if road:
            move_cost = max(0.25, move_cost * (0.25 if road["type"] == "railroad" else 0.5))
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
                # AI: auto-declare war (only log if not already at war)
                if self.players[unit["player"]]["diplomacy"].get(territory_owner) != "war":
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

    def _hex_move_cost(self, q, r):
        """Move cost to enter hex (q,r) using current road costs. Roads/railroads discount."""
        t = self.tiles.get((q, r))
        if t is None:
            return 99.0
        cost = float(TERRAIN_MOVE_COST.get(t, 1))
        road = self.roads.get((q, r))
        if road:
            cost = max(0.25, cost * (0.25 if road["type"] == "railroad" else 0.5))
        return cost

    def _compute_path(self, sq, sr, tq, tr, pid):
        """A* full path as list of [q,r] for rendering goto lines."""
        import heapq
        start = (sq, sr)
        target = (tq, tr)
        if start == target:
            return []
        # A* — heap entry: (f_cost, g_cost, tiebreak, pos, path).
        # Heuristic uses min possible step cost (0.25 = railroad) for admissibility.
        heap = [(0.0, 0.0, 0, start, [])]
        visited = {}  # pos -> best g_cost seen
        steps = 0
        while heap and steps < 1000:
            _, g_cost, _, (cq, cr), path = heapq.heappop(heap)
            steps += 1
            if (cq, cr) == target:
                return [[p[0], p[1]] for p in path]
            if (cq, cr) in visited and visited[(cq, cr)] <= g_cost:
                continue
            visited[(cq, cr)] = g_cost
            for nq, nr in hex_neighbors(cq, cr):
                t = self.tiles.get((nq, nr))
                if not t or t == Terrain.MOUNTAIN or t in (Terrain.WATER, Terrain.COAST):
                    continue
                move_cost = float(TERRAIN_MOVE_COST.get(t, 1))
                road = self.roads.get((nq, nr))
                if road:
                    move_cost = max(0.25, move_cost * (0.25 if road["type"] == "railroad" else 0.5))
                new_g = g_cost + move_cost
                if (nq, nr) in visited and visited[(nq, nr)] <= new_g:
                    continue
                h = hex_distance(nq, nr, tq, tr) * 0.25
                heapq.heappush(heap, (new_g + h, new_g, steps, (nq, nr), path + [(nq, nr)]))
        return []  # no path found

    def _find_path_next(self, unit, tq, tr):
        """A* pathfinding with move cost — prefers roads, avoids foreign territory."""
        import heapq
        start = (unit["q"], unit["r"])
        target = (tq, tr)
        if start == target:
            return None

        pid = unit["player"]
        player = self.players[pid]
        is_naval = unit["cat"] in ("naval",)
        is_air = unit["cat"] == "air"

        # A* with proper g/f separation. Admissible heuristic (min step cost 0.25).
        # Heap entry: (f_cost, g_cost, tiebreak, pos, path).
        heap = [(0.0, 0.0, 0, start, [start])]
        visited = {}  # pos -> best g_cost seen
        max_search = min(600, self.width * self.height // 2)
        steps = 0

        while heap and steps < max_search:
            _, g_cost, _, (cq, cr), path = heapq.heappop(heap)
            steps += 1

            if (cq, cr) == target:
                return path[1] if len(path) > 1 else None

            if (cq, cr) in visited and visited[(cq, cr)] <= g_cost:
                continue
            visited[(cq, cr)] = g_cost

            for nq, nr in hex_neighbors(cq, cr):
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
                # Avoid foreign territory unless at war or target
                if (nq, nr) != target:
                    tile_owner = self.get_tile_owner(nq, nr)
                    if tile_owner is not None and tile_owner != pid:
                        rel = player.get("diplomacy", {}).get(tile_owner, "peace")
                        if rel not in ("war", "alliance"):
                            continue

                # Move cost — roads halve, railroads quarter
                move_cost = float(TERRAIN_MOVE_COST.get(t, 1))
                road = self.roads.get((nq, nr))
                if road:
                    move_cost = max(0.25, move_cost * (0.25 if road["type"] == "railroad" else 0.5))

                new_g = g_cost + move_cost
                if (nq, nr) in visited and visited[(nq, nr)] <= new_g:
                    continue
                h = hex_distance(nq, nr, tq, tr) * 0.25
                heapq.heappush(heap, (new_g + h, new_g, steps, (nq, nr), path + [(nq, nr)]))

        # A* failed — fallback to greedy step
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

    def set_goto(self, unit_id, q, r):
        """Set auto-move target for unit."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        if q < 0 or q >= self.width or r < 0 or r >= self.height:
            return {"ok": False, "msg": "Target off map"}
        if not self.tiles.get((q, r)):
            return {"ok": False, "msg": "Invalid target"}
        unit["goto"] = {"q": q, "r": r}
        unit["fortified"] = False
        unit["sentry"] = False
        unit["exploring"] = False
        # Immediately start moving toward target
        while unit["id"] in self.units and unit.get("moves_left", 0) > 0 and unit.get("goto"):
            old_q, old_r = unit["q"], unit["r"]
            next_step = self._find_path_next(unit, q, r)
            if next_step:
                result = self.move_unit(unit["id"], next_step[0], next_step[1])
                if not result.get("ok") or (unit["q"] == old_q and unit["r"] == old_r):
                    break
                if result.get("combat"):
                    break
                if unit["q"] == q and unit["r"] == r:
                    unit["goto"] = None
                    break
            else:
                break
        return {"ok": True, "msg": f"Moving to ({q},{r})"}

