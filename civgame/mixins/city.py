"""City founding, yields, defense, and production targeting."""
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain, TERRAIN_YIELDS, TERRAIN_DEFENSE, CITY_NAMES, GAME_CONFIG
from civgame.data import (BUILDINGS, UNIT_TYPES, IMPROVEMENTS, TECHNOLOGIES, CIVILIZATIONS,
                          RESOURCES, LUXURY_HAPPINESS_PER_TYPE)

class CityMixin:
    def get_player_resources(self, pid):
        """Return {resource_name: count} for resources accessible to player pid.

        A resource is accessible if it sits on a tile the player owns (city hex
        or within a city's border_radius). Trades add resources via deal effects
        — we include those here too via self._bonus_resources.
        """
        counts = {}
        my_cities = [c for c in self.cities.values() if c["player"] == pid]
        seen = set()
        for c in my_cities:
            brd = c.get("border_radius", 1)
            for dq in range(-brd, brd + 1):
                for dr in range(-brd, brd + 1):
                    tq, tr = c["q"] + dq, c["r"] + dr
                    if hex_distance(c["q"], c["r"], tq, tr) > brd:
                        continue
                    if (tq, tr) in seen:
                        continue
                    seen.add((tq, tr))
                    res = self.resources.get((tq, tr))
                    if res is None:
                        continue
                    rdata = RESOURCES.get(res, {})
                    # Need required tech to access? (e.g. gems need mining)
                    tech_req = rdata.get("tech")
                    if tech_req and tech_req not in self.players[pid]["techs"]:
                        continue
                    counts[res] = counts.get(res, 0) + 1
        # Extra resources granted by active trade agreements
        for ag in getattr(self, "agreements", []):
            if ag["type"] == "resource_trade" and pid in ag["params"].get("receivers", []):
                res = ag["params"].get("resource")
                if res:
                    counts[res] = counts.get(res, 0) + 1
        return counts

    def _count_unique_luxuries(self, pid):
        """Number of distinct luxury resources the player can benefit from."""
        counts = self.get_player_resources(pid)
        return sum(1 for r in counts if RESOURCES.get(r, {}).get("type") == "luxury")

    def player_can_build_unit(self, pid, unit_type):
        """Check strategic-resource gating. Returns (ok, missing_resource_or_None)."""
        from civgame.data import strategic_units_requirement
        req = strategic_units_requirement(unit_type)
        if req is None:
            return True, None
        counts = self.get_player_resources(pid)
        if counts.get(req, 0) > 0:
            return True, None
        return False, req

    def is_connected_to_capital(self, city_id):
        """Check if city is connected to player's capital via roads/railroads.
        Uses cached result per turn to avoid repeated BFS."""
        # Cache key: (turn, city_id)
        cache = getattr(self, '_road_cache', None)
        cache_turn = getattr(self, '_road_cache_turn', -1)
        if cache_turn != self.turn:
            self._road_cache = {}
            self._road_cache_turn = self.turn
        if city_id in self._road_cache:
            return self._road_cache[city_id]

        city = self.cities.get(city_id)
        if not city:
            return False
        pid = city["player"]
        capital = None
        for c in self.cities.values():
            if c["player"] == pid and "palace" in c["buildings"]:
                capital = c
                break
        if not capital:
            for c in self.cities.values():
                if c["player"] == pid:
                    capital = c
                    break
        if not capital or capital["id"] == city_id:
            self._road_cache[city_id] = True
            return True

        start = (city["q"], city["r"])
        goal = (capital["q"], capital["r"])
        visited = {start}
        queue = [start]
        while queue:
            pos = queue.pop(0)
            if pos == goal:
                self._road_cache[city_id] = True
                return True
            for nq, nr in hex_neighbors(pos[0], pos[1]):
                npos = (nq, nr)
                if npos in visited:
                    continue
                if npos not in self.roads:
                    if npos == goal:
                        self._road_cache[city_id] = True
                        return True
                    continue
                visited.add(npos)
                queue.append(npos)
        self._road_cache[city_id] = False
        return False

    def get_city_yields(self, city_id, detail=False):
        city = self.cities[city_id]
        player = self.players[city["player"]]
        civ_bonus = CIVILIZATIONS[player["civ"]]["bonus"]

        food = 2  # base (city center)
        prod = 1  # base
        gold = 0
        science = 0
        culture = 1  # base

        # Tile yields (work radius = border_radius) + improvements
        brd = city.get("border_radius", 1)
        max_work = city["population"] + 1  # +1 for city center
        # Shared tile check: find same-player cities that could claim tiles
        same_player_cities = [c for c in self.cities.values()
                              if c["player"] == city["player"] and c["id"] != city_id]
        tiles_detail = []  # for city management UI
        for dq in range(-brd, brd + 1):
            for dr in range(-brd, brd + 1):
                tq, tr = city["q"] + dq, city["r"] + dr
                if hex_distance(city["q"], city["r"], tq, tr) <= brd:
                    # Shared tile: if another own city is closer, skip this tile
                    my_dist = hex_distance(city["q"], city["r"], tq, tr)
                    claimed_by_other = False
                    for oc in same_player_cities:
                        oc_brd = oc.get("border_radius", 1)
                        oc_dist = hex_distance(oc["q"], oc["r"], tq, tr)
                        if oc_dist <= oc_brd and oc_dist < my_dist:
                            claimed_by_other = True
                            break
                    if claimed_by_other:
                        continue
                    tile_owner = self.get_tile_owner(tq, tr)
                    if tile_owner is not None and tile_owner != city["player"]:
                        continue  # foreign culture controls this tile
                    t = self.tiles.get((tq, tr))
                    if t:
                        y = TERRAIN_YIELDS[t]
                        tf, tp, tg = y["food"], y["prod"], y["gold"]
                        imp_name = None
                        imp = self.improvements.get((tq, tr))
                        if imp:
                            idata = IMPROVEMENTS.get(imp["type"], {})
                            tf += idata.get("food", 0)
                            tp += idata.get("prod", 0)
                            tg += idata.get("gold", 0)
                            imp_name = imp["type"]
                        # Resource bonus: bonus resources always boost yield.
                        # Strategic/luxury add small gold when worked.
                        res_name = self.resources.get((tq, tr))
                        if res_name:
                            rdata = RESOURCES.get(res_name, {})
                            if rdata.get("type") == "bonus":
                                ry = rdata.get("yield", {})
                                tf += ry.get("food", 0)
                                tp += ry.get("prod", 0)
                                tg += ry.get("gold", 0)
                            else:
                                tg += 1  # strategic/luxury small gold when worked
                        road = self.roads.get((tq, tr))
                        road_name = road["type"] if road else None
                        if road and road["type"] == "railroad":
                            tp += 1
                        tiles_detail.append({
                            "q": tq, "r": tr,
                            "terrain": t.value,
                            "food": tf, "prod": tp, "gold": tg,
                            "total": tf + tp + tg,
                            "improvement": imp_name,
                            "road": road_name,
                            "resource": res_name,
                        })

        # Sort by total value, best tiles first
        tiles_detail.sort(key=lambda x: -x["total"])
        # Mark which tiles are worked vs available
        for i, td in enumerate(tiles_detail):
            td["worked"] = i < max_work

        for td in tiles_detail[:max_work]:
            food += td["food"]
            prod += td["prod"]
            gold += td["gold"]

        # Leader trait bonuses
        trait = player.get("trait", "")
        if trait == "creative":
            culture += 4
        elif trait == "expansive":
            food += 1
        elif trait == "financial":
            gold += max(2, gold // 3)
        elif trait == "industrious":
            prod += max(1, prod // 5)
        elif trait == "aggressive":
            prod += 1
        elif trait == "protective":
            science += max(1, science // 5)

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

        # Trade route bonus
        connected = self.is_connected_to_capital(city_id)
        if connected:
            trade_bonus = max(1, city["population"] // 2)
            gold += trade_bonus

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

        # Happiness
        happiness = 0
        for bname in city["buildings"]:
            happiness += BUILDINGS.get(bname, {}).get("happiness", 0)
        happiness -= max(0, city["population"] - 4)
        # Luxury resources: each unique accessible luxury gives +happy per type.
        # Cached per (player, turn) to avoid recomputation across all cities.
        cache_key = (city["player"], self.turn)
        lux_cache = getattr(self, "_lux_cache", None)
        if lux_cache is None or lux_cache[0] != cache_key:
            unique_lux = self._count_unique_luxuries(city["player"])
            self._lux_cache = (cache_key, unique_lux)
        else:
            unique_lux = lux_cache[1]
        happiness += unique_lux * LUXURY_HAPPINESS_PER_TYPE

        if happiness < 0:
            prod = max(1, int(prod * 0.75))
            science = max(0, int(science * 0.75))

        # Food consumed by population (2 per pop)
        pop_food_cost = city["population"] * 2

        # Food consumed by units — scales: first 2 free, then 1 each, above 4 costs 2 each
        home_mil = sum(1 for u in self.units.values()
                       if u.get("home_city") == city_id and u["cat"] != "civilian")
        unit_food_cost = 0
        for i in range(home_mil):
            if i < 2:
                unit_food_cost += 0  # first 2 units free
            elif i < 4:
                unit_food_cost += 1  # units 3-4 cost 1 food each
            else:
                unit_food_cost += 2  # units 5+ cost 2 food each

        total_food_cost = pop_food_cost + unit_food_cost
        food_surplus = food - total_food_cost
        if happiness < 0:
            food_surplus = min(food_surplus, 1)

        # Growth info
        growth_needed = 10 + city["population"] * 5
        turns_to_grow = max(0, (growth_needed - city["food_store"]) // max(1, food_surplus)) if food_surplus > 0 else -1
        turns_to_starve = abs(city["food_store"] // min(-1, food_surplus)) if food_surplus < 0 else -1

        result = {
            "food": food, "food_surplus": food_surplus,
            "food_cost_pop": pop_food_cost, "food_cost_units": unit_food_cost,
            "prod": prod, "gold": gold,
            "science": science, "culture": culture,
            "happiness": happiness,
            "connected": connected,
            "growth_needed": growth_needed,
            "food_stored": city["food_store"],
            "turns_to_grow": turns_to_grow,
            "turns_to_starve": turns_to_starve,
        }
        if detail:
            result["tiles"] = tiles_detail
            result["max_work"] = max_work
            result["unit_count"] = unit_food_cost
        return result

    def get_city_defense(self, city_id):
        city = self.cities[city_id]
        defense = 10  # base
        for bname in city["buildings"]:
            defense += BUILDINGS[bname]["defense"]
        return defense

    # --------------------------------------------------------
    # TERRITORY
    # --------------------------------------------------------

    def found_city(self, unit_id, name):
        """Found a city with a settler."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        if unit["type"] != "settler":
            return {"ok": False, "msg": "Only settlers can found cities"}

        # Check no city nearby
        for c in self.cities.values():
            if hex_distance(c["q"], c["r"], unit["q"], unit["r"]) < 4:
                return {"ok": False, "msg": "Too close to another city"}

        # Cannot found city in foreign territory or too close to foreign cities
        territory_owner = self.get_tile_owner(unit["q"], unit["r"])
        if territory_owner is not None and territory_owner != unit["player"]:
            return {"ok": False, "msg": "Cannot found city in foreign territory"}
        # Check proximity to foreign cities — can't settle within their potential border growth
        for c in self.cities.values():
            if c["player"] != unit["player"]:
                d = hex_distance(c["q"], c["r"], unit["q"], unit["r"])
                max_border = max(c.get("border_radius", 1) + 1, 3)  # at least 3
                if d <= max_border:
                    return {"ok": False, "msg": f"Too close to {c['name']} (foreign city)"}
        # Check if near foreign territory — provocation
        for nq, nr in hex_neighbors(unit["q"], unit["r"]):
            nowner = self.get_tile_owner(nq, nr)
            if nowner is not None and nowner != unit["player"]:
                self.players[nowner]["relations"].setdefault(unit["player"], 0)
                self.players[nowner]["relations"][unit["player"]] -= 30
                self._log_ai(nowner, f"PROVOKED: {self.players[unit['player']]['name']} founded city near our border!")
                break

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

