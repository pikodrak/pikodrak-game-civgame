#!/usr/bin/env python3
"""Generate game sprites using DALL-E API."""
import os
import requests
import base64
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
UNIT_DIR = "static/img/units"
BUILDING_DIR = "static/img/buildings"
TERRAIN_DIR = "static/img/terrain"

STYLE = "Civilization II pixel art style, 2D icon, detailed shading with light from upper-left, rich colors, clean edges, transparent background, no text, single object centered"

UNITS = {
    "warrior": "ancient warrior with wooden club and round shield, leather armor, barefoot, primitive",
    "spearman": "ancient greek hoplite with long spear, bronze helmet, round hoplon shield, bronze armor",
    "archer": "medieval archer with longbow drawn, green hood and cloak, quiver of arrows on back",
    "swordsman": "roman legionary with gladius sword, red shield with gold eagle, lorica segmentata armor, red plume helmet",
    "horseman": "mounted cavalry rider on brown horse, holding javelin, light leather armor, galloping pose",
    "knight": "medieval knight in full plate armor on armored black warhorse, lance and heraldic shield, red plume on helmet",
    "musketman": "18th century musketeer soldier in blue coat with white cross-straps, tricorn hat, holding musket with bayonet",
    "rifleman": "WWI soldier in khaki uniform, Brodie helmet, puttees on legs, holding bolt-action rifle, ammo pouches on belt",
    "infantry": "WWII infantry soldier in olive green uniform, M1 steel helmet, web gear harness, holding submachine gun, backpack",
    "catapult": "medieval wooden catapult siege engine with counterweight, wheels, loaded with stone projectile",
    "artillery": "WWI field artillery cannon with gun shield, large spoked wheels, long barrel",
    "tank": "WWII medium tank olive green, rotating turret with long cannon, track wheels visible, side profile view",
    "settler": "pioneer settler family with covered wagon pulled by oxen, canvas top, walking alongside",
    "worker": "medieval peasant worker with shovel and straw hat, simple brown clothes, work tools",
    "spy": "1940s spy in black suit and fedora hat, carrying briefcase, red tie, mysterious pose",
    "caravan": "trade caravan camel loaded with colorful goods bags and gold, desert trader",
    "galley": "ancient greek trireme war galley with rows of oars, single square sail, ram bow, wooden hull",
    "caravel": "15th century Portuguese caravel sailing ship, red cross on white sails, two masts, wooden hull",
    "ironclad": "civil war era ironclad warship, metal armor hull, gun turret, smokestack with black smoke",
    "fighter": "WWII propeller fighter plane side view, olive green fuselage, roundel markings, single engine",
    "bomber": "WWII heavy bomber plane side view, four engines, glass nose, bomb bay, large wingspan",
}

BUILDINGS = {
    "palace": "grand royal palace with golden dome, columns, red flags, stone steps, ornate entrance",
    "granary": "wooden grain storage barn with thatched roof, wheat sheaves by door, rustic",
    "barracks": "military barracks building with flag pole, crossed swords emblem, training dummy outside",
    "harbor": "harbor dock with wooden pier, crane, warehouse, ship mast visible, blue water",
    "library": "classical greek library with columns, pediment, colorful books visible through windows",
    "walls": "medieval stone city walls with battlements, gate with portcullis, guard towers",
    "colosseum": "roman colosseum arena oval structure, arched exterior, sand fighting pit inside",
    "marketplace": "medieval market stall with striped awning, goods on counter, hanging gold coin sign",
    "aqueduct": "roman stone aqueduct with three arches, water channel on top flowing blue water",
    "forge": "blacksmith forge with glowing orange fire, anvil, hammer, chimney with smoke",
    "stable": "wooden horse stable with hay bales, horse head peeking out, horseshoe on wall",
    "temple": "ancient greek temple with tall columns, triangular pediment, altar with golden glow inside",
    "monastery": "medieval stone monastery with bell tower, cross on top, arched windows and door",
    "castle": "medieval stone castle with corner towers, cone roofs, drawbridge, flag on keep",
    "workshop": "craftsman workshop with gear emblem on door, lumber pile outside, tools visible",
    "school": "small schoolhouse with bell tower, blackboard visible in window, welcoming door",
    "university": "grand university building with clock tower, pointed roof, many windows, stone steps",
    "bank": "neoclassical bank with tall columns, golden coin emblem in pediment, heavy bronze door",
    "museum": "grand museum with many columns, wide steps, red banner, sculptures in pediment",
    "theater": "theater building with comedy and tragedy masks, red curtains, domed roof",
    "observatory": "observatory with large dome, telescope slit opening, telescope pointing at stars",
    "military_academy": "imposing military academy building, star emblem over entrance, symmetrical wings, cannon decoration",
    "factory": "industrial factory with sawtooth roof, tall smokestack with smoke, loading dock",
    "power_plant": "power plant with two smokestacks, lightning bolt emblem, industrial pipes",
    "hospital": "white hospital building with large red cross on roof, clean modern look",
    "airport": "airport terminal with control tower, radar antenna, runway markings, small plane",
    "stadium": "sports stadium oval with green field, floodlights, seating tiers",
    "bunker": "military concrete bunker half-buried, gun slit, sandbags, camouflage",
    "nuclear_plant": "nuclear power plant with two cooling towers with steam, reactor building between",
}

TERRAINS = {
    "grass": "lush green grass terrain tile, bright green with subtle grass blade texture, wildflowers",
    "plains": "golden wheat plains terrain tile, dry golden grass with grain stalks",
    "forest": "dense forest terrain tile, tree canopy tops viewed from above, multiple green shades",
    "hills": "rolling green hills terrain tile, rounded hills with light/shadow shading, grass",
    "mountain": "rocky mountain peak terrain tile, grey stone with white snow cap, dramatic",
    "desert": "sandy desert terrain tile, light golden sand with subtle dune ripples",
    "water": "deep ocean water terrain tile, dark blue with subtle wave highlights",
    "coast": "shallow coastal water terrain tile, light turquoise blue, slightly transparent",
}


def generate_image(prompt, size="256x256"):
    """Generate image with DALL-E and return PNG bytes."""
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
        response_format="b64_json",
    )
    return base64.b64decode(response.data[0].b64_json)


def save_image(data, path):
    """Save PNG bytes to file, resize to target size."""
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(data))
    # Units: 128x128, Buildings: 96x96, Terrain: 128x128
    if "units" in path:
        img = img.resize((128, 128), Image.LANCZOS)
    elif "buildings" in path:
        img = img.resize((96, 96), Image.LANCZOS)
    else:
        img = img.resize((128, 128), Image.LANCZOS)
    img.save(path)


def main():
    generated = 0
    errors = 0

    # Units
    print("=== GENERATING UNITS ===")
    os.makedirs(UNIT_DIR, exist_ok=True)
    for name, desc in UNITS.items():
        path = os.path.join(UNIT_DIR, f"{name}.png")
        prompt = f"{desc}, {STYLE}, game unit icon 128x128 pixels"
        print(f"  {name}...", end=" ", flush=True)
        try:
            data = generate_image(prompt)
            save_image(data, path)
            print("OK")
            generated += 1
        except Exception as e:
            print(f"FAILED: {e}")
            errors += 1

    # Buildings
    print("\n=== GENERATING BUILDINGS ===")
    os.makedirs(BUILDING_DIR, exist_ok=True)
    for name, desc in BUILDINGS.items():
        path = os.path.join(BUILDING_DIR, f"{name}.png")
        prompt = f"{desc}, {STYLE}, building icon 96x96 pixels"
        print(f"  {name}...", end=" ", flush=True)
        try:
            data = generate_image(prompt)
            save_image(data, path)
            print("OK")
            generated += 1
        except Exception as e:
            print(f"FAILED: {e}")
            errors += 1

    # Terrain (base + 4 variants = just generate base, copy for variants)
    print("\n=== GENERATING TERRAIN ===")
    os.makedirs(TERRAIN_DIR, exist_ok=True)
    for name, desc in TERRAINS.items():
        base_path = os.path.join(TERRAIN_DIR, f"{name}.png")
        prompt = f"{desc}, {STYLE}, seamless terrain tile, top-down view"
        print(f"  {name}...", end=" ", flush=True)
        try:
            data = generate_image(prompt)
            save_image(data, base_path)
            # Copy base to variants (slightly different would cost 4x more)
            from PIL import Image, ImageEnhance
            base_img = Image.open(base_path)
            for v in range(4):
                vpath = os.path.join(TERRAIN_DIR, f"{name}_{v}.png")
                vimg = base_img.copy()
                # Subtle brightness variation per variant
                enhancer = ImageEnhance.Brightness(vimg)
                vimg = enhancer.enhance(0.95 + v * 0.03)
                vimg.save(vpath)
            print("OK (+4 variants)")
            generated += 1
        except Exception as e:
            print(f"FAILED: {e}")
            errors += 1

    print(f"\nDone! Generated: {generated}, Errors: {errors}")


if __name__ == "__main__":
    main()
