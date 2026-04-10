#!/usr/bin/env python3
"""Generate Civ2-style terrain tiles at 128x128 with 4 variants each."""
from PIL import Image, ImageDraw
import os, random

OUT = "static/img/terrain"
os.makedirs(OUT, exist_ok=True)
SIZE = 128

def gen_grass(variant):
    random.seed(42 + variant)
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    base = (105+variant*4, 185+variant*3, 75+variant*3)  # Brighter green
    d.rectangle([0, 0, SIZE, SIZE], fill=base)
    # Subtle lighter patches only (no dark spots!)
    for _ in range(15):
        x, y = random.randint(0, SIZE-16), random.randint(0, SIZE-16)
        w, h = random.randint(12, 28), random.randint(10, 20)
        c = (base[0]+random.randint(5,15), base[1]+random.randint(5,12), base[2]+random.randint(3,10))
        d.ellipse([x, y, x+w, y+h], fill=c)
    # Grass blades (lighter green, more visible)
    for _ in range(60):
        x = random.randint(4, SIZE-4)
        y = random.randint(4, SIZE-4)
        h = random.randint(5, 11)
        lean = random.randint(-3, 3)
        green = (90+random.randint(0,30), 170+random.randint(0,30), 60+random.randint(0,20))
        d.line([(x, y), (x+lean, y-h)], fill=green, width=1)
    # Small flowers (brighter)
    for _ in range(3+variant):
        x, y = random.randint(10, SIZE-10), random.randint(10, SIZE-10)
        colors = [(240,220,80), (230,90,90), (200,200,240), (240,180,60)]
        d.ellipse([x-2, y-2, x+2, y+2], fill=random.choice(colors))
    return img

def gen_plains(variant):
    random.seed(100 + variant)
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    base = (190+variant*4, 175+variant*3, 105+variant*4)  # Warmer, lighter golden
    d.rectangle([0, 0, SIZE, SIZE], fill=base)
    # Subtle lighter swaths only
    for _ in range(10):
        x, y = random.randint(0, SIZE-20), random.randint(0, SIZE-16)
        w, h = random.randint(20, 40), random.randint(12, 24)
        c = (base[0]+random.randint(5,12), base[1]+random.randint(5,10), base[2]+random.randint(3,8))
        d.ellipse([x, y, x+w, y+h], fill=c)
    # Wheat stalks (brighter)
    for _ in range(50):
        x = random.randint(4, SIZE-4)
        y = random.randint(10, SIZE-4)
        h = random.randint(6, 14)
        lean = random.randint(-2, 2)
        stalk = (175+random.randint(0,25), 160+random.randint(0,20), 85+random.randint(0,20))
        d.line([(x, y), (x+lean, y-h)], fill=stalk, width=1)
        # Grain head
        d.ellipse([x+lean-1, y-h-2, x+lean+1, y-h], fill=(220+random.randint(0,20), 200+random.randint(0,15), 100))
    return img

def gen_forest(variant):
    random.seed(200 + variant)
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    # Medium green floor (not too dark!)
    base = (55+variant*3, 105+variant*4, 45+variant*3)
    d.rectangle([0, 0, SIZE, SIZE], fill=base)
    # Lighter ground patches (dappled sunlight)
    for _ in range(10):
        x, y = random.randint(0, SIZE-16), random.randint(0, SIZE-16)
        d.ellipse([x, y, x+random.randint(10,20), y+random.randint(8,14)], fill=(base[0]+8, base[1]+10, base[2]+6))
    # Trees (8-12 per tile)
    trees = []
    for _ in range(8 + variant):
        tx = random.randint(10, SIZE-10)
        ty = random.randint(20, SIZE-10)
        trees.append((ty, tx))  # Sort by Y for depth
    trees.sort()
    for ty, tx in trees:
        trunk_h = random.randint(10, 18)
        crown_r = random.randint(10, 18)
        trunk_c = (80+random.randint(0,20), 55+random.randint(0,15), 25+random.randint(0,10))
        # Trunk
        d.rectangle([tx-2, ty-trunk_h, tx+2, ty], fill=trunk_c)
        # Crown (dark bottom, lighter top for 3D effect)
        dark = (30+random.randint(0,20), 80+random.randint(0,30), 20+random.randint(0,15))
        mid = (40+random.randint(0,25), 110+random.randint(0,30), 30+random.randint(0,15))
        light = (60+random.randint(0,25), 135+random.randint(0,25), 45+random.randint(0,15))
        # Shadow
        d.ellipse([tx-crown_r, ty-trunk_h-crown_r+4, tx+crown_r, ty-trunk_h+crown_r+4], fill=dark)
        # Main crown
        d.ellipse([tx-crown_r+2, ty-trunk_h-crown_r+2, tx+crown_r-2, ty-trunk_h+crown_r+2], fill=mid)
        # Highlight (upper left)
        d.ellipse([tx-crown_r+4, ty-trunk_h-crown_r, tx+crown_r-6, ty-trunk_h+crown_r-6], fill=light)
    return img

def gen_hills(variant):
    random.seed(300 + variant)
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    # Green-brown base (grassier than plains)
    base_g = (110+variant*4, 135+variant*3, 65+variant*4)
    d.rectangle([0, 0, SIZE, SIZE], fill=base_g)
    # Ground patches
    for _ in range(10):
        x, y = random.randint(0, SIZE-20), random.randint(60, SIZE-10)
        d.ellipse([x, y, x+random.randint(12,24), y+random.randint(8,14)], fill=(base_g[0]-8, base_g[1]-8, base_g[2]-5))
    # Rolling hills — bigger, more contrast
    hills_data = [
        (5+variant*12, 55, 90, 55),    # back hill (large)
        (50+variant*8, 65, 75, 50),     # mid hill
        (-5+variant*15, 80, 100, 45),   # front hill (widest)
    ]
    hill_colors = [
        ((130, 150, 70), (145, 165, 80), (165, 185, 95)),   # back: darker
        ((120, 140, 60), (140, 160, 75), (160, 180, 90)),   # mid
        ((110, 135, 55), (135, 155, 70), (155, 175, 85)),   # front: darkest base, light top
    ]
    for i, (hx, hy, hw, hh) in enumerate(hills_data):
        dark, mid, light = hill_colors[i]
        # Full hill shadow
        d.ellipse([hx, hy-hh, hx+hw, hy], fill=dark)
        # Main body
        d.ellipse([hx+4, hy-hh+4, hx+hw-4, hy-4], fill=mid)
        # Sunlit upper-left area
        d.ellipse([hx+8, hy-hh+2, hx+hw*2//3, hy-hh//2], fill=light)
    # Grass tufts on hills
    for _ in range(30):
        x = random.randint(8, SIZE-8)
        y = random.randint(20, SIZE-8)
        green = (80+random.randint(0,40), 120+random.randint(0,30), 40+random.randint(0,20))
        d.line([(x, y), (x+random.randint(-2,2), y-random.randint(4,8))], fill=green, width=1)
    # Rocks scattered
    for _ in range(3+variant):
        rx, ry = random.randint(10, SIZE-15), random.randint(40, SIZE-10)
        rs = random.randint(5, 12)
        d.ellipse([rx, ry, rx+rs, ry+rs-3], fill=(135, 130, 110))
        d.ellipse([rx+1, ry+1, rx+rs-3, ry+rs-5], fill=(155, 150, 135))
    return img

def gen_mountain(variant):
    random.seed(400 + variant)
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    base = (100+variant*3, 95+variant*3, 90+variant*3)
    d.rectangle([0, 0, SIZE, SIZE], fill=base)
    # Back mountains
    for _ in range(2):
        mx = random.randint(10, 80)
        mw = random.randint(40, 60)
        mh = random.randint(40, 60)
        dark = (90, 85, 85)
        mid = (110, 105, 105)
        # Full mountain
        d.polygon([(mx, SIZE-20), (mx+mw//2, SIZE-20-mh), (mx+mw, SIZE-20)], fill=dark)
        d.polygon([(mx+4, SIZE-20), (mx+mw//2, SIZE-20-mh+4), (mx+mw//2, SIZE-20)], fill=mid)
    # Main peak
    peak_x = 30 + variant*12
    peak_w = 70
    peak_h = 80
    dark = (base[0]-15, base[1]-15, base[2]-12)
    mid = base
    light = (base[0]+20, base[1]+20, base[2]+20)
    # Shadow side (right)
    d.polygon([(peak_x, SIZE-10), (peak_x+peak_w//2, SIZE-10-peak_h), (peak_x+peak_w, SIZE-10)], fill=dark)
    # Lit side (left)
    d.polygon([(peak_x+2, SIZE-10), (peak_x+peak_w//2, SIZE-10-peak_h+2), (peak_x+peak_w//2, SIZE-10)], fill=mid)
    d.polygon([(peak_x+6, SIZE-12), (peak_x+peak_w//2, SIZE-10-peak_h+6), (peak_x+peak_w//3, SIZE-12)], fill=light)
    # Snow cap
    snow_y = SIZE - 10 - peak_h
    d.polygon([(peak_x+peak_w//2, snow_y), (peak_x+peak_w//2-14, snow_y+20), (peak_x+peak_w//2+14, snow_y+20)], fill=(230, 230, 235))
    d.polygon([(peak_x+peak_w//2, snow_y+2), (peak_x+peak_w//2-10, snow_y+16), (peak_x+peak_w//2, snow_y+16)], fill=(245, 245, 250))
    # Rocky texture
    for _ in range(10):
        rx = random.randint(peak_x+10, peak_x+peak_w-10)
        ry = random.randint(SIZE-10-peak_h+30, SIZE-15)
        d.line([(rx, ry), (rx+random.randint(-4,4), ry+random.randint(3,8))], fill=dark, width=1)
    return img

def gen_desert(variant):
    random.seed(500 + variant)
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    base = (225+variant*3, 210+variant*3, 160+variant*4)  # Brighter, more sandy
    d.rectangle([0, 0, SIZE, SIZE], fill=base)
    # Gentle dune curves — lighter only
    for _ in range(3):
        dx = random.randint(0, SIZE-30)
        dy = random.randint(20, SIZE-20)
        dw = random.randint(40, 80)
        dh = random.randint(12, 25)
        light = (min(255, base[0]+10), min(255, base[1]+8), min(255, base[2]+6))
        # Subtle dune highlight
        d.ellipse([dx, dy, dx+dw, dy+dh], fill=light)
        # Very subtle shadow on one side
        d.arc([dx+dw//3, dy+dh//3, dx+dw, dy+dh], 0, 180, fill=(base[0]-8, base[1]-8, base[2]-6), width=1)
    # Sand ripples (very subtle)
    for _ in range(12):
        rx = random.randint(0, SIZE-30)
        ry = random.randint(10, SIZE-10)
        rw = random.randint(15, 35)
        d.arc([rx, ry, rx+rw, ry+5], 0, 180, fill=(base[0]-6, base[1]-6, base[2]-4), width=1)
    # Sparse dead vegetation
    if variant > 1:
        for _ in range(2):
            x, y = random.randint(10, SIZE-10), random.randint(30, SIZE-10)
            d.line([(x, y), (x-3, y-8)], fill=(170, 150, 90), width=1)
            d.line([(x, y), (x+4, y-6)], fill=(170, 150, 90), width=1)
    return img

def gen_water(variant):
    random.seed(600 + variant)
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    base = (35+variant*4, 85+variant*4, 170+variant*4)  # Brighter blue
    d.rectangle([0, 0, SIZE, SIZE], fill=base)
    # Subtle lighter areas (no dark spots!)
    for _ in range(6):
        x, y = random.randint(0, SIZE-25), random.randint(0, SIZE-20)
        w, h = random.randint(20, 40), random.randint(14, 28)
        d.ellipse([x, y, x+w, y+h], fill=(base[0]+6, base[1]+6, base[2]+5))
    # Wave highlights (gentle white lines)
    for _ in range(10):
        wx = random.randint(0, SIZE-40)
        wy = random.randint(8, SIZE-12)
        ww = random.randint(20, 45)
        d.arc([wx, wy, wx+ww, wy+6], 0, 180, fill=(base[0]+40, base[1]+40, base[2]+30, 90), width=1)
    # Specular highlights
    for _ in range(4):
        sx, sy = random.randint(10, SIZE-10), random.randint(10, SIZE-10)
        d.ellipse([sx-2, sy-1, sx+2, sy+1], fill=(200, 210, 230, 80))
    return img

def gen_coast(variant):
    random.seed(700 + variant)
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    # Shallow water — lighter than deep water, no sand (hex can't orient sand correctly)
    base = (65+variant*5, 140+variant*4, 195+variant*3)  # Light turquoise/cyan
    d.rectangle([0, 0, SIZE, SIZE], fill=base)
    # Very subtle lighter patches (sandy bottom)
    for _ in range(6):
        x, y = random.randint(0, SIZE-20), random.randint(0, SIZE-16)
        w, h = random.randint(10, 20), random.randint(8, 14)
        d.ellipse([x, y, x+w, y+h], fill=(base[0]+6, base[1]+5, base[2]+3))
    # Gentle wave lines (thin, subtle)
    for _ in range(6):
        wx = random.randint(0, SIZE-30)
        wy = random.randint(10, SIZE-10)
        ww = random.randint(15, 30)
        d.arc([wx, wy, wx+ww, wy+4], 0, 180, fill=(base[0]+20, base[1]+18, base[2]+10, 60), width=1)
    return img

TERRAINS = {
    "grass": gen_grass,
    "plains": gen_plains,
    "forest": gen_forest,
    "hills": gen_hills,
    "mountain": gen_mountain,
    "desert": gen_desert,
    "water": gen_water,
    "coast": gen_coast,
}

if __name__ == "__main__":
    count = 0
    for name, gen_func in TERRAINS.items():
        # Base (variant 0)
        img = gen_func(0)
        img.save(os.path.join(OUT, f"{name}.png"))
        count += 1
        # 4 variants
        for v in range(4):
            img = gen_func(v)
            img.save(os.path.join(OUT, f"{name}_{v}.png"))
            count += 1
        print(f"Generated {name} (base + 4 variants)")
    print(f"\nDone! {count} terrain tiles generated.")
