"""Core game constants: terrain, runtime config, city name pool."""
from enum import Enum


class Terrain(str, Enum):
    GRASS = "grass"
    PLAINS = "plains"
    FOREST = "forest"
    HILLS = "hills"
    MOUNTAIN = "mountain"
    DESERT = "desert"
    WATER = "water"
    COAST = "coast"


TERRAIN_YIELDS = {
    Terrain.GRASS:    {"food": 2, "prod": 1, "gold": 0},
    Terrain.PLAINS:   {"food": 1, "prod": 2, "gold": 0},
    Terrain.FOREST:   {"food": 1, "prod": 2, "gold": 0},
    Terrain.HILLS:    {"food": 0, "prod": 3, "gold": 0},
    Terrain.MOUNTAIN: {"food": 0, "prod": 1, "gold": 1},
    Terrain.DESERT:   {"food": 0, "prod": 1, "gold": 1},
    Terrain.WATER:    {"food": 2, "prod": 0, "gold": 1},
    Terrain.COAST:    {"food": 1, "prod": 0, "gold": 2},
}

TERRAIN_MOVE_COST = {
    Terrain.GRASS: 1, Terrain.PLAINS: 1, Terrain.FOREST: 2,
    Terrain.HILLS: 2, Terrain.MOUNTAIN: 99, Terrain.DESERT: 1,
    Terrain.WATER: 99, Terrain.COAST: 99,
}

TERRAIN_DEFENSE = {
    Terrain.GRASS: 0, Terrain.PLAINS: 0, Terrain.FOREST: 25,
    Terrain.HILLS: 50, Terrain.MOUNTAIN: 0, Terrain.DESERT: -10,
    Terrain.WATER: 0, Terrain.COAST: 0,
}

# Runtime config populated by config_loader from game_config.ini.
# Mutated in place (clear/update) so references stay valid across modules.
GAME_CONFIG = {}
CITY_NAMES = {}  # civ_key -> [city names]
