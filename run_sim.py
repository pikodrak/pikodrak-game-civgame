#!/usr/bin/env python3
"""Run simulation and produce detailed analysis report."""
import json
import sys
import random
import config_loader
config_loader.check_and_reload()  # Load game_config.ini into game_engine globals
from game_engine import GameState, GAME_CONFIG

def run_and_analyze(width, height, num_players, num_turns, sim_id=1):
    print(f"\n{'='*70}")
    print(f"SIMULATION #{sim_id}: {width}x{height} map, {num_players} players, {num_turns} turns")
    print(f"{'='*70}")

    log = GameState.simulate(width=width, height=height, num_players=num_players, num_turns=num_turns)
    r = log["result"]

    # === MAP ANALYSIS ===
    print(f"\n--- MAP ---")
    m = log["map"]
    print(f"Total tiles: {m['total_tiles']}, Passable: {m['passable_tiles']} ({m['passable_tiles']*100//m['total_tiles']}%)")
    print(f"Terrain: {m['terrain_counts']}")

    # === PLAYERS ===
    print(f"\n--- PLAYERS ---")
    for p in log["players"]:
        print(f"  {p['name']} ({p['civ']}) - {p['trait']}/{p['strategy']} start={p.get('start_pos')}")

    # === RESULT ===
    print(f"\n--- RESULT ---")
    print(f"Winner: {r['winner']} ({r.get('victory_type','?')}) at turn {r['final_turn']}")
    print(f"Total cities: {r['total_cities']}, Improvements: {r['total_improvements']}, Roads: {r['total_roads']}")

    for s in r["scores"]:
        alive_str = "" if s["alive"] else " [DEAD]"
        print(f"  {s['name']} ({s['civ']}): score={s['score']}, cities={s['cities']}, units={s['units']}, "
              f"techs={s['techs']}, gold={s['gold']}, culture={s['culture_pool']}, "
              f"buildings={s['buildings_total']}{alive_str}")
        if s.get("city_names"):
            print(f"    Cities: {', '.join(s['city_names'])}")
        if s.get("tech_list"):
            print(f"    Techs: {', '.join(s['tech_list'][-8:])}" + (f" (+{len(s['tech_list'])-8} more)" if len(s['tech_list'])>8 else ""))

    # === EVENT ANALYSIS ===
    events = {"settle": 0, "combat": 0, "capture": 0, "disband": 0, "sold_building": 0,
              "tech_discovered": 0, "war": 0, "peace": 0, "alliance": 0,
              "buildings_built": 0, "units_produced": 0, "growth": 0,
              "eliminated": 0, "trade_route": 0}
    building_counts = {}
    unit_prod_counts = {}
    war_declarations = []
    economy_warnings = []
    idle_city_turns = 0

    for turn in log["turns"]:
        for e in turn["events"]:
            if isinstance(e, str):
                if "SETTLE:" in e: events["settle"] += 1
                if "destroyed" in e or "COMBAT" in e.upper(): events["combat"] += 1
                if "captured" in e: events["capture"] += 1
                if "Disbanded" in e and "bankrupt" in e: events["disband"] += 1
                if "Sold" in e and "bankrupt" in e: events["sold_building"] += 1
                if "Discovered:" in e: events["tech_discovered"] += 1
                if "declares WAR" in e or "WAR:" in e:
                    events["war"] += 1
                    war_declarations.append(f"T{turn['turn']}: {e}")
                if "PEACE" in e: events["peace"] += 1
                if "ALLIANCE" in e or "alliance" in e: events["alliance"] += 1
                # Match "CityName built building_name" or "[Player] CityName built building_name"
                import re
                bm = re.search(r'\b(\w+) built (\w+)$', e)
                if bm:
                    events["buildings_built"] += 1
                    bname = bm.group(2)
                    building_counts[bname] = building_counts.get(bname, 0) + 1
                pm = re.search(r'\b(\w+) produced (\w+)$', e)
                if pm:
                    events["units_produced"] += 1
                    uname = pm.group(2)
                    unit_prod_counts[uname] = unit_prod_counts.get(uname, 0) + 1
                if "grew to" in e: events["growth"] += 1
                if "eliminated" in e.lower(): events["eliminated"] += 1
                if "Caravan" in e and "gold" in e: events["trade_route"] += 1
            elif isinstance(e, dict) and "player" in e:
                # Player snapshot
                net = e.get("economy", {}).get("net", 0)
                gold = e.get("gold", 0)
                if net < -10 and gold < 0:  # only warn when both negative net AND negative gold
                    economy_warnings.append(f"T{turn['turn']} {e['player']}: net={net}, gold={gold}")
                for city in e.get("cities", []):
                    if city.get("producing") == "IDLE":
                        idle_city_turns += 1

    print(f"\n--- EVENT SUMMARY ---")
    for k, v in events.items():
        if v > 0:
            print(f"  {k}: {v}")

    print(f"\n--- BUILDINGS BUILT ---")
    for b, c in sorted(building_counts.items(), key=lambda x: -x[1]):
        print(f"  {b}: {c}")

    print(f"\n--- UNITS PRODUCED ---")
    for u, c in sorted(unit_prod_counts.items(), key=lambda x: -x[1]):
        print(f"  {u}: {c}")

    # === PROBLEMS DETECTED ===
    problems = []

    if events["disband"] > 20:
        problems.append(f"HIGH DISBANDS: {events['disband']} units disbanded (bankrupt)")

    if events["sold_building"] > 5:
        problems.append(f"BUILDING SALES: {events['sold_building']} buildings sold (severe bankruptcy)")

    if idle_city_turns > 10:
        problems.append(f"IDLE CITIES: {idle_city_turns} city-turns with no production")

    if events["war"] > 30:
        problems.append(f"WAR SPAM: {events['war']} war declarations")

    if events["settle"] < num_players:
        problems.append(f"LOW EXPANSION: only {events['settle']} cities settled (expected > {num_players})")

    if r["total_roads"] < events["settle"]:
        problems.append(f"LOW ROADS: only {r['total_roads']} roads for {r['total_cities']} cities")

    if r["total_improvements"] < r["total_cities"] * 3:
        problems.append(f"LOW IMPROVEMENTS: {r['total_improvements']} for {r['total_cities']} cities (should be 3+/city)")

    # Check if any player has 0 buildings
    for s in r["scores"]:
        if s["alive"] and s["cities"] > 0 and s["buildings_total"] <= s["cities"]:
            problems.append(f"NO BUILDINGS: {s['name']} has {s['buildings_total']} buildings for {s['cities']} cities")

    # Check if new buildings are being built
    new_buildings = {"barracks", "harbor", "colosseum", "forge", "stable", "workshop", "school", "museum", "theater", "military_academy", "airport", "bunker"}
    built_new = set(building_counts.keys()) & new_buildings
    if not built_new:
        problems.append(f"NO NEW BUILDINGS: none of the new buildings ({', '.join(sorted(new_buildings))}) were built")

    # Economy check
    if economy_warnings:
        problems.append(f"ECONOMY ISSUES: {len(economy_warnings)} turns with negative income (first 3: {economy_warnings[:3]})")

    # Tech balance
    max_techs = max((s["techs"] for s in r["scores"]), default=0)
    min_techs_alive = min((s["techs"] for s in r["scores"] if s["alive"]), default=0)
    if max_techs > 0 and min_techs_alive < max_techs // 3:
        problems.append(f"TECH IMBALANCE: {min_techs_alive} vs {max_techs} techs among alive players")

    # Score balance
    alive_scores = [s["score"] for s in r["scores"] if s["alive"]]
    if alive_scores and max(alive_scores) > min(alive_scores) * 5:
        problems.append(f"SCORE IMBALANCE: {min(alive_scores)} vs {max(alive_scores)}")

    print(f"\n--- PROBLEMS DETECTED ({len(problems)}) ---")
    if problems:
        for p in problems:
            print(f"  !! {p}")
    else:
        print("  No major issues detected!")

    # War declarations
    if war_declarations:
        print(f"\n--- WAR DECLARATIONS (first 10) ---")
        for w in war_declarations[:10]:
            print(f"  {w}")

    return log, problems


if __name__ == "__main__":
    configs = [
        (30, 25, 4, 300),   # small 4p
        (40, 30, 6, 300),   # medium 6p
        (50, 35, 8, 300),   # large 8p
    ]

    all_problems = []
    for i, (w, h, p, t) in enumerate(configs):
        log, problems = run_and_analyze(w, h, p, t, sim_id=i+1)
        all_problems.extend(problems)

    print(f"\n{'='*70}")
    print(f"ALL PROBLEMS ACROSS {len(configs)} SIMULATIONS:")
    print(f"{'='*70}")
    for p in all_problems:
        print(f"  {p}")
