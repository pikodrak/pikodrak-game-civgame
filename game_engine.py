"""
Backward-compat shim. The engine was split into the ``civgame`` package
(see civgame/state.py, civgame/mixins/, civgame/ai/, civgame/data/…).

External modules (server.py, config_loader.py, run_sim.py, sim_report.py)
import from here — re-export the same objects so they keep working.
"""
from civgame import (
    Terrain,
    TERRAIN_YIELDS,
    TERRAIN_MOVE_COST,
    TERRAIN_DEFENSE,
    GAME_CONFIG,
    CITY_NAMES,
    TECHNOLOGIES,
    UNIT_TYPES,
    BUILDINGS,
    CIVILIZATIONS,
    IMPROVEMENTS,
    hex_neighbors,
    hex_distance,
    generate_map,
    generate_earth_map,
    GameState,
)

__all__ = [
    "Terrain", "TERRAIN_YIELDS", "TERRAIN_MOVE_COST", "TERRAIN_DEFENSE",
    "GAME_CONFIG", "CITY_NAMES",
    "TECHNOLOGIES", "UNIT_TYPES", "BUILDINGS", "CIVILIZATIONS", "IMPROVEMENTS",
    "hex_neighbors", "hex_distance",
    "generate_map", "generate_earth_map",
    "GameState",
]
