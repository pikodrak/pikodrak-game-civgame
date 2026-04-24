"""
FastAPI server for Civilization-like web game
"""
import html
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
from game_engine import GameState, CIVILIZATIONS
import config_loader
import auth

config_loader.start_watcher(interval=2)

GAME_VERSION = "0.9.5"
GAME_BUILD = "2026-04-11"

SAVE_DIR = Path("saves")
SAVE_DIR.mkdir(exist_ok=True)

app = FastAPI(title="CivGame", version=GAME_VERSION)

# Per-user game state: user_id -> {game_id -> GameState}
user_games = {}
next_game_id = 1
games = {}


class GameOwnershipMiddleware(BaseHTTPMiddleware):
    """Block access to games owned by another authenticated user.

    Anonymous games (created without auth) remain open to all callers.
    Owned games require the requesting user to match the owner or be admin.
    Covers all mutations (POST/PUT/PATCH/DELETE) and GET on /ai/* sub-paths,
    which expose full unfogged state and must not be readable by other users.
    """
    async def dispatch(self, request: Request, call_next):
        parts = request.url.path.strip("/").split("/")
        # Matches /api/game/{game_id}/...
        is_game_path = len(parts) >= 3 and parts[0] == "api" and parts[1] == "game"
        # GET /api/game/{id}/ai/* exposes full unfogged state — requires ownership check
        is_ai_subpath = is_game_path and len(parts) >= 4 and parts[3] == "ai"

        needs_check = (
            (request.method in ("POST", "PUT", "PATCH", "DELETE") and is_game_path) or
            (request.method == "GET" and is_ai_subpath)
        )

        if needs_check:
            try:
                game_id = int(parts[2])
                owner_id = next(
                    (uid for uid, g_map in user_games.items() if game_id in g_map),
                    None,
                )
                if owner_id is not None:
                    token = request.headers.get("Authorization", "").replace("Bearer ", "")
                    user = auth.verify_token(token) if token else None
                    if not user:
                        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
                    if user["id"] != owner_id and not auth.is_admin(user.get("username", "")):
                        return JSONResponse({"detail": "Not your game"}, status_code=403)
            except (ValueError, IndexError):
                pass
        return await call_next(request)


app.add_middleware(GameOwnershipMiddleware)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject standard browser-security headers on every response."""

    _HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in self._HEADERS.items():
            response.headers[header] = value
        return response


app.add_middleware(SecurityHeadersMiddleware)


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

            # Ranged attack targets
            unit_range = UNIT_TYPES.get(u["type"], {}).get("range", 0)
            if unit_range > 0:
                unit_info["actions"].append("ranged_attack")
                unit_info["range"] = unit_range
                ranged_targets = []
                for eu in game.units.values():
                    if eu["player"] != player_id:
                        d = hex_distance(u["q"], u["r"], eu["q"], eu["r"])
                        if 1 <= d <= unit_range:
                            ranged_targets.append({"q": eu["q"], "r": eu["r"], "type": eu["type"],
                                                   "hp": eu["hp"], "player": eu["player"], "distance": d})
                for ec in game.cities.values():
                    if ec["player"] != player_id:
                        d = hex_distance(u["q"], u["r"], ec["q"], ec["r"])
                        if 1 <= d <= unit_range:
                            ranged_targets.append({"q": ec["q"], "r": ec["r"], "type": "city",
                                                   "name": ec["name"], "hp": ec["hp"], "player": ec["player"], "distance": d})
                unit_info["ranged_targets"] = ranged_targets

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


@app.get("/api/version")
def api_version():
    """Game version, build, and recent changelog."""
    changelog = []
    try:
        with open("CHANGELOG.md") as f:
            lines = f.readlines()
            section = None
            for line in lines:
                line = line.rstrip()
                if line.startswith("## "):
                    if section:
                        break  # only latest session
                    section = line[3:].strip()
                elif section and line.startswith("### "):
                    changelog.append({"section": line[4:].strip(), "items": []})
                elif section and line.startswith("- ") and changelog:
                    changelog[-1]["items"].append(line[2:].strip())
    except:
        pass
    return {
        "version": GAME_VERSION,
        "build": GAME_BUILD,
        "changelog": changelog,
    }


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
                "percent_needed": GAME_CONFIG.get("domination_city_percent", 0.65),
                "how": f"Own {int(GAME_CONFIG.get('domination_city_percent', 0.65)*100)}%+ of all cities on map (including captured ones). Min 4 total cities required.",
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
            "fortify_bonus": "+25% defense when fortified (fortify only uses current turn movement, next turn unit moves normally; setting goto/move clears fortified state)",
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
                "capture_requires": "Melee unit must deliver final blow. Ranged attacks cannot capture (city HP floors at 1).",
            },
            "ranged_combat": {
                "description": "Ranged/siege units can attack from distance WITHOUT moving to target hex",
                "units_with_range": {
                    "archer": "range 2 (tech: archery)",
                    "catapult": "range 2 (tech: mathematics)",
                    "artillery": "range 3 (tech: dynamite)",
                    "bomber": "range 3 (tech: flight)",
                },
                "mechanics": [
                    "Ranged units attack at distance 1-N (where N = unit range)",
                    "Attacker stays on their hex (does NOT move to target)",
                    "Defender takes full damage, attacker takes only 25% return fire",
                    "Ranged attacks CANNOT capture cities — city HP floors at 1",
                    "To capture a city, use a melee unit (warrior/swordsman/knight etc.) for the final attack",
                    "Use ranged to soften targets, then melee to finish/capture",
                ],
                "damage_to_defender": "Same as melee: 50 * atk_roll / total + 15",
                "return_fire_to_attacker": "25% of normal: (40 * def_roll / total + 10) * 0.25",
                "api": "POST /api/game/{id}/ranged_attack {unit_id, q, r}",
                "strategy": "Position archers/catapults 2 hexes from target. Bombard to weaken, then send melee to capture.",
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

        "roads_and_railroads": {
            "road": {
                "build_time": "3 turns",
                "movement_bonus": "+60% speed (move cost * 0.4). Forest 2→1, hills 2→1, grass stays 1",
                "yield_bonus": "Trade route: cities connected to capital via road earn +1 gold per 2 pop",
                "strategy": "PRIORITY: build between cities and capital for trade income + fast troop movement. A* pathfinding prefers roads.",
            },
            "railroad": {
                "build_time": "4 turns",
                "tech_required": "railroad",
                "movement_bonus": "+80% speed (move cost * 0.2). Almost free movement.",
                "yield_bonus": "+1 production per tile",
                "upgrades_from": "road (worker auto-upgrades when tech available)",
            },
        },

        "city_mechanics": {
            "founding": {
                "min_distance": 4,
                "forbidden_terrain": ["water", "coast", "mountain"],
                "forbidden_in_foreign_territory": True,
                "min_distance_from_foreign_city": "max(border_radius + 1, 3) hexes from any foreign city",
                "provocation": "Founding near foreign border: -30 relations with neighbor",
            },
            "growth": {
                "food_needed": "10 + population * 5",
                "food_surplus": "city food yield - population * 2",
                "starvation": "If food_store < 0 and population > 1: lose 1 pop",
            },
            "production": {
                "how": "Each turn, city prod yield added to prod_progress. When >= cost, item completed.",
                "queue": "Up to 5 items can be queued. After current item completes, next from queue starts automatically.",
                "auto_produce": "Modes: 'units' (military only), 'buildings' (buildings only), 'auto' (AI decides best), 'off' (manual).",
                "settler_halts_growth": "While producing a settler, city food surplus is NOT stored — city does not grow.",
                "api_queue": "POST /api/game/{id}/production/queue {city_id, item_type, item_name}",
                "api_auto": "POST /api/game/{id}/production/auto {city_id, mode: units/buildings/auto/off}",
            },
            "culture_borders": {
                "thresholds": {"radius_2": 10, "radius_3": 50, "radius_4": 150, "radius_5": 400},
                "culture_per_turn": "Base 1 + building bonuses + trait bonuses",
                "culture_pressure": {
                    "how": "When borders overlap, tile belongs to city with higher culture/distance ratio",
                    "city_hex": "City's own hex ALWAYS belongs to its owner (never taken by culture)",
                    "yield_loss": "City can only harvest resources from tiles it owns. If foreign culture takes your tiles, you lose those yields (food/prod/gold)",
                    "strategy": "Build temples/monasteries to push borders. A city surrounded by foreign culture will starve",
                },
            },
            "defense": "Base 10 + building defense bonuses. City heals +10 hp/turn. Key: Palace=10, Barracks=10, Walls=50, Castle=80, Bunker=60.",
            "happiness": {
                "base": "0 per city",
                "population_penalty": "-1 per population above 4",
                "building_sources": "colosseum(+3), temple(+2), theater(+2), museum(+2), stadium(+4), marketplace(+1), monastery(+1), school(+1), hospital(+1), bank(+1)",
                "unhappy_penalties": "If happiness < 0: -25% production, -25% science, food surplus capped at 1 (city barely grows)",
                "strategy": "Build happiness buildings (colosseum, temple, stadium) before growing cities past pop 4",
            },
        },

        "diplomacy": {
            "states": ["peace", "war", "alliance"],
            "default": "peace (all start at peace)",
            "api_action_names": "Use: war, peace, alliance, break_alliance (NOT declare_war/make_peace)",
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
                "score_leader": f"Leader has {GAME_CONFIG.get('gang_up_score_ratio', 1.8)}x your score and > {GAME_CONFIG.get('gang_up_min_score', 1000)}, chance {GAME_CONFIG.get('gang_up_chance', 0.05) * 100}% per turn.",
                "anti_warmonger": "Any civ with 2+ active wars triggers gang-up rolls from each peaceful neighbour at chance × active_wars.",
                "anti_victor": "Any civ >60% toward any victory triggers panic war declarations from non-allies. Chance scales: 60% → 0%, 90% → 40%.",
            },
            "opinion": {
                "range": "-100 to +100",
                "modifiers": {
                    "trade_completed": "+5 for 20 turns; +2 permanent memory",
                    "declaration_of_friendship": "+15 for 30 turns (both sides)",
                    "denounced_us": "-20 for 30 turns",
                    "broken_gold_pt_promise": "-10 for 30 turns + permanent -20 per broken_promise in memory",
                    "warmonger_count": "-8 permanent per war declared by this civ (peaceful observers only)",
                    "axis_approval": "+5 permanent per war this civ declared (aggressive observers, aggression >= 0.7)",
                    "wars_declared_on_me": "-10 permanent (victim's memory)",
                    "cities_taken_from_me": "-15 permanent per city",
                    "betrayals": "-25 permanent per broken DoF/alliance",
                    "trait_affinity": "similar aggression +10, opposite -10, same strategy +5, conqueror vs culturalist -8",
                    "peace_bloc": "both civs with 0 wars_started +10, additionally both aggression<=0.4 +20 total",
                },
            },
            "deals": {
                "description": "Rich deal system — propose bundles of items, receiver accepts/rejects/counters.",
                "item_types": {
                    "gold": "{amount: int}",
                    "gold_per_turn": "{amount: int} — paid over deal_gold_pt_duration turns",
                    "tech": "{name: str} — one-shot tech transfer",
                    "map": "share explored tiles",
                    "city": "{city_id: int} — transfer ownership",
                    "open_borders": "free passage for deal_open_borders_duration turns",
                    "defensive_pact": "auto-join defensive wars",
                    "declaration_of_friendship": "opinion boost, blocks denounce",
                    "research_agreement": "both invest gold, random tech after deal_research_duration turns (Modern-era techs blocked)",
                    "trade_route": "+3 gold/turn to both sides",
                    "resource_trade": "{resource: str} — grant access to strategic/luxury resource",
                    "luxury_trade": "{resource: str} — happiness share",
                    "tribute": "{amount: int} — forced per-turn payment",
                    "peace_treaty": "{with: pid} — end war, bypass cooldown",
                    "denounce": "-20 opinion on target, 30-turn cooldown, signals to third parties",
                },
                "counter_offer": "POST /api/game/{id}/deal/ai_counter — AI suggests items to match player's give value",
                "demand": "POST /api/game/{id}/deal/demand — threaten weaker civs; needs ≥1.3× military",
                "evaluation": "Receiver computes total item values in gold-equivalent; accepts when gain >= loss * threshold (opinion-weighted 0.75..1.5). Victors >70% get hard-rejected on tech/research/resource trades.",
            },
            "resources": {
                "description": "Tile resources placed at ~5% of map matching terrain. 18 resource types.",
                "strategic": "iron, horse, coal, oil, uranium — GATE unit production (swordsman needs iron, knight needs horse, tank needs oil, nuclear_plant needs uranium).",
                "luxury": "wine, silk, gems, gold_ore, incense, spices, ivory, dyes — each UNIQUE type gives +2 happiness per city.",
                "bonus": "wheat, cattle, fish, deer, stone — passive tile yield boost. Not tradeable.",
                "access": "Resource on a tile within any of your cities' border_radius is accessible. Strategic/luxury may require a tech (e.g. gems needs mining).",
                "road_bonus": "Road on worked tile gives +1 gold; railroad +1 gold +1 prod.",
            },
        },

        "economy": {
            "gold": {
                "income": "Sum of city gold yields + trade route bonuses",
                "trade_routes": {
                    "description": "Cities connected to capital by road/railroad earn extra gold",
                    "bonus": "+1 gold per 2 population (minimum 1)",
                    "connection": "BFS via road/railroad tiles from city to capital (palace city)",
                    "strategy": "Build roads between cities and capital ASAP for gold income boost",
                },
                "maintenance": f"({GAME_CONFIG.get('unit_maintenance_cost', 2)} gold per unit, first {GAME_CONFIG.get('unit_maintenance_free', 2)} free)",
                "bankruptcy": {
                    "threshold": GAME_CONFIG.get("bankruptcy_threshold", -50),
                    "step_1": "Disband military units (weakest first, multiple units if deeply in debt)",
                    "step_2": "If no military units left, sell cheapest building (except palace) for half cost",
                    "gold_per_disband": 20,
                    "human_players": "Bankruptcy auto-disband affects CPU players. Human players keep negative gold but still pay maintenance every turn.",
                "warning": "Negative gold IS a problem — maintenance costs accumulate. Do NOT ignore gold management.",
                },
            },
            "unit_food": {
                "description": "Military units consume food from their home city",
                "home_city": "Each unit belongs to the city where it was produced",
                "cost_first_2": "FREE (no food cost)",
                "cost_3_to_4": "1 food per unit per turn",
                "cost_5_plus": "2 food per unit per turn",
                "example_6_units": "0+0+1+1+2+2 = 6 food/turn total",
                "redistribution": "AI balances home_city assignments across cities each turn to spread food load",
                "starvation": "If city food surplus < 0, city population shrinks. Too many units = city starves.",
                "strategy": "Spread military production across cities. Build farms before armies.",
            },
            "science": {
                "per_city": "population + building bonuses",
                "research": "Each turn, total science added to researching tech progress",
            },
        },

        "city_capture": {
            "mechanics": "Melee unit attacks city with HP <= 0 to capture it",
            "population": "City loses 1 population on capture (min 1)",
            "enemy_units": "Old owner's units inside city borders are PUSHED OUT to nearest tile outside borders",
            "no_exit": "If no valid tile exists (surrounded), unit is disbanded",
            "home_city": "Orphaned units (home_city was captured) reassign to nearest remaining city",
            "production": "City production resets to nothing on capture",
        },

        "special_units": {
            "settler": {
                "cost": UNIT_TYPES.get("settler", {}).get("cost", 60),
                "action": "found_city — creates new city, settler consumed",
                "population_cost": "Settler costs 1 population from the producing city. City must have pop >= 2 to build settler.",
                "restrictions": "Min 3 hex from other cities, not in foreign territory, not on water/mountain",
                "important": "Settlers are civilian units — they CANNOT use explore command. Move them manually with move/goto.",
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

        "barracks_system": {
            "barracks": {"effect": "Military units produced here start with +10 XP", "tech": "bronze_working"},
            "military_academy": {"effect": "Military units produced here start with +15 XP (stacks with barracks)", "tech": "military_science"},
            "combined": "Barracks + Military Academy = +25 XP for new military units",
        },

        "technologies": {name: {
            "cost": data["cost"],
            "era": data["era"],
            "prereqs": data["prereqs"],
            "unlocks": data["unlocks"],
        } for name, data in game_engine.TECHNOLOGIES.items()},

        "civilizations": {name: {
            "display_name": data["name"],
            "bonus": data["bonus"],
            "leader": data["leader"],
            "trait": data["trait"],
            "strategy": data["strategy"],
            "aggression": data["aggression"],
            "loyalty": data["loyalty"],
        } for name, data in game_engine.CIVILIZATIONS.items()},

        "city_yields_formula": {
            "description": "How city yields (food/prod/gold/science/culture) are calculated each turn",
            "base": {"food": 2, "prod": 1, "gold": 0, "science": 0, "culture": 1},
            "tile_yields": "Each worked tile adds food/prod/gold from terrain + improvement bonuses. Max worked tiles = population + 1",
            "tile_selection": "Best tiles (highest total yield) worked first",
            "improvements": {
                "farm": "+1 food", "mine": "+2 prod", "lumber_mill": "+1 prod",
                "trading_post": "+2 gold", "railroad_tile": "+1 prod",
            },
            "buildings": "Each building adds its food/prod/gold/science/culture/defense",
            "leader_trait": {
                "creative": "+4 culture", "expansive": "+1 food",
                "financial": "+33% gold", "industrious": "+20% prod",
                "aggressive": "+1 prod", "protective": "+20% science",
            },
            "civ_bonus": "food/prod/gold/science/culture: +15% to matching yield type",
            "trade_route": "+1 gold per 2 population if city connected to capital by road (min 1)",
            "population_science": "+1 science per population",
            "happiness_penalty": "If happiness < 0: prod * 0.75, science * 0.75, food_surplus capped at 1",
            "food_surplus": "food - population * 2 - unit_food_cost = surplus for growth",
            "unit_food_cost": {
                "description": "Military units consume food from their home city (scaling cost)",
                "home_city": "Each unit has a home_city (city where it was produced). Food is deducted from that city.",
                "cost_scaling": "First 2 units: FREE. Units 3-4: 1 food each. Units 5+: 2 food each.",
                "example": "City with 6 military units: 0+0+1+1+2+2 = 6 food/turn for army",
                "redistribution": "AI redistributes home_city each turn to balance food across cities",
                "strategy": "Don't build too many units from one city — it will starve. Spread production across cities.",
            },
        },

        "score_formula": {
            "formula": "cities * 100 + total_population * 20 + techs * 30 + culture_pool / 10",
            "how": "Calculated dynamically, shown in top bar during game",
        },

        "pathfinding": {
            "algorithm": "A* with move cost weighting",
            "road_bonus": "Road: move cost * 0.4 (60% faster). Railroad: move cost * 0.2 (80% faster)",
            "terrain_cost": {k.value: v for k, v in game_engine.TERRAIN_MOVE_COST.items()},
            "impassable": ["water (land units)", "coast (land units)", "mountain"],
            "naval_only": ["water", "coast"],
            "foreign_territory": "A* avoids foreign territory unless at war",
            "preference": "A* prefers roads — units automatically route through fastest path",
        },

        "culture_pressure": {
            "how": "When city borders overlap, tile belongs to city with higher culture/distance ratio",
            "city_hex": "City's own hex ALWAYS belongs to its owner (never taken by culture)",
            "yield_loss": "City can only harvest resources from tiles it owns. Foreign culture = lost yields",
            "border_growth": "City borders grow with accumulated culture: radius 1→2(10)→3(50)→4(150)→5(400)",
        },

        "unit_experience": {
            "xp_from_barracks": 10,
            "xp_from_military_academy": 15,
            "xp_stacking": "Barracks + Military Academy = +25 XP for new military units",
            "xp_from_combat": "Planned but not yet implemented",
        },

        "upgrade_chains": {
            "melee": "warrior → swordsman → musketman → rifleman → infantry",
            "mounted": "horseman → knight → tank",
            "ranged": "archer → musketman",
            "siege": "catapult → artillery",
            "naval": "galley → caravel → ironclad",
            "cost": "Half of target unit cost",
            "requirement": "Must be in own city with enough gold",
        },

        "api_reference": {
            "game_state": "GET /api/game/{id}/ai/state — complete state, no fog",
            "possible_actions": "GET /api/game/{id}/ai/actions/{player} — all possible actions per unit/city",
            "map_data": "GET /api/game/{id}/ai/map — terrain/improvements/roads/territory",
            "move": "POST /api/game/{id}/move {unit_id, q, r} — melee attack or movement",
            "ranged_attack": "POST /api/game/{id}/ranged_attack {unit_id, q, r} — ranged fire without moving (archer/catapult/artillery/bomber)",
            "found_city": "POST /api/game/{id}/found_city {unit_id, name}",
            "production": "POST /api/game/{id}/production {city_id, item_type, item_name}",
            "research": "POST /api/game/{id}/research {tech_name}",
            "diplomacy": "POST /api/game/{id}/diplomacy {target_player, action: war|peace|alliance|break_alliance}",
            "diplomacy_info": "GET /api/game/{id}/diplomacy/info — opinions, breakdowns, active agreements, pending deals, victory progress for all civs",
            "deal_propose": "POST /api/game/{id}/deal/propose {target_player, give: [items], ask: [items]} — propose a deal. Response includes ai_decision (accepted/rejected/pending) and valuation hints.",
            "deal_accept": "POST /api/game/{id}/deal/accept {deal_id}",
            "deal_reject": "POST /api/game/{id}/deal/reject {deal_id}",
            "deal_ai_counter": "POST /api/game/{id}/deal/ai_counter {target_player, give, ask} — AI suggests what it would offer in return for your 'give' items",
            "deal_demand": "POST /api/game/{id}/deal/demand {target_player, ask: [items]} — threaten/coerce weaker civs. Outcomes: accepted (paid), rejected, rejected_war.",
            "deal_item_types": "gold | gold_per_turn {amount} | tech {name} | map | city {city_id} | open_borders | defensive_pact | declaration_of_friendship | research_agreement | trade_route | resource_trade {resource} | luxury_trade {resource} | tribute {amount} | peace_treaty {with} | denounce",
            "end_turn": "POST /api/game/{id}/end_turn",
            "fortify": "POST /api/game/{id}/fortify/{unit_id}",
            "sentry": "POST /api/game/{id}/sentry/{unit_id}",
            "explore": "POST /api/game/{id}/explore/{unit_id} — military units only, civilians (settler/worker/spy/caravan) CANNOT explore",
            "goto": "POST /api/game/{id}/goto {unit_id, q, r} — multi-turn movement (cancels if: enemy nearby, foreign territory without war, path blocked)",
            "path_preview": "POST /api/game/{id}/path_preview {unit_id, q, r} — read-only A* path, cost, turns estimate. Does not mutate state.",
            "worker_build": "POST /api/game/{id}/worker_build {unit_id, improvement}",
            "worker_road_to": "POST /api/game/{id}/worker/road_to {unit_id, q, r} — put worker in road-trail mode; it will build road/railroad along the path to target, one tile per turn",
            "auto_worker": "POST /api/game/{id}/auto_worker/{unit_id}",
            "skip": "POST /api/game/{id}/skip/{unit_id}",
            "disband": "POST /api/game/{id}/disband/{unit_id}",
            "upgrade": "POST /api/game/{id}/upgrade/{unit_id}",
            "save": "POST /api/user/save",
            "rules": "GET /api/rules — this endpoint, complete game rules",
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

@app.delete("/api/user/save/{save_id}")
def api_delete_save(save_id: int, request: Request):
    user = require_user(request)
    auth.delete_save(user["id"], save_id)
    return {"ok": True, "msg": "Save deleted"}


class NewGameRequest(BaseModel):
    width: int = Field(default=40, ge=10, le=200)
    height: int = Field(default=30, ge=10, le=200)
    num_players: int = Field(default=4, ge=2, le=12)
    seed: Optional[int] = None
    civ: str = "rome"
    map_type: str = "random"  # random / earth_s / earth_m / earth_l
    wrap: bool = False  # wrap-around globe map


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
    name: str = Field(max_length=64)


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
    width: int = Field(default=40, ge=10, le=100)
    height: int = Field(default=30, ge=10, le=100)
    num_players: int = Field(default=4, ge=2, le=8)
    num_turns: int = Field(default=100, ge=1, le=500)
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
                     num_players=req.num_players, seed=req.seed,
                     map_type=req.map_type, wrap=req.wrap)

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


@app.post("/api/game/{game_id}/worker/road_to")
def api_worker_road_to(game_id: int, req: GotoRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.set_road_to(req.unit_id, req.q, req.r)
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/path_preview")
def path_preview(game_id: int, req: GotoRequest):
    """Return the full path for a unit without setting goto (read-only preview).

    Iterates _find_path_next to mirror the exact movement rules (naval/air,
    foreign territory, roads), so the preview matches what the unit will actually do.
    """
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    unit = game.units.get(req.unit_id)
    if not unit:
        raise HTTPException(404, "Unit not found")
    tq, tr = req.q, req.r
    if (unit["q"], unit["r"]) == (tq, tr):
        return {"ok": True, "path": [], "dist": 0, "cost": 0.0, "turns": 0}
    sim = dict(unit)
    path = []
    total_cost = 0.0
    seen = {(sim["q"], sim["r"])}
    for _ in range(200):
        nxt = game._find_path_next(sim, tq, tr)
        if not nxt:
            break
        total_cost += game._hex_move_cost(nxt[0], nxt[1])
        path.append([nxt[0], nxt[1]])
        sim["q"], sim["r"] = nxt[0], nxt[1]
        if (sim["q"], sim["r"]) == (tq, tr):
            break
        if (sim["q"], sim["r"]) in seen:
            break
        seen.add((sim["q"], sim["r"]))
    turns = game._path_turns(path, unit.get("mov", 1), unit.get("moves_left"))
    return {"ok": True, "path": path, "dist": len(path), "cost": total_cost, "turns": turns}


@app.post("/api/game/{game_id}/move")
def move_unit(game_id: int, req: MoveRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.move_unit(req.unit_id, req.q, req.r)
    auth.log_action(game_id, game.turn, 0, "move", {"unit_id": req.unit_id, "to": [req.q, req.r], "result": result.get("msg", "")})
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/ranged_attack")
def ranged_attack(game_id: int, req: MoveRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.ranged_attack(req.unit_id, req.q, req.r)
    auth.log_action(game_id, game.turn, 0, "ranged_attack", {"unit_id": req.unit_id, "target": [req.q, req.r], "result": result.get("msg", "")})
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/found_city")
def found_city(game_id: int, req: FoundCityRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.found_city(req.unit_id, html.escape(req.name))
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

class QueueRequest(BaseModel):
    city_id: int
    item_type: str
    item_name: str

@app.post("/api/game/{game_id}/production/queue")
def add_to_queue(game_id: int, req: QueueRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    city = game.cities.get(req.city_id)
    if not city:
        raise HTTPException(404, "City not found")
    queue = city.setdefault("prod_queue", [])
    if len(queue) >= 5:
        return {"ok": False, "msg": "Queue full (max 5)"}
    queue.append({"type": req.item_type, "name": req.item_name})
    return {"ok": True, "msg": f"Added {req.item_name} to queue ({len(queue)}/5)", "state": game.to_dict(for_player=0)}

class AutoProduceRequest(BaseModel):
    city_id: int
    mode: str  # "units" / "buildings" / "auto" / "off"

@app.post("/api/game/{game_id}/production/auto")
def set_auto_produce(game_id: int, req: AutoProduceRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    city = game.cities.get(req.city_id)
    if not city:
        raise HTTPException(404, "City not found")
    city["auto_produce"] = req.mode if req.mode != "off" else None
    # If city is idle, immediately start producing based on auto mode
    if not city.get("producing") and req.mode != "off":
        player = game.players[city["player"]]
        game._auto_produce_mode(city, player, city["player"])
    return {"ok": True, "msg": f"Auto-produce: {req.mode}" + (f" → {city['producing']['name']}" if city.get('producing') else ""), "state": game.to_dict(for_player=0)}


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


class DealRequest(BaseModel):
    target_player: int
    give: list
    ask: list


class DealDecisionRequest(BaseModel):
    deal_id: int


@app.post("/api/game/{game_id}/deal/propose")
def api_deal_propose(game_id: int, req: DealRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    r = game.propose_deal(0, req.target_player, req.give, req.ask)
    # If target is AI, let them decide immediately and report the outcome
    # so the frontend can show "accepted" or "rejected" right away.
    if r.get("ok") and not game.players[req.target_player].get("is_human"):
        deal_id = r["deal_id"]
        existed_before = any(d["id"] == deal_id for d in game.pending_deals)
        game._ai_respond_to_deal(deal_id, req.target_player)
        # If the deal is no longer pending, it was resolved (accept or reject).
        still_pending = any(d["id"] == deal_id for d in game.pending_deals)
        if not still_pending and existed_before:
            accepted_flag = False
            for msg in reversed(game.ai_log[-20:]) if hasattr(game, "ai_log") else []:
                if "DEAL: accepted" in msg and game.players[req.target_player]["name"] in msg:
                    accepted_flag = True
                    break
                if "DEAL: rejected" in msg and game.players[req.target_player]["name"] in msg:
                    break
            r["ai_decision"] = "accepted" if accepted_flag else "rejected"
            # Attach valuation breakdown so the UI can explain WHY a deal was rejected
            gain = sum(game._ai_value_item(it, req.target_player) for it in req.give)
            loss = sum(game._ai_value_item(it, req.target_player) for it in req.ask)
            r["ai_gain"] = gain   # what AI gets from accepting
            r["ai_loss"] = loss   # what AI gives up
        else:
            r["ai_decision"] = "pending"
    r["state"] = game.to_dict(for_player=0)
    return r


class DemandRequest(BaseModel):
    target_player: int
    ask: list


@app.post("/api/game/{game_id}/deal/demand")
def api_deal_demand(game_id: int, req: DemandRequest):
    """Player demands items from an AI. AI evaluates based on military
    strength and opinion. Outcomes:
      - accepted: items transfer, big opinion hit on target
      - rejected_war: target declares war immediately
      - rejected: target refuses, big opinion hit on player
    """
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    me = 0
    ai = req.target_player
    if ai >= len(game.players):
        raise HTTPException(400, "Invalid target")

    def military(pid):
        return sum(1 for u in game.units.values()
                   if u["player"] == pid and u["cat"] != "civilian")
    my_mil = military(me)
    their_mil = military(ai)
    power_ratio = my_mil / max(1, their_mil)

    demand_value = sum(game._ai_value_item(it, ai) for it in req.ask)
    opinion = game.get_opinion(ai, me)
    aggression = game.players[ai].get("aggression", 0.5)

    # Accept threshold: must be clearly stronger AND demand reasonably sized
    result = {"state": None, "outcome": None}
    if my_mil == 0 or their_mil == 0:
        # No armies → no intimidation
        outcome = "rejected"
    elif power_ratio >= 2.0 and demand_value < 500:
        outcome = "accepted"
    elif power_ratio >= 1.3 and demand_value < 200:
        outcome = "accepted"
    elif power_ratio < 1.0:
        # We're weaker than them — they may declare war for the insult
        war_chance = aggression * 0.6
        import random as _r
        outcome = "rejected_war" if _r.random() < war_chance else "rejected"
    else:
        outcome = "rejected"

    result["outcome"] = outcome
    result["power_ratio"] = round(power_ratio, 2)
    result["demand_value"] = demand_value

    if outcome == "accepted":
        # Transfer items from AI to player
        for item in req.ask:
            game._apply_item(item, ai, me)
        # Target resents it — big opinion hit and memory mark
        game._add_opinion(ai, me, "demanded_from_us", -30, turns=40)
        game._bump_memory(ai, me, "broken_promises")
        game.ai_log.append(f"[{game.players[ai]['name']}] paid demand from {game.players[me]['name']}")
    elif outcome == "rejected":
        # AI refuses — player's reputation with target tanks
        game._add_opinion(ai, me, "insulted_us", -20, turns=30)
        game.ai_log.append(f"[{game.players[ai]['name']}] refused demand from {game.players[me]['name']}")
    elif outcome == "rejected_war":
        game._add_opinion(ai, me, "insulted_us", -30, turns=30)
        game.declare_war(ai, me)
        game.ai_log.append(f"[{game.players[ai]['name']}] declared WAR after {game.players[me]['name']} made demands")

    result["state"] = game.to_dict(for_player=0)
    result["ok"] = True
    return result


@app.post("/api/game/{game_id}/deal/ai_counter")
def api_deal_ai_counter(game_id: int, req: DealRequest):
    """Player offers items; AI suggests what it would give in return.

    Computes the gold-equivalent value of the player's offer, then picks a
    set of items the AI has available that roughly matches that value.
    Returns the suggested "ask" list — player can accept, modify, or discard.
    """
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    if req.target_player >= len(game.players):
        raise HTTPException(400, "Invalid target")
    me = 0
    ai = req.target_player
    # Value of what player offers, from AI receiver's perspective
    offer_value = sum(game._ai_value_item(it, ai) for it in req.give)
    if offer_value <= 0:
        return {"ok": False, "msg": "Your offer has no value to them", "suggested": []}

    player_ai = game.players[ai]
    player_me = game.players[me]
    # Candidate items AI could give, scored by value to me (the proposer)
    candidates = []

    # Gold buckets AI could pay
    for amt in (30, 60, 120, 250, 500):
        if player_ai["gold"] >= amt:
            candidates.append({"type": "gold", "amount": amt})

    # Techs AI has that I don't
    for t in player_ai["techs"]:
        if t in player_me["techs"]:
            continue
        from civgame.data import TECHNOLOGIES
        tdata = TECHNOLOGIES.get(t)
        if not tdata:
            continue
        if all(pr in player_me["techs"] for pr in tdata.get("prereqs", [])):
            candidates.append({"type": "tech", "name": t})

    # World map
    candidates.append({"type": "map"})
    # Open borders etc — always possible offers
    for agr in ("open_borders", "trade_route", "declaration_of_friendship",
                 "defensive_pact", "research_agreement"):
        if not game.has_active(me, ai, agr):
            candidates.append({"type": agr})

    # Luxuries AI has
    ai_res = game.get_player_resources(ai)
    my_res = game.get_player_resources(me)
    for r_name in ai_res:
        from civgame.data import RESOURCES
        if RESOURCES.get(r_name, {}).get("type") == "luxury" and r_name not in my_res:
            candidates.append({"type": "luxury_trade", "resource": r_name})
        if RESOURCES.get(r_name, {}).get("type") == "strategic" and r_name not in my_res:
            candidates.append({"type": "resource_trade", "resource": r_name})

    # Pick items whose *total* value (from my perspective as proposer) best
    # matches `offer_value`. Greedy fit — take most valuable items up to budget.
    # But value should be close to what AI views as equivalent — use AI's
    # view of cost (asymmetric 1.08×) to simulate what AI would actually
    # give up.
    scored = []
    for item in candidates:
        my_gain = game._ai_value_item(item, me)
        ai_cost = int(game._ai_value_item(item, ai) * 1.08)
        if ai_cost <= 0:
            continue
        scored.append((item, my_gain, ai_cost))
    # Sort by ai_cost descending so we fit larger items first
    scored.sort(key=lambda x: -x[2])

    budget = offer_value
    suggested = []
    used_types = set()  # avoid duplicate categories (don't suggest two gold buckets)
    for item, my_gain, ai_cost in scored:
        if ai_cost > budget * 1.2:
            continue  # way too big
        cat_key = item["type"] + "|" + str(item.get("resource", ""))
        if cat_key in used_types:
            continue
        used_types.add(cat_key)
        suggested.append(item)
        budget -= ai_cost
        if budget <= offer_value * 0.1:
            break

    return {
        "ok": True,
        "offer_value": offer_value,
        "suggested": suggested,
        "ai_name": player_ai["name"],
    }


@app.post("/api/game/{game_id}/deal/accept")
def api_deal_accept(game_id: int, req: DealDecisionRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    r = game.accept_deal(req.deal_id, accepting_pid=0)
    r["state"] = game.to_dict(for_player=0)
    return r


@app.post("/api/game/{game_id}/deal/reject")
def api_deal_reject(game_id: int, req: DealDecisionRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    r = game.reject_deal(req.deal_id, rejecting_pid=0)
    r["state"] = game.to_dict(for_player=0)
    return r


@app.get("/api/game/{game_id}/diplomacy/info")
def api_diplomacy_info(game_id: int):
    """Return opinion matrix, active agreements, pending deals for player 0."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    me = 0
    opinions = {}
    breakdowns = {}
    victory_progress = {}
    # Use scaled thresholds (grow with num_players + map size)
    thr = game._victory_thresholds() if hasattr(game, "_victory_thresholds") else {}
    space_threshold = thr.get("space", 50000)
    culture_threshold = thr.get("culture", 8000)
    domination_pct = thr.get("domination", 0.65)
    total_cities = max(1, len(game.cities))
    space_techs_needed = ["space_program", "rocketry", "nuclear_fission"]
    for p in game.players:
        if p["id"] != me:
            opinions[p["id"]] = game.get_opinion(me, p["id"])
            breakdowns[p["id"]] = game.get_opinion_breakdown(me, p["id"])
        # Per-civ victory progress — visible for ALL players (espionage-free)
        space_techs_done = sum(1 for t in space_techs_needed if t in p.get("techs", []))
        space_prog = p.get("space_progress", 0)
        culture = p.get("culture_pool", 0)
        my_cities = sum(1 for c in game.cities.values() if c["player"] == p["id"])
        victory_progress[p["id"]] = {
            "space_techs": space_techs_done,  # 0-3
            "space_progress": space_prog,
            "space_pct": int(100 * space_prog / space_threshold) if space_techs_done == 3 else min(75, space_techs_done * 25),
            "culture_pool": culture,
            "culture_pct": int(100 * culture / culture_threshold),
            "domination_pct": int(100 * my_cities / total_cities),
            "domination_needed_pct": int(100 * domination_pct),
            "cities": my_cities,
            "total_cities": total_cities,
        }
    return {
        "opinions": opinions,
        "breakdowns": breakdowns,
        "victory_progress": victory_progress,
        "thresholds": {
            "space_production": space_threshold,
            "culture": culture_threshold,
            "domination_pct": domination_pct,
        },
        "agreements": game.get_active_agreements(me),
        "incoming": game.incoming_deals(me),
        "outgoing": game.outgoing_deals(me),
        "my_techs": game.players[me]["techs"],
        "my_gold": game.players[me]["gold"],
        "my_resources": game.get_player_resources(me),
    }


@app.post("/api/simulate")
def simulate(req: SimulateRequest, request: Request):
    require_user(request)
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

@app.get("/api/game/{game_id}/city/{city_id}/manage")
def city_manage(game_id: int, city_id: int):
    """Detailed city management: worked tiles, yields breakdown, growth info, unit food cost."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    city = game.cities.get(city_id)
    if not city:
        raise HTTPException(404, "City not found")
    yields = game.get_city_yields(city_id, detail=True)
    home_units = [{"id": u["id"], "type": u["type"], "hp": u["hp"]}
                  for u in game.units.values() if u.get("home_city") == city_id]
    warnings = []
    if yields["food_surplus"] < 0:
        warnings.append({"type": "starvation", "msg": f"Starvation! Food deficit {yields['food_surplus']}/turn. City shrinks in ~{yields['turns_to_starve']} turns."})
    if yields["food_surplus"] == 0:
        warnings.append({"type": "stagnant", "msg": "City stagnant — no growth."})
    if yields["food_cost_units"] > 0:
        warnings.append({"type": "info", "msg": f"Feeding {yields['food_cost_units']} military unit(s) ({yields['food_cost_units']} food/turn)."})
    if yields["food_surplus"] > 0:
        warnings.append({"type": "growth", "msg": f"Grows in ~{yields['turns_to_grow']} turns ({yields['food_stored']}/{yields['growth_needed']} stored)."})
    if yields["happiness"] < 0:
        warnings.append({"type": "unhappy", "msg": f"Unhappy ({yields['happiness']}). -25% prod/science, growth stalled."})
    if not yields.get("connected"):
        warnings.append({"type": "info", "msg": "Not connected to capital — no trade income."})
    return {
        "city": {"id": city["id"], "name": city["name"], "population": city["population"],
                 "buildings": city["buildings"], "producing": city["producing"],
                 "prod_progress": city["prod_progress"], "hp": city["hp"]},
        "yields": yields,
        "home_units": home_units,
        "warnings": warnings,
    }


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
    # Resolve the path and verify it stays within SAVE_DIR to prevent traversal
    save_dir_resolved = SAVE_DIR.resolve()
    filepath = (SAVE_DIR / filename).resolve()
    try:
        filepath.relative_to(save_dir_resolved)
    except ValueError:
        raise HTTPException(404, "Save not found")
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
