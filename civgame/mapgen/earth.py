"""Earth-shaped map: approximates real continent outlines on a hex grid."""
import math
import random

from civgame.constants import Terrain
from civgame.hex import hex_neighbors


def generate_earth_map(width, height, seed=None):
    """Generate simplified Earth map with real continent shapes."""
    if seed is not None:
        random.seed(seed)

    tiles = {}
    for q in range(width):
        for r in range(height):
            tiles[(q, r)] = Terrain.WATER

    def is_land(nx, ny):
        """Rough continent outlines based on lat/lon proportions."""
        # nx = 0..1 (longitude), ny = 0..1 (latitude, 0=north pole, 1=south pole)
        # North America
        if 0.05 < nx < 0.25 and 0.15 < ny < 0.55:
            if nx < 0.08 and ny > 0.4: return False
            if ny < 0.2 and nx > 0.2: return True
            if 0.1 < nx < 0.22 and 0.2 < ny < 0.5: return True
            if 0.12 < nx < 0.18 and 0.48 < ny < 0.55: return True
            return ny < 0.45 and nx > 0.08
        # South America
        if 0.15 < nx < 0.32 and 0.55 < ny < 0.92:
            cx, cy = 0.22, 0.72
            dx, dy = (nx - cx) / 0.1, (ny - cy) / 0.2
            return dx * dx + dy * dy < 1.2
        # Europe
        if 0.42 < nx < 0.56 and 0.15 < ny < 0.40:
            if ny < 0.2: return nx > 0.48
            return True
        # Africa
        if 0.42 < nx < 0.60 and 0.38 < ny < 0.82:
            cx, cy = 0.50, 0.58
            dx, dy = (nx - cx) / 0.1, (ny - cy) / 0.22
            return dx * dx + dy * dy < 1.3
        # Asia
        if 0.55 < nx < 0.88 and 0.10 < ny < 0.52:
            if ny < 0.15: return nx > 0.65 and nx < 0.82
            if nx > 0.82 and ny > 0.35: return False
            return True
        # India
        if 0.62 < nx < 0.72 and 0.42 < ny < 0.58:
            return True
        # Southeast Asia / Indonesia
        if 0.72 < nx < 0.88 and 0.48 < ny < 0.62:
            return random.random() < 0.4
        # Australia
        if 0.78 < nx < 0.92 and 0.65 < ny < 0.82:
            cx, cy = 0.85, 0.73
            dx, dy = (nx - cx) / 0.07, (ny - cy) / 0.08
            return dx * dx + dy * dy < 1.0
        # Greenland
        if 0.28 < nx < 0.36 and 0.08 < ny < 0.22:
            return True
        # Japan
        if 0.84 < nx < 0.89 and 0.25 < ny < 0.38:
            return random.random() < 0.5
        # UK
        if 0.43 < nx < 0.47 and 0.18 < ny < 0.26:
            return True
        return False

    def pick_terrain(nx, ny, is_coast):
        """Choose terrain based on latitude (ny) and randomness."""
        if is_coast:
            return Terrain.COAST
        lat = abs(ny - 0.5) * 2  # 0=equator, 1=pole
        r = random.random()
        if lat > 0.85:
            return Terrain.MOUNTAIN if r < 0.3 else Terrain.PLAINS
        if lat > 0.6:
            return Terrain.FOREST if r < 0.5 else Terrain.HILLS if r < 0.7 else Terrain.PLAINS
        if lat > 0.3:
            if r < 0.3: return Terrain.FOREST
            if r < 0.5: return Terrain.PLAINS
            if r < 0.7: return Terrain.GRASS
            if r < 0.85: return Terrain.HILLS
            return Terrain.MOUNTAIN
        if r < 0.35: return Terrain.GRASS
        if r < 0.55: return Terrain.FOREST
        if r < 0.7: return Terrain.PLAINS
        if r < 0.85: return Terrain.HILLS
        return Terrain.DESERT if ny > 0.35 and ny < 0.45 else Terrain.GRASS

    # Fill land tiles
    for q in range(width):
        for r in range(height):
            nx = q / width
            ny = r / height
            noise = math.sin(q * 0.8) * 0.02 + math.cos(r * 0.6) * 0.02
            if is_land(nx + noise, ny + noise):
                tiles[(q, r)] = Terrain.GRASS  # placeholder

    # Add coasts around land
    for q in range(width):
        for r in range(height):
            if tiles[(q, r)] != Terrain.WATER:
                continue
            for nq, nr in hex_neighbors(q, r):
                if 0 <= nq < width and 0 <= nr < height:
                    if tiles.get((nq, nr), Terrain.WATER) not in (Terrain.WATER, Terrain.COAST):
                        tiles[(q, r)] = Terrain.COAST
                        break

    # Set actual terrain types based on latitude
    for q in range(width):
        for r in range(height):
            if tiles[(q, r)] in (Terrain.WATER, Terrain.COAST):
                continue
            nx, ny = q / width, r / height
            tiles[(q, r)] = pick_terrain(nx, ny, False)

    # Sahara desert band
    for q in range(width):
        for r in range(height):
            nx, ny = q / width, r / height
            if 0.42 < nx < 0.58 and 0.35 < ny < 0.48 and tiles[(q, r)] not in (Terrain.WATER, Terrain.COAST):
                if random.random() < 0.7:
                    tiles[(q, r)] = Terrain.DESERT

    # Mountains — major ranges
    def add_mountain_range(x1, y1, x2, y2, thickness=0.02):
        for q in range(width):
            for r in range(height):
                nx, ny = q / width, r / height
                dx, dy = x2 - x1, y2 - y1
                t = max(0, min(1, ((nx - x1) * dx + (ny - y1) * dy) / (dx * dx + dy * dy + 0.001)))
                px, py = x1 + t * dx, y1 + t * dy
                dist = math.sqrt((nx - px) ** 2 + (ny - py) ** 2)
                if dist < thickness and tiles[(q, r)] not in (Terrain.WATER, Terrain.COAST):
                    if random.random() < 0.6:
                        tiles[(q, r)] = Terrain.MOUNTAIN
                    elif random.random() < 0.5:
                        tiles[(q, r)] = Terrain.HILLS

    add_mountain_range(0.12, 0.20, 0.15, 0.45, 0.015)  # Rockies
    add_mountain_range(0.20, 0.60, 0.22, 0.85, 0.012)  # Andes
    add_mountain_range(0.46, 0.26, 0.52, 0.32, 0.012)  # Alps
    add_mountain_range(0.65, 0.28, 0.78, 0.35, 0.015)  # Himalayas
    add_mountain_range(0.58, 0.12, 0.58, 0.35, 0.008)  # Urals

    return tiles
