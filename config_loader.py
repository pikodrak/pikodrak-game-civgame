"""
Hot-reloadable configuration loader for CivGame.
Reads game_config.ini and updates global game data.
Watches file modification time for automatic reload.
"""
import configparser
import os
import threading
import time

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "game_config.ini")
_last_mtime = 0
_lock = threading.Lock()


def _parse_int_or_none(val):
    val = val.strip()
    return int(val) if val else None


def _parse_float(val):
    return float(val.strip())


def _parse_tech(val):
    val = val.strip()
    return val if val else None


def load_config():
    """Load all game data from INI file. Returns dict of all sections."""
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)

    data = {"game": {}, "civilizations": {}, "unit_types": {}, "buildings": {},
            "improvements": {}, "terrain_yields": {}, "terrain_move_cost": {},
            "terrain_defense": {}}

    # [game] section
    if cfg.has_section("game"):
        g = data["game"]
        for key in cfg["game"]:
            val = cfg["game"][key]
            try:
                if "." in val:
                    g[key] = float(val)
                else:
                    g[key] = int(val)
            except ValueError:
                g[key] = val

    # [terrain_*] sections
    for section in ("terrain_yields", "terrain_move_cost", "terrain_defense"):
        if cfg.has_section(section):
            for key in cfg[section]:
                val = cfg[section][key]
                if "," in val:
                    parts = [int(x.strip()) for x in val.split(",")]
                    data[section][key] = {"food": parts[0], "prod": parts[1], "gold": parts[2]}
                else:
                    data[section][key] = int(val)

    # [civ.*] sections
    for section in cfg.sections():
        if section.startswith("civ."):
            civ_key = section[4:]
            c = dict(cfg[section])
            data["civilizations"][civ_key] = {
                "name": c.get("name", civ_key),
                "color": c.get("color", "#888"),
                "bonus": c.get("bonus", ""),
                "leader": c.get("leader", "Unknown"),
                "trait": c.get("trait", "aggressive"),
                "aggression": float(c.get("aggression", "0.5")),
                "loyalty": float(c.get("loyalty", "0.5")),
                "strategy": c.get("strategy", "balanced"),
            }

    # [unit.*] sections
    for section in cfg.sections():
        if section.startswith("unit."):
            unit_key = section[5:]
            u = dict(cfg[section])
            data["unit_types"][unit_key] = {
                "atk": int(u.get("atk", "0")),
                "def": int(u.get("def", "0")),
                "mov": int(u.get("mov", "2")),
                "cost": int(u.get("cost", "10")),
                "tech": _parse_tech(u.get("tech", "")),
                "cat": u.get("cat", "melee"),
            }

    # [building.*] sections
    for section in cfg.sections():
        if section.startswith("building."):
            bld_key = section[9:]
            b = dict(cfg[section])
            data["buildings"][bld_key] = {
                "cost": int(b.get("cost", "50")),
                "tech": _parse_tech(b.get("tech", "")),
                "food": int(b.get("food", "0")),
                "prod": int(b.get("prod", "0")),
                "gold": int(b.get("gold", "0")),
                "science": int(b.get("science", "0")),
                "culture": int(b.get("culture", "0")),
                "defense": int(b.get("defense", "0")),
                "happiness": int(b.get("happiness", "0")),
            }

    # [improvement.*] sections
    for section in cfg.sections():
        if section.startswith("improvement."):
            imp_key = section[12:]
            im = dict(cfg[section])
            data["improvements"][imp_key] = {
                "tech": _parse_tech(im.get("tech", "")),
                "turns": int(im.get("turns", "4")),
                "terrain": [t.strip() for t in im.get("terrain", "").split(",") if t.strip()],
                "food": int(im.get("food", "0")),
                "prod": int(im.get("prod", "0")),
                "gold": int(im.get("gold", "0")),
            }

    return data


def apply_config(data):
    """Apply loaded config to game_engine globals."""
    import game_engine

    if data["civilizations"]:
        game_engine.CIVILIZATIONS.clear()
        game_engine.CIVILIZATIONS.update(data["civilizations"])

    if data["unit_types"]:
        game_engine.UNIT_TYPES.clear()
        game_engine.UNIT_TYPES.update(data["unit_types"])

    if data["buildings"]:
        game_engine.BUILDINGS.clear()
        game_engine.BUILDINGS.update(data["buildings"])

    if data["improvements"]:
        game_engine.IMPROVEMENTS.clear()
        game_engine.IMPROVEMENTS.update(data["improvements"])

    if data["terrain_yields"]:
        from game_engine import Terrain
        game_engine.TERRAIN_YIELDS.clear()
        for key, val in data["terrain_yields"].items():
            try:
                t = Terrain(key)
                game_engine.TERRAIN_YIELDS[t] = val
            except ValueError:
                pass

    if data["terrain_move_cost"]:
        from game_engine import Terrain
        game_engine.TERRAIN_MOVE_COST.clear()
        for key, val in data["terrain_move_cost"].items():
            try:
                t = Terrain(key)
                game_engine.TERRAIN_MOVE_COST[t] = val
            except ValueError:
                pass

    if data["terrain_defense"]:
        from game_engine import Terrain
        game_engine.TERRAIN_DEFENSE.clear()
        for key, val in data["terrain_defense"].items():
            try:
                t = Terrain(key)
                game_engine.TERRAIN_DEFENSE[t] = val
            except ValueError:
                pass

    # Store game settings for access
    game_engine.GAME_CONFIG = data.get("game", {})


def check_and_reload():
    """Check if config file changed and reload if so. Returns True if reloaded."""
    global _last_mtime
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if mtime > _last_mtime:
            with _lock:
                _last_mtime = mtime
                data = load_config()
                apply_config(data)
                return True
    except (OSError, Exception) as e:
        print(f"Config reload error: {e}")
    return False


def start_watcher(interval=2):
    """Start background thread that watches for config changes."""
    def _watch():
        while True:
            if check_and_reload():
                print(f"[CONFIG] Reloaded game_config.ini")
            time.sleep(interval)

    t = threading.Thread(target=_watch, daemon=True)
    t.start()


# Initial load
check_and_reload()
