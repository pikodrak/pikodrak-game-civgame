"""CivGame — civilization-like turn-based strategy game engine."""
from .constants import (
    Terrain,
    TERRAIN_YIELDS,
    TERRAIN_MOVE_COST,
    TERRAIN_DEFENSE,
    GAME_CONFIG,
    CITY_NAMES,
)
from .data import TECHNOLOGIES, UNIT_TYPES, BUILDINGS, CIVILIZATIONS, IMPROVEMENTS, RESOURCES
from .hex import hex_neighbors, hex_distance, offset_to_cube
from .mapgen import generate_map, generate_earth_map
from .state import GameState

__all__ = [
    "Terrain",
    "TERRAIN_YIELDS", "TERRAIN_MOVE_COST", "TERRAIN_DEFENSE",
    "GAME_CONFIG", "CITY_NAMES",
    "TECHNOLOGIES", "UNIT_TYPES", "BUILDINGS", "CIVILIZATIONS", "IMPROVEMENTS", "RESOURCES",
    "hex_neighbors", "hex_distance", "offset_to_cube",
    "generate_map", "generate_earth_map",
    "GameState",
]
