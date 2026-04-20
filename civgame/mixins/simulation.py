"""Headless simulation runner."""
import random
from civgame.data import UNIT_TYPES, BUILDINGS, IMPROVEMENTS, TECHNOLOGIES, CIVILIZATIONS
from civgame.constants import Terrain, GAME_CONFIG

class SimulationMixin:
    @classmethod
    def simulate(cls, width=40, height=30, num_players=4, num_turns=100, seed=None):
        """Run a full AI-only game and return detailed log."""
        game = cls(width=width, height=height, num_players=num_players, seed=seed)
        # Make all players AI
        for p in game.players:
            p["is_human"] = False

        # Build terrain summary for map log
        terrain_counts = {}
        for pos, t in game.tiles.items():
            terrain_counts[t.value] = terrain_counts.get(t.value, 0) + 1

        log = {
            "settings": {"width": width, "height": height, "players": num_players, "seed": seed, "turns": num_turns},
            "map": {
                "terrain_counts": terrain_counts,
                "total_tiles": len(game.tiles),
                "passable_tiles": sum(1 for t in game.tiles.values() if t not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN)),
            },
            "players": [{"id": p["id"], "name": p["name"], "civ": p["civ"],
                         "trait": CIVILIZATIONS.get(p["civ"], {}).get("trait", ""),
                         "strategy": CIVILIZATIONS.get(p["civ"], {}).get("strategy", ""),
                         "start_pos": next(((u["q"], u["r"]) for u in game.units.values() if u["player"] == p["id"] and u["type"] == "settler"), None),
                         } for p in game.players],
            "turns": [],
            "result": None,
        }

        for turn_num in range(num_turns):
            if game.game_over:
                break

            turn_log = {"turn": game.turn, "events": []}

            # Snapshot before turn
            for p in game.players:
                if not p["alive"]:
                    continue
                pid = p["id"]
                my_cities = [c for c in game.cities.values() if c["player"] == pid]
                my_units = [u for u in game.units.values() if u["player"] == pid]
                # Economy breakdown
                total_income = sum(game.get_city_yields(c["id"])["gold"] for c in my_cities)
                unit_count = len(my_units)
                free = GAME_CONFIG.get("unit_maintenance_free", 2)
                maint = max(0, unit_count - free) * GAME_CONFIG.get("unit_maintenance_cost", 1)
                total_prod_out = sum(game.get_city_yields(c["id"])["prod"] for c in my_cities)
                total_science_out = sum(game.get_city_yields(c["id"])["science"] for c in my_cities)
                total_culture_out = sum(game.get_city_yields(c["id"])["culture"] for c in my_cities)
                total_food_out = sum(game.get_city_yields(c["id"])["food"] for c in my_cities)

                # Territory
                territory = sum(1 for q in range(game.width) for r in range(game.height)
                                if game.get_tile_owner(q, r) == pid) if game.turn % 10 == 0 else 0

                # Victory progress
                space_techs = ["space_program", "rocketry", "nuclear_fission"]
                space_tech_done = sum(1 for t in space_techs if t in p["techs"])
                space_prog = p.get("space_progress", 0)
                space_need = GAME_CONFIG.get("space_victory_production", 5000)
                culture_prog = p["culture_pool"]
                culture_need = GAME_CONFIG.get("culture_victory_threshold", 8000)
                total_cities_all = len(game.cities)
                my_city_count = len(my_cities)
                domin_pct = my_city_count / max(1, total_cities_all)

                # Improvements on my territory
                my_imps = sum(1 for pos in game.improvements if game.get_tile_owner(*pos) == pid)
                my_roads = sum(1 for pos in game.roads if game.get_tile_owner(*pos) == pid)

                plog = {
                    "player": p["name"],
                    "gold": p["gold"],
                    "score": p["score"],
                    "techs": len(p["techs"]),
                    "researching": p["researching"]["name"] if p["researching"] else None,
                    "economy": {"income": total_income, "maintenance": maint, "net": total_income - maint},
                    "yields": {"food": total_food_out, "prod": total_prod_out, "science": total_science_out, "culture": total_culture_out},
                    "victory": {
                        "space": f"{space_tech_done}/3 techs, {space_prog}/{space_need} prod ({int(space_prog/space_need*100)}%)" if space_tech_done > 0 else "0/3 techs",
                        "culture": f"{culture_prog}/{culture_need} ({int(culture_prog/culture_need*100)}%)",
                        "domination": f"{my_city_count}/{total_cities_all} ({int(domin_pct*100)}%)",
                    },
                    "territory": territory,
                    "improvements": my_imps,
                    "roads": my_roads,
                    "cities": [{
                        "name": c["name"],
                        "pop": c["population"],
                        "producing": c["producing"]["name"] if c.get("producing") else "IDLE",
                        "buildings": list(c["buildings"]),
                        "connected_to_capital": game.is_connected_to_capital(c["id"]),
                        "hp": c.get("hp", 200),
                    } for c in my_cities],
                    "units": {},
                }
                for u in my_units:
                    utype = u["type"]
                    plog["units"][utype] = plog["units"].get(utype, 0) + 1
                # Diplomacy snapshot
                plog["diplomacy"] = {game.players[op]["name"]: rel
                                     for op, rel in p.get("diplomacy", {}).items()
                                     if op < len(game.players) and game.players[op]["alive"]}
                turn_log["events"].append(plog)

            log["turns"].append(turn_log)

            # Run one full round (all players)
            start_turn = game.turn
            # Process each player's turn
            for pid in range(num_players):
                if not game.players[pid]["alive"] or game.game_over:
                    continue
                game.current_player = pid
                pname = game.players[pid]["name"]
                # Snapshot before AI
                units_before = set(game.units.keys())
                cities_before = {c["id"]: c["player"] for c in game.cities.values()}
                # Reset movement
                for u in game.units.values():
                    if u["player"] == pid:
                        u["moves_left"] = u["mov"]
                # Run AI (clear log before, collect after)
                game.ai_log = []
                game._run_ai(pid)
                # Add AI decisions to turn log
                if game.ai_log:
                    turn_log["events"].extend(game.ai_log)
                # Detect combat results (exclude settlers consumed by founding cities)
                units_after = set(game.units.keys())
                disappeared = units_before - units_after
                # Filter out settlers that were consumed to found cities
                new_cities = set(game.cities.keys()) - set(cities_before.keys())
                settlers_consumed = len(new_cities)  # each new city consumes 1 settler
                combat_killed = len(disappeared) - settlers_consumed
                if combat_killed > 0:
                    turn_log["events"].append(f"[{pname}] {combat_killed} unit(s) destroyed in combat")
                for cid, cdata in game.cities.items():
                    old_owner = cities_before.get(cid)
                    if old_owner is not None and old_owner != cdata["player"]:
                        turn_log["events"].append(f"[{pname}] captured {cdata['name']}!")
                # Check new cities founded
                for cid in game.cities:
                    if cid not in cities_before:
                        turn_log["events"].append(f"[{pname}] founded {game.cities[cid]['name']}")
                # Process end of turn (cities, research, etc.)
                result = game._process_turn(pid)
                if result.get("events"):
                    turn_log["events"].extend([f"[{pname}] {e}" for e in result["events"]])

            game.turn += 1

        # Score victory — if no winner, highest score wins
        if not game.game_over:
            alive = [p for p in game.players if p["alive"]]
            if alive:
                best = max(alive, key=lambda p: p["score"])
                game.game_over = True
                game.winner = best["id"]
                log["turns"][-1]["events"].append(f"{best['name']} achieves SCORE victory! ({best['score']} pts)")

        # Final result
        victory_type = None
        if game.winner is not None:
            wp = game.players[game.winner]
            space_techs = ["space_program", "rocketry", "nuclear_fission"]
            if all(t in wp["techs"] for t in space_techs):
                victory_type = "space"
            elif wp["culture_pool"] >= GAME_CONFIG.get("culture_victory_threshold", 8000):
                victory_type = "culture"
            elif len([c for c in game.cities.values() if c["player"] == game.winner]) / max(1, len(game.cities)) >= GAME_CONFIG.get("domination_city_percent", 0.75):
                victory_type = "domination"
            else:
                victory_type = "score"

        # Final map state
        final_improvements = {}
        for pos, imp in game.improvements.items():
            final_improvements[f"{pos[0]},{pos[1]}"] = imp["type"]
        final_roads = {}
        for pos, road in game.roads.items():
            final_roads[f"{pos[0]},{pos[1]}"] = road["type"]

        log["result"] = {
            "game_over": game.game_over,
            "winner": game.players[game.winner]["name"] if game.winner is not None else None,
            "victory_type": victory_type,
            "final_turn": game.turn,
            "total_improvements": len(game.improvements),
            "total_roads": len(game.roads),
            "total_cities": len(game.cities),
            "scores": [{
                "name": p["name"],
                "civ": p["civ"],
                "score": p["score"],
                "alive": p["alive"],
                "gold": p["gold"],
                "techs": len(p["techs"]),
                "tech_list": list(p["techs"]),
                "culture_pool": p["culture_pool"],
                "cities": len([c for c in game.cities.values() if c["player"] == p["id"]]),
                "city_names": [c["name"] for c in game.cities.values() if c["player"] == p["id"]],
                "units": len([u for u in game.units.values() if u["player"] == p["id"]]),
                "buildings_total": sum(len(c["buildings"]) for c in game.cities.values() if c["player"] == p["id"]),
            } for p in game.players],
        }
        return log

    def _process_turn(self, pid):
        """Process yields, production, research for one player. Returns events."""
        player = self.players[pid]
        if not player["alive"]:
            return {"events": []}

        # Tick diplomacy cooldowns
        for k in list(player.get("diplo_cooldown", {}).keys()):
            if player["diplo_cooldown"][k] > 0:
                player["diplo_cooldown"][k] -= 1

        total_gold = 0
        total_science = 0
        total_culture = 0
        events = []

        for city in list(self.cities.values()):
            if city["player"] != pid:
                continue
            yields = self.get_city_yields(city["id"])
            total_gold += yields["gold"]
            total_science += yields["science"]
            total_culture += yields["culture"]

            # While producing settler, food surplus halted
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

            if city["producing"]:
                city["prod_progress"] += yields["prod"]
                if city["prod_progress"] >= city["producing"]["cost"]:
                    item = city["producing"]
                    if item["type"] == "unit":
                        # Settler costs 1 population
                        if item["name"] == "settler":
                            if city["population"] < 2:
                                city["producing"] = None
                                city["prod_progress"] = 0
                                self._ai_auto_produce(city, player, pid)
                                continue
                            city["population"] -= 1
                            city["food_store"] = 0
                        uid = self._create_unit(pid, item["name"], city["q"], city["r"])
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
                    self._ai_auto_produce(city, player, pid)

            city["culture"] = city.get("culture", 0) + yields["culture"]
            old_br = city.get("border_radius", 1)
            thresholds = [(400, 5), (150, 4), (50, 3), (10, 2)]
            new_br = 1
            for threshold, radius in thresholds:
                if city["culture"] >= threshold:
                    new_br = radius
                    break
            city["border_radius"] = new_br

            if city["hp"] < city["max_hp"]:
                city["hp"] = min(city["max_hp"], city["hp"] + 10)

        # Worker building progress (simulation)
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

        # Spy/caravan processing (simulation)
        for u in list(self.units.values()):
            if u["player"] == pid and u["type"] == "spy":
                for ec in self.cities.values():
                    if ec["player"] != pid and ec["q"] == u["q"] and ec["r"] == u["r"]:
                        if random.random() < 0.3:
                            enemy = self.players[ec["player"]]
                            stealable = [t for t in enemy["techs"] if t not in player["techs"]]
                            if stealable:
                                stolen = random.choice(stealable)
                                player["techs"].append(stolen)
                                events.append(f"Spy stole {stolen}")
                            else:
                                ec["prod_progress"] = max(0, ec.get("prod_progress", 0) - 10)
                                events.append(f"Spy sabotaged {ec['name']}")
                            if random.random() < 0.4:
                                del self.units[u["id"]]
                                events.append(f"Spy caught!")
                        break
            elif u["player"] == pid and u["type"] == "caravan":
                for fc in self.cities.values():
                    if fc["player"] != pid and fc["q"] == u["q"] and fc["r"] == u["r"]:
                        rel = player["diplomacy"].get(fc["player"], "neutral")
                        if rel != "war":
                            total_gold += 8
                            events.append(f"Caravan trade +8 gold")
                            del self.units[u["id"]]
                        break

        unit_count = sum(1 for u in self.units.values() if u["player"] == pid)
        maintenance = max(0, unit_count - 2) * 1
        total_gold -= maintenance
        player["gold"] += total_gold

        # Bankruptcy — disband units, then sell buildings
        if player["gold"] < GAME_CONFIG.get("bankruptcy_threshold", -50):
            mil_units = [u for u in self.units.values()
                         if u["player"] == pid and u["cat"] != "civilian"]
            if mil_units:
                disband_count = max(1, abs(player["gold"]) // 50)
                mil_units.sort(key=lambda u: u["hp"])
                for i in range(min(disband_count, len(mil_units))):
                    u = mil_units[i]
                    if u["id"] in self.units:
                        del self.units[u["id"]]
                        player["gold"] += 20
                        events.append(f"Disbanded {u['type']} (bankrupt)")

            # No military units left — sell buildings
            if not mil_units and player["gold"] < GAME_CONFIG.get("bankruptcy_threshold", -50):
                my_cities = [c for c in self.cities.values() if c["player"] == pid]
                for city in my_cities:
                    if player["gold"] >= 0:
                        break
                    sellable = [b for b in city["buildings"] if b != "palace"]
                    if sellable:
                        sellable.sort(key=lambda b: BUILDINGS.get(b, {}).get("cost", 50))
                        bld = sellable[0]
                        sell_gold = BUILDINGS.get(bld, {}).get("cost", 50) // 2
                        city["buildings"].remove(bld)
                        player["gold"] += sell_gold
                        events.append(f"Sold {bld} in {city['name']} for {sell_gold}g (bankrupt)")

        if player["researching"]:
            player["researching"]["progress"] += total_science
            if player["researching"]["progress"] >= player["researching"]["cost"]:
                tech_name = player["researching"]["name"]
                if tech_name not in player["techs"]:
                    player["techs"].append(tech_name)
                    events.append(f"Discovered: {tech_name}")
                player["researching"] = None

        player["culture_pool"] += total_culture

        for u in self.units.values():
            if u["player"] == pid and u["hp"] < 100:
                in_city = any(c["q"] == u["q"] and c["r"] == u["r"] and c["player"] == pid
                             for c in self.cities.values())
                if in_city:
                    u["hp"] = min(100, u["hp"] + 15)
                elif u.get("fortified"):
                    u["hp"] = min(100, u["hp"] + 10)
                else:
                    u["hp"] = min(100, u["hp"] + 5)

        player["score"] = self._calc_score(pid)

        space_techs = ["space_program", "rocketry", "nuclear_fission"]
        if all(t in player["techs"] for t in space_techs):
            player["space_progress"] = player.get("space_progress", 0) + sum(
                self.get_city_yields(c["id"])["prod"] for c in self.cities.values() if c["player"] == pid)
            if player.get("space_progress", 0) >= GAME_CONFIG.get("space_victory_production", 5000):
                self.game_over = True
                self.winner = pid
                events.append(f"{player['name']} achieves SPACE victory!")
        if not self.game_over and player["culture_pool"] >= GAME_CONFIG.get("culture_victory_threshold", 8000):
            self.game_over = True
            self.winner = pid
            events.append(f"{player['name']} achieves CULTURE victory!")
        if not self.game_over:
            total_cities = len(self.cities)
            my_city_count = len([c for c in self.cities.values() if c["player"] == pid])
            if total_cities >= 4 and my_city_count >= total_cities * GAME_CONFIG.get("domination_city_percent", 0.6):
                self.game_over = True
                self.winner = pid
                events.append(f"{player['name']} achieves DOMINATION victory!")

        self._check_elimination()
        return {"events": events}

    # --------------------------------------------------------
    # SAVE / LOAD
    # --------------------------------------------------------

