"""AI worker: tile improvement and road/railroad building."""
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain, TERRAIN_MOVE_COST
from civgame.data import IMPROVEMENTS

class AIWorkerMixin:
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

            # Priority 1: Terrain improvement (farm/mine/lumber_mill) near city
            if near_city and not existing_imp:
                imp_type = self._ai_pick_improvement(terrain.value, player)
                if imp_type:
                    idata = IMPROVEMENTS.get(imp_type, {})
                    bonus = f"+{idata.get('food',0)}f +{idata.get('prod',0)}p +{idata.get('gold',0)}g"
                    self.current_player = pid
                    self.worker_build(unit["id"], imp_type)
                    self._log_ai(pid, f"WORKER: {imp_type} at ({unit['q']},{unit['r']}) [{bonus}] terrain={terrain.value}")
                    return

            # Priority 2: Road — only if on path between cities OR near city with all improvements done
            needs_local_road = near_city and existing_imp and not existing_road
            if not existing_road:
                # Check if we're on a path between two cities (connecting road)
                on_connect_path = False
                if len(my_cities) >= 2:
                    for c in my_cities:
                        d = hex_distance(unit["q"], unit["r"], c["q"], c["r"])
                        if 1 < d < 10:  # between cities, not AT city
                            on_connect_path = True
                            break
                if on_connect_path or needs_local_road:
                    self.current_player = pid
                    self.worker_build(unit["id"], "road")
                    self._log_ai(pid, f"WORKER: road at ({unit['q']},{unit['r']})" + (" [connecting]" if on_connect_path else ""))
                    return

            # Priority 3: Upgrade to railroad
            if has_railroad and existing_road and existing_road["type"] == "road":
                self.current_player = pid
                self.worker_build(unit["id"], "railroad")
                self._log_ai(pid, f"WORKER: railroad at ({unit['q']},{unit['r']})")
                return

        # --- WHERE TO MOVE? ---
        task = self._ai_worker_find_task(unit, pid, my_cities, has_railroad)
        if task:
            self._ai_step_toward(unit, task[0], task[1])

    def _ai_worker_find_task(self, unit, pid, my_cities, has_railroad):
        """Find best tile for worker. Priority: 2 improvements per city > roads to capital > more improvements."""
        player = self.players[pid]
        candidates = []  # (priority, q, r, reason)

        # Count improvements per city
        city_imp_count = {}
        for city in my_cities:
            br = city.get("border_radius", 1) + 1
            count = 0
            for dq in range(-br, br + 1):
                for dr in range(-br, br + 1):
                    tq, tr = city["q"] + dq, city["r"] + dr
                    if hex_distance(city["q"], city["r"], tq, tr) <= br and (tq, tr) in self.improvements:
                        count += 1
            city_imp_count[city["id"]] = count

        # Check if cities need food (any city with food_surplus <= 1)
        cities_need_food = False
        for city in my_cities:
            try:
                y = self.get_city_yields(city["id"])
                if y["food_surplus"] <= 1:
                    cities_need_food = True
                    break
            except:
                pass

        # Task 1: Improvements near cities — always highest priority when food is needed
        need_threshold = 999 if cities_need_food else 2  # if food needed: build ALL improvements; if not: only first 2
        for city in my_cities:
            if city_imp_count[city["id"]] >= need_threshold:
                continue
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
                    if d > 15 or (tq, tr) in self.improvements:
                        continue
                    if self._ai_pick_improvement(t.value, player):
                        candidates.append((d, tq, tr, "improve"))

        # Task 2: Roads to CAPITAL — connect unconnected cities (HIGH priority)
        if len(my_cities) >= 2:
            import heapq
            capital = None
            for c in my_cities:
                if "palace" in c["buildings"]:
                    capital = c
                    break
            if not capital:
                capital = my_cities[0]

            # Find up to 3 nearest unconnected cities
            unconnected = []
            for city in my_cities:
                if city["id"] == capital["id"]:
                    continue
                if not self.is_connected_to_capital(city["id"]):
                    unconnected.append(city)
            unconnected.sort(key=lambda c: hex_distance(capital["q"], capital["r"], c["q"], c["r"]))

            for city in unconnected[:3]:
                # A* path from capital to city, preferring existing roads
                start = (capital["q"], capital["r"])
                goal = (city["q"], city["r"])
                heap = [(0, 0, start, [start])]
                visited = {}
                path_found = None
                step = 0
                while heap:
                    cost, _, (cq, cr), path = heapq.heappop(heap)
                    if (cq, cr) == goal:
                        path_found = path
                        break
                    if (cq, cr) in visited:
                        continue
                    visited[(cq, cr)] = cost
                    if len(visited) > 300:
                        break
                    for nq, nr in hex_neighbors(cq, cr):
                        if (nq, nr) in visited:
                            continue
                        t = self.tiles.get((nq, nr))
                        if not t or t in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                            continue
                        mc = TERRAIN_MOVE_COST.get(t, 1)
                        if (nq, nr) in self.roads:
                            mc = 0.1  # heavily prefer existing roads
                        h = hex_distance(nq, nr, goal[0], goal[1])
                        step += 1
                        heapq.heappush(heap, (cost + mc + h, step, (nq, nr), path + [(nq, nr)]))

                if path_found:
                    # Find nearest unroaded tile on this path
                    for pq, pr in path_found:
                        if (pq, pr) not in self.roads:
                            d = hex_distance(unit["q"], unit["r"], pq, pr)
                            # Priority BOOST: roads to capital are very important (d - 5)
                            candidates.append((max(0, d - 5), pq, pr, "road->%s" % city["name"][:8]))
                            break

        # Task 3: Remaining improvements (lower priority — after roads)
        for city in my_cities:
            if city_imp_count[city["id"]] < 2:
                continue  # already handled above
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
                    if d > 20 or (tq, tr) in self.improvements:
                        continue
                    if self._ai_pick_improvement(t.value, player):
                        candidates.append((d + 2, tq, tr, "improve"))
                    if has_railroad and (tq, tr) in self.roads and self.roads[(tq, tr)]["type"] == "road":
                        candidates.append((d + 20, tq, tr, "railroad"))

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

