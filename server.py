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
                too_close = any(hex_distance(c["q"], c["r"], u["q"], u["r"]) < 3 for c in game.cities.values())
                if not too_close and terrain and terrain not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                    unit_info["actions"].append("found_city")

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


from game_engine import hex_neighbors, hex_distance, Terrain, IMPROVEMENTS, TERRAIN_YIELDS

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
    auth.log_action(game_id, game.turn, 0, "end_turn", {"events": result.get("events", [])[:10]})
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
