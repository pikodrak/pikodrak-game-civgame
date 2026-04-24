"""
User authentication system with SQLite + bcrypt + JWT.
"""
import sqlite3
import bcrypt
import jwt
import time
import os
from pathlib import Path

import secrets as _secrets
import sys as _sys

DB_PATH = Path(__file__).parent / "civgame.db"
_env_secret = os.environ.get("JWT_SECRET")
if _env_secret:
    JWT_SECRET = _env_secret
else:
    # Generate a random secret at startup rather than using a hardcoded fallback.
    # Sessions are lost on restart, but tokens cannot be forged from a known string.
    JWT_SECRET = _secrets.token_hex(32)
    print("[SECURITY WARNING] JWT_SECRET env var not set — using random secret; sessions will not survive restart", file=_sys.stderr)
TOKEN_EXPIRY = 86400 * 7  # 7 days


def get_db():
    """Get SQLite connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at REAL NOT NULL,
            last_login REAL
        );
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at REAL NOT NULL,
            last_used REAL,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            user_id INTEGER,
            turn INTEGER NOT NULL,
            player_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            timestamp REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS active_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER UNIQUE NOT NULL,
            user_id INTEGER,
            username TEXT,
            width INTEGER,
            height INTEGER,
            num_players INTEGER,
            turn INTEGER DEFAULT 1,
            started_at REAL NOT NULL,
            last_action REAL
        );
        CREATE TABLE IF NOT EXISTS saves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            turn INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()


def register(username, password):
    """Register a new user. Returns user dict or raises."""
    if not username or len(username) < 2:
        raise ValueError("Username must be at least 2 characters")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters")

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                      (username, pw_hash, time.time()))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        return {"id": user["id"], "username": user["username"]}
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError("Username already taken")


def login(username, password):
    """Login user. Returns JWT token or raises."""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        conn.close()
        raise ValueError("Invalid username or password")

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        conn.close()
        raise ValueError("Invalid username or password")

    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (time.time(), user["id"]))
    conn.commit()
    conn.close()

    token = jwt.encode({
        "user_id": user["id"],
        "username": user["username"],
        "exp": time.time() + TOKEN_EXPIRY,
    }, JWT_SECRET, algorithm="HS256")

    return token


def verify_token(token):
    """Verify JWT or API token. Returns user dict or None."""
    # Try JWT first
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("exp", 0) < time.time():
            return None
        return {"id": payload["user_id"], "username": payload["username"]}
    except (jwt.InvalidTokenError, Exception):
        pass

    # Try API token
    conn = get_db()
    row = conn.execute(
        "SELECT api_tokens.*, users.username FROM api_tokens JOIN users ON api_tokens.user_id = users.id "
        "WHERE api_tokens.token = ? AND api_tokens.active = 1", (token,)
    ).fetchone()
    if row:
        conn.execute("UPDATE api_tokens SET last_used = ? WHERE id = ?", (time.time(), row["id"]))
        conn.commit()
        conn.close()
        return {"id": row["user_id"], "username": row["username"]}
    conn.close()
    return None


def create_api_token(user_id, name="default"):
    """Create a persistent API token for a user."""
    import secrets
    token = f"civ_{secrets.token_hex(32)}"
    conn = get_db()
    conn.execute("INSERT INTO api_tokens (user_id, token, name, created_at) VALUES (?, ?, ?, ?)",
                  (user_id, token, name, time.time()))
    conn.commit()
    conn.close()
    return token


def list_api_tokens(user_id):
    """List API tokens for user."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, token, created_at, last_used, active FROM api_tokens WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"],
             "token": r["token"][:8] + "..." + r["token"][-4:],
             "created_at": r["created_at"], "last_used": r["last_used"],
             "active": bool(r["active"])} for r in rows]


def revoke_api_token(user_id, token_id):
    """Revoke an API token."""
    conn = get_db()
    conn.execute("UPDATE api_tokens SET active = 0 WHERE id = ? AND user_id = ?", (token_id, user_id))
    conn.commit()
    conn.close()


def save_game(user_id, name, data, turn=0):
    """Save game for user. Updates if name exists, creates if not."""
    import json
    conn = get_db()
    existing = conn.execute("SELECT id FROM saves WHERE user_id = ? AND name = ?",
                             (user_id, name)).fetchone()
    now = time.time()
    data_json = json.dumps(data)
    if existing:
        conn.execute("UPDATE saves SET data = ?, turn = ?, updated_at = ? WHERE id = ?",
                      (data_json, turn, now, existing["id"]))
    else:
        conn.execute("INSERT INTO saves (user_id, name, data, turn, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                      (user_id, name, data_json, turn, now, now))
    conn.commit()
    conn.close()


def list_saves(user_id):
    """List all saves for user."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, turn, created_at, updated_at FROM saves WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "turn": r["turn"],
             "updated_at": r["updated_at"]} for r in rows]


def load_save(user_id, save_id):
    """Load a save for user."""
    import json
    conn = get_db()
    row = conn.execute("SELECT * FROM saves WHERE id = ? AND user_id = ?",
                        (save_id, user_id)).fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row["data"])


def delete_save(user_id, save_id):
    """Delete a save."""
    conn = get_db()
    conn.execute("DELETE FROM saves WHERE id = ? AND user_id = ?", (save_id, user_id))
    conn.commit()
    conn.close()


# ---- GAME LOGGING ----

def log_action(game_id, turn, player_id, action, detail=None, user_id=None):
    """Log a game action."""
    import json
    conn = get_db()
    conn.execute("INSERT INTO game_logs (game_id, user_id, turn, player_id, action, detail, timestamp) VALUES (?,?,?,?,?,?,?)",
                  (game_id, user_id, turn, player_id, action,
                   json.dumps(detail) if isinstance(detail, dict) else str(detail) if detail else None,
                   time.time()))
    conn.commit()
    conn.close()


def register_active_game(game_id, user_id, username, width, height, num_players):
    """Register a game as active for spectating."""
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO active_games (game_id, user_id, username, width, height, num_players, started_at, last_action) VALUES (?,?,?,?,?,?,?,?)",
        (game_id, user_id, username, width, height, num_players, time.time(), time.time()))
    conn.commit()
    conn.close()


def update_active_game(game_id, turn):
    """Update turn and last_action for active game."""
    conn = get_db()
    conn.execute("UPDATE active_games SET turn = ?, last_action = ? WHERE game_id = ?",
                  (turn, time.time(), game_id))
    conn.commit()
    conn.close()


def list_active_games():
    """List all active games for spectating."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM active_games ORDER BY last_action DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_game_log(game_id, from_turn=0, limit=200):
    """Get game log entries."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM game_logs WHERE game_id = ? AND turn >= ? ORDER BY id DESC LIMIT ?",
        (game_id, from_turn, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_admin(username):
    """Check if user is admin (pikodrak)."""
    return username == "pikodrak"


# Initialize DB on import
init_db()
