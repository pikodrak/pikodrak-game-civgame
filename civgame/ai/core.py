"""AI main loop and per-player turn orchestration."""
import random
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain, GAME_CONFIG
from civgame.data import UNIT_TYPES, TECHNOLOGIES, CIVILIZATIONS

class AICoreMixin:
    def _ai_redistribute_home_cities(self, pid):
        """Rebalance home_city assignments so food cost is spread across cities."""
        my_cities = [c for c in self.cities.values() if c["player"] == pid]
        if len(my_cities) < 2:
            return
        mil_units = [u for u in self.units.values()
                     if u["player"] == pid and u["cat"] != "civilian"]
        if not mil_units:
            return

        # Compute base food capacity per city (food production - pop*2, ignoring units)
        # Temporarily clear home_city to get yields without unit food cost
        old_homes = {u["id"]: u.get("home_city") for u in mil_units}
        for u in mil_units:
            u["home_city"] = None

        city_capacity = {}
        for c in my_cities:
            y = self.get_city_yields(c["id"])
            # food - pop*2 = capacity available for units + growth
            # Reserve 2 food for growth, rest for units
            city_capacity[c["id"]] = max(0, y["food"] - c["population"] * 2 - 2)

        # Assign units to cities with most capacity, closest first
        city_assigned = {c["id"]: 0 for c in my_cities}
        # Sort units: assign those nearest to high-capacity cities first
        for u in mil_units:
            best_city = None
            best_score = -999
            for c in my_cities:
                remaining = city_capacity[c["id"]] - city_assigned[c["id"]]
                d = hex_distance(u["q"], u["r"], c["q"], c["r"])
                # Score: prefer capacity, then proximity
                score = remaining * 10 - d
                if score > best_score:
                    best_score = score
                    best_city = c["id"]
            if best_city:
                u["home_city"] = best_city
                city_assigned[best_city] += 1
            else:
                # Fallback to nearest city
                u["home_city"] = min(my_cities, key=lambda c: hex_distance(u["q"], u["r"], c["q"], c["r"]))["id"]

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

        # Redistribute home_city: balance food load across cities
        self._ai_redistribute_home_cities(pid)
        # Refresh after redistribution
        my_units = [u for u in self.units.values() if u["player"] == pid]
        my_military = [u for u in my_units if u["cat"] not in ("civilian",)]

        # Diplomacy — power-based + personality (respect cooldowns)
        for other in self.players:
            if other["id"] == pid or not other["alive"]:
                continue
            rel = player["diplomacy"].get(other["id"], "peace")
            opinion = player.get("relations", {}).get(other["id"], 0)
            cd = player.get("diplo_cooldown", {}).get(other["id"], 0)
            if cd > 0:
                continue

            # Power score: military * tech * cities
            other_mil = len([u for u in self.units.values() if u["player"] == other["id"] and u["cat"] != "civilian"])
            other_cities = len([c for c in self.cities.values() if c["player"] == other["id"]])
            other_techs = len(other.get("techs", []))
            my_power = len(my_military) * (1 + len(player.get("techs", [])) / 10) * (1 + len(my_cities) / 5)
            other_power = other_mil * (1 + other_techs / 10) * (1 + other_cities / 5)
            power_ratio = my_power / max(1, other_power)

            if rel == "war":
                # Peace if clearly losing
                if power_ratio < 0.5:
                    self.make_peace(pid, other["id"])
                    self._log_ai(pid, f"DIPLO: peace with {other['name']} (power {my_power:.0f} vs {other_power:.0f})")
                elif len(my_military) < 2:
                    self.make_peace(pid, other["id"])
                    self._log_ai(pid, f"DIPLO: peace with {other['name']} (no army)")
            elif rel in ("neutral", "peace"):
                # War only if STRONGER + angry
                war_threshold = -30 if player.get("strategy") == "conqueror" else -50
                if power_ratio > 1.3 and opinion <= war_threshold and random.random() < aggression * 0.2:
                    self.declare_war(pid, other["id"])
                    self._log_ai(pid, f"DIPLO: WAR on {other['name']} (power {power_ratio:.1f}x, opinion={opinion})")
                elif rel == "peace" and power_ratio > 2.0 and opinion < -20:
                    if random.random() < aggression * (1 - loyalty) * 0.02:
                        self.declare_war(pid, other["id"])
                        self._log_ai(pid, f"DIPLO: BETRAYAL of {other['name']}! (power {power_ratio:.1f}x)")

            # Relations drift
            if opinion > 0:
                player.setdefault("relations", {})[other["id"]] = opinion - 1
            elif opinion < 0:
                player.setdefault("relations", {})[other["id"]] = opinion + 1

        # Gang up on the leader — if someone is way ahead, declare war
        alive_players = [p for p in self.players if p["alive"] and p["id"] != pid]
        if alive_players:
            leader = max(alive_players, key=lambda p: p["score"])
            gang_ratio = GAME_CONFIG.get("gang_up_score_ratio", 1.5)
            gang_min = GAME_CONFIG.get("gang_up_min_score", 1000)
            gang_chance = GAME_CONFIG.get("gang_up_chance", 0.10)
            if leader["score"] > player["score"] * gang_ratio and leader["score"] > gang_min:
                rel = player["diplomacy"].get(leader["id"], "neutral")
                if rel != "war" and random.random() < gang_chance:
                    self.declare_war(pid, leader["id"])
                    self._log_ai(pid, f"DIPLO: gang-up WAR on leader {leader['name']} (score {leader['score']} vs my {player['score']})")

        # Alliance AI — loyal/peaceful civs seek alliances against common enemies
        current_alliances = sum(1 for p in self.players if p["alive"] and player["diplomacy"].get(p["id"]) == "alliance")
        max_alliances = 2  # max 2 alliances per player to prevent web of obligations
        for other in self.players:
            if other["id"] == pid or not other["alive"]:
                continue
            rel = player["diplomacy"].get(other["id"], "peace")
            # Form alliance: both at peace AND share a common enemy AND not too many alliances
            if rel == "peace" and loyalty > 0.5 and current_alliances < max_alliances:
                common_enemy = any(
                    player["diplomacy"].get(e["id"]) == "war" and other["diplomacy"].get(e["id"]) == "war"
                    for e in self.players if e["id"] != pid and e["id"] != other["id"] and e["alive"]
                )
                if common_enemy and random.random() < loyalty * 0.1:
                    self.form_alliance(pid, other["id"])
                    current_alliances += 1
                    self._log_ai(pid, f"DIPLO: ALLIANCE with {other['name']} (common enemy, loyalty={loyalty})")
            # Break alliance if disloyal and strong enough
            elif rel == "alliance" and random.random() < (1 - loyalty) * aggression * 0.03:
                self.break_alliance(pid, other["id"])
                self._log_ai(pid, f"DIPLO: broke alliance with {other['name']} (disloyal)")

        # Diplomacy: propose deals to other civs
        self._ai_propose_deals(pid)

        # Upgrade obsolete units
        self._ai_upgrade_units(pid)

        # Research: strategy-weighted tech selection
        if not player["researching"]:
            strategy = player.get("strategy", "balanced")
            available = []
            # Priority techs by strategy
            priority_techs = {
                "conqueror": ["bronze_working", "iron_working", "horseback", "feudalism", "gunpowder", "military_science", "dynamite", "industrialization", "flight"],
                "warmonger": ["archery", "bronze_working", "iron_working", "horseback", "gunpowder", "military_science", "dynamite", "flight"],
                "turtle": ["construction", "engineering", "education", "astronomy", "printing_press", "electricity", "nuclear_fission", "rocketry", "space_program"],
                "builder": ["mining", "construction", "engineering", "education", "industrialization", "steam_power", "railroad", "rocketry", "space_program"],
                "culturalist": ["pottery", "writing", "theology", "education", "printing_press", "aesthetics", "astronomy"],
                "economist": ["pottery", "writing", "currency", "printing_press", "navigation", "sailing"],
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

