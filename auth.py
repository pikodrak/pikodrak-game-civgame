"""
User authentication system with SQLite + bcrypt + JWT.
"""
import sqlite3
import bcrypt
import jwt
import time
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "civgame.db"
JWT_SECRET = os.environ.get("JWT_SECRET", "civgame-secret-key-change-in-production")
TOKEN_EXPIRY = 86400 * 30  # 30 days


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
    """Verify JWT token. Returns user dict or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("exp", 0) < time.time():
            return None
        return {"id": payload["user_id"], "username": payload["username"]}
    except (jwt.InvalidTokenError, Exception):
        return None


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


# Initialize DB on import
init_db()
