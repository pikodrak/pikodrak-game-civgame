"""Random procedural map: continents grown by random walk + latitude biomes."""
import random

from civgame.constants import Terrain
from civgame.hex import hex_neighbors


def generate_map(width, height, seed=None):
    """Generate a hex map with continents and varied terrain."""
    if seed is not None:
        random.seed(seed)

    tiles = {}
    for q in range(width):
        for r in range(height):
            tiles[(q, r)] = Terrain.WATER

    num_land = int(width * height * 0.55)
    land_tiles = set()

    area = width * height
    num_continents = max(3, min(15, int(area / 300)))
    seeds = []
    for _ in range(num_continents):
        sq = random.randint(2, width - 3)
        sr = random.randint(2, height - 3)
        seeds.append((sq, sr))
        land_tiles.add((sq, sr))

    # Grow continents
    while len(land_tiles) < num_land:
        seed_tile = random.choice(list(land_tiles))
        neighbors = hex_neighbors(*seed_tile)
        valid = [(nq, nr) for nq, nr in neighbors
                 if 0 <= nq < width and 0 <= nr < height]
        if valid:
            chosen = random.choice(valid)
            land_tiles.add(chosen)

    # Biomes by latitude band
    for (q, r) in land_tiles:
        lat = r / height
        rand = random.random()
        if lat < 0.15 or lat > 0.85:  # Polar-ish
            if rand < 0.4:
                tiles[(q, r)] = Terrain.HILLS
            elif rand < 0.7:
                tiles[(q, r)] = Terrain.PLAINS
            else:
                tiles[(q, r)] = Terrain.MOUNTAIN
        elif 0.35 < lat < 0.65:  # Equatorial
            if rand < 0.3:
                tiles[(q, r)] = Terrain.DESERT
            elif rand < 0.5:
                tiles[(q, r)] = Terrain.PLAINS
            elif rand < 0.8:
                tiles[(q, r)] = Terrain.GRASS
            else:
                tiles[(q, r)] = Terrain.HILLS
        else:  # Temperate
            if rand < 0.3:
                tiles[(q, r)] = Terrain.GRASS
            elif rand < 0.55:
                tiles[(q, r)] = Terrain.FOREST
            elif rand < 0.75:
                tiles[(q, r)] = Terrain.PLAINS
            elif rand < 0.9:
                tiles[(q, r)] = Terrain.HILLS
            else:
                tiles[(q, r)] = Terrain.MOUNTAIN

    # Coastal tiles
    for q in range(width):
        for r in range(height):
            if tiles[(q, r)] == Terrain.WATER:
                for nq, nr in hex_neighbors(q, r):
                    if (nq, nr) in tiles and tiles[(nq, nr)] not in (Terrain.WATER, Terrain.COAST):
                        tiles[(q, r)] = Terrain.COAST
                        break

    return tiles
