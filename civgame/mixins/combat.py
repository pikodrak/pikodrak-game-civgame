"""Combat: melee, ranged, city capture."""
import random
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain, TERRAIN_DEFENSE, GAME_CONFIG
from civgame.data import UNIT_TYPES, BUILDINGS, CIVILIZATIONS

class CombatMixin:
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
            old_pid = city["player"]
            old_owner = self.players[old_pid]["name"]
            if hasattr(self, "_bump_memory"):
                self._bump_memory(old_pid, attacker["player"], "cities_taken_from_me")
            city["player"] = attacker["player"]
            city["hp"] = city["max_hp"] // 2
            if city["population"] > 1:
                city["population"] = max(1, city["population"] - 1)
            # Reset production for new owner
            city["producing"] = None
            city["prod_progress"] = 0
            attacker["q"] = city["q"]
            attacker["r"] = city["r"]
            result["msg"] = f"City {city['name']} captured!"
            result["captured"] = True
            self._log_ai(attacker["player"],
                f"CITY CAPTURED: {city['name']} from {old_owner} by {attacker['type']}(hp={attacker['hp']})")
            # Push old owner's units out of captured city borders
            old_pid = [p["id"] for p in self.players if p["name"] == old_owner]
            if old_pid:
                br = city.get("border_radius", 1)
                for u in list(self.units.values()):
                    if u["player"] != old_pid[0] or u["id"] == attacker["id"]:
                        continue
                    if hex_distance(city["q"], city["r"], u["q"], u["r"]) > br:
                        continue
                    # BFS outward to find nearest tile outside city borders
                    from collections import deque
                    queue = deque([(u["q"], u["r"])])
                    visited = {(u["q"], u["r"])}
                    exit_tile = None
                    while queue and not exit_tile:
                        cq, cr = queue.popleft()
                        for nq, nr in hex_neighbors(cq, cr):
                            if (nq, nr) in visited:
                                continue
                            visited.add((nq, nr))
                            t = self.tiles.get((nq, nr))
                            if not t or t in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                                continue
                            if hex_distance(city["q"], city["r"], nq, nr) > br:
                                exit_tile = (nq, nr)
                                break
                            queue.append((nq, nr))
                        if len(visited) > 100:
                            break
                    if exit_tile:
                        u["q"], u["r"] = exit_tile
                        self._log_ai(old_pid[0], f"PUSHED OUT: {u['type']} from {city['name']} to ({exit_tile[0]},{exit_tile[1]})")
                    else:
                        self._log_ai(old_pid[0], f"DISBANDED: {u['type']} trapped in captured {city['name']}")
                        del self.units[u["id"]]
                # Reassign home_city for old owner's remaining units
                for u in self.units.values():
                    if u.get("home_city") == city["id"] and u["player"] == old_pid[0]:
                        nearest = None
                        best_d = 999
                        for c in self.cities.values():
                            if c["player"] == old_pid[0] and c["id"] != city["id"]:
                                d = hex_distance(c["q"], c["r"], u["q"], u["r"])
                                if d < best_d:
                                    best_d = d
                                    nearest = c["id"]
                        u["home_city"] = nearest
            # AI: immediately set production in captured city
            new_owner = self.players[attacker["player"]]
            if not new_owner.get("is_human"):
                self._ai_auto_produce(city, new_owner, attacker["player"])
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

    def ranged_attack(self, unit_id, target_q, target_r):
        """Ranged attack: unit fires at target hex without moving. Only for ranged/siege units."""
        unit = self.units.get(unit_id)
        if not unit or unit["player"] != self.current_player:
            return {"ok": False, "msg": "Not your unit"}
        if unit["moves_left"] <= 0:
            return {"ok": False, "msg": "No moves left"}

        unit_range = UNIT_TYPES.get(unit["type"], {}).get("range", 0)
        if unit_range == 0:
            return {"ok": False, "msg": "This unit cannot make ranged attacks"}

        dist = hex_distance(unit["q"], unit["r"], target_q, target_r)
        if dist < 1 or dist > unit_range:
            return {"ok": False, "msg": f"Target out of range (range={unit_range}, distance={dist})"}

        terrain = self.tiles.get((target_q, target_r))
        if not terrain:
            return {"ok": False, "msg": "Off map"}

        # Find enemy unit on target hex
        enemy_units = [u for u in self.units.values()
                       if u["q"] == target_q and u["r"] == target_r and u["player"] != unit["player"]]
        # Find enemy city on target hex
        enemy_cities = [c for c in self.cities.values()
                        if c["q"] == target_q and c["r"] == target_r and c["player"] != unit["player"]]

        if not enemy_units and not enemy_cities:
            return {"ok": False, "msg": "No enemy target at that hex"}

        # Check war status
        if enemy_units:
            target_player = enemy_units[0]["player"]
        else:
            target_player = enemy_cities[0]["player"]

        rel = self.players[unit["player"]]["diplomacy"].get(target_player, "peace")
        if rel != "war":
            if self.players[unit["player"]].get("is_human"):
                return {"ok": False, "needs_war": True,
                        "war_target": target_player,
                        "war_target_name": self.players[target_player]["name"],
                        "msg": f"Attack {self.players[target_player]['name']}? This means WAR!"}
            self.declare_war(unit["player"], target_player)

        # Attack enemy unit (priority over city)
        if enemy_units:
            return self._ranged_combat(unit, enemy_units[0])

        # Attack enemy city
        if enemy_cities:
            return self._ranged_city_attack(unit, enemy_cities[0])

        return {"ok": False, "msg": "No valid target"}

    def _ranged_combat(self, attacker, defender):
        """Ranged combat: attacker deals damage but takes reduced return fire. Attacker stays in place."""
        terrain = self.tiles.get((defender["q"], defender["r"]), Terrain.GRASS)
        terrain_def = TERRAIN_DEFENSE.get(terrain, 0)

        atk_str = attacker["atk"] * (attacker["hp"] / 100)
        atk_player = self.players[attacker["player"]]
        if atk_player.get("trait") == "aggressive":
            atk_str *= 1.15
        def_str = defender["def"] * (defender["hp"] / 100) * (1 + terrain_def / 100)
        def_player = self.players[defender["player"]]
        if def_player.get("trait") == "protective":
            near_own_city = any(c["player"] == defender["player"]
                                and hex_distance(c["q"], c["r"], defender["q"], defender["r"]) <= 3
                                for c in self.cities.values())
            if near_own_city:
                def_str *= 1.15
        if defender["fortified"]:
            def_str *= 1.25

        atk_roll = atk_str * (0.8 + random.random() * 0.4)
        def_roll = def_str * (0.8 + random.random() * 0.4)
        total = atk_roll + def_roll
        if total == 0:
            total = 1

        # Ranged: full damage to defender, but only 25% return fire (distance protection)
        dmg_to_def = int(50 * atk_roll / total + 15)
        dmg_to_atk = int((40 * def_roll / total + 10) * 0.25)

        defender["hp"] -= dmg_to_def
        attacker["hp"] -= dmg_to_atk
        attacker["moves_left"] = 0

        result = {"ok": True, "combat": True, "ranged": True, "atk_dmg": dmg_to_atk, "def_dmg": dmg_to_def}
        atk_name = self.players[attacker["player"]]["name"]
        def_name = self.players[defender["player"]]["name"]

        if defender["hp"] <= 0:
            result["defender_killed"] = True
            result["msg"] = f"Ranged kill! Enemy {defender['type']} destroyed"
            self._log_ai(attacker["player"],
                f"RANGED KILL: {attacker['type']}(hp={attacker['hp']}) killed {def_name} {defender['type']} at range")
            # Ranged unit does NOT move to target hex
            attacker["xp"] += 5
            del self.units[defender["id"]]
        elif attacker["hp"] <= 0:
            result["attacker_killed"] = True
            result["msg"] = f"Your {attacker['type']} was destroyed by return fire"
            self._log_ai(defender["player"],
                f"RANGED COUNTER: {defender['type']}(hp={defender['hp']}) killed {atk_name} {attacker['type']} via return fire")
            del self.units[attacker["id"]]
        else:
            result["msg"] = f"Ranged attack: dealt {dmg_to_def} dmg, took {dmg_to_atk} return fire"
            self._log_ai(attacker["player"],
                f"RANGED: {attacker['type']}(hp={attacker['hp']}) vs {def_name} {defender['type']}(hp={defender['hp']}) | dealt {dmg_to_def} took {dmg_to_atk}")

        self._check_elimination()
        return result

    def _ranged_city_attack(self, attacker, city):
        """Ranged attack on city: deals damage without entering city hex. Cannot capture."""
        city_def = self.get_city_defense(city["id"])
        atk_str = attacker["atk"] * (attacker["hp"] / 100)
        def_str = city_def / 10

        atk_roll = atk_str * (0.8 + random.random() * 0.4)
        def_roll = def_str * (0.8 + random.random() * 0.4)

        dmg_to_city = int(25 * atk_roll / (atk_roll + def_roll + 1) + 5)
        # Ranged: only 25% return fire from city
        dmg_to_atk = int((15 * def_roll / (atk_roll + def_roll + 1) + 3) * 0.25)

        city["hp"] -= dmg_to_city
        attacker["hp"] -= dmg_to_atk
        attacker["moves_left"] = 0

        result = {"ok": True, "combat": True, "city_attack": True, "ranged": True}

        # Ranged cannot capture — city HP floors at 1
        if city["hp"] <= 0:
            city["hp"] = 1
            result["msg"] = f"Ranged bombardment: {city['name']} reduced to 1 HP! Send melee unit to capture."
            self._log_ai(attacker["player"],
                f"RANGED SIEGE: {attacker['type']} bombarded {city['name']} to 1 HP — needs melee capture")
        elif attacker["hp"] <= 0:
            self._log_ai(attacker["player"],
                f"RANGED SIEGE FAILED: {attacker['type']} destroyed bombarding {city['name']}")
            del self.units[attacker["id"]]
            result["msg"] = f"Bombardment failed! {attacker['type']} destroyed by return fire"
            result["attacker_killed"] = True
        else:
            result["msg"] = f"Bombardment: dealt {dmg_to_city} dmg to {city['name']}, took {dmg_to_atk} return fire (City HP: {city['hp']}/{city['max_hp']})"

        return result

