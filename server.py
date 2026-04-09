"""
FastAPI server for Civilization-like web game
"""
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from game_engine import GameState, CIVILIZATIONS
import config_loader
import auth

config_loader.start_watcher(interval=2)

SAVE_DIR = Path("saves")
SAVE_DIR.mkdir(exist_ok=True)

app = FastAPI(title="CivGame")

# Per-user game state: user_id -> {game_id -> GameState}
user_games = {}
next_game_id = 1
games = {}


def restore_active_games():
    """Restore active games from auto-saves on startup."""
    global next_game_id
    import json
    try:
        conn = auth.get_db()
        active = conn.execute("SELECT game_id, user_id FROM active_games").fetchall()
        for row in active:
            gid = row["game_id"]
            uid = row["user_id"]
            save = conn.execute("SELECT data FROM saves WHERE user_id = ? AND name = ? ORDER BY updated_at DESC LIMIT 1",
                                 (uid, f"auto_{gid}")).fetchone()
            if save:
                data = json.loads(save["data"])
                game = GameState.load_full(data)
                games[gid] = game
                if uid not in user_games:
                    user_games[uid] = {}
                user_games[uid][gid] = game
                if gid >= next_game_id:
                    next_game_id = gid + 1
                print(f"[RESTORE] Game #{gid} restored (turn {game.turn})")
        conn.close()
    except Exception as e:
        print(f"[RESTORE] Error: {e}")

restore_active_games()


class AuthRequest(BaseModel):
    username: str
    password: str


def get_user(request: Request):
    """Extract user from Authorization header. Returns user dict or None."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return None
    return auth.verify_token(token)


def require_user(request: Request):
    """Require authenticated user. Raises 401 if not."""
    user = get_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


# ---- AUTH ENDPOINTS ----

@app.post("/api/auth/register")
def api_register(req: AuthRequest):
    try:
        user = auth.register(req.username, req.password)
        token = auth.login(req.username, req.password)
        return {"ok": True, "user": user, "token": token}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/auth/login")
def api_login(req: AuthRequest):
    try:
        token = auth.login(req.username, req.password)
        user = auth.verify_token(token)
        return {"ok": True, "user": user, "token": token}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/auth/me")
def api_me(request: Request):
    user = get_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return {"ok": True, "user": user}


# ---- USER SAVES ----

@app.post("/api/user/save")
def api_user_save(request: Request):
    user = require_user(request)
    uid = user["id"]
    # Get active game
    if uid not in user_games or not user_games[uid]:
        raise HTTPException(400, "No active game")
    gid = max(user_games[uid].keys())
    game = user_games[uid][gid]
    save_data = game.save_full()
    save_data["_game_id"] = gid
    auth.save_game(uid, f"save_{gid}", save_data, game.turn)
    return {"ok": True, "msg": f"Game saved (Turn {game.turn})"}


@app.get("/api/user/saves")
def api_user_saves(request: Request):
    user = require_user(request)
    return auth.list_saves(user["id"])


@app.post("/api/user/load/{save_id}")
def api_user_load(save_id: int, request: Request):
    global next_game_id
    user = require_user(request)
    data = auth.load_save(user["id"], save_id)
    if not data:
        raise HTTPException(404, "Save not found")
    gid = next_game_id
    next_game_id += 1
    game = GameState.load_full(data)
    if user["id"] not in user_games:
        user_games[user["id"]] = {}
    user_games[user["id"]][gid] = game
    # Also add to legacy games for API compat
    games[gid] = game
    return {"game_id": gid, "state": game.to_dict(for_player=0)}


# ---- API TOKENS ----

class TokenRequest(BaseModel):
    name: str = "default"

@app.post("/api/auth/token")
def api_create_token(req: TokenRequest, request: Request):
    user = require_user(request)
    token = auth.create_api_token(user["id"], req.name)
    return {"ok": True, "token": token, "name": req.name}

@app.get("/api/auth/tokens")
def api_list_tokens(request: Request):
    user = require_user(request)
    return auth.list_api_tokens(user["id"])

@app.delete("/api/auth/token/{token_id}")
def api_revoke_token(token_id: int, request: Request):
    user = require_user(request)
    auth.revoke_api_token(user["id"], token_id)
    return {"ok": True}


# ---- AI API — Full game state + possible actions ----

@app.get("/api/game/{game_id}/ai/state")
def ai_full_state(game_id: int, request: Request):
    """Complete game state for AI — no fog of war, all info visible."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    # Full state without fog
    state = game.to_dict(for_player=None)
    # Add extra info for AI
    state["improvements"] = {f"{q},{r}": v for (q, r), v in game.improvements.items()}
    state["roads"] = {f"{q},{r}": v for (q, r), v in game.roads.items()}
    state["territory"] = {}
    for q in range(game.width):
        for r in range(game.height):
            owner = game.get_tile_owner(q, r)
            if owner is not None:
                state["territory"][f"{q},{r}"] = owner
    return state


@app.get("/api/game/{game_id}/ai/actions/{player_id}")
def ai_possible_actions(game_id: int, player_id: int, request: Request):
    """All possible actions for a player — units, cities, research, diplomacy."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")

    player = game.players[player_id]
    result = {
        "player": {"id": player_id, "name": player["name"], "gold": player["gold"],
                    "techs": player["techs"], "researching": player["researching"]},
        "units": [],
        "cities": [],
        "available_techs": game.get_available_techs(player_id),
        "diplomacy": {},
    }

    # Per-unit actions
    for u in game.units.values():
        if u["player"] != player_id:
            continue
        unit_info = {
            "id": u["id"], "type": u["type"], "q": u["q"], "r": u["r"],
            "hp": u["hp"], "atk": u["atk"], "def": u["def"],
            "moves_left": u["moves_left"], "mov": u["mov"],
            "fortified": u["fortified"], "sentry": u.get("sentry"),
            "exploring": u.get("exploring"), "goto": u.get("goto"),
            "building": u.get("building"),
            "actions": [],
        }

        if u["moves_left"] > 0:
            # Possible moves
            movable = []
            for nq, nr in hex_neighbors(u["q"], u["r"]):
                t = game.tiles.get((nq, nr))
                if t is None:
                    continue
                if t == Terrain.MOUNTAIN and u["cat"] != "air":
                    continue
                if t in (Terrain.WATER, Terrain.COAST) and u["cat"] not in ("naval", "air"):
                    continue
                if t not in (Terrain.WATER, Terrain.COAST) and u["cat"] == "naval":
                    continue
                enemy_unit = any(eu["q"] == nq and eu["r"] == nr and eu["player"] != player_id
                                 for eu in game.units.values())
                enemy_city = any(c["q"] == nq and c["r"] == nr and c["player"] != player_id
                                 for c in game.cities.values())
                movable.append({"q": nq, "r": nr, "enemy_unit": enemy_unit, "enemy_city": enemy_city})
            unit_info["movable_hexes"] = movable

            unit_info["actions"].append("move")
            unit_info["actions"].append("skip")
            unit_info["actions"].append("goto")

            if u["type"] == "settler":
                # Can found city?
                terrain = game.tiles.get((u["q"], u["r"]))
                nearest_city_dist = min((hex_distance(c["q"], c["r"], u["q"], u["r"]) for c in game.cities.values()), default=999)
                can_found = terrain and terrain not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN) and nearest_city_dist >= 3
                if can_found:
                    unit_info["actions"].append("found_city")
                unit_info["can_found_info"] = {
                    "terrain": terrain.value if terrain else None,
                    "nearest_city_dist": nearest_city_dist,
                    "min_required": 3,
                    "can_found": can_found,
                }

            if u["type"] == "worker":
                unit_info["actions"].append("auto_build")
                # Available improvements at current tile
                terrain = game.tiles.get((u["q"], u["r"]))
                if terrain:
                    buildable = []
                    for imp_name, imp_data in IMPROVEMENTS.items():
                        if imp_data["tech"] and imp_data["tech"] not in player["techs"]:
                            continue
                        if terrain.value not in imp_data["terrain"]:
                            continue
                        pos = (u["q"], u["r"])
                        if imp_name in ("road", "railroad"):
                            if game.roads.get(pos, {}).get("type") == imp_name:
                                continue
                        else:
                            if pos in game.improvements:
                                continue
                        buildable.append({"name": imp_name, "turns": imp_data["turns"],
                                          "food": imp_data["food"], "prod": imp_data["prod"], "gold": imp_data["gold"]})
                    unit_info["buildable_improvements"] = buildable

            if u["cat"] != "civilian":
                unit_info["actions"].extend(["fortify", "sentry", "explore"])

        unit_info["actions"].append("disband")
        result["units"].append(unit_info)

    # Per-city actions
    for c in game.cities.values():
        if c["player"] != player_id:
            continue
        city_info = {
            "id": c["id"], "name": c["name"], "q": c["q"], "r": c["r"],
            "population": c["population"], "hp": c["hp"], "max_hp": c["max_hp"],
            "producing": c["producing"], "prod_progress": c.get("prod_progress", 0),
            "buildings": c["buildings"],
            "available_productions": game.get_available_productions(c["id"]),
            "yields": game.get_city_yields(c["id"]),
        }
        result["cities"].append(city_info)

    # Diplomacy options
    for other in game.players:
        if other["id"] == player_id:
            continue
        rel = player["diplomacy"].get(other["id"], "peace")
        cd = player.get("diplo_cooldown", {}).get(other["id"], 0)
        actions = []
        if cd == 0:
            if rel != "war":
                actions.append("declare_war")
            if rel == "war":
                actions.append("make_peace")
            if rel == "peace":
                actions.append("form_alliance")
            if rel == "alliance":
                actions.append("break_alliance")
        result["diplomacy"][other["id"]] = {
            "player_name": other["name"], "relation": rel,
            "cooldown": cd, "available_actions": actions,
            "military_strength": len([u for u in game.units.values() if u["player"] == other["id"] and u["cat"] != "civilian"]),
            "cities": len([c for c in game.cities.values() if c["player"] == other["id"]]),
            "score": other["score"], "alive": other["alive"],
        }

    return result


@app.get("/api/game/{game_id}/ai/map")
def ai_map_info(game_id: int):
    """Full map data — terrain, improvements, roads, territory for AI analysis."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    tiles = {}
    for (q, r), t in game.tiles.items():
        tile_data = {"terrain": t.value, "yields": TERRAIN_YIELDS.get(t, {})}
        imp = game.improvements.get((q, r))
        if imp:
            tile_data["improvement"] = imp
        road = game.roads.get((q, r))
        if road:
            tile_data["road"] = road
        owner = game.get_tile_owner(q, r)
        if owner is not None:
            tile_data["owner"] = owner
        tiles[f"{q},{r}"] = tile_data
    return {"width": game.width, "height": game.height, "tiles": tiles}


@app.get("/api/spectate/analysis/{game_id}")
def spectate_analysis(game_id: int, request: Request):
    """Analyze game log — summary of AI behavior (admin only)."""
    user = get_user(request)
    if not user or not auth.is_admin(user["username"]):
        raise HTTPException(403, "Admin only")
    conn = auth.get_db()
    rows = conn.execute("SELECT * FROM game_logs WHERE game_id = ? ORDER BY id", (game_id,)).fetchall()
    conn.close()

    summary = {"total_actions": len(rows), "by_action": {}, "ai_decisions": [], "turns": 0}
    for r in rows:
        action = r["action"]
        summary["by_action"][action] = summary["by_action"].get(action, 0) + 1
        if r["turn"] and r["turn"] > summary["turns"]:
            summary["turns"] = r["turn"]
        if action == "ai" and r["detail"]:
            summary["ai_decisions"].append({"turn": r["turn"], "detail": r["detail"]})

    # Limit AI decisions to last 200
    summary["ai_decisions"] = summary["ai_decisions"][-200:]
    return summary


from game_engine import hex_neighbors, hex_distance, Terrain, IMPROVEMENTS, TERRAIN_YIELDS, TECHNOLOGIES, UNIT_TYPES, BUILDINGS, GAME_CONFIG, CITY_NAMES


@app.get("/api/rules")
def api_rules():
    """Complete game rules, mechanics, formulas — everything AI needs to understand the game."""
    return {
        "overview": {
            "description": "Turn-based civilization strategy game on hex grid",
            "objective": "Achieve victory through Space, Culture, Domination, or Score",
            "turn_flow": [
                "1. Move units (click adjacent hex or set goto for multi-turn movement)",
                "2. Found cities with settlers (min 3 hex distance from other cities, not in foreign territory)",
                "3. Set city production (units or buildings)",
                "4. Set research (one tech at a time)",
                "5. Manage diplomacy (war/peace/alliance)",
                "6. End turn — AI players act, yields processed, production/research advance",
            ],
            "hex_grid": "Odd-row offset coordinates (pointy-top hexagons)",
        },

        "victory_conditions": {
            "space": {
                "description": "Research 3 end-game techs and accumulate production",
                "required_techs": ["space_program", "rocketry", "nuclear_fission"],
                "production_needed": GAME_CONFIG.get("space_victory_production", 5000),
                "how": "After all 3 techs researched, each turn your total city production accumulates. Reach threshold to win.",
            },
            "culture": {
                "description": "Accumulate culture points",
                "threshold": GAME_CONFIG.get("culture_victory_threshold", 8000),
                "how": "Culture from cities (base 1 + buildings + trait bonuses) accumulates each turn in culture_pool.",
            },
            "domination": {
                "description": "Control majority of all cities",
                "percent_needed": GAME_CONFIG.get("domination_city_percent", 0.75),
                "how": "Own 75%+ of all cities on map (including captured ones). Min 4 total cities required.",
            },
            "score": {
                "description": "Highest score when turn limit reached (fallback)",
                "formula": "cities * 100 + total_population * 20 + techs * 30 + culture_pool / 10",
            },
        },

        "combat": {
            "formula": {
                "attack_strength": "unit.atk * (unit.hp / 100) * trait_bonus",
                "defense_strength": "unit.def * (unit.hp / 100) * (1 + terrain_defense / 100) * fortify_bonus",
                "damage_to_defender": "50 * atk_roll / (atk_roll + def_roll) + 15",
                "damage_to_attacker": "40 * def_roll / (atk_roll + def_roll) + 10",
                "random_factor": "strength * (0.8 + random * 0.4)",
            },
            "trait_bonuses": {
                "aggressive": "+15% attack strength",
                "protective": "+15% defense when near own city (within 3 hexes)",
            },
            "fortify_bonus": "+25% defense when fortified",
            "terrain_defense": {k.value: v for k, v in game_engine.TERRAIN_DEFENSE.items()},
            "unit_hp": 100,
            "healing": {
                "in_own_city": "+15 hp/turn",
                "fortified": "+10 hp/turn",
                "in_field": "+5 hp/turn",
            },
            "city_attack": {
                "damage_to_city": "25 * atk_roll / (atk_roll + def_roll + 1) + 5",
                "damage_to_attacker": "15 * def_roll / (atk_roll + def_roll + 1) + 3",
                "city_captured_when": "city.hp <= 0 (population -1, hp reset to half)",
            },
        },

        "terrain": {
            t.value: {
                "yields": TERRAIN_YIELDS.get(t, {}),
                "move_cost": game_engine.TERRAIN_MOVE_COST.get(t, 1),
                "defense_bonus": game_engine.TERRAIN_DEFENSE.get(t, 0),
                "passable": t not in (Terrain.MOUNTAIN, Terrain.WATER, Terrain.COAST),
                "naval_only": t in (Terrain.WATER, Terrain.COAST),
            } for t in Terrain
        },

        "units": {
            name: {
                **data,
                "upgrade_to": {
                    "warrior": "swordsman", "swordsman": "musketman", "musketman": "rifleman",
                    "rifleman": "infantry", "spearman": "musketman", "archer": "musketman",
                    "horseman": "knight", "knight": "tank", "catapult": "artillery",
                    "galley": "caravel", "caravel": "ironclad",
                }.get(name),
                "upgrade_cost": "half of target unit cost",
            } for name, data in UNIT_TYPES.items()
        },

        "buildings": BUILDINGS,
        "technologies": TECHNOLOGIES,
        "improvements": IMPROVEMENTS,

        "city_mechanics": {
            "founding": {
                "min_distance": 3,
                "forbidden_terrain": ["water", "coast", "mountain"],
                "forbidden_in_foreign_territory": True,
                "provocation": "Founding near foreign border: -30 relations with neighbor",
            },
            "growth": {
                "food_needed": "10 + population * 5",
                "food_surplus": "city food yield - population * 2",
                "starvation": "If food_store < 0 and population > 1: lose 1 pop",
            },
            "production": {
                "how": "Each turn, city prod yield added to prod_progress. When >= cost, item completed.",
                "auto_queue": "AI cities auto-pick next production via scoring system.",
            },
            "culture_borders": {
                "thresholds": {"radius_2": 10, "radius_3": 50, "radius_4": 150, "radius_5": 400},
                "culture_per_turn": "Base 1 + building bonuses + trait bonuses",
                "culture_pressure": "When two cities' borders overlap, tile belongs to city with higher culture/distance ratio. Build temples/monasteries to push borders.",
            },
            "defense": "Base 10 + building defense bonuses. City heals +10 hp/turn.",
        },

        "diplomacy": {
            "states": ["peace", "war", "alliance"],
            "default": "peace (all start at peace)",
            "cooldown": {
                "after_war_declaration": f"{GAME_CONFIG.get('diplo_war_cooldown', 10)} turns",
                "after_peace_treaty": f"{GAME_CONFIG.get('diplo_peace_cooldown', 15)} turns",
                "effect": "Cannot change diplomatic status during cooldown",
            },
            "territory": {
                "entering_non_allied_territory": "Triggers war declaration (human gets confirmation prompt)",
                "only_alliance_allows_passage": True,
            },
            "relations": {
                "range": "-100 (hostile) to +100 (friendly)",
                "events": {
                    "city_near_border": "-30 (provocation when founding near foreign border)",
                    "war_declaration": "-50",
                    "drift": "+1 or -1 per turn toward 0 (slowly normalize)",
                },
                "cpu_war_decision": {
                    "power_score": "military * (1 + techs/10) * (1 + cities/5)",
                    "requirements": "Must be 1.3x stronger AND opinion below threshold",
                    "threshold": "-30 for conquerors, -50 for others",
                    "weaker_never_attacks": "CPU with power_ratio < 1.3 will NEVER declare war",
                    "peace_when_losing": "CPU sues for peace when power_ratio < 0.5",
                },
            },
            "alliance": {
                "requires": "Both at peace first",
                "effect": "Free passage through territory",
                "auto_war": "If ally is attacked, ALL alliance members auto-declare war on attacker",
                "break": "Breaking alliance sets peace + cooldown",
            },
            "war_mobilization": {
                "description": "During war, ALL military units march toward nearest enemy city",
                "behavior": "No patrolling — full offensive push",
                "explore_cancel": "Military units stop exploring during war (should fight, not wander)",
            },
            "gang_up": {
                "trigger": f"Leader has {GAME_CONFIG.get('gang_up_score_ratio', 1.2)}x your score and > {GAME_CONFIG.get('gang_up_min_score', 500)}",
                "chance": f"{GAME_CONFIG.get('gang_up_chance', 0.25) * 100}% per turn",
            },
        },

        "economy": {
            "gold": {
                "income": "Sum of city gold yields + trade",
                "maintenance": f"({GAME_CONFIG.get('unit_maintenance_cost', 2)} gold per unit, first {GAME_CONFIG.get('unit_maintenance_free', 2)} free)",
                "bankruptcy": f"If gold < {GAME_CONFIG.get('bankruptcy_threshold', -50)}: AI disbands weakest units",
            },
            "science": {
                "per_city": "population + building bonuses",
                "research": "Each turn, total science added to researching tech progress",
            },
        },

        "special_units": {
            "settler": {
                "cost": UNIT_TYPES.get("settler", {}).get("cost", 60),
                "action": "found_city — creates new city, settler consumed",
                "restrictions": "Min 3 hex from other cities, not in foreign territory, not on water/mountain",
            },
            "worker": {
                "cost": UNIT_TYPES.get("worker", {}).get("cost", 25),
                "action": "Build improvements on tiles (farm, mine, road, railroad, lumber_mill, trading_post)",
                "build_time": "3-5 turns per improvement",
                "auto_build": "Can be set to auto-build mode (explores and improves near cities)",
            },
            "spy": {
                "cost": UNIT_TYPES.get("spy", {}).get("cost", 40),
                "action": "Move to enemy city. 30% chance/turn: steal tech or sabotage (-10 prod). 40% chance caught and killed.",
            },
            "caravan": {
                "cost": UNIT_TYPES.get("caravan", {}).get("cost", 30),
                "action": "Move to foreign non-enemy city. Delivers trade gold (8g), consumed on delivery.",
            },
        },

        "leader_traits": {
            "aggressive": {"yield_bonus": "+1 production", "combat": "+15% attack", "ai": "Needs fewer military for war"},
            "creative": {"yield_bonus": "+4 culture/city", "combat": None, "ai": "Pursues culture victory"},
            "expansive": {"yield_bonus": "+1 food/city", "combat": None, "ai": "More settlers, more cities"},
            "financial": {"yield_bonus": "+33% gold", "combat": None, "ai": "Trade focus"},
            "industrious": {"yield_bonus": "+20% production", "combat": None, "ai": "Fast space victory"},
            "protective": {"yield_bonus": "+20% science", "combat": "+15% defense near cities", "ai": "Turtle strategy"},
        },

        "api_reference": {
            "game_state": "GET /api/game/{id}/ai/state — complete state, no fog",
            "possible_actions": "GET /api/game/{id}/ai/actions/{player} — all possible actions",
            "map_data": "GET /api/game/{id}/ai/map — terrain/improvements/roads/territory",
            "move": "POST /api/game/{id}/move {unit_id, q, r}",
            "found_city": "POST /api/game/{id}/found_city {unit_id, name}",
            "production": "POST /api/game/{id}/production {city_id, item_type, item_name}",
            "research": "POST /api/game/{id}/research {tech_name}",
            "diplomacy": "POST /api/game/{id}/diplomacy {target_player, action: war|peace|alliance|break_alliance}",
            "end_turn": "POST /api/game/{id}/end_turn",
            "fortify": "POST /api/game/{id}/fortify/{unit_id}",
            "sentry": "POST /api/game/{id}/sentry/{unit_id}",
            "explore": "POST /api/game/{id}/explore/{unit_id}",
            "goto": "POST /api/game/{id}/goto {unit_id, q, r}",
            "worker_build": "POST /api/game/{id}/worker_build {unit_id, improvement}",
            "auto_worker": "POST /api/game/{id}/auto_worker/{unit_id}",
            "skip": "POST /api/game/{id}/skip/{unit_id}",
            "disband": "POST /api/game/{id}/disband/{unit_id}",
            "save": "POST /api/user/save",
        },
    }


import game_engine

# ---- SPECTATOR MODE (admin only) ----

@app.delete("/api/game/{game_id}")
def delete_game(game_id: int, request: Request):
    """Delete a game (owner or admin)."""
    user = get_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    # Check ownership or admin
    conn = auth.get_db()
    row = conn.execute("SELECT user_id FROM active_games WHERE game_id = ?", (game_id,)).fetchone()
    conn.close()
    if row and row["user_id"] != user["id"] and not auth.is_admin(user["username"]):
        raise HTTPException(403, "Not your game")
    # Remove from memory and DB
    games.pop(game_id, None)
    for uid in user_games:
        user_games[uid].pop(game_id, None)
    conn = auth.get_db()
    conn.execute("DELETE FROM active_games WHERE game_id = ?", (game_id,))
    conn.execute("DELETE FROM game_logs WHERE game_id = ?", (game_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "msg": f"Game {game_id} deleted"}


@app.get("/api/spectate/games")
def spectate_games(request: Request):
    """List active games for spectating (admin only)."""
    user = get_user(request)
    if not user or not auth.is_admin(user["username"]):
        raise HTTPException(403, "Admin only")
    return auth.list_active_games()

@app.get("/api/spectate/game/{game_id}")
def spectate_game(game_id: int, request: Request):
    """Get full game state for spectating (admin only, no fog)."""
    user = get_user(request)
    if not user or not auth.is_admin(user["username"]):
        raise HTTPException(403, "Admin only")
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    state = game.to_dict(for_player=None)
    state["improvements"] = {f"{q},{r}": v for (q, r), v in game.improvements.items()}
    state["roads"] = {f"{q},{r}": v for (q, r), v in game.roads.items()}
    # Full player data for spectator
    state["players"] = []
    for p in game.players:
        pd = {
            "id": p["id"], "name": p["name"], "civ": p["civ"],
            "color": p["color"], "leader": p["leader"],
            "alive": p["alive"], "score": p["score"],
            "gold": p["gold"], "techs": p["techs"],
            "researching": p["researching"],
            "diplomacy": {str(k): v for k, v in p["diplomacy"].items()},
            "culture_pool": p["culture_pool"],
            "trait": p.get("trait", ""), "strategy": p.get("strategy", ""),
            "aggression": p.get("aggression", 0), "loyalty": p.get("loyalty", 0),
            "cities": len([c for c in game.cities.values() if c["player"] == p["id"]]),
            "units": len([u for u in game.units.values() if u["player"] == p["id"]]),
            "military": len([u for u in game.units.values() if u["player"] == p["id"] and u["cat"] != "civilian"]),
        }
        state["players"].append(pd)
    return state

@app.get("/api/spectate/log/{game_id}")
def spectate_log(game_id: int, from_turn: int = 0, request: Request = None):
    """Get game action log (admin only)."""
    user = get_user(request)
    if not user or not auth.is_admin(user["username"]):
        raise HTTPException(403, "Admin only")
    return auth.get_game_log(game_id, from_turn)

class NewGameRequest(BaseModel):
    width: int = 40
    height: int = 30
    num_players: int = 4
    seed: Optional[int] = None
    civ: str = "rome"


class MoveRequest(BaseModel):
    unit_id: int
    q: int
    r: int


class GotoRequest(BaseModel):
    unit_id: int
    q: int
    r: int


class FoundCityRequest(BaseModel):
    unit_id: int
    name: str


class WorkerBuildRequest(BaseModel):
    unit_id: int
    improvement: str


class ProductionRequest(BaseModel):
    city_id: int
    item_type: str  # "unit" or "building"
    item_name: str


class ResearchRequest(BaseModel):
    tech_name: str


class DiplomacyRequest(BaseModel):
    target_player: int
    action: str  # "war" or "peace"


class SimulateRequest(BaseModel):
    width: int = 40
    height: int = 30
    num_players: int = 4
    num_turns: int = 100
    seed: Optional[int] = None


# ----------------------------------------------------------
# API ROUTES
# ----------------------------------------------------------

@app.post("/api/new_game")
def new_game(req: NewGameRequest, request: Request):
    global next_game_id
    gid = next_game_id
    next_game_id += 1

    game = GameState(width=req.width, height=req.height,
                     num_players=req.num_players, seed=req.seed)

    if req.civ in CIVILIZATIONS:
        # Swap: if another player has this civ, give them player 0's civ
        for p in game.players[1:]:
            if p["civ"] == req.civ:
                old_civ = game.players[0]["civ"]
                p["civ"] = old_civ
                p["name"] = CIVILIZATIONS[old_civ]["name"]
                p["color"] = CIVILIZATIONS[old_civ]["color"]
                p["leader"] = CIVILIZATIONS[old_civ]["leader"]
                for k in ("trait", "aggression", "loyalty", "strategy"):
                    if k in CIVILIZATIONS[old_civ]:
                        p[k] = CIVILIZATIONS[old_civ][k]
                break
        game.players[0]["civ"] = req.civ
        game.players[0]["name"] = CIVILIZATIONS[req.civ]["name"]
        game.players[0]["color"] = CIVILIZATIONS[req.civ]["color"]
        game.players[0]["leader"] = CIVILIZATIONS[req.civ]["leader"]

    games[gid] = game
    # Associate with user if logged in
    user = get_user(request)
    if user:
        uid = user["id"]
        if uid not in user_games:
            user_games[uid] = {}
        user_games[uid][gid] = game
        auth.register_active_game(gid, uid, user["username"], req.width, req.height, req.num_players)
    auth.log_action(gid, 1, 0, "new_game", {"width": req.width, "height": req.height, "players": req.num_players, "civ": req.civ})
    return {"game_id": gid, "state": game.to_dict(for_player=0)}


@app.get("/api/game/{game_id}")
def get_game(game_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    return game.to_dict(for_player=0)


@app.post("/api/game/{game_id}/goto")
def goto_unit(game_id: int, req: GotoRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.set_goto(req.unit_id, req.q, req.r)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/move")
def move_unit(game_id: int, req: MoveRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.move_unit(req.unit_id, req.q, req.r)
    auth.log_action(game_id, game.turn, 0, "move", {"unit_id": req.unit_id, "to": [req.q, req.r], "result": result.get("msg", "")})
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/found_city")
def found_city(game_id: int, req: FoundCityRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.found_city(req.unit_id, req.name)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/disband/{unit_id}")
def disband(game_id: int, unit_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.disband_unit(unit_id)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/auto_worker/{unit_id}")
def auto_worker(game_id: int, unit_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.auto_worker(unit_id)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/worker_build")
def worker_build(game_id: int, req: WorkerBuildRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.worker_build(req.unit_id, req.improvement)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/production")
def set_production(game_id: int, req: ProductionRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.set_production(req.city_id, req.item_type, req.item_name)
    auth.log_action(game_id, game.turn, 0, "production", {"city_id": req.city_id, "type": req.item_type, "name": req.item_name})
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/research")
def set_research(game_id: int, req: ResearchRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.set_research(0, req.tech_name)
    auth.log_action(game_id, game.turn, 0, "research", {"tech": req.tech_name})
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/fortify/{unit_id}")
def fortify(game_id: int, unit_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.fortify_unit(unit_id)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/explore/{unit_id}")
def explore(game_id: int, unit_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.explore_unit(unit_id)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/sentry/{unit_id}")
def sentry(game_id: int, unit_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.sentry_unit(unit_id)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/skip/{unit_id}")
def skip(game_id: int, unit_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.skip_unit(unit_id)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/end_turn")
def end_turn(game_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.end_turn()
    # Log player end_turn + all AI decisions
    auth.log_action(game_id, game.turn, 0, "end_turn", {"events": result.get("events", [])[:10]})
    # Log AI decisions collected during _run_ai (called from _advance_turn inside end_turn)
    if hasattr(game, 'ai_log') and game.ai_log:
        for ai_entry in game.ai_log[-100:]:
            auth.log_action(game_id, game.turn, None, "ai", ai_entry)
        game.ai_log = []  # clear after logging
    auth.update_active_game(game_id, game.turn)
    # Auto-save to DB every 5 turns
    if game.turn % 5 == 0:
        # Find owner
        conn = auth.get_db()
        row = conn.execute("SELECT user_id FROM active_games WHERE game_id = ?", (game_id,)).fetchone()
        conn.close()
        if row:
            auth.save_game(row["user_id"], f"auto_{game_id}", game.save_full(), game.turn)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/diplomacy")
def diplomacy(game_id: int, req: DiplomacyRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    # Check cooldown before any diplomatic action
    cd = game.players[0].get("diplo_cooldown", {}).get(req.target_player, 0)
    if cd > 0:
        return {"ok": False, "msg": f"Diplomatic cooldown: {cd} turns remaining", "state": game.to_dict(for_player=0)}
    if req.action == "war":
        game.declare_war(0, req.target_player)
    elif req.action == "peace":
        game.make_peace(0, req.target_player)
    elif req.action == "alliance":
        game.form_alliance(0, req.target_player)
    elif req.action == "break_alliance":
        game.break_alliance(0, req.target_player)
    auth.log_action(game_id, game.turn, 0, "diplomacy", {"target": req.target_player, "action": req.action})
    return {"ok": True, "state": game.to_dict(for_player=0)}


@app.post("/api/simulate")
def simulate(req: SimulateRequest):
    log = GameState.simulate(
        width=req.width, height=req.height,
        num_players=req.num_players, num_turns=req.num_turns,
        seed=req.seed,
    )
    # Save log to file
    filepath = SAVE_DIR / "sim_log.json"
    with open(filepath, "w") as f:
        json.dump(log, f, indent=2)
    return log


@app.get("/api/game/{game_id}/city/{city_id}/productions")
def get_productions(game_id: int, city_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    return game.get_available_productions(city_id)


@app.get("/api/game/{game_id}/techs")
def get_techs(game_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    return game.get_available_techs(0)


@app.get("/api/game/{game_id}/city/{city_id}/yields")
def get_yields(game_id: int, city_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    return game.get_city_yields(city_id)


# ----------------------------------------------------------
# SAVE / LOAD
# ----------------------------------------------------------

@app.post("/api/game/{game_id}/save")
def save_game(game_id: int):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    save_data = game.save_full()
    save_data["_game_id"] = game_id
    filepath = SAVE_DIR / f"save_{game_id}.json"
    with open(filepath, "w") as f:
        json.dump(save_data, f)
    return {"ok": True, "msg": f"Game saved (Turn {game.turn})", "filename": filepath.name}


@app.get("/api/saves")
def list_saves():
    saves = []
    for fp in sorted(SAVE_DIR.glob("save_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(fp) as f:
                data = json.load(f)
            saves.append({
                "filename": fp.name,
                "game_id": data.get("_game_id", 0),
                "turn": data.get("turn", 0),
                "players": [p["name"] for p in data.get("players", [])],
                "size": f"{fp.stat().st_size // 1024}KB",
                "width": data.get("width", 0),
                "height": data.get("height", 0),
            })
        except Exception:
            continue
    return saves


@app.post("/api/load/{filename}")
def load_game(filename: str):
    filepath = SAVE_DIR / filename
    if not filepath.exists() or not filepath.name.startswith("save_"):
        raise HTTPException(404, "Save not found")
    with open(filepath) as f:
        data = json.load(f)

    global next_game_id
    gid = next_game_id
    next_game_id += 1

    game = GameState.load_full(data)
    games[gid] = game
    return {"game_id": gid, "state": game.to_dict(for_player=0)}


# Serve frontend
@app.get("/")
def index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
