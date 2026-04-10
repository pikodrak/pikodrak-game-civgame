#!/usr/bin/env python3
"""Generate detailed Civ2-style building icons at 96x96 with proper shading."""
from PIL import Image, ImageDraw
import os

OUT = "static/img/buildings"
os.makedirs(OUT, exist_ok=True)
SIZE = 96

def shade(r, g, b):
    hi = (min(255, r+45), min(255, g+45), min(255, b+45))
    mid = (r, g, b)
    sh = (max(0, r-35), max(0, g-35), max(0, b-35))
    dsh = (max(0, r-65), max(0, g-65), max(0, b-65))
    return hi, mid, sh, dsh

def rect3d(d, x, y, w, h, hi, mid, sh):
    d.rectangle([x, y, x+w, y+h], fill=mid)
    d.rectangle([x, y, x+2, y+h], fill=hi)
    d.rectangle([x, y, x+w, y+2], fill=hi)
    d.rectangle([x+w-2, y, x+w, y+h], fill=sh)
    d.rectangle([x, y+h-2, x+w, y+h], fill=sh)

def roof(d, x1, y_top, x2, y_base, color):
    hi, mid, sh, _ = shade(*color)
    cx = (x1 + x2) // 2
    d.polygon([(cx, y_top), (x1-4, y_base), (x2+4, y_base)], fill=sh)
    d.polygon([(cx, y_top), (x1-2, y_base), (cx, y_base)], fill=mid)
    d.polygon([(cx, y_top+2), (x1, y_base), (cx-2, y_base)], fill=hi)

def window(d, x, y, w=6, h=8, color=(180, 210, 240)):
    d.rectangle([x, y, x+w, y+h], fill=color)
    d.rectangle([x, y, x+w, y+1], fill=(140, 170, 200))
    d.line([(x+w//2, y), (x+w//2, y+h)], fill=(120, 140, 160))
    d.line([(x, y+h//2), (x+w, y+h//2)], fill=(120, 140, 160))

def door(d, x, y, w=10, h=16, color=(101, 67, 33)):
    hi, mid, sh, _ = shade(*color)
    d.rectangle([x, y, x+w, y+h], fill=mid)
    d.rectangle([x, y, x+2, y+h], fill=hi)
    d.rectangle([x+w-2, y, x+w, y+h], fill=sh)
    d.ellipse([x+w-4, y+h//2-1, x+w-2, y+h//2+1], fill=(200, 180, 40))

# === BUILDINGS ===

def gen_palace():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(180, 160, 120)
    # Main building
    rect3d(d, 16, 40, 62, 38, hi, mid, sh)
    # Central tower
    rect3d(d, 34, 18, 26, 24, hi, mid, sh)
    # Tower roof (gold dome)
    d.ellipse([36, 8, 58, 24], fill=(200, 170, 40))
    d.ellipse([38, 10, 56, 22], fill=(230, 200, 60))
    d.ellipse([42, 12, 52, 18], fill=(250, 225, 90))
    # Spire
    d.polygon([(47, 2), (45, 10), (49, 10)], fill=(200, 170, 40))
    # Columns
    for cx in [22, 34, 56, 68]:
        d.rectangle([cx, 44, cx+4, 76], fill=hi)
        d.rectangle([cx+1, 44, cx+3, 76], fill=(200, 190, 170))
        d.ellipse([cx-1, 42, cx+5, 47], fill=hi)
    # Door
    d.rectangle([40, 58, 54, 78], fill=(120, 80, 40))
    d.arc([40, 52, 54, 64], 180, 360, fill=hi, width=2)
    # Windows
    window(d, 22, 50, 8, 10)
    window(d, 64, 50, 8, 10)
    # Steps
    for i in range(3):
        d.rectangle([30-i*4, 78+i*4, 64+i*4, 82+i*4], fill=(max(0,mid[0]-i*15), max(0,mid[1]-i*15), max(0,mid[2]-i*15)))
    # Flags
    d.line([(20, 40), (20, 28)], fill=(101, 67, 33), width=2)
    d.polygon([(20, 28), (30, 31), (20, 34)], fill=(180, 40, 40))
    d.line([(74, 40), (74, 28)], fill=(101, 67, 33), width=2)
    d.polygon([(74, 28), (84, 31), (74, 34)], fill=(180, 40, 40))
    return img

def gen_granary():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(160, 130, 80)
    # Main barn
    rect3d(d, 18, 42, 58, 40, hi, mid, sh)
    # Thatched roof
    d.polygon([(48, 18), (10, 44), (84, 44)], fill=(140, 120, 50))
    d.polygon([(48, 20), (14, 44), (48, 44)], fill=(160, 140, 60))
    d.polygon([(48, 22), (18, 42), (46, 42)], fill=(180, 160, 80))
    # Hay texture lines on roof
    for yy in range(26, 44, 4):
        w = (yy - 18) * 2
        d.line([(48-w//2, yy), (48+w//2, yy)], fill=(130, 110, 45), width=1)
    # Large door
    d.rectangle([34, 54, 60, 82], fill=(120, 80, 40))
    d.line([(34, 54), (60, 82)], fill=(100, 65, 30), width=1)
    d.line([(60, 54), (34, 82)], fill=(100, 65, 30), width=1)
    # Wheat sheaves
    for sx in [22, 68]:
        d.line([(sx, 82), (sx, 62)], fill=(200, 180, 60), width=3)
        d.ellipse([sx-4, 56, sx+4, 64], fill=(220, 200, 80))
        d.ellipse([sx-3, 58, sx+3, 62], fill=(240, 220, 100))
    # Ground
    d.rectangle([14, 82, 82, 86], fill=(120, 100, 60))
    return img

def gen_library():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(170, 155, 135)
    # Main building
    rect3d(d, 16, 38, 62, 44, hi, mid, sh)
    # Pediment (triangular top)
    d.polygon([(48, 18), (12, 40), (82, 40)], fill=sh)
    d.polygon([(48, 20), (16, 40), (48, 40)], fill=mid)
    d.polygon([(48, 22), (20, 38), (46, 38)], fill=hi)
    # Columns (4 classical)
    for cx in [22, 34, 52, 64]:
        d.rectangle([cx, 40, cx+5, 80], fill=(210, 200, 185))
        d.rectangle([cx+1, 40, cx+4, 80], fill=(225, 218, 200))
        d.rectangle([cx-1, 38, cx+6, 42], fill=hi)
        d.rectangle([cx-1, 78, cx+6, 82], fill=sh)
    # Books visible through windows
    for bx in [28, 44, 58]:
        d.rectangle([bx, 52, bx+8, 70], fill=(40, 40, 50))
        for by in range(54, 68, 4):
            colors = [(180, 40, 40), (40, 80, 160), (40, 140, 60), (180, 140, 40)]
            d.rectangle([bx+1, by, bx+7, by+3], fill=colors[(by-54)//4 % 4])
    # Steps
    for i in range(2):
        d.rectangle([18-i*6, 82+i*4, 76+i*6, 86+i*4], fill=(190-i*20, 180-i*20, 165-i*20))
    return img

def gen_walls():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(150, 140, 120)
    # Wall sections
    rect3d(d, 8, 40, 78, 42, hi, mid, sh)
    # Stone texture
    for yy in range(42, 80, 8):
        offset = 12 if (yy // 8) % 2 == 0 else 0
        for xx in range(10+offset, 84, 24):
            d.rectangle([xx, yy, xx+20, yy+6], outline=sh, width=1)
    # Battlements (crenellations)
    for bx in range(8, 86, 14):
        rect3d(d, bx, 30, 10, 12, hi, mid, sh)
    # Gate
    d.rectangle([34, 50, 60, 82], fill=(80, 55, 30))
    d.arc([34, 42, 60, 58], 180, 360, fill=mid, width=3)
    # Portcullis lines
    for xx in range(38, 58, 4):
        d.line([(xx, 50), (xx, 82)], fill=(100, 100, 105), width=1)
    d.line([(36, 60), (58, 60)], fill=(100, 100, 105), width=1)
    d.line([(36, 70), (58, 70)], fill=(100, 100, 105), width=1)
    # Tower left
    rect3d(d, 2, 28, 16, 54, hi, mid, sh)
    rect3d(d, 0, 24, 8, 8, hi, mid, sh)
    rect3d(d, 10, 24, 8, 8, hi, mid, sh)
    # Tower right
    rect3d(d, 78, 28, 16, 54, hi, mid, sh)
    rect3d(d, 76, 24, 8, 8, hi, mid, sh)
    rect3d(d, 86, 24, 8, 8, hi, mid, sh)
    return img

def gen_marketplace():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(160, 120, 70)
    # Main structure
    rect3d(d, 14, 44, 66, 38, hi, mid, sh)
    # Awning/canopy (red striped)
    for i in range(0, 70, 10):
        color = (180, 40, 30) if (i // 10) % 2 == 0 else (220, 200, 170)
        d.polygon([(14+i, 34), (14+i+10, 34), (14+i+12, 44), (14+i-2, 44)], fill=color)
    # Counter/stall
    rect3d(d, 20, 56, 54, 8, (200, 180, 100), (180, 160, 80), (150, 130, 60))
    # Goods on counter
    d.ellipse([24, 52, 32, 58], fill=(200, 40, 30))  # Apples
    d.ellipse([34, 52, 42, 58], fill=(230, 200, 40))  # Cheese/gold
    d.ellipse([44, 52, 52, 58], fill=(100, 60, 30))  # Bread
    d.ellipse([54, 52, 62, 58], fill=(60, 140, 60))  # Veggies
    # Columns
    for cx in [16, 76]:
        d.rectangle([cx, 34, cx+4, 80], fill=(139, 90, 43))
    # Coin sign
    d.ellipse([40, 22, 56, 38], fill=(200, 170, 40))
    d.ellipse([42, 24, 54, 36], fill=(230, 200, 60))
    d.text((45, 26), "$", fill=(180, 140, 20))
    # Baskets
    for bx in [20, 60]:
        d.polygon([(bx, 82), (bx-4, 72), (bx+10, 72), (bx+6, 82)], fill=(180, 140, 70))
    return img

def gen_aqueduct():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(160, 150, 130)
    # Arches (3)
    for ax in [6, 34, 62]:
        # Pillar left
        rect3d(d, ax, 30, 10, 56, hi, mid, sh)
        # Arch
        d.arc([ax+8, 46, ax+30, 78], 180, 360, fill=sh, width=3)
        d.arc([ax+10, 48, ax+28, 76], 180, 360, fill=mid, width=2)
    # Right end pillar
    rect3d(d, 84, 30, 10, 56, hi, mid, sh)
    # Water channel on top
    rect3d(d, 4, 26, 88, 8, (100, 140, 180), (70, 120, 170), (50, 90, 140))
    # Water flowing
    d.rectangle([6, 28, 90, 32], fill=(80, 150, 200))
    d.rectangle([8, 29, 88, 31], fill=(120, 180, 220))
    # Top rail
    rect3d(d, 4, 22, 88, 6, hi, mid, sh)
    return img

def gen_temple():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(190, 175, 150)
    # Base platform
    rect3d(d, 12, 72, 72, 10, hi, mid, sh)
    # Main building
    rect3d(d, 20, 40, 56, 34, hi, mid, sh)
    # Pediment
    d.polygon([(48, 20), (16, 42), (80, 42)], fill=sh)
    d.polygon([(48, 22), (20, 42), (48, 42)], fill=mid)
    # Columns (6)
    for cx in [22, 32, 42, 52, 62, 72]:
        d.rectangle([cx, 42, cx+3, 72], fill=(220, 210, 195))
        d.rectangle([cx-1, 40, cx+4, 43], fill=hi)
        d.rectangle([cx-1, 71, cx+4, 74], fill=sh)
    # Inner sanctum (dark)
    d.rectangle([36, 48, 58, 72], fill=(60, 50, 40))
    # Altar glow
    d.ellipse([42, 54, 52, 64], fill=(220, 180, 60, 180))
    d.ellipse([44, 56, 50, 62], fill=(250, 220, 100, 200))
    # Steps
    for i in range(3):
        d.rectangle([14-i*3, 82+i*3, 82+i*3, 85+i*3], fill=(180-i*15, 165-i*15, 140-i*15))
    return img

def gen_monastery():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(165, 150, 125)
    # Main building
    rect3d(d, 14, 44, 66, 38, hi, mid, sh)
    roof(d, 14, 26, 80, 44, (140, 90, 50))
    # Bell tower
    rect3d(d, 38, 10, 18, 36, hi, mid, sh)
    # Bell opening
    d.arc([40, 14, 54, 26], 180, 360, fill=sh, width=2)
    d.rectangle([40, 20, 54, 26], fill=(60, 50, 40))
    # Bell
    d.ellipse([44, 16, 50, 24], fill=(200, 170, 40))
    # Cross on top
    d.rectangle([46, 2, 48, 12], fill=(200, 170, 40))
    d.rectangle([43, 4, 51, 6], fill=(200, 170, 40))
    # Windows (arched)
    for wx in [20, 62]:
        d.rectangle([wx, 54, wx+10, 68], fill=(180, 210, 240))
        d.arc([wx, 50, wx+10, 60], 180, 360, fill=mid, width=2)
    # Door
    d.rectangle([40, 60, 54, 82], fill=(101, 67, 33))
    d.arc([40, 54, 54, 66], 180, 360, fill=mid, width=2)
    # Garden path
    d.rectangle([42, 82, 52, 90], fill=(160, 140, 100))
    return img

def gen_castle():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(140, 135, 120)
    # Main keep
    rect3d(d, 24, 32, 46, 50, hi, mid, sh)
    # Stone texture
    for yy in range(34, 80, 7):
        off = 8 if (yy//7)%2 else 0
        for xx in range(26+off, 68, 16):
            d.rectangle([xx, yy, xx+14, yy+5], outline=sh, width=1)
    # Towers (4 corners)
    for tx in [8, 72]:
        rect3d(d, tx, 24, 16, 58, hi, mid, sh)
        # Battlements
        for bx in range(tx, tx+16, 6):
            rect3d(d, bx, 18, 4, 8, hi, mid, sh)
        # Tower roof (cone)
        d.polygon([(tx+8, 6), (tx-2, 20), (tx+18, 20)], fill=(120, 50, 40))
        d.polygon([(tx+8, 8), (tx, 20), (tx+8, 20)], fill=(150, 65, 50))
    # Gate
    d.rectangle([38, 56, 56, 82], fill=(80, 55, 30))
    d.arc([38, 48, 56, 64], 180, 360, fill=mid, width=3)
    # Central battlements
    for bx in range(26, 68, 8):
        rect3d(d, bx, 26, 6, 8, hi, mid, sh)
    # Flag
    d.line([(47, 26), (47, 10)], fill=(101, 67, 33), width=2)
    d.polygon([(47, 10), (58, 14), (47, 18)], fill=(40, 40, 160))
    return img

def gen_university():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(160, 140, 110)
    # Main building
    rect3d(d, 10, 40, 74, 42, hi, mid, sh)
    # Roof
    roof(d, 10, 22, 84, 42, (130, 80, 45))
    # Clock tower
    rect3d(d, 38, 6, 18, 38, hi, mid, sh)
    # Clock
    d.ellipse([40, 10, 54, 24], fill=(220, 215, 200))
    d.ellipse([42, 12, 52, 22], fill=(240, 235, 220))
    d.line([(47, 17), (47, 13)], fill=(40, 40, 40), width=2)
    d.line([(47, 17), (51, 17)], fill=(40, 40, 40), width=2)
    # Pointed roof on tower
    d.polygon([(47, 0), (36, 8), (58, 8)], fill=(130, 80, 45))
    # Windows (rows)
    for wx in [16, 28, 58, 70]:
        window(d, wx, 50, 8, 12)
    for wx in [16, 28, 58, 70]:
        window(d, wx, 66, 8, 10)
    # Main entrance
    door(d, 40, 60, 14, 22)
    d.arc([40, 54, 54, 66], 180, 360, fill=hi, width=2)
    # Steps
    d.rectangle([36, 82, 58, 86], fill=sh)
    d.rectangle([32, 86, 62, 90], fill=(mid[0]-15, mid[1]-15, mid[2]-15))
    return img

def gen_bank():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(175, 165, 145)
    # Main building (neoclassical)
    rect3d(d, 14, 38, 66, 44, hi, mid, sh)
    # Pediment
    d.polygon([(48, 16), (10, 40), (84, 40)], fill=sh)
    d.polygon([(48, 18), (14, 40), (48, 40)], fill=mid)
    # Columns (6 grand)
    for cx in [18, 28, 38, 52, 62, 72]:
        d.rectangle([cx, 40, cx+4, 80], fill=(215, 205, 190))
        d.rectangle([cx-1, 38, cx+5, 42], fill=hi)
        d.rectangle([cx-1, 78, cx+5, 82], fill=sh)
    # Large coin emblem in pediment
    d.ellipse([38, 22, 56, 38], fill=(200, 170, 40))
    d.ellipse([40, 24, 54, 36], fill=(230, 200, 60))
    d.ellipse([43, 27, 51, 33], fill=(200, 170, 40))
    # Heavy door
    d.rectangle([38, 56, 56, 80], fill=(80, 55, 30))
    d.rectangle([38, 56, 47, 80], fill=(90, 65, 35))
    # Steps
    for i in range(3):
        d.rectangle([12-i*4, 82+i*3, 82+i*4, 85+i*3], fill=(165-i*15, 155-i*15, 135-i*15))
    return img

def gen_observatory():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(150, 145, 135)
    # Base building
    rect3d(d, 22, 50, 50, 32, hi, mid, sh)
    # Dome
    d.ellipse([24, 22, 70, 56], fill=sh)
    d.ellipse([26, 24, 68, 54], fill=mid)
    d.ellipse([30, 26, 64, 48], fill=hi)
    # Dome slit (telescope opening)
    d.rectangle([44, 24, 50, 46], fill=(40, 40, 60))
    # Telescope
    d.line([(47, 36), (62, 14)], fill=(120, 120, 130), width=4)
    d.ellipse([60, 10, 68, 18], fill=(100, 100, 110))
    # Windows
    window(d, 28, 60, 8, 12)
    window(d, 58, 60, 8, 12)
    # Door
    door(d, 40, 64, 14, 18)
    # Stars (decorative)
    for sx, sy in [(16, 14), (80, 20), (12, 32), (82, 8)]:
        d.ellipse([sx-2, sy-2, sx+2, sy+2], fill=(240, 240, 200))
    return img

def gen_factory():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(140, 120, 100)
    # Main building
    rect3d(d, 10, 44, 60, 38, hi, mid, sh)
    # Saw-tooth roof
    for rx in range(10, 70, 20):
        d.polygon([(rx, 44), (rx+10, 28), (rx+20, 44)], fill=(130, 110, 90))
        d.polygon([(rx, 44), (rx+10, 30), (rx+10, 44)], fill=(150, 130, 110))
        # Glass on one side
        d.polygon([(rx+10, 30), (rx+20, 44), (rx+10, 44)], fill=(160, 190, 210))
    # Smokestack
    rect3d(d, 72, 14, 14, 68, (130, 120, 115), (110, 100, 95), (85, 75, 70))
    # Smoke
    d.ellipse([68, 4, 82, 16], fill=(140, 140, 140, 150))
    d.ellipse([64, -2, 80, 10], fill=(160, 160, 160, 100))
    d.ellipse([72, -6, 86, 6], fill=(180, 180, 180, 80))
    # Windows
    for wx in range(16, 60, 14):
        window(d, wx, 56, 8, 10)
    # Loading dock
    d.rectangle([14, 72, 38, 82], fill=(100, 80, 60))
    d.rectangle([14, 72, 38, 74], fill=(120, 100, 80))
    # Gear emblem
    d.ellipse([44, 66, 56, 78], fill=(100, 100, 110))
    d.ellipse([46, 68, 54, 76], fill=(130, 130, 140))
    return img

def gen_power_plant():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(130, 125, 120)
    # Main building
    rect3d(d, 10, 44, 52, 38, hi, mid, sh)
    # Flat roof
    d.rectangle([8, 40, 64, 46], fill=sh)
    # Two smokestacks
    for sx in [66, 80]:
        rect3d(d, sx, 16, 10, 66, hi, mid, sh)
        d.ellipse([sx-1, 12, sx+11, 20], fill=sh)
    # Smoke
    d.ellipse([62, 4, 78, 16], fill=(140, 140, 140, 150))
    d.ellipse([76, 2, 92, 14], fill=(150, 150, 150, 120))
    # Lightning bolt emblem
    d.polygon([(30, 50), (38, 50), (34, 60), (42, 60), (28, 76), (32, 64), (24, 64)], fill=(230, 200, 40))
    # Windows
    for wx in [14, 28, 44]:
        window(d, wx, 60, 8, 10)
    # Pipes
    d.line([(62, 60), (66, 60)], fill=(120, 120, 130), width=3)
    d.line([(62, 70), (66, 70)], fill=(120, 120, 130), width=3)
    return img

def gen_nuclear_plant():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(160, 155, 150)
    # Cooling tower 1 (hyperboloid shape)
    d.polygon([(14, 82), (10, 50), (16, 20), (36, 20), (42, 50), (38, 82)], fill=sh)
    d.polygon([(16, 80), (12, 50), (18, 22), (26, 22), (28, 50), (26, 80)], fill=mid)
    d.polygon([(18, 78), (14, 50), (20, 24), (24, 24), (26, 50), (24, 78)], fill=hi)
    # Steam from tower 1
    d.ellipse([14, 8, 34, 22], fill=(200, 200, 200, 120))
    d.ellipse([18, 2, 30, 14], fill=(220, 220, 220, 80))
    # Cooling tower 2
    d.polygon([(54, 82), (50, 50), (56, 20), (76, 20), (82, 50), (78, 82)], fill=sh)
    d.polygon([(56, 80), (52, 50), (58, 22), (66, 22), (68, 50), (66, 80)], fill=mid)
    # Steam
    d.ellipse([54, 8, 74, 22], fill=(200, 200, 200, 120))
    # Reactor building (between towers)
    rect3d(d, 34, 52, 24, 30, hi, mid, sh)
    # Radiation symbol
    d.ellipse([40, 58, 52, 70], fill=(230, 200, 40))
    d.ellipse([43, 61, 49, 67], fill=(40, 40, 40))
    return img

def gen_barracks():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(140, 110, 80)
    # Main building (long, low)
    rect3d(d, 8, 46, 78, 36, hi, mid, sh)
    # Flat/low roof
    roof(d, 8, 34, 86, 48, (120, 80, 45))
    # Windows (many, military style)
    for wx in range(14, 80, 12):
        window(d, wx, 56, 6, 10, (160, 180, 200))
    # Central door with emblem
    door(d, 40, 60, 14, 22)
    # Crossed swords emblem above door
    d.line([(42, 50), (52, 40)], fill=(180, 180, 190), width=2)
    d.line([(52, 50), (42, 40)], fill=(180, 180, 190), width=2)
    # Flag pole
    d.line([(47, 34), (47, 16)], fill=(101, 67, 33), width=2)
    d.polygon([(47, 16), (60, 20), (47, 24)], fill=(180, 40, 40))
    # Training dummy
    d.line([(82, 82), (82, 60)], fill=(139, 90, 43), width=3)
    d.line([(76, 68), (88, 68)], fill=(139, 90, 43), width=3)
    d.ellipse([78, 56, 86, 64], fill=(180, 150, 100))
    return img

def gen_harbor():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    # Water
    d.rectangle([0, 60, 96, 96], fill=(50, 100, 170))
    d.rectangle([0, 62, 96, 96], fill=(60, 110, 180))
    # Wave lines
    for yy in range(66, 94, 8):
        d.arc([0, yy-4, 32, yy+4], 0, 180, fill=(80, 130, 200), width=1)
        d.arc([32, yy-4, 64, yy+4], 180, 360, fill=(80, 130, 200), width=1)
        d.arc([64, yy-4, 96, yy+4], 0, 180, fill=(80, 130, 200), width=1)
    # Dock/pier
    hi, mid, sh, _ = shade(130, 90, 50)
    rect3d(d, 30, 52, 40, 10, hi, mid, sh)
    # Dock posts
    for px in [32, 46, 60, 66]:
        d.rectangle([px, 52, px+4, 72], fill=sh)
    # Warehouse
    whi, wmid, wsh, _ = shade(150, 130, 100)
    rect3d(d, 10, 26, 40, 30, whi, wmid, wsh)
    roof(d, 10, 14, 50, 28, (140, 80, 40))
    # Crane
    d.line([(62, 52), (62, 18)], fill=(100, 100, 110), width=3)
    d.line([(62, 20), (82, 20)], fill=(100, 100, 110), width=3)
    d.line([(82, 20), (82, 36)], fill=(140, 120, 60), width=2)
    # Crate hanging
    rect3d(d, 78, 34, 10, 10, (160, 130, 70), (140, 110, 50), (110, 80, 30))
    # Ship mast
    d.rectangle([74, 52, 76, 30], fill=(139, 90, 43))
    d.polygon([(76, 32), (88, 40), (76, 48)], fill=(230, 220, 200))
    return img

def gen_colosseum():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(180, 165, 140)
    # Oval structure
    d.ellipse([8, 20, 88, 80], fill=sh)
    d.ellipse([10, 22, 86, 78], fill=mid)
    # Inner arena (sand)
    d.ellipse([22, 32, 74, 68], fill=(210, 190, 140))
    d.ellipse([24, 34, 72, 66], fill=(220, 200, 150))
    # Arches around exterior (3 tiers)
    for yy_off, count in [(26, 10), (38, 8), (50, 6)]:
        for i in range(count):
            ax = 14 + i * 7 + (10-count)*3
            d.arc([ax, yy_off, ax+8, yy_off+10], 180, 360, fill=sh, width=1)
    # Seating tiers
    for tier in range(3):
        d.ellipse([18+tier*4, 28+tier*4, 78-tier*4, 72-tier*4], outline=(160, 145, 120), width=2)
    # Fighters in arena
    d.ellipse([38, 46, 44, 54], fill=(200, 40, 40))  # Fighter 1
    d.ellipse([52, 46, 58, 54], fill=(40, 40, 160))  # Fighter 2
    return img

def gen_forge():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(120, 90, 60)
    # Main building
    rect3d(d, 14, 42, 56, 40, hi, mid, sh)
    roof(d, 14, 28, 70, 44, (110, 70, 35))
    # Chimney with smoke
    rect3d(d, 58, 16, 12, 50, (120, 110, 100), (100, 90, 80), (75, 65, 55))
    d.ellipse([56, 6, 72, 18], fill=(140, 140, 140, 150))
    d.ellipse([60, 0, 74, 12], fill=(160, 160, 160, 100))
    # Forge fire glow
    d.rectangle([24, 52, 44, 72], fill=(40, 30, 25))
    d.ellipse([26, 56, 42, 70], fill=(200, 80, 20, 180))
    d.ellipse([28, 58, 40, 68], fill=(240, 140, 40, 200))
    d.ellipse([30, 60, 38, 66], fill=(255, 200, 80, 220))
    # Anvil
    d.polygon([(48, 72), (44, 66), (56, 66), (60, 72)], fill=(80, 80, 90))
    d.rectangle([46, 64, 58, 68], fill=(100, 100, 110))
    # Hammer
    d.line([(54, 52), (54, 64)], fill=(139, 90, 43), width=2)
    d.rectangle([50, 48, 58, 54], fill=(110, 110, 120))
    # Door
    d.rectangle([26, 72, 42, 82], fill=(80, 55, 30))
    return img

def gen_stable():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(140, 100, 55)
    # Main barn
    rect3d(d, 12, 42, 70, 40, hi, mid, sh)
    roof(d, 12, 26, 82, 44, (120, 80, 35))
    # Large door (open — dark inside)
    d.rectangle([30, 50, 56, 82], fill=(50, 35, 20))
    d.rectangle([30, 50, 43, 82], fill=(60, 40, 25))
    # Horse head peeking out
    horse_c = (140, 110, 70)
    d.ellipse([36, 52, 50, 68], fill=horse_c)  # head
    d.ellipse([38, 54, 48, 66], fill=(160, 130, 80))
    d.ellipse([42, 56, 46, 60], fill=(40, 30, 20))  # eye
    d.polygon([(40, 52), (38, 46), (44, 50)], fill=horse_c)  # ear
    # Hay bales
    d.ellipse([16, 68, 30, 82], fill=(200, 180, 80))
    d.ellipse([18, 70, 28, 80], fill=(220, 200, 100))
    # Horseshoe emblem
    d.arc([60, 48, 74, 62], 180, 360, fill=(120, 120, 130), width=3)
    d.arc([60, 48, 74, 62], 0, 180, fill=(120, 120, 130), width=3)
    # Fence
    for fx in [12, 76]:
        d.rectangle([fx, 68, fx+4, 82], fill=(139, 90, 43))
    d.line([(12, 72), (16, 72)], fill=(139, 90, 43), width=2)
    d.line([(76, 72), (84, 72)], fill=(139, 90, 43), width=2)
    return img

def gen_workshop():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(145, 120, 85)
    # Main building
    rect3d(d, 12, 40, 70, 42, hi, mid, sh)
    roof(d, 12, 26, 82, 42, (125, 85, 45))
    # Windows
    for wx in [18, 58]:
        window(d, wx, 52, 10, 12)
    # Large workshop door
    d.rectangle([34, 52, 56, 82], fill=(100, 70, 35))
    d.rectangle([34, 52, 45, 82], fill=(110, 78, 40))
    # Gear emblem on door
    d.ellipse([38, 58, 52, 72], fill=(130, 130, 140))
    d.ellipse([41, 61, 49, 69], fill=(100, 70, 35))
    # Lumber outside
    for ly in range(72, 84, 4):
        d.rectangle([68, ly, 86, ly+3], fill=(160, 120, 60))
        d.ellipse([84, ly, 88, ly+3], fill=(140, 100, 40))
    # Saw
    d.polygon([(10, 82), (6, 60), (10, 60)], fill=(160, 160, 170))
    for ty in range(62, 80, 3):
        d.polygon([(6, ty), (4, ty+2), (6, ty+2)], fill=(140, 140, 150))
    return img

def gen_school():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(170, 140, 100)
    # Main building
    rect3d(d, 14, 42, 66, 40, hi, mid, sh)
    roof(d, 14, 26, 80, 44, (150, 80, 40))
    # Bell tower small
    rect3d(d, 42, 16, 12, 12, hi, mid, sh)
    d.polygon([(48, 8), (40, 18), (56, 18)], fill=(150, 80, 40))
    d.ellipse([44, 18, 50, 24], fill=(200, 170, 40))  # bell
    # Windows
    for wx in [20, 34, 52, 66]:
        window(d, wx, 52, 8, 12)
    # Door
    door(d, 40, 62, 14, 20)
    # Blackboard visible through window
    d.rectangle([22, 54, 30, 62], fill=(40, 60, 40))
    # Book emblem
    d.rectangle([56, 54, 64, 62], fill=(40, 60, 160))
    d.rectangle([58, 55, 62, 61], fill=(200, 190, 170))
    # Steps
    d.rectangle([38, 82, 56, 86], fill=sh)
    return img

def gen_museum():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(185, 175, 160)
    # Grand building
    rect3d(d, 10, 38, 74, 44, hi, mid, sh)
    # Pediment with tympanum
    d.polygon([(48, 14), (6, 40), (88, 40)], fill=sh)
    d.polygon([(48, 16), (10, 40), (48, 40)], fill=mid)
    # Sculptures in pediment
    d.ellipse([30, 28, 38, 38], fill=(200, 190, 175))
    d.ellipse([56, 28, 64, 38], fill=(200, 190, 175))
    d.rectangle([44, 24, 50, 38], fill=(200, 190, 175))
    # Grand columns (8)
    for cx in range(14, 82, 10):
        d.rectangle([cx, 40, cx+4, 80], fill=(210, 202, 190))
        d.rectangle([cx-1, 38, cx+5, 42], fill=hi)
    # Entrance
    d.rectangle([38, 58, 56, 80], fill=(60, 50, 40))
    d.arc([38, 52, 56, 66], 180, 360, fill=hi, width=2)
    # Banner
    d.rectangle([40, 42, 54, 52], fill=(180, 40, 40))
    d.rectangle([42, 44, 52, 50], fill=(220, 40, 40))
    # Steps (grand)
    for i in range(4):
        d.rectangle([8-i*3, 82+i*3, 86+i*3, 85+i*3], fill=(175-i*12, 165-i*12, 150-i*12))
    return img

def gen_theater():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(160, 130, 100)
    # Main building
    rect3d(d, 14, 38, 66, 44, hi, mid, sh)
    # Curved/domed roof
    d.ellipse([12, 20, 82, 46], fill=(140, 90, 45))
    d.ellipse([14, 22, 80, 44], fill=(160, 105, 55))
    d.ellipse([18, 24, 76, 40], fill=(175, 118, 65))
    # Theater masks (comedy/tragedy)
    # Happy mask
    d.ellipse([24, 28, 40, 44], fill=(230, 210, 170))
    d.arc([28, 34, 36, 42], 0, 180, fill=(40, 40, 40), width=2)
    d.ellipse([28, 30, 32, 34], fill=(40, 40, 40))
    d.ellipse([34, 30, 38, 34], fill=(40, 40, 40))
    # Sad mask
    d.ellipse([54, 28, 70, 44], fill=(230, 210, 170))
    d.arc([58, 36, 66, 44], 180, 360, fill=(40, 40, 40), width=2)
    d.ellipse([58, 30, 62, 34], fill=(40, 40, 40))
    d.ellipse([64, 30, 68, 34], fill=(40, 40, 40))
    # Curtains
    d.rectangle([18, 50, 24, 80], fill=(160, 30, 30))
    d.rectangle([70, 50, 76, 80], fill=(160, 30, 30))
    # Stage area
    d.rectangle([24, 70, 70, 80], fill=(139, 90, 43))
    d.rectangle([26, 72, 68, 78], fill=(160, 110, 55))
    # Entrance
    door(d, 40, 60, 14, 20)
    return img

def gen_military_academy():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(130, 115, 95)
    # Main building (imposing)
    rect3d(d, 10, 38, 74, 44, hi, mid, sh)
    # Flat military roof
    d.rectangle([8, 34, 86, 40], fill=sh)
    # Symmetrical wings
    rect3d(d, 4, 44, 16, 38, hi, mid, sh)
    rect3d(d, 74, 44, 16, 38, hi, mid, sh)
    # Central entrance
    rect3d(d, 36, 30, 22, 52, (hi[0]+10, hi[1]+10, hi[2]+10), hi, mid)
    door(d, 40, 58, 14, 24)
    d.arc([40, 52, 54, 64], 180, 360, fill=hi, width=2)
    # Star emblem
    star_cx, star_cy = 47, 42
    d.polygon([(star_cx, 34), (star_cx-4, 46), (star_cx+6, 38), (star_cx-6, 38), (star_cx+4, 46)], fill=(200, 170, 40))
    # Windows
    for wx in [12, 78]:
        window(d, wx, 54, 8, 10)
        window(d, wx, 68, 8, 10)
    # Cannon decoration
    d.line([(8, 82), (20, 74)], fill=(80, 80, 90), width=3)
    d.ellipse([4, 78, 12, 86], fill=(80, 80, 90))
    return img

def gen_hospital():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(200, 195, 185)
    # Main building (white/clean)
    rect3d(d, 14, 38, 66, 44, hi, mid, sh)
    # Flat roof
    d.rectangle([12, 34, 82, 40], fill=sh)
    # Red cross
    d.rectangle([40, 14, 54, 34], fill=(200, 40, 40))
    d.rectangle([36, 20, 58, 28], fill=(200, 40, 40))
    # Inner cross (lighter)
    d.rectangle([42, 16, 52, 32], fill=(230, 60, 60))
    d.rectangle([38, 22, 56, 26], fill=(230, 60, 60))
    # Windows (many)
    for wx in [18, 30, 56, 68]:
        window(d, wx, 48, 8, 12)
    # Entrance (wide)
    d.rectangle([38, 62, 56, 82], fill=(180, 200, 220))
    d.rectangle([38, 62, 47, 82], fill=(190, 210, 230))
    # Ambulance cross on entrance
    d.rectangle([44, 66, 50, 78], fill=(200, 40, 40))
    d.rectangle([42, 70, 52, 74], fill=(200, 40, 40))
    # Steps
    d.rectangle([36, 82, 58, 86], fill=sh)
    return img

def gen_airport():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(160, 155, 145)
    # Terminal building
    rect3d(d, 10, 42, 60, 32, hi, mid, sh)
    # Curved roof (modern)
    d.ellipse([8, 28, 72, 50], fill=sh)
    d.ellipse([10, 30, 70, 48], fill=mid)
    d.ellipse([14, 32, 66, 44], fill=hi)
    # Control tower
    rect3d(d, 64, 24, 14, 50, hi, mid, sh)
    # Tower windows (wrap-around)
    d.rectangle([64, 26, 78, 34], fill=(160, 200, 230))
    d.rectangle([66, 28, 76, 32], fill=(180, 210, 240))
    # Tower top
    d.rectangle([62, 22, 80, 26], fill=sh)
    # Antenna
    d.line([(71, 22), (71, 10)], fill=(100, 100, 110), width=2)
    d.ellipse([67, 8, 75, 14], fill=(200, 40, 40))
    # Windows on terminal
    for wx in range(16, 60, 10):
        d.rectangle([wx, 42, wx+6, 54], fill=(160, 200, 230))
    # Runway line
    d.rectangle([0, 78, 96, 82], fill=(80, 80, 85))
    for rx in range(4, 92, 12):
        d.rectangle([rx, 79, rx+8, 81], fill=(220, 220, 220))
    # Small plane silhouette
    d.ellipse([10, 72, 30, 80], fill=(100, 100, 105))
    d.polygon([(16, 70), (24, 70), (28, 74), (12, 74)], fill=(90, 90, 95))
    return img

def gen_stadium():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(160, 155, 145)
    # Oval stadium
    d.ellipse([6, 18, 90, 78], fill=sh)
    d.ellipse([8, 20, 88, 76], fill=mid)
    # Seating tiers
    d.ellipse([12, 24, 84, 72], fill=(170, 160, 140))
    d.ellipse([16, 28, 80, 68], fill=(180, 170, 150))
    # Field (green)
    d.ellipse([22, 34, 74, 62], fill=(60, 140, 60))
    d.ellipse([24, 36, 72, 60], fill=(70, 155, 70))
    # Field lines
    d.line([(48, 36), (48, 60)], fill=(90, 180, 90), width=1)
    d.ellipse([40, 42, 56, 54], outline=(90, 180, 90), width=1)
    # Floodlights
    for lx, ly in [(8, 18), (84, 18), (8, 72), (84, 72)]:
        d.line([(lx, ly), (lx, ly-12)], fill=(120, 120, 130), width=2)
        d.ellipse([lx-3, ly-16, lx+3, ly-12], fill=(250, 240, 180))
    # Score/entrance
    d.rectangle([36, 74, 58, 82], fill=sh)
    d.rectangle([40, 76, 54, 80], fill=(200, 40, 40))
    return img

def gen_bunker():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    hi, mid, sh, _ = shade(110, 105, 95)
    # Ground level
    d.rectangle([0, 60, 96, 96], fill=(100, 90, 60))
    d.rectangle([0, 58, 96, 62], fill=(80, 100, 50))  # Grass
    # Bunker (mostly underground, dome top)
    d.ellipse([12, 36, 82, 72], fill=sh)
    d.ellipse([14, 38, 80, 70], fill=mid)
    d.ellipse([18, 40, 76, 66], fill=hi)
    # Entrance (gun slit)
    d.rectangle([34, 50, 60, 56], fill=(30, 30, 35))
    d.rectangle([36, 51, 58, 55], fill=(20, 20, 25))
    # Gun barrel
    d.line([(60, 53), (78, 50)], fill=(80, 80, 90), width=3)
    # Sandbags
    for sx in range(10, 86, 10):
        d.ellipse([sx, 62, sx+12, 70], fill=(160, 145, 100))
        d.ellipse([sx+1, 63, sx+11, 69], fill=(170, 155, 110))
    for sx in range(16, 80, 10):
        d.ellipse([sx, 68, sx+12, 76], fill=(155, 140, 95))
    # Camouflage
    d.ellipse([20, 40, 34, 50], fill=(80, 100, 50, 100))
    d.ellipse([60, 42, 74, 52], fill=(80, 100, 50, 100))
    # Antenna
    d.line([(47, 38), (47, 20)], fill=(100, 100, 110), width=2)
    d.line([(47, 22), (55, 28)], fill=(100, 100, 110), width=1)
    return img

# === GENERATE ALL ===
BUILDINGS = {
    "palace": gen_palace, "granary": gen_granary, "library": gen_library,
    "walls": gen_walls, "marketplace": gen_marketplace, "aqueduct": gen_aqueduct,
    "temple": gen_temple, "monastery": gen_monastery, "castle": gen_castle,
    "university": gen_university, "bank": gen_bank, "observatory": gen_observatory,
    "factory": gen_factory, "power_plant": gen_power_plant, "nuclear_plant": gen_nuclear_plant,
    "barracks": gen_barracks, "harbor": gen_harbor, "colosseum": gen_colosseum,
    "forge": gen_forge, "stable": gen_stable, "workshop": gen_workshop,
    "school": gen_school, "museum": gen_museum, "theater": gen_theater,
    "military_academy": gen_military_academy, "hospital": gen_hospital,
    "airport": gen_airport, "stadium": gen_stadium, "bunker": gen_bunker,
}

if __name__ == "__main__":
    for name, gen_func in BUILDINGS.items():
        img = gen_func()
        path = os.path.join(OUT, f"{name}.png")
        img.save(path)
        print(f"Generated {path}")
    print(f"\nDone! {len(BUILDINGS)} building icons generated.")
