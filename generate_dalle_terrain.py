#!/usr/bin/env python3
"""Generate flat seamless terrain textures via DALL-E for hex tile use."""
import os
import base64
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
OUT = "static/img/terrain"
os.makedirs(OUT, exist_ok=True)

STYLE = "seamless flat texture, top-down aerial view, NO borders, NO frame, NO edges, NO isometric, NO 3D perspective, fills entire image edge to edge, pixel art style, vibrant colors"

TERRAINS = {
    "grass":    "lush green grass lawn texture, bright vivid green, small grass blades and tiny wildflowers, natural variation",
    "plains":   "golden wheat field texture from above, dry golden yellow grass with grain stalks, warm harvest colors",
    "forest":   "dense forest canopy from directly above, round tree tops in various greens, dark green to emerald",
    "hills":    "rolling grassy green hills from above, rounded bumps with light and shadow, green with brown patches",
    "mountain": "rocky grey mountain terrain from above, jagged grey rocks with white snow patches, stone texture",
    "desert":   "sandy desert texture from above, light golden sand with subtle wind ripple patterns, warm beige",
    "water":    "deep ocean water surface from above, dark navy blue with subtle wave pattern, white foam highlights",
    "coast":    "shallow tropical water from above, light turquoise cyan clear water, slightly transparent, bright blue-green",
}


def generate_and_save(name, desc):
    prompt = f"{desc}, {STYLE}"
    print(f"  {name}...", end=" ", flush=True)
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
            response_format="b64_json",
        )
        img_data = base64.b64decode(response.data[0].b64_json)

        from PIL import Image, ImageEnhance
        import io
        img = Image.open(io.BytesIO(img_data))
        img = img.resize((128, 128), Image.LANCZOS)

        # Save base
        img.save(os.path.join(OUT, f"{name}.png"))

        # 4 variants with subtle brightness shift
        for v in range(4):
            vimg = img.copy()
            enhancer = ImageEnhance.Brightness(vimg)
            vimg = enhancer.enhance(0.94 + v * 0.04)
            vimg.save(os.path.join(OUT, f"{name}_{v}.png"))

        print("OK (+4 variants)")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False


if __name__ == "__main__":
    ok = 0
    for name, desc in TERRAINS.items():
        if generate_and_save(name, desc):
            ok += 1
    print(f"\nDone! {ok}/{len(TERRAINS)} terrain types generated.")
