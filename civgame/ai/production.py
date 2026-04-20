"""AI production decisions: what each city should build next."""
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain, GAME_CONFIG
from civgame.data import UNIT_TYPES, BUILDINGS, TECHNOLOGIES, CIVILIZATIONS

class AIProductionMixin:
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
        strategy = player.get("strategy", "balanced")
        max_cities = base_max + 3 if trait == "expansive" else base_max + 2 if strategy == "culturalist" else base_max
        game_phase = min(1.0, self.turn / 120)  # 0=early, 1=late
        # Fix 4: Late-game expansion boost for all strategies
        if game_phase > 0.4:
            max_cities += 2
        candidates = []  # (score, type, name, reason)

        # Fix 1: Emergency military — defenseless civ under threat. Force production.
        if len(my_military) == 0 and my_cities and (at_war or nearby_enemies > 0):
            best_mil_emergency = self._ai_best_military(player)
            candidates.append((250, "unit", best_mil_emergency,
                              f"EMERGENCY: no military while threatened (at_war={at_war}, enemies_near={nearby_enemies})"))

        # --- UNITS ---

        # Worker — 1 per city, max 4
        needed_workers = min(4, max(1, len(my_cities)))
        if len(my_workers) < needed_workers:
            urgency = 80 if len(my_workers) == 0 else 40
            candidates.append((urgency, "unit", "worker", f"need workers ({len(my_workers)}/{needed_workers})"))

        # Settler — requires city pop >= 2 (settler costs 1 pop)
        max_settlers = min(3, max(1, max_cities // 3))
        if city["population"] >= 2 and len(my_cities) + len(my_settlers) < max_cities and len(my_settlers) < max_settlers:
            # Use real settle spot search from city position
            settle_target = self._ai_find_settle_spot((city["q"], city["r"]), pid)
            if settle_target:
                score = 55 - len(my_cities) * 4
                if trait == "expansive":
                    score += 15
                if strategy == "expansionist":
                    score += 25
                elif strategy == "culturalist":
                    score += 10  # culturalists need more cities for culture victory
                elif strategy == "warmonger":
                    score -= 10
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
            mil_score -= int((mil_per_city - 3) * 15)
        if mil_per_city > 4:
            mil_score -= int((mil_per_city - 4) * 25)  # harsh above 4 per city
        # HARD CAP: never build military above 4 per city (unless at war and losing)
        if mil_per_city > 4 and not at_war:
            mil_score = -100
        if mil_per_city > 6:
            mil_score = -100  # absolute hard cap even during war
        # Economy check: don't build military when gold is negative or maintenance too high
        unit_count = sum(1 for u in self.units.values() if u["player"] == pid)
        free = GAME_CONFIG.get("unit_maintenance_free", 2)
        mcost = GAME_CONFIG.get("unit_maintenance_cost", 2)
        maintenance = max(0, unit_count - free) * mcost
        total_income = sum(self.get_city_yields(c["id"])["gold"] for c in my_cities)
        if maintenance > total_income:
            mil_score -= 40  # spending more on army than earning
        if player["gold"] < -30:
            mil_score -= 30
        if player["gold"] < 0:
            mil_score -= 15
        if mil_score > 0:
            candidates.append((mil_score, "unit", best_mil, f"military (ratio={mil_ratio:.1f}/{desired_ratio:.1f}, war={at_war})"))

        # Spy — max 1 per player
        if "writing" in player["techs"] and len(my_spies) < 1:
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
            elif bname == "barracks":
                score += 20  # always useful for any civ
                if at_war or strategy in ("conqueror", "warmonger"):
                    score += 15
                if len(my_military) > 3:
                    score += 10  # more valuable with larger army
            elif bname == "forge":
                score += 12
            elif bname == "workshop":
                score += 15
                if trait == "industrious":
                    score += 10
            elif bname == "stable":
                score += 10
                if strategy in ("conqueror", "warmonger"):
                    score += 8
            elif bname == "harbor":
                # Only valuable in coastal cities
                has_coast = any(self.tiles.get(pos) in (Terrain.WATER, Terrain.COAST)
                               for pos in [(city["q"]+dq, city["r"]+dr) for dq in range(-1,2) for dr in range(-1,2)])
                if has_coast:
                    score += 18
                else:
                    score -= 50  # can't build harbor without coast
            elif bname == "colosseum":
                score += 18
                if city["population"] >= 4:
                    score += 10  # more valuable in larger cities
            elif bname == "school":
                score += 18
            elif bname == "museum":
                score += 15
                if strategy == "culturalist":
                    score += 20
            elif bname == "theater":
                score += 15
                if strategy == "culturalist":
                    score += 15
            elif bname == "military_academy":
                score += 10
                if at_war or strategy in ("conqueror", "warmonger"):
                    score += 15
            elif bname == "airport":
                score += 12
            elif bname == "bunker":
                score += 10
                if at_war or nearby_enemies > 2:
                    score += 20
            elif bname == "hospital":
                score += 18
                if city["population"] >= 5:
                    score += 10  # more valuable in large cities
            elif bname == "stadium":
                score += 15
                # Counter factory/power_plant unhappiness
                if "factory" in city["buildings"] or "power_plant" in city["buildings"]:
                    score += 15

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

    def _auto_produce_mode(self, city, player, pid):
        """Auto-produce for human cities based on auto_produce setting."""
        mode = city.get("auto_produce")
        if not mode:
            return
        my_cities = [c for c in self.cities.values() if c["player"] == pid]
        my_military = [u for u in self.units.values() if u["player"] == pid and u["cat"] != "civilian"]
        my_settlers = [u for u in self.units.values() if u["player"] == pid and u["type"] == "settler"]
        saved = self.current_player
        self.current_player = pid
        if mode == "auto":
            self._ai_choose_production(city, player, my_cities, my_military, my_settlers, pid)
        elif mode == "units":
            best = self._ai_best_military(player)
            self.set_production(city["id"], "unit", best)
        elif mode == "buildings":
            # Pick highest-scoring building
            for bname, bdata in BUILDINGS.items():
                if bname in city["buildings"] or bname == "palace":
                    continue
                if bdata["tech"] and bdata["tech"] not in player["techs"]:
                    continue
                self.set_production(city["id"], "building", bname)
                break
        self.current_player = saved

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
        if player["gold"] < 30:
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

