"""AI military unit decisions: attack, defend, explore."""
import random
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain, GAME_CONFIG
from civgame.data import UNIT_TYPES, CIVILIZATIONS

class AIMilitaryMixin:
    def _ai_military_move(self, unit, pid):
        """Personality-driven military AI."""
        if unit["moves_left"] <= 0:
            return
        player = self.players[pid]
        aggression = player.get("aggression", 0.5)
        trait = player.get("trait", "")
        my_military = [u for u in self.units.values() if u["player"] == pid and u["cat"] != "civilian"]
        my_cities = [c for c in self.cities.values() if c["player"] == pid]

        unit_range = UNIT_TYPES.get(unit["type"], {}).get("range", 0)

        # Ranged units: try to fire at enemies within range before moving
        if unit_range > 0:
            best_target = None
            best_dist = unit_range + 1
            # Check enemy units in range
            for eu in list(self.units.values()):
                if eu["player"] != pid and eu["cat"] != "civilian":
                    d = hex_distance(unit["q"], unit["r"], eu["q"], eu["r"])
                    if 1 <= d <= unit_range:
                        rel = self.players[pid]["diplomacy"].get(eu["player"], "peace")
                        if rel == "war" and d < best_dist:
                            best_target = ("unit", eu)
                            best_dist = d
            # Check enemy cities in range
            for ec in list(self.cities.values()):
                if ec["player"] != pid:
                    d = hex_distance(unit["q"], unit["r"], ec["q"], ec["r"])
                    if 1 <= d <= unit_range:
                        rel = self.players[pid]["diplomacy"].get(ec["player"], "peace")
                        if rel == "war" and d < best_dist:
                            best_target = ("city", ec)
                            best_dist = d
            if best_target:
                ttype, target = best_target
                self._log_ai(pid, f"RANGED: {unit['type']}(hp={unit['hp']}) fires at {target.get('type') or target.get('name')} at range {best_dist}")
                self.current_player = pid
                self.ranged_attack(unit["id"], target["q"], target["r"])
                return

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

        # Adjacent enemy city — attack if at war (melee only for capture, ranged already handled above)
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

        # WAR MOBILIZATION — during war, march toward enemy border
        war_enemies = [p for p in self.players if p["alive"] and p["id"] != pid
                       and player["diplomacy"].get(p["id"]) == "war"]
        if war_enemies:
            # Find nearest enemy city and march there
            enemy_cities = [c for c in self.cities.values()
                            if any(c["player"] == e["id"] for e in war_enemies)]
            if enemy_cities:
                target = min(enemy_cities, key=lambda c: hex_distance(unit["q"], unit["r"], c["q"], c["r"]))
                self._ai_step_toward(unit, target["q"], target["r"])
                return

        # Peacetime: patrol near own cities
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

