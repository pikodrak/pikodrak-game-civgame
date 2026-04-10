#!/usr/bin/env python3
"""Generate detailed Civ2-style unit sprites at 128x128 with proper shading."""
from PIL import Image, ImageDraw
import os

OUT = "static/img/units"
os.makedirs(OUT, exist_ok=True)
SIZE = 128

# Light from upper-left: top=brightest, left=medium, right=darkest
def shade(base_r, base_g, base_b):
    """Return (highlight, mid, shadow, deep_shadow) color tuples."""
    hi = (min(255, base_r + 40), min(255, base_g + 40), min(255, base_b + 40))
    mid = (base_r, base_g, base_b)
    sh = (max(0, base_r - 35), max(0, base_g - 35), max(0, base_b - 35))
    dsh = (max(0, base_r - 65), max(0, base_g - 65), max(0, base_b - 65))
    return hi, mid, sh, dsh

def draw_drop_shadow(draw, bbox, offset=3):
    """Draw a subtle drop shadow."""
    x0, y0, x1, y1 = bbox
    draw.ellipse([x0+offset, y1-4, x1+offset, y1+6], fill=(0, 0, 0, 60))

def draw_head(draw, cx, cy, skin_hi, skin_mid, skin_sh, radius=12):
    """Draw a shaded head/face."""
    # Shadow side
    draw.ellipse([cx-radius, cy-radius, cx+radius, cy+radius], fill=skin_sh)
    # Main face
    draw.ellipse([cx-radius, cy-radius, cx+radius-2, cy+radius-2], fill=skin_mid)
    # Highlight
    draw.ellipse([cx-radius+2, cy-radius+1, cx+radius-5, cy+radius-5], fill=skin_hi)

def draw_body_rect(draw, x, y, w, h, hi, mid, sh):
    """Draw a shaded rectangular body part."""
    draw.rectangle([x, y, x+w, y+h], fill=mid)
    # Left highlight edge
    draw.rectangle([x, y, x+2, y+h], fill=hi)
    # Top highlight
    draw.rectangle([x, y, x+w, y+2], fill=hi)
    # Right shadow
    draw.rectangle([x+w-2, y, x+w, y+h], fill=sh)
    # Bottom shadow
    draw.rectangle([x, y+h-2, x+w, y+h], fill=sh)

def draw_shield(draw, cx, cy, r, color1, color2):
    """Draw a round shield with emblem."""
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color2)
    draw.ellipse([cx-r+2, cy-r+2, cx+r-2, cy+r-2], fill=color1)
    draw.ellipse([cx-r+4, cy-r+4, cx+r-4, cy+r-4], fill=color2)
    # Highlight
    draw.arc([cx-r+2, cy-r+2, cx+r-6, cy+r-6], 200, 340, fill=(255,255,255,120), width=2)

def draw_legs(draw, cx, y_start, h, hi, mid, sh, stance=10):
    """Draw two shaded legs."""
    lw = 7
    # Left leg
    draw_body_rect(draw, cx-stance, y_start, lw, h, hi, mid, sh)
    # Right leg
    draw_body_rect(draw, cx+stance-lw, y_start, lw, h, hi, mid, sh)

def draw_boots(draw, cx, y, boot_hi, boot_mid, boot_sh, stance=10):
    """Draw boots at the bottom of legs."""
    draw_body_rect(draw, cx-stance-2, y, 11, 7, boot_hi, boot_mid, boot_sh)
    draw_body_rect(draw, cx+stance-9, y, 11, 7, boot_hi, boot_mid, boot_sh)

def draw_sword(draw, cx, cy, length=40, color=(180,180,195)):
    """Draw a sword."""
    hi, mid, sh, _ = shade(*color)
    # Blade
    draw.polygon([(cx, cy-length), (cx+3, cy-length+8), (cx+3, cy), (cx-3, cy), (cx-3, cy-length+8)], fill=mid)
    draw.line([(cx, cy-length), (cx, cy)], fill=hi, width=1)
    draw.line([(cx+2, cy-length+5), (cx+2, cy)], fill=sh, width=1)
    # Guard
    draw.rectangle([cx-8, cy-2, cx+8, cy+2], fill=(139, 119, 42))
    # Grip
    draw.rectangle([cx-2, cy+2, cx+2, cy+14], fill=(101, 67, 33))

def draw_spear(draw, cx, cy, length=55, color=(139, 90, 43)):
    """Draw a spear/lance."""
    # Shaft
    draw.line([(cx, cy), (cx, cy-length)], fill=color, width=3)
    # Spearhead
    draw.polygon([(cx, cy-length-10), (cx-4, cy-length), (cx+4, cy-length)], fill=(180, 180, 195))

def draw_bow(draw, cx, cy, h=35, color=(139, 90, 43)):
    """Draw a bow."""
    draw.arc([cx-12, cy-h, cx+12, cy+h], 250, 110, fill=color, width=3)
    # String
    draw.line([(cx+10, cy-h+8), (cx+10, cy+h-8)], fill=(200, 200, 200), width=1)

def draw_helmet(draw, cx, cy, color, style="round"):
    hi, mid, sh, dsh = shade(*color)
    if style == "round":
        draw.ellipse([cx-14, cy-16, cx+14, cy+2], fill=sh)
        draw.ellipse([cx-14, cy-16, cx+12, cy], fill=mid)
        draw.ellipse([cx-12, cy-14, cx+8, cy-4], fill=hi)
    elif style == "pointed":
        draw.polygon([(cx, cy-22), (cx-14, cy), (cx+14, cy)], fill=sh)
        draw.polygon([(cx-1, cy-20), (cx-12, cy), (cx+10, cy)], fill=mid)
        draw.polygon([(cx-2, cy-16), (cx-8, cy-2), (cx+4, cy-2)], fill=hi)
    elif style == "flat":
        draw.rectangle([cx-14, cy-8, cx+14, cy+2], fill=mid)
        draw.rectangle([cx-16, cy-2, cx+16, cy+2], fill=sh)
        draw.rectangle([cx-12, cy-6, cx+12, cy-2], fill=hi)
    elif style == "modern":
        draw.ellipse([cx-14, cy-14, cx+14, cy+4], fill=sh)
        draw.ellipse([cx-13, cy-13, cx+11, cy+2], fill=mid)
        draw.chord([cx-13, cy-13, cx+11, cy-2], 180, 360, fill=hi)

def add_outline(img, color=(20, 20, 20, 200), thickness=2):
    """Add dark outline around all non-transparent pixels for map readability."""
    from PIL import ImageFilter
    # Create alpha mask of original
    alpha = img.split()[3]
    # Expand alpha by dilation (MaxFilter)
    for _ in range(thickness):
        alpha = alpha.filter(ImageFilter.MaxFilter(3))
    # Create outline layer
    outline = Image.new("RGBA", img.size, (0, 0, 0, 0))
    outline_draw = ImageDraw.Draw(outline)
    # Fill expanded area with outline color
    for y in range(img.height):
        for x in range(img.width):
            if alpha.getpixel((x, y)) > 128 and img.getpixel((x, y))[3] < 128:
                outline.putpixel((x, y), color)
    # Composite: outline behind original
    result = Image.alpha_composite(outline, img)
    return result


# ============================================================
# UNIT GENERATORS
# ============================================================

def gen_warrior():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx, cy = 64, 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    tunic_hi, tunic_mid, tunic_sh, _ = shade(160, 60, 40)
    boot_hi, boot_mid, boot_sh, _ = shade(101, 67, 33)

    # Legs
    draw_legs(d, cx, 82, 24, tunic_hi, tunic_mid, tunic_sh)
    draw_boots(d, cx, 106, boot_hi, boot_mid, boot_sh)
    # Body
    draw_body_rect(d, cx-16, 52, 32, 32, tunic_hi, tunic_mid, tunic_sh)
    # Belt
    d.rectangle([cx-16, 72, cx+16, 76], fill=(101, 67, 33))
    d.rectangle([cx-2, 72, cx+2, 78], fill=(180, 160, 40))
    # Arms
    draw_body_rect(d, cx-24, 54, 10, 22, skin_hi, skin_mid, skin_sh)
    draw_body_rect(d, cx+14, 54, 10, 22, skin_hi, skin_mid, skin_sh)
    # Head
    draw_head(d, cx, 40, skin_hi, skin_mid, skin_sh, 13)
    # Eyes
    d.rectangle([cx-5, 38, cx-3, 41], fill=(40, 40, 40))
    d.rectangle([cx+3, 38, cx+5, 41], fill=(40, 40, 40))
    # Club/weapon in right hand
    d.line([(cx+19, 54), (cx+25, 20)], fill=(101, 67, 33), width=4)
    d.ellipse([cx+21, 14, cx+31, 26], fill=(120, 85, 50))
    # Shield in left hand
    draw_shield(d, cx-28, 66, 12, (160, 60, 40), (139, 119, 42))
    return img

def gen_spearman():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    armor_hi, armor_mid, armor_sh, _ = shade(140, 120, 80)
    boot_hi, boot_mid, boot_sh, _ = shade(101, 67, 33)

    draw_legs(d, cx, 82, 24, armor_hi, armor_mid, armor_sh)
    draw_boots(d, cx, 106, boot_hi, boot_mid, boot_sh)
    draw_body_rect(d, cx-16, 50, 32, 34, armor_hi, armor_mid, armor_sh)
    # Chest plate lines
    for yy in range(52, 82, 4):
        d.line([(cx-14, yy), (cx+14, yy)], fill=armor_sh, width=1)
    # Belt
    d.rectangle([cx-16, 74, cx+16, 78], fill=(101, 67, 33))
    draw_body_rect(d, cx-24, 52, 10, 22, skin_hi, skin_mid, skin_sh)
    draw_body_rect(d, cx+14, 52, 10, 22, skin_hi, skin_mid, skin_sh)
    draw_head(d, cx, 38, skin_hi, skin_mid, skin_sh, 13)
    draw_helmet(d, cx, 36, (160, 140, 60), "round")
    d.rectangle([cx-5, 36, cx-3, 39], fill=(40, 40, 40))
    d.rectangle([cx+3, 36, cx+5, 39], fill=(40, 40, 40))
    # Spear
    draw_spear(d, cx+20, 52, 50)
    # Large shield
    draw_shield(d, cx-28, 66, 14, (40, 80, 140), (200, 180, 60))
    return img

def gen_archer():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    tunic_hi, tunic_mid, tunic_sh, _ = shade(60, 100, 50)
    boot_hi, boot_mid, boot_sh, _ = shade(101, 67, 33)

    draw_legs(d, cx, 82, 24, tunic_hi, tunic_mid, tunic_sh)
    draw_boots(d, cx, 106, boot_hi, boot_mid, boot_sh)
    draw_body_rect(d, cx-14, 50, 28, 34, tunic_hi, tunic_mid, tunic_sh)
    # Belt
    d.rectangle([cx-14, 74, cx+14, 77], fill=(101, 67, 33))
    draw_body_rect(d, cx-22, 52, 10, 22, tunic_hi, tunic_mid, tunic_sh)
    draw_body_rect(d, cx+12, 52, 10, 22, skin_hi, skin_mid, skin_sh)
    draw_head(d, cx, 38, skin_hi, skin_mid, skin_sh, 12)
    # Hood
    d.ellipse([cx-14, 24, cx+12, 42], fill=(50, 85, 42))
    d.rectangle([cx-5, 36, cx-3, 39], fill=(40, 40, 40))
    d.rectangle([cx+3, 36, cx+5, 39], fill=(40, 40, 40))
    # Bow
    draw_bow(d, cx+22, 56, 28)
    # Quiver on back (shifted right so it's visible beside body)
    draw_body_rect(d, cx+14, 32, 7, 28, (160, 110, 55), (139, 90, 43), (110, 70, 30))
    # Arrow shafts sticking out
    for i in range(4):
        d.line([(cx+16+i*2, 32), (cx+16+i*2, 24)], fill=(139, 90, 43), width=1)
        d.polygon([(cx+16+i*2, 22), (cx+15+i*2, 26), (cx+17+i*2, 26)], fill=(180, 180, 195))
    # Fletching
    for i in range(4):
        d.line([(cx+16+i*2, 32), (cx+14+i*2, 34)], fill=(200, 200, 200), width=1)
    return img

def gen_swordsman():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    armor_hi, armor_mid, armor_sh, _ = shade(165, 50, 50)
    metal_hi, metal_mid, metal_sh, _ = shade(160, 160, 170)
    boot_hi, boot_mid, boot_sh, _ = shade(80, 55, 30)

    draw_legs(d, cx, 82, 24, armor_hi, armor_mid, armor_sh)
    draw_boots(d, cx, 106, boot_hi, boot_mid, boot_sh)
    # Chain mail body
    draw_body_rect(d, cx-16, 48, 32, 36, armor_hi, armor_mid, armor_sh)
    # Chain mail texture
    for yy in range(50, 82, 3):
        for xx in range(cx-14, cx+14, 4):
            offset = 2 if (yy // 3) % 2 == 0 else 0
            d.ellipse([xx+offset, yy, xx+offset+2, yy+2], fill=armor_sh)
    # Belt
    d.rectangle([cx-16, 76, cx+16, 80], fill=(101, 67, 33))
    d.rectangle([cx-2, 76, cx+2, 82], fill=(200, 170, 40))
    # Arms with armor
    draw_body_rect(d, cx-24, 50, 10, 24, metal_hi, metal_mid, metal_sh)
    draw_body_rect(d, cx+14, 50, 10, 24, metal_hi, metal_mid, metal_sh)
    # Head
    draw_head(d, cx, 36, skin_hi, skin_mid, skin_sh, 13)
    # Metal helmet
    draw_helmet(d, cx, 34, (150, 150, 160), "round")
    # Nose guard
    d.rectangle([cx-1, 30, cx+1, 40], fill=metal_sh)
    d.rectangle([cx-5, 34, cx-3, 37], fill=(40, 40, 40))
    d.rectangle([cx+3, 34, cx+5, 37], fill=(40, 40, 40))
    # Sword
    draw_sword(d, cx+22, 50, 38)
    # Shield
    draw_shield(d, cx-30, 64, 14, (180, 40, 40), (200, 180, 40))
    return img

def draw_horse_profile(d, cx, cy, horse_color, facing_right=True):
    """Draw a horse from the side profile — proper proportions."""
    hi, mid, sh, dsh = shade(*horse_color)
    flip = 1 if facing_right else -1
    # Body (horizontal ellipse)
    d.ellipse([cx-28, cy-10, cx+28, cy+16], fill=sh)
    d.ellipse([cx-26, cy-8, cx+26, cy+14], fill=mid)
    d.ellipse([cx-22, cy-6, cx+22, cy+10], fill=hi)
    # Neck (angled up-right)
    nx = cx + 22*flip
    d.polygon([(nx, cy-4), (nx+12*flip, cy-28), (nx+20*flip, cy-24), (nx+8*flip, cy+4)], fill=mid)
    d.polygon([(nx+2*flip, cy-2), (nx+14*flip, cy-26), (nx+18*flip, cy-22), (nx+6*flip, cy+2)], fill=hi)
    # Head
    hx = nx + 18*flip
    d.ellipse([hx-8, cy-34, hx+8, cy-20], fill=mid)
    d.ellipse([hx-6, cy-32, hx+6, cy-22], fill=hi)
    # Snout
    d.ellipse([hx+2*flip, cy-28, hx+12*flip, cy-18], fill=mid)
    # Eye
    d.ellipse([hx-2*flip, cy-30, hx+2*flip, cy-26], fill=(30, 20, 15))
    # Ear
    d.polygon([(hx-2*flip, cy-34), (hx, cy-42), (hx+4*flip, cy-34)], fill=mid)
    # Mane
    for yy in range(cy-26, cy-4, 4):
        mx = nx + int((yy - cy + 26) * 0.4 * flip)
        d.line([(mx, yy), (mx-6*flip, yy-6)], fill=dsh, width=3)
    # Tail
    tx = cx - 28*flip
    d.arc([tx-10*flip, cy-4, tx+8*flip, cy+20], 90 if facing_right else 270, 270 if facing_right else 90, fill=dsh, width=4)
    # Legs (front pair, back pair — slight offset for depth)
    for lx_off, shade_c in [(-16, sh), (-10, mid), (14, sh), (20, mid)]:
        lx = cx + lx_off * flip
        d.rectangle([lx-3, cy+12, lx+3, cy+34], fill=shade_c)
        d.rectangle([lx-4, cy+32, lx+4, cy+36], fill=dsh)  # Hoof

def gen_horseman():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 60
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    tunic_hi, tunic_mid, tunic_sh, _ = shade(100, 60, 140)

    draw_horse_profile(d, cx, 78, (160, 120, 70))
    # Saddle
    d.ellipse([cx-10, 62, cx+10, 74], fill=(160, 40, 30))
    d.ellipse([cx-8, 64, cx+8, 72], fill=(190, 50, 40))
    # Rider body
    draw_body_rect(d, cx-10, 38, 20, 26, tunic_hi, tunic_mid, tunic_sh)
    # Rider arms
    draw_body_rect(d, cx-16, 40, 8, 16, skin_hi, skin_mid, skin_sh)
    draw_body_rect(d, cx+10, 40, 8, 16, skin_hi, skin_mid, skin_sh)
    # Rider legs on horse
    d.rectangle([cx-12, 62, cx-6, 76], fill=tunic_sh)
    d.rectangle([cx+6, 62, cx+12, 76], fill=tunic_sh)
    # Rider head
    draw_head(d, cx, 28, skin_hi, skin_mid, skin_sh, 11)
    d.rectangle([cx-4, 26, cx-2, 29], fill=(40, 40, 40))
    d.rectangle([cx+2, 26, cx+4, 29], fill=(40, 40, 40))
    # Javelin
    draw_spear(d, cx+16, 40, 44)
    return img

def gen_knight():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 60
    metal_hi, metal_mid, metal_sh, _ = shade(170, 170, 180)

    # Armored horse (dark, with barding)
    draw_horse_profile(d, cx, 78, (55, 55, 60))
    # Horse barding (armor cloth)
    d.ellipse([cx-24, 70, cx+24, 92], fill=(50, 50, 130), outline=(70, 70, 150))
    # Caparison cross
    d.rectangle([cx-2, 72, cx+2, 88], fill=(200, 180, 40))
    d.rectangle([cx-10, 78, cx+10, 82], fill=(200, 180, 40))
    # Saddle
    d.ellipse([cx-10, 62, cx+10, 74], fill=(120, 30, 30))
    # Rider (full plate armor)
    draw_body_rect(d, cx-12, 34, 24, 30, metal_hi, metal_mid, metal_sh)
    # Pauldrons
    d.ellipse([cx-18, 34, cx-6, 48], fill=metal_mid)
    d.ellipse([cx+6, 34, cx+18, 48], fill=metal_sh)
    # Arms
    draw_body_rect(d, cx-20, 40, 10, 18, metal_hi, metal_mid, metal_sh)
    draw_body_rect(d, cx+12, 40, 10, 18, metal_hi, metal_mid, metal_sh)
    # Rider legs on horse
    d.rectangle([cx-14, 62, cx-6, 78], fill=metal_sh)
    d.rectangle([cx+6, 62, cx+14, 78], fill=metal_sh)
    # Helmet with visor (great helm)
    draw_helmet(d, cx, 28, (170, 170, 180), "pointed")
    d.rectangle([cx-7, 28, cx+7, 31], fill=(30, 30, 30))  # Visor slit
    # Red plume
    d.ellipse([cx-5, 6, cx+3, 22], fill=(200, 40, 40))
    d.ellipse([cx-3, 8, cx+1, 18], fill=(230, 60, 60))
    # Lance
    d.line([(cx+18, 40), (cx+34, 6)], fill=(139, 90, 43), width=5)
    d.polygon([(cx+34, 0), (cx+31, 10), (cx+37, 10)], fill=metal_mid)
    # Shield with cross
    d.ellipse([cx-26, 44, cx-10, 68], fill=(40, 40, 160))
    d.rectangle([cx-20, 52, cx-16, 64], fill=(220, 220, 40))
    d.rectangle([cx-22, 56, cx-14, 60], fill=(220, 220, 40))
    return img

def gen_musketman():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    coat_hi, coat_mid, coat_sh, _ = shade(40, 60, 140)
    pants_hi, pants_mid, pants_sh, _ = shade(200, 190, 160)
    boot_hi, boot_mid, boot_sh, _ = shade(40, 35, 30)

    draw_legs(d, cx, 82, 24, pants_hi, pants_mid, pants_sh, 11)
    draw_boots(d, cx, 106, boot_hi, boot_mid, boot_sh, 11)
    draw_body_rect(d, cx-16, 46, 32, 38, coat_hi, coat_mid, coat_sh)
    # Buttons
    for yy in range(50, 80, 6):
        d.ellipse([cx-2, yy, cx+2, yy+3], fill=(200, 180, 40))
    # White cross-straps
    d.line([(cx-16, 48), (cx+16, 80)], fill=(220, 220, 210), width=2)
    d.line([(cx+16, 48), (cx-16, 80)], fill=(220, 220, 210), width=2)
    # Belt
    d.rectangle([cx-16, 78, cx+16, 82], fill=(200, 190, 160))
    draw_body_rect(d, cx-24, 48, 10, 22, coat_hi, coat_mid, coat_sh)
    draw_body_rect(d, cx+14, 48, 10, 22, coat_hi, coat_mid, coat_sh)
    draw_head(d, cx, 34, skin_hi, skin_mid, skin_sh, 13)
    # Tricorn hat
    d.polygon([(cx-18, 28), (cx, 14), (cx+18, 28)], fill=(30, 30, 35))
    d.rectangle([cx-20, 26, cx+20, 30], fill=(30, 30, 35))
    d.rectangle([cx-5, 32, cx-3, 35], fill=(40, 40, 40))
    d.rectangle([cx+3, 32, cx+5, 35], fill=(40, 40, 40))
    # Musket
    d.line([(cx+22, 46), (cx+26, 14)], fill=(101, 67, 33), width=4)
    d.line([(cx+26, 14), (cx+26, 6)], fill=(120, 120, 130), width=3)
    # Bayonet
    d.polygon([(cx+26, 2), (cx+24, 8), (cx+28, 8)], fill=(180, 180, 195))
    return img

def gen_rifleman():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    uni_hi, uni_mid, uni_sh, _ = shade(130, 120, 85)  # WWI khaki — visibly lighter
    boot_hi, boot_mid, boot_sh, _ = shade(50, 40, 30)

    draw_legs(d, cx, 82, 24, uni_hi, uni_mid, uni_sh, 10)
    draw_boots(d, cx, 106, boot_hi, boot_mid, boot_sh, 10)
    # Puttees/wraps on legs (WWI style)
    for yy in range(86, 106, 3):
        d.line([(cx-14, yy), (cx-4, yy)], fill=(115, 105, 70), width=1)
        d.line([(cx+4, yy), (cx+14, yy)], fill=(115, 105, 70), width=1)
    draw_body_rect(d, cx-16, 46, 32, 38, uni_hi, uni_mid, uni_sh)
    # Pockets
    d.rectangle([cx-12, 54, cx-4, 62], fill=uni_sh)
    d.rectangle([cx+4, 54, cx+12, 62], fill=uni_sh)
    # Belt + ammo pouches (leather brown)
    d.rectangle([cx-16, 76, cx+16, 80], fill=(101, 67, 33))
    d.rectangle([cx-14, 72, cx-8, 78], fill=(101, 67, 33))
    d.rectangle([cx+8, 72, cx+14, 78], fill=(101, 67, 33))
    draw_body_rect(d, cx-24, 48, 10, 22, uni_hi, uni_mid, uni_sh)
    draw_body_rect(d, cx+14, 48, 10, 22, uni_hi, uni_mid, uni_sh)
    draw_head(d, cx, 34, skin_hi, skin_mid, skin_sh, 12)
    # Brodie helmet (WWI — flat brim, shallow dome) — khaki colored
    d.ellipse([cx-16, 24, cx+16, 36], fill=(120, 110, 75))  # Wide brim
    d.ellipse([cx-10, 20, cx+10, 32], fill=(130, 120, 85))  # Dome
    d.ellipse([cx-8, 22, cx+8, 28], fill=(145, 135, 95))    # Highlight
    d.rectangle([cx-5, 32, cx-3, 35], fill=(40, 40, 40))
    d.rectangle([cx+3, 32, cx+5, 35], fill=(40, 40, 40))
    # Long rifle (bolt-action, longer than infantry's SMG)
    d.line([(cx+22, 48), (cx+28, 10)], fill=(80, 55, 30), width=4)
    d.line([(cx+28, 10), (cx+28, 4)], fill=(100, 100, 110), width=3)
    # Bayonet
    d.polygon([(cx+28, 0), (cx+26, 6), (cx+30, 6)], fill=(170, 170, 180))
    return img

def gen_infantry():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    uni_hi, uni_mid, uni_sh, _ = shade(90, 95, 70)  # Lighter olive drab
    boot_hi, boot_mid, boot_sh, _ = shade(50, 42, 30)

    draw_legs(d, cx, 82, 24, uni_hi, uni_mid, uni_sh, 10)
    draw_boots(d, cx, 106, boot_hi, boot_mid, boot_sh, 10)
    draw_body_rect(d, cx-16, 44, 32, 40, uni_hi, uni_mid, uni_sh)
    # Webbing / chest rig (X pattern)
    d.line([(cx-14, 46), (cx+14, 78)], fill=(110, 100, 65), width=3)
    d.line([(cx+14, 46), (cx-14, 78)], fill=(110, 100, 65), width=3)
    # Ammo pouches on belt
    d.rectangle([cx-16, 76, cx+16, 80], fill=(110, 100, 65))
    d.rectangle([cx-16, 72, cx-10, 78], fill=(100, 90, 55))
    d.rectangle([cx+10, 72, cx+16, 78], fill=(100, 90, 55))
    draw_body_rect(d, cx-24, 46, 10, 24, uni_hi, uni_mid, uni_sh)
    draw_body_rect(d, cx+14, 46, 10, 24, uni_hi, uni_mid, uni_sh)
    draw_head(d, cx, 32, skin_hi, skin_mid, skin_sh, 12)
    # Steel helmet (M1 style — round, with chin strap)
    draw_helmet(d, cx, 28, (90, 95, 70), "modern")
    # Chin strap
    d.line([(cx-10, 34), (cx-12, 38)], fill=(100, 90, 55), width=1)
    d.line([(cx+10, 34), (cx+12, 38)], fill=(100, 90, 55), width=1)
    d.rectangle([cx-5, 30, cx-3, 33], fill=(40, 40, 40))
    d.rectangle([cx+3, 30, cx+5, 33], fill=(40, 40, 40))
    # Submachine gun (held across body)
    d.line([(cx+14, 54), (cx+30, 38)], fill=(55, 55, 60), width=4)
    d.rectangle([cx+28, 36, cx+34, 40], fill=(55, 55, 60))  # Magazine
    # Backpack
    draw_body_rect(d, cx-8, 36, 14, 16, (100, 90, 55), (90, 80, 48), (70, 62, 35))
    # Canteen on hip
    d.ellipse([cx+16, 68, cx+24, 78], fill=(90, 95, 70))
    return img

def gen_catapult():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    wood_hi, wood_mid, wood_sh, _ = shade(139, 90, 43)

    # Base frame
    draw_body_rect(d, cx-34, 90, 68, 10, wood_hi, wood_mid, wood_sh)
    # Wheels
    for wx in [-28, 28]:
        d.ellipse([cx+wx-10, 86, cx+wx+10, 106], fill=wood_sh, outline=wood_mid, width=2)
        d.ellipse([cx+wx-4, 92, cx+wx+4, 100], fill=wood_mid)
    # Upright frame
    draw_body_rect(d, cx-6, 40, 6, 52, wood_hi, wood_mid, wood_sh)
    draw_body_rect(d, cx+2, 40, 6, 52, wood_hi, wood_mid, wood_sh)
    # Cross beam
    draw_body_rect(d, cx-8, 42, 20, 6, wood_hi, wood_mid, wood_sh)
    # Throwing arm
    d.line([(cx, 44), (cx-30, 30)], fill=wood_mid, width=5)
    # Bucket/sling
    d.arc([cx-38, 24, cx-24, 38], 0, 180, fill=(101, 67, 33), width=3)
    # Ammo (stone)
    d.ellipse([cx-34, 22, cx-28, 28], fill=(140, 140, 140))
    # Ropes
    d.line([(cx-4, 60), (cx-20, 86)], fill=(180, 160, 100), width=2)
    d.line([(cx+6, 60), (cx+20, 86)], fill=(180, 160, 100), width=2)
    return img

def gen_artillery():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    metal_hi, metal_mid, metal_sh, _ = shade(100, 100, 105)
    wood_hi, wood_mid, wood_sh, _ = shade(100, 70, 40)

    # Trail legs
    d.line([(cx-10, 80), (cx-30, 108)], fill=wood_mid, width=5)
    d.line([(cx+10, 80), (cx+30, 108)], fill=wood_mid, width=5)
    # Wheels
    for wx in [-20, 20]:
        d.ellipse([cx+wx-12, 72, cx+wx+12, 96], fill=wood_sh, outline=wood_mid, width=3)
        d.ellipse([cx+wx-4, 80, cx+wx+4, 88], fill=(80, 60, 30))
        # Spokes
        for angle_step in range(0, 360, 60):
            import math
            rad = math.radians(angle_step)
            sx = int(cx+wx + 10*math.cos(rad))
            sy = int(84 + 10*math.sin(rad))
            d.line([(cx+wx, 84), (sx, sy)], fill=wood_mid, width=1)
    # Gun shield
    draw_body_rect(d, cx-18, 50, 36, 28, metal_hi, metal_mid, metal_sh)
    # Barrel
    d.rectangle([cx-4, 36, cx+4, 58], fill=metal_mid)
    d.rectangle([cx-4, 36, cx+2, 56], fill=metal_hi)
    d.rectangle([cx-5, 34, cx+5, 38], fill=metal_sh)  # Muzzle
    d.ellipse([cx-3, 32, cx+3, 38], fill=(40, 40, 45))
    return img

def gen_tank():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    hull_hi, hull_mid, hull_sh, _ = shade(85, 95, 65)
    track_hi, track_mid, track_sh, _ = shade(55, 55, 50)

    # Tracks
    d.rounded_rectangle([cx-40, 78, cx+40, 108], radius=12, fill=track_sh)
    d.rounded_rectangle([cx-38, 80, cx+38, 106], radius=10, fill=track_mid)
    # Track detail (wheels)
    for wx in range(-32, 36, 12):
        d.ellipse([cx+wx-5, 86, cx+wx+5, 100], fill=track_sh)
        d.ellipse([cx+wx-3, 88, cx+wx+3, 98], fill=(70, 70, 65))
    # Hull
    d.polygon([(cx-36, 78), (cx-30, 58), (cx+30, 58), (cx+36, 78)], fill=hull_sh)
    d.polygon([(cx-34, 76), (cx-28, 60), (cx+28, 60), (cx+34, 76)], fill=hull_mid)
    d.polygon([(cx-30, 72), (cx-26, 62), (cx+24, 62), (cx+30, 72)], fill=hull_hi)
    # Turret
    d.ellipse([cx-18, 48, cx+14, 68], fill=hull_sh)
    d.ellipse([cx-16, 50, cx+12, 66], fill=hull_mid)
    d.ellipse([cx-12, 52, cx+8, 62], fill=hull_hi)
    # Gun barrel
    d.rectangle([cx+10, 54, cx+44, 58], fill=hull_mid)
    d.rectangle([cx+10, 54, cx+42, 56], fill=hull_hi)
    d.rectangle([cx+40, 52, cx+46, 60], fill=hull_sh)  # Muzzle brake
    # Hatch
    d.ellipse([cx-6, 50, cx+2, 56], fill=hull_sh)
    # Details
    d.rectangle([cx-32, 60, cx-28, 66], fill=hull_sh)  # Headlight
    return img

def gen_settler():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    cloth_hi, cloth_mid, cloth_sh, _ = shade(140, 120, 80)
    boot_hi, boot_mid, boot_sh, _ = shade(101, 67, 33)

    # Wagon
    wagon_hi, wagon_mid, wagon_sh, _ = shade(130, 95, 55)
    draw_body_rect(d, cx-8, 70, 50, 28, wagon_hi, wagon_mid, wagon_sh)
    # Wagon wheels
    d.ellipse([cx-2, 88, cx+14, 104], fill=wagon_sh, outline=wagon_mid, width=2)
    d.ellipse([cx+24, 88, cx+40, 104], fill=wagon_sh, outline=wagon_mid, width=2)
    # Canvas top
    d.arc([cx-6, 48, cx+46, 78], 180, 360, fill=(220, 210, 190), width=30)
    d.ellipse([cx+2, 50, cx+38, 74], fill=(230, 220, 200))
    # Person walking alongside
    draw_legs(d, cx-20, 82, 20, cloth_hi, cloth_mid, cloth_sh, 7)
    draw_boots(d, cx-20, 102, boot_hi, boot_mid, boot_sh, 7)
    draw_body_rect(d, cx-30, 58, 22, 26, cloth_hi, cloth_mid, cloth_sh)
    draw_head(d, cx-19, 48, skin_hi, skin_mid, skin_sh, 11)
    # Hat
    d.ellipse([cx-30, 36, cx-8, 48], fill=(140, 120, 80))
    d.ellipse([cx-28, 34, cx-10, 44], fill=(160, 140, 100))
    d.rectangle([cx-23, 38, cx-21, 41], fill=(40, 40, 40))
    d.rectangle([cx-17, 38, cx-15, 41], fill=(40, 40, 40))
    return img

def gen_worker():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    cloth_hi, cloth_mid, cloth_sh, _ = shade(150, 140, 110)
    boot_hi, boot_mid, boot_sh, _ = shade(101, 67, 33)

    draw_legs(d, cx, 82, 24, cloth_hi, cloth_mid, cloth_sh)
    draw_boots(d, cx, 106, boot_hi, boot_mid, boot_sh)
    draw_body_rect(d, cx-14, 50, 28, 34, cloth_hi, cloth_mid, cloth_sh)
    # Suspenders
    d.line([(cx-8, 50), (cx-8, 76)], fill=(101, 67, 33), width=2)
    d.line([(cx+8, 50), (cx+8, 76)], fill=(101, 67, 33), width=2)
    draw_body_rect(d, cx-22, 52, 10, 20, skin_hi, skin_mid, skin_sh)
    draw_body_rect(d, cx+12, 52, 10, 20, skin_hi, skin_mid, skin_sh)
    draw_head(d, cx, 38, skin_hi, skin_mid, skin_sh, 12)
    # Straw hat
    d.ellipse([cx-16, 26, cx+16, 38], fill=(200, 180, 100))
    d.ellipse([cx-12, 24, cx+12, 34], fill=(220, 200, 120))
    d.rectangle([cx-5, 34, cx-3, 37], fill=(40, 40, 40))
    d.rectangle([cx+3, 34, cx+5, 37], fill=(40, 40, 40))
    # Shovel
    d.line([(cx+18, 52), (cx+24, 100)], fill=(139, 90, 43), width=3)
    d.polygon([(cx+20, 98), (cx+28, 98), (cx+28, 112), (cx+20, 112)], fill=(140, 140, 150))
    d.polygon([(cx+20, 98), (cx+28, 98), (cx+28, 112), (cx+20, 112)], fill=(130, 130, 140))
    return img

def gen_spy():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    skin_hi, skin_mid, skin_sh, _ = shade(210, 170, 130)
    suit_hi, suit_mid, suit_sh, _ = shade(40, 40, 45)
    shoe_hi, shoe_mid, shoe_sh, _ = shade(30, 25, 20)

    draw_legs(d, cx, 82, 24, suit_hi, suit_mid, suit_sh, 9)
    draw_boots(d, cx, 106, shoe_hi, shoe_mid, shoe_sh, 9)
    draw_body_rect(d, cx-14, 46, 28, 38, suit_hi, suit_mid, suit_sh)
    # Lapels
    d.line([(cx, 46), (cx-8, 70)], fill=(30, 30, 35), width=2)
    d.line([(cx, 46), (cx+8, 70)], fill=(30, 30, 35), width=2)
    # White shirt/tie
    d.line([(cx, 48), (cx, 82)], fill=(180, 180, 180), width=2)
    d.polygon([(cx-3, 48), (cx, 56), (cx+3, 48)], fill=(160, 30, 30))  # Red tie
    draw_body_rect(d, cx-22, 48, 10, 20, suit_hi, suit_mid, suit_sh)
    draw_body_rect(d, cx+12, 48, 10, 20, suit_hi, suit_mid, suit_sh)
    draw_head(d, cx, 34, skin_hi, skin_mid, skin_sh, 12)
    # Fedora hat
    d.ellipse([cx-16, 22, cx+16, 32], fill=(35, 35, 40))
    d.ellipse([cx-12, 16, cx+12, 28], fill=(45, 45, 50))
    d.rectangle([cx-12, 26, cx+12, 28], fill=(60, 40, 30))  # hat band
    d.rectangle([cx-5, 30, cx-3, 33], fill=(40, 40, 40))
    d.rectangle([cx+3, 30, cx+5, 33], fill=(40, 40, 40))
    # Briefcase
    draw_body_rect(d, cx+16, 64, 16, 12, (80, 50, 25), (101, 67, 33), (70, 45, 20))
    d.rectangle([cx+20, 63, cx+28, 65], fill=(180, 160, 40))  # Handle
    return img

def gen_caravan():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    camel_hi, camel_mid, camel_sh, _ = shade(180, 150, 100)

    # Camel body
    d.ellipse([cx-24, 60, cx+24, 90], fill=camel_sh)
    d.ellipse([cx-22, 58, cx+22, 86], fill=camel_mid)
    d.ellipse([cx-18, 60, cx+18, 82], fill=camel_hi)
    # Hump
    d.ellipse([cx-8, 48, cx+10, 66], fill=camel_mid)
    d.ellipse([cx-6, 50, cx+8, 64], fill=camel_hi)
    # Legs
    for lx in [-18, -8, 8, 18]:
        d.rectangle([cx+lx-3, 86, cx+lx+3, 108], fill=camel_sh)
    for lx in [-18, -8, 8, 18]:
        d.rectangle([cx+lx-4, 106, cx+lx+4, 110], fill=(140, 120, 70))
    # Head/neck
    d.rectangle([cx+18, 38, cx+24, 62], fill=camel_mid)
    d.ellipse([cx+18, 30, cx+34, 46], fill=camel_mid)
    d.ellipse([cx+20, 32, cx+32, 44], fill=camel_hi)
    d.ellipse([cx+26, 34, cx+30, 38], fill=(40, 30, 20))
    # Ears
    d.polygon([(cx+22, 30), (cx+20, 24), (cx+26, 28)], fill=camel_mid)
    # Trade goods (bags)
    draw_body_rect(d, cx-26, 56, 14, 18, (160, 100, 40), (140, 80, 30), (110, 60, 20))
    draw_body_rect(d, cx+14, 56, 14, 18, (160, 100, 40), (140, 80, 30), (110, 60, 20))
    # Gold coin emblem on bag
    d.ellipse([cx-22, 62, cx-16, 68], fill=(220, 200, 40))
    d.ellipse([cx+18, 62, cx+24, 68], fill=(220, 200, 40))
    return img

def gen_galley():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    wood_hi, wood_mid, wood_sh, _ = shade(130, 85, 45)

    # Hull
    d.polygon([(cx-44, 72), (cx-36, 96), (cx+36, 96), (cx+44, 72)], fill=wood_sh)
    d.polygon([(cx-42, 74), (cx-34, 94), (cx+34, 94), (cx+42, 74)], fill=wood_mid)
    d.polygon([(cx-38, 76), (cx-32, 90), (cx+30, 90), (cx+38, 76)], fill=wood_hi)
    # Planks
    for yy in range(76, 94, 4):
        d.line([(cx-40, yy), (cx+40, yy)], fill=wood_sh, width=1)
    # Bow decoration
    d.polygon([(cx+44, 72), (cx+50, 68), (cx+46, 74)], fill=wood_mid)
    # Mast
    d.rectangle([cx-2, 26, cx+2, 74], fill=wood_mid)
    # Sail
    d.polygon([(cx+2, 28), (cx+36, 40), (cx+2, 66)], fill=(220, 210, 190))
    d.polygon([(cx+4, 30), (cx+32, 40), (cx+4, 64)], fill=(235, 225, 205))
    # Oars
    for i in range(-3, 4):
        ox = cx + i * 10
        d.line([(ox, 80), (ox-6, 104)], fill=wood_sh, width=2)
    # Flag
    d.polygon([(cx, 26), (cx+12, 22), (cx+12, 30)], fill=(180, 40, 40))
    return img

def gen_caravel():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    wood_hi, wood_mid, wood_sh, _ = shade(110, 70, 40)

    # Hull (bigger, deeper)
    d.polygon([(cx-40, 68), (cx-30, 98), (cx+30, 98), (cx+40, 68)], fill=wood_sh)
    d.polygon([(cx-38, 70), (cx-28, 96), (cx+28, 96), (cx+38, 70)], fill=wood_mid)
    d.polygon([(cx-34, 72), (cx-26, 92), (cx+26, 92), (cx+34, 72)], fill=wood_hi)
    # Stern castle
    draw_body_rect(d, cx-38, 58, 16, 14, wood_hi, wood_mid, wood_sh)
    # Bow
    d.polygon([(cx+40, 68), (cx+48, 62), (cx+42, 72)], fill=wood_mid)
    # Bow castle
    draw_body_rect(d, cx+28, 60, 14, 12, wood_hi, wood_mid, wood_sh)
    # Main mast
    d.rectangle([cx-2, 18, cx+2, 70], fill=wood_mid)
    # Main sail
    d.rectangle([cx-24, 22, cx+24, 54], fill=(230, 220, 200))
    d.rectangle([cx-22, 24, cx+22, 52], fill=(240, 235, 215))
    # Cross on sail
    d.rectangle([cx-2, 26, cx+2, 50], fill=(180, 40, 40))
    d.rectangle([cx-12, 36, cx+12, 40], fill=(180, 40, 40))
    # Crow's nest
    draw_body_rect(d, cx-6, 16, 12, 6, wood_hi, wood_mid, wood_sh)
    # Flag
    d.polygon([(cx, 14), (cx+14, 10), (cx+14, 18)], fill=(40, 40, 160))
    return img

def gen_ironclad():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    hull_hi, hull_mid, hull_sh, _ = shade(80, 80, 85)

    # Hull
    d.polygon([(cx-42, 72), (cx-34, 96), (cx+34, 96), (cx+42, 72)], fill=hull_sh)
    d.polygon([(cx-40, 74), (cx-32, 94), (cx+32, 94), (cx+40, 74)], fill=hull_mid)
    # Armor plates
    for yy in range(74, 94, 5):
        d.line([(cx-38, yy), (cx+38, yy)], fill=hull_sh, width=1)
    # Deck
    d.polygon([(cx-36, 72), (cx-36, 68), (cx+36, 68), (cx+36, 72)], fill=hull_hi)
    # Turret
    d.ellipse([cx-14, 56, cx+14, 72], fill=hull_sh)
    d.ellipse([cx-12, 58, cx+12, 70], fill=hull_mid)
    # Gun barrels (2)
    d.rectangle([cx+10, 60, cx+38, 63], fill=hull_sh)
    d.rectangle([cx+10, 65, cx+38, 68], fill=hull_sh)
    # Smokestack
    d.rectangle([cx-4, 42, cx+4, 60], fill=(50, 50, 55))
    d.ellipse([cx-5, 40, cx+5, 46], fill=(60, 60, 65))
    # Smoke
    d.ellipse([cx-8, 30, cx+4, 42], fill=(100, 100, 100, 120))
    d.ellipse([cx-12, 22, cx+2, 36], fill=(120, 120, 120, 80))
    # Ram bow
    d.polygon([(cx+42, 72), (cx+50, 76), (cx+42, 80)], fill=hull_sh)
    return img

def gen_fighter():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    body_hi, body_mid, body_sh, _ = shade(80, 100, 70)

    # Side view fuselage
    d.ellipse([cx-38, 50, cx+28, 72], fill=body_sh)
    d.ellipse([cx-36, 52, cx+26, 70], fill=body_mid)
    d.ellipse([cx-32, 54, cx+22, 66], fill=body_hi)
    # Nose cone
    d.polygon([(cx+26, 58), (cx+40, 60), (cx+26, 64)], fill=body_mid)
    # Propeller disc
    d.ellipse([cx+38, 52, cx+44, 70], fill=(180, 180, 190, 120))
    # Cockpit canopy
    d.ellipse([cx-4, 48, cx+12, 56], fill=(180, 200, 230))
    d.ellipse([cx-2, 50, cx+10, 54], fill=(200, 220, 245))
    # Wing (side view = bottom edge)
    d.polygon([(cx-20, 68), (cx-8, 68), (cx+10, 68), (cx+10, 72), (cx-30, 72), (cx-20, 68)], fill=body_sh)
    d.polygon([(cx-18, 68), (cx+8, 68), (cx+8, 70), (cx-28, 70)], fill=body_mid)
    # Tail wing
    d.polygon([(cx-36, 58), (cx-50, 54), (cx-50, 58), (cx-36, 62)], fill=body_mid)
    # Vertical tail
    d.polygon([(cx-34, 52), (cx-46, 38), (cx-50, 38), (cx-50, 54), (cx-34, 54)], fill=body_mid)
    d.polygon([(cx-36, 52), (cx-48, 40), (cx-48, 52)], fill=body_hi)
    # Roundel on fuselage
    d.ellipse([cx-14, 56, cx-6, 64], fill=(40, 40, 160))
    d.ellipse([cx-12, 58, cx-8, 62], fill=(220, 220, 220))
    # Exhaust
    d.ellipse([cx-40, 58, cx-36, 64], fill=(100, 100, 105))
    # Machine gun bumps
    d.rectangle([cx+14, 54, cx+18, 58], fill=(80, 80, 85))
    return img

def gen_bomber():
    img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = 64
    body_hi, body_mid, body_sh, _ = shade(85, 95, 80)

    # Side view — larger fuselage
    d.ellipse([cx-40, 44, cx+32, 72], fill=body_sh)
    d.ellipse([cx-38, 46, cx+30, 70], fill=body_mid)
    d.ellipse([cx-34, 48, cx+26, 66], fill=body_hi)
    # Glass nose (bombardier)
    d.polygon([(cx+28, 54), (cx+44, 58), (cx+28, 62)], fill=(180, 200, 220))
    d.polygon([(cx+30, 56), (cx+40, 58), (cx+30, 60)], fill=(200, 220, 240))
    # Cockpit
    d.ellipse([cx+10, 42, cx+22, 50], fill=(180, 200, 230))
    # Wing (thicker)
    d.polygon([(cx-22, 68), (cx+14, 68), (cx+14, 74), (cx-32, 74)], fill=body_sh)
    d.polygon([(cx-20, 68), (cx+12, 68), (cx+12, 72), (cx-30, 72)], fill=body_mid)
    # Engine on wing
    d.ellipse([cx-12, 66, cx+2, 78], fill=(70, 70, 75))
    d.ellipse([cx-10, 68, cx, 76], fill=(85, 85, 90))
    # Tail
    d.polygon([(cx-38, 52), (cx-52, 48), (cx-52, 52), (cx-38, 56)], fill=body_mid)
    d.polygon([(cx-36, 46), (cx-50, 30), (cx-52, 30), (cx-52, 48), (cx-36, 48)], fill=body_mid)
    d.polygon([(cx-38, 46), (cx-50, 32), (cx-50, 46)], fill=body_hi)
    # Bombs underneath
    for bx in [-4, 2, 8]:
        d.ellipse([cx+bx-2, 70, cx+bx+2, 78], fill=(60, 60, 65))
    # Turret on top
    d.ellipse([cx-8, 42, cx+2, 50], fill=(70, 70, 75))
    d.line([(cx-3, 44), (cx-3, 36)], fill=(60, 60, 65), width=2)
    # Roundel
    d.ellipse([cx-24, 52, cx-16, 60], fill=(40, 40, 160))
    d.ellipse([cx-22, 54, cx-18, 58], fill=(220, 220, 220))
    return img

# ============================================================
# GENERATE ALL
# ============================================================

UNITS = {
    "warrior": gen_warrior,
    "spearman": gen_spearman,
    "archer": gen_archer,
    "swordsman": gen_swordsman,
    "horseman": gen_horseman,
    "knight": gen_knight,
    "musketman": gen_musketman,
    "rifleman": gen_rifleman,
    "infantry": gen_infantry,
    "catapult": gen_catapult,
    "artillery": gen_artillery,
    "tank": gen_tank,
    "settler": gen_settler,
    "worker": gen_worker,
    "spy": gen_spy,
    "caravan": gen_caravan,
    "galley": gen_galley,
    "caravel": gen_caravel,
    "ironclad": gen_ironclad,
    "fighter": gen_fighter,
    "bomber": gen_bomber,
}

if __name__ == "__main__":
    for name, gen_func in UNITS.items():
        img = gen_func()
        img = add_outline(img, thickness=3)
        path = os.path.join(OUT, f"{name}.png")
        img.save(path)
        print(f"Generated {path}")
    print(f"\nDone! {len(UNITS)} unit sprites generated.")
