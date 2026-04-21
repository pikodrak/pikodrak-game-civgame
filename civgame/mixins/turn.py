"""Turn processing: end_turn, score, elimination."""
import random
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain, TERRAIN_YIELDS, TERRAIN_MOVE_COST, TERRAIN_DEFENSE, GAME_CONFIG
from civgame.data import TECHNOLOGIES, UNIT_TYPES, BUILDINGS, IMPROVEMENTS, CIVILIZATIONS

class TurnMixin:
    def end_turn(self):
        """Process end of turn for current player."""
        pid = self.current_player
        player = self.players[pid]

        if not player["alive"]:
            self._advance_turn()
            return {"ok": True, "msg": "Skipped (eliminated)"}

        # Tick diplomacy cooldowns
        for k in list(player.get("diplo_cooldown", {}).keys()):
            if player["diplo_cooldown"][k] > 0:
                player["diplo_cooldown"][k] -= 1

        # Wake sentry units if enemies nearby
        woken = []
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("sentry"):
                for eu in self.units.values():
                    if eu["player"] != pid and hex_distance(u["q"], u["r"], eu["q"], eu["r"]) <= 2:
                        u["sentry"] = False
                        woken.append(u["type"])
                        break

        # Auto-explore units — but cancel if at war (units should defend instead)
        at_war = any(player["diplomacy"].get(p["id"]) == "war" for p in self.players if p["id"] != pid and p["alive"])
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("exploring") and u.get("moves_left", 0) > 0:
                # Cancel explore for military units during war — they should fight
                if at_war and u["cat"] != "civilian":
                    u["exploring"] = False
                    continue
                while u["id"] in self.units and u.get("exploring") and u.get("moves_left", 0) > 0:
                    old_q, old_r = u["q"], u["r"]
                    self._auto_explore_step(u, pid)
                    if u["id"] not in self.units or (u["q"] == old_q and u["r"] == old_r):
                        break

        # Auto-move units with goto targets
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("goto") and u.get("moves_left", 0) > 0:
                tgt = u["goto"]
                # Check for non-peace enemy adjacent — cancel goto
                enemy_near = False
                for nq, nr in hex_neighbors(u["q"], u["r"]):
                    for eu in self.units.values():
                        if eu["player"] != pid and eu["q"] == nq and eu["r"] == nr:
                            rel = player["diplomacy"].get(eu["player"], "peace")
                            if rel != "peace":
                                enemy_near = True
                                break
                    if enemy_near:
                        break
                if enemy_near:
                    u["goto"] = None
                    continue
                # Cancel goto if target is in foreign territory (not alliance)
                tgt_owner = self.get_tile_owner(tgt["q"], tgt["r"])
                if tgt_owner is not None and tgt_owner != pid:
                    rel = player["diplomacy"].get(tgt_owner, "peace")
                    if rel != "alliance":
                        u["goto"] = None
                        continue
                # Move toward target using all movement
                while u["id"] in self.units and u.get("goto") and u.get("moves_left", 0) > 0:
                    if u["q"] == tgt["q"] and u["r"] == tgt["r"]:
                        u["goto"] = None
                        break
                    # BFS pathfinding toward target
                    best = self._find_path_next(u, tgt["q"], tgt["r"])
                    if not best:
                        u["goto"] = None
                        break
                    old_q, old_r = u["q"], u["r"]
                    self.move_unit(u["id"], best[0], best[1])
                    if u["id"] not in self.units or (u["q"] == old_q and u["r"] == old_r):
                        u["goto"] = None
                        break

        total_gold = 0
        total_science = 0
        total_culture = 0
        events = []
        for w in woken:
            events.append(f"Sentry {w} spotted enemy!")

        # Process cities
        for city in list(self.cities.values()):
            if city["player"] != pid:
                continue

            yields = self.get_city_yields(city["id"])
            total_gold += yields["gold"]
            total_science += yields["science"]
            total_culture += yields["culture"]

            # Food & growth
            # While producing settler, food surplus halted (food goes to settler)
            producing_settler = city.get("producing") and city["producing"].get("name") == "settler"
            if not producing_settler:
                city["food_store"] += yields["food_surplus"]
                growth_needed = 10 + city["population"] * 5
                if city["food_store"] >= growth_needed:
                    city["population"] += 1
                    city["food_store"] = 0
                    events.append(f"{city['name']} grew to pop {city['population']}")
                elif city["food_store"] < 0:
                    if city["population"] > 1:
                        city["population"] -= 1
                        city["food_store"] = 0
                        events.append(f"{city['name']} lost population (starvation)")

            # Production
            if city["producing"]:
                city["prod_progress"] += yields["prod"]
                if city["prod_progress"] >= city["producing"]["cost"]:
                    item = city["producing"]
                    if item["type"] == "unit":
                        # Settler costs 1 population
                        if item["name"] == "settler":
                            if city["population"] < 2:
                                # Can't produce settler from size 1 city — cancel
                                city["producing"] = None
                                city["prod_progress"] = 0
                                events.append(f"{city['name']}: settler cancelled (need pop 2+)")
                                if not player["is_human"]:
                                    self._ai_auto_produce(city, player, pid)
                                continue
                            city["population"] -= 1
                            city["food_store"] = 0
                            events.append(f"{city['name']} lost 1 pop for settler (now {city['population']})")
                        uid = self._create_unit(pid, item["name"], city["q"], city["r"])
                        # Barracks/military academy bonus for military units
                        u = self.units.get(uid)
                        if u and u["cat"] not in ("civilian",):
                            if "barracks" in city["buildings"]:
                                u["xp"] += 10
                            if "military_academy" in city["buildings"]:
                                u["xp"] += 15
                        events.append(f"{city['name']} produced {item['name']}")
                    elif item["type"] == "building":
                        city["buildings"].append(item["name"])
                        events.append(f"{city['name']} built {item['name']}")
                    city["producing"] = None
                    city["prod_progress"] = 0
                    # Next from queue, auto-mode, or AI
                    queue = city.get("prod_queue", [])
                    if queue:
                        next_item = queue.pop(0)
                        self.set_production(city["id"], next_item["type"], next_item["name"])
                    elif city.get("auto_produce") and player["is_human"]:
                        self._auto_produce_mode(city, player, pid)
                    elif not player["is_human"]:
                        self._ai_auto_produce(city, player, pid)

            # City culture & border expansion
            city["culture"] = city.get("culture", 0) + yields["culture"]
            old_br = city.get("border_radius", 1)
            # Thresholds: 0->1, 10->2, 50->3, 150->4, 400->5
            thresholds = [(400, 5), (150, 4), (50, 3), (10, 2)]
            new_br = 1
            for threshold, radius in thresholds:
                if city["culture"] >= threshold:
                    new_br = radius
                    break
            city["border_radius"] = new_br
            if new_br > old_br:
                events.append(f"{city['name']} borders expanded! (radius {new_br})")

            # City healing
            if city["hp"] < city["max_hp"]:
                city["hp"] = min(city["max_hp"], city["hp"] + 10)

        # Worker building progress
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("building"):
                u["building"]["turns_left"] -= 1
                if u["building"]["turns_left"] <= 0:
                    imp_type = u["building"]["type"]
                    pos = (u["q"], u["r"])
                    if imp_type in ("road", "railroad"):
                        self.roads[pos] = {"type": imp_type, "player": pid}
                    else:
                        self.improvements[pos] = {"type": imp_type, "player": pid}
                    events.append(f"Worker built {imp_type}")
                    u["building"] = None

        # Road-trail workers: after a completed build, resume moving/building
        # toward the target. Also handle workers that just moved and now need
        # to start building on the new tile.
        for u in list(self.units.values()):
            if u["player"] == pid and u.get("road_to") and not u.get("building"):
                self.process_road_trail(u)

        # Spy actions — sabotage or steal tech if in enemy city
        for u in list(self.units.values()):
            if u["player"] == pid and u["type"] == "spy":
                for ec in self.cities.values():
                    if ec["player"] != pid and ec["q"] == u["q"] and ec["r"] == u["r"]:
                        enemy = self.players[ec["player"]]
                        if random.random() < 0.3:  # 30% chance per turn
                            # Steal tech
                            stealable = [t for t in enemy["techs"] if t not in player["techs"]]
                            if stealable:
                                stolen = random.choice(stealable)
                                player["techs"].append(stolen)
                                events.append(f"Spy stole {stolen} from {ec['name']}!")
                            else:
                                # Sabotage production
                                ec["prod_progress"] = max(0, ec.get("prod_progress", 0) - 10)
                                events.append(f"Spy sabotaged {ec['name']}!")
                            # Spy has 40% chance of being caught and killed
                            if random.random() < 0.4:
                                del self.units[u["id"]]
                                events.append(f"Spy was caught and executed!")
                        break

        # Caravan trade — earn gold when in foreign city
        for u in list(self.units.values()):
            if u["player"] == pid and u["type"] == "caravan":
                for fc in self.cities.values():
                    if fc["player"] != pid and fc["q"] == u["q"] and fc["r"] == u["r"]:
                        rel = player["diplomacy"].get(fc["player"], "neutral")
                        if rel != "war":
                            trade_gold = 5 + hex_distance(
                                u["q"], u["r"],
                                min((c for c in self.cities.values() if c["player"] == pid),
                                    key=lambda c: hex_distance(c["q"], c["r"], u["q"], u["r"]),
                                    default={"q": 0, "r": 0})["q"],
                                min((c for c in self.cities.values() if c["player"] == pid),
                                    key=lambda c: hex_distance(c["q"], c["r"], u["q"], u["r"]),
                                    default={"q": 0, "r": 0})["r"])
                            total_gold += trade_gold
                            events.append(f"Caravan earned {trade_gold} gold from {fc['name']}")
                            # Caravan is consumed after delivery
                            del self.units[u["id"]]
                        break

        # Gold
        # Unit maintenance
        unit_count = sum(1 for u in self.units.values() if u["player"] == pid)
        free = GAME_CONFIG.get("unit_maintenance_free", 2)
        mcost = GAME_CONFIG.get("unit_maintenance_cost", 1)
        maintenance = max(0, unit_count - free) * mcost
        total_gold -= maintenance
        player["gold"] += total_gold

        # Bankruptcy — disband units aggressively when gold negative.
        # Fix 2: During war, keep the army together unless deeply broke (disbanding
        # mid-war is a death spiral). Peacetime uses the normal threshold.
        at_war_now = any(player["diplomacy"].get(op["id"]) == "war"
                         for op in self.players if op["id"] != pid and op["alive"])
        threshold = GAME_CONFIG.get("bankruptcy_threshold", -50)
        if at_war_now:
            threshold = min(threshold, -150)
        if player["gold"] < threshold and not player["is_human"]:
            mil_units = [u for u in self.units.values()
                         if u["player"] == pid and u["cat"] != "civilian"]
            # Disband multiple units if deeply in debt
            disband_count = max(1, abs(player["gold"]) // 50)
            mil_units.sort(key=lambda u: u["hp"])
            for i in range(min(disband_count, len(mil_units))):
                u = mil_units[i]
                if u["id"] in self.units:
                    del self.units[u["id"]]
                    player["gold"] += 20
                    events.append(f"Disbanded {u['type']} (bankrupt)")

            # No military units left — sell buildings to recover
            if not mil_units and player["gold"] < GAME_CONFIG.get("bankruptcy_threshold", -50):
                my_cities = [c for c in self.cities.values() if c["player"] == pid]
                for city in my_cities:
                    if player["gold"] >= 0:
                        break
                    sellable = [b for b in city["buildings"] if b != "palace"]
                    if sellable:
                        # Sell cheapest building first
                        sellable.sort(key=lambda b: BUILDINGS.get(b, {}).get("cost", 50))
                        bld = sellable[0]
                        sell_gold = BUILDINGS.get(bld, {}).get("cost", 50) // 2
                        city["buildings"].remove(bld)
                        player["gold"] += sell_gold
                        events.append(f"Sold {bld} in {city['name']} for {sell_gold}g (bankrupt)")

        # Research
        if player["researching"]:
            player["researching"]["progress"] += total_science
            if player["researching"]["progress"] >= player["researching"]["cost"]:
                tech_name = player["researching"]["name"]
                if tech_name not in player["techs"]:  # prevent duplicates (spy could have stolen it)
                    player["techs"].append(tech_name)
                    events.append(f"Discovered: {tech_name}!")
                player["researching"] = None

        # Culture
        player["culture_pool"] += total_culture

        # Heal units
        for u in self.units.values():
            if u["player"] == pid and u["hp"] < 100:
                # In friendly city: +15, in friendly territory: +10, else: +5
                in_city = any(c["q"] == u["q"] and c["r"] == u["r"] and c["player"] == pid
                             for c in self.cities.values())
                if in_city:
                    u["hp"] = min(100, u["hp"] + 15)
                elif u["fortified"]:
                    u["hp"] = min(100, u["hp"] + 10)
                else:
                    u["hp"] = min(100, u["hp"] + 5)

        # Calculate score
        player["score"] = self._calc_score(pid)

        # --- VICTORY CONDITIONS ---

        # Space victory — 3 end-game techs + accumulated production
        space_techs = ["space_program", "rocketry", "nuclear_fission"]
        if all(t in player["techs"] for t in space_techs):
            player["space_progress"] = player.get("space_progress", 0) + sum(
                self.get_city_yields(c["id"])["prod"] for c in self.cities.values() if c["player"] == pid)
            if player.get("space_progress", 0) >= GAME_CONFIG.get("space_victory_production", 5000):
                self.game_over = True
                self.winner = pid
                self.victory_type = "space"
                events.append(f"{player['name']} achieves SPACE victory!")

        # Culture victory — accumulate threshold
        if not self.game_over and player["culture_pool"] >= GAME_CONFIG.get("culture_victory_threshold", 8000):
            self.game_over = True
            self.winner = pid
            self.victory_type = "culture"
            events.append(f"{player['name']} achieves CULTURE victory!")

        # Domination victory — control threshold% of all cities
        if not self.game_over:
            total_cities = len(self.cities)
            my_city_count = len([c for c in self.cities.values() if c["player"] == pid])
            if total_cities >= 4 and my_city_count >= total_cities * GAME_CONFIG.get("domination_city_percent", 0.6):
                self.game_over = True
                self.winner = pid
                self.victory_type = "domination"
                events.append(f"{player['name']} achieves DOMINATION victory!")

        # Turn limit — score victory
        max_turns = GAME_CONFIG.get("max_turns", 0)
        if not self.game_over and max_turns > 0 and self.turn >= max_turns:
            # Score victory: highest score wins
            best_pid = max(
                (p["id"] for p in self.players if p["alive"]),
                key=lambda pid2: self._calc_score(pid2))
            self.game_over = True
            self.winner = best_pid
            self.victory_type = "score"
            events.append(f"Turn limit reached! {self.players[best_pid]['name']} wins by SCORE ({self._calc_score(best_pid)})!")

        # Tick diplomatic agreements once per round (on player 0's turn end).
        if pid == 0:
            self._tick_agreements(events)

        # Advance to next player
        self._advance_turn()

        return {"ok": True, "events": events, "gold": total_gold, "science": total_science}

    def _advance_turn(self):
        """Move to next alive player, or next turn.

        After advancing, recursively run AI turns until control returns to
        the human player. If no human is alive, end the game — otherwise
        the AI loop would recurse forever with no stopping condition.
        """
        start = self.current_player
        while True:
            self.current_player = (self.current_player + 1) % len(self.players)
            if self.current_player == 0:
                self.turn += 1
            if self.players[self.current_player]["alive"]:
                break
            if self.current_player == start:
                break

        # Reset movement for new current player
        for u in self.units.values():
            if u["player"] == self.current_player:
                u["moves_left"] = u["mov"]

        # If the sole human is dead, stop cycling — the game is effectively over
        # for the player-controlled perspective. End so caller can observe outcome.
        if not any(p["is_human"] and p["alive"] for p in self.players):
            self.game_over = True
            if self.winner is None:
                alive = [p for p in self.players if p["alive"]]
                if alive:
                    self.winner = max(alive, key=lambda p: p["score"])["id"]
            return

        # Run AI turn then chain to next player
        if not self.players[self.current_player]["is_human"] and not self.game_over:
            self._run_ai(self.current_player)
            self.end_turn()

    def _calc_score(self, pid):
        """Calculate player score."""
        player = self.players[pid]
        return (
            len([c for c in self.cities.values() if c["player"] == pid]) * 100 +
            sum(c["population"] for c in self.cities.values() if c["player"] == pid) * 20 +
            len(player["techs"]) * 30 +
            player["culture_pool"] // 10
        )

    def _check_elimination(self):
        """Check if any player is eliminated."""
        for p in self.players:
            if not p["alive"]:
                continue
            has_cities = any(c["player"] == p["id"] for c in self.cities.values())
            has_settlers = any(u["player"] == p["id"] and u["type"] == "settler" for u in self.units.values())
            if not has_cities and not has_settlers:
                p["alive"] = False
                remaining = len([u for u in self.units.values() if u["player"] == p["id"]])
                self._log_ai(p["id"], f"ELIMINATED: {p['name']} destroyed! (had {remaining} units remaining, turn {self.turn})")
                to_remove = [uid for uid, u in self.units.items() if u["player"] == p["id"]]
                for uid in to_remove:
                    del self.units[uid]

        alive = [p for p in self.players if p["alive"]]
        if len(alive) == 1:
            self.game_over = True
            self.winner = alive[0]["id"]

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

