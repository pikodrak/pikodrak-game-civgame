"""Unit actions: worker build, fortify, sentry, explore, disband."""
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain
from civgame.data import IMPROVEMENTS

class ActionsMixin:
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

    def set_road_to(self, unit_id, q, r):
        """Put a worker in 'road mode' — it will build a road trail from its
        current tile to (q,r), one tile per turn."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        if unit["type"] != "worker":
            return {"ok": False, "msg": "Only workers can build road trails"}
        if q < 0 or q >= self.width or r < 0 or r >= self.height:
            return {"ok": False, "msg": "Target off map"}
        if not self.tiles.get((q, r)):
            return {"ok": False, "msg": "Invalid target"}
        unit["road_to"] = {"q": q, "r": r}
        unit["fortified"] = False
        unit["sentry"] = False
        unit["exploring"] = False
        unit["goto"] = None
        return {"ok": True, "msg": f"Road trail mode to ({q},{r})"}

    def process_road_trail(self, unit):
        """Per-turn worker tick: build or move along road_to target.

        Priority: if current tile lacks a road and terrain allows one, start
        building it. Otherwise step one hex toward target.
        """
        rt = unit.get("road_to")
        if not rt or unit.get("building"):
            return
        pos = (unit["q"], unit["r"])
        target = (rt["q"], rt["r"])
        if pos == target:
            unit["road_to"] = None
            return
        # Pick railroad if we have the tech, else road
        player = self.players[unit["player"]]
        imp = "railroad" if "railroad" in player.get("techs", []) else "road"
        terrain = self.tiles.get(pos)
        from civgame.data import IMPROVEMENTS
        if terrain and terrain.value in IMPROVEMENTS[imp]["terrain"]:
            existing = self.roads.get(pos)
            if not existing or existing.get("type") != imp:
                # Build here
                self.current_player = unit["player"]
                self.worker_build(unit["id"], imp)
                return
        # Otherwise move one step toward target
        if unit["moves_left"] > 0:
            nxt = self._find_path_next(unit, target[0], target[1])
            if nxt:
                self.current_player = unit["player"]
                self.move_unit(unit["id"], nxt[0], nxt[1])

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

    def skip_unit(self, unit_id):
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        unit["moves_left"] = 0
        return {"ok": True, "msg": "Unit skipped"}

    def _auto_explore_step(self, unit, pid):
        """BFS explore — find nearest REACHABLE unexplored tile and move toward it."""
        if unit["id"] not in self.units:
            return
        from collections import deque
        explored = self.explored.get(pid, set())
        is_naval = unit["cat"] == "naval"
        is_air = unit["cat"] == "air"
        player = self.players[pid]
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
                # Avoid foreign territory (would trigger war)
                tile_owner = self.get_tile_owner(nq, nr)
                if tile_owner is not None and tile_owner != pid:
                    rel = player.get("diplomacy", {}).get(tile_owner, "peace")
                    if rel not in ("war", "alliance"):
                        continue
                visited.add((nq, nr))
                queue.append(((nq, nr), path + [(nq, nr)]))

        if not target_path or len(target_path) < 2:
            unit["exploring"] = False
            self._log_ai(pid, f"EXPLORE: {unit['type']} finished exploring (no reachable unexplored tiles)")
            return

        # Move to next hex in path using A* (not raw BFS step)
        next_step = self._find_path_next(unit, target_path[-1][0], target_path[-1][1])
        if not next_step:
            next_step = target_path[1]
        result = self.move_unit(unit["id"], next_step[0], next_step[1])

        # If move failed, mark this direction as explored to avoid retrying
        if not result.get("ok") and unit["id"] in self.units:
            explored.add(target_path[1])
            return

        if result.get("combat") and unit["id"] in self.units:
            self.units[unit["id"]]["exploring"] = False

