"""Map generators: random continents and Earth-shaped."""
from .earth import generate_earth_map
from .random_map import generate_map

__all__ = ["generate_earth_map", "generate_map"]
