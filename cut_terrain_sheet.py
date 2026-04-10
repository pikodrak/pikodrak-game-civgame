#!/usr/bin/env python3
"""
Cut an isometric terrain sprite sheet into individual tiles.
Replaces magenta (transparency key) with actual transparency.
Resizes diamond tiles to 128x128 for use in hex game.

Usage: python3 cut_terrain_sheet.py <sprite_sheet.png>
"""
from PIL import Image
import os
import sys

OUT = "static/img/terrain"
os.makedirs(OUT, exist_ok=True)

# Isometric diamond tile size in the sheet
TILE_W = 64
TILE_H = 32

# Magenta threshold for transparency replacement
MAGENTA_THRESHOLD = 200  # r > thresh, g < 50, b > thresh


def replace_magenta_with_alpha(img):
    """Replace magenta pixels with transparency."""
    img = img.convert("RGBA")
    data = list(img.getdata())
    new_data = []
    for r, g, b, a in data:
        if r > MAGENTA_THRESHOLD and g < 50 and b > MAGENTA_THRESHOLD:
            new_data.append((0, 0, 0, 0))
        else:
            new_data.append((r, g, b, 255))
    img.putdata(new_data)
    return img


def extract_tile(sheet, x, y, w=TILE_W, h=TILE_H):
    """Extract a tile from sprite sheet at pixel coordinates."""
    tile = sheet.crop((x, y, x + w, y + h))
    tile = replace_magenta_with_alpha(tile)
    # Resize to 128x128 for game use
    tile = tile.resize((128, 128), Image.LANCZOS)
    return tile


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 cut_terrain_sheet.py <sprite_sheet.png>")
        print("\nEdit the TILES dict below with correct x,y coordinates from your sheet.")
        sys.exit(1)

    sheet_path = sys.argv[1]
    sheet = Image.open(sheet_path)
    print(f"Sheet size: {sheet.size}")

    # ============================================================
    # EDIT THESE COORDINATES to match your sprite sheet layout!
    # Each entry: "game_name": (x_pixel, y_pixel)
    # Open the sheet in an image editor to find coordinates.
    # ============================================================
    TILES = {
        # Basic terrain - find the x,y of top-left corner of each diamond
        # Row 1 in the sheet (adjust y for each row)
        "water":    (0, 0),      # Ocean/deep water
        "coast":    (64, 0),     # Shallow water / coast
        "grass":    (0, 32),     # Grassland
        "plains":   (64, 32),    # Plains
        "forest":   (0, 64),     # Forest
        "hills":    (64, 64),    # Hills
        "mountain": (0, 96),     # Mountains
        "desert":   (64, 96),    # Desert
    }

    # Generate base + 4 variants per terrain type
    for name, (x, y) in TILES.items():
        print(f"  Extracting {name} at ({x}, {y})...", end=" ")
        try:
            base = extract_tile(sheet, x, y)
            base.save(os.path.join(OUT, f"{name}.png"))

            # Create 4 variants with slight brightness changes
            from PIL import ImageEnhance
            for v in range(4):
                vimg = base.copy()
                enhancer = ImageEnhance.Brightness(vimg)
                vimg = enhancer.enhance(0.95 + v * 0.03)
                vimg.save(os.path.join(OUT, f"{name}_{v}.png"))

            print(f"OK (base + 4 variants)")
        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\nDone! Check {OUT}/ for results.")
    print("NOTE: You probably need to adjust the TILES coordinates.")
    print("Open the sprite sheet in an image editor and find the x,y of each tile.")


if __name__ == "__main__":
    main()
