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
# Legacy compat
games = {}


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
    result["state"] = game.to_dict(for_player=0)
    return result


@app.post("/api/game/{game_id}/research")
def set_research(game_id: int, req: ResearchRequest):
    game = games.get(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    result = game.set_research(0, req.tech_name)
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
