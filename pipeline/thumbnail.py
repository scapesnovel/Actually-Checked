"""
STEP 6 — THUMBNAIL
High-CTR investigative style: dark bg + real screenshot tilted + huge verdict
text + red/green accents + arrow. All generated with Pillow (free).
"""
import json, math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .util import WORK_DIR, ASSETS

FONT_BOLD = str(ASSETS / "fonts" / "Anton-Regular.ttf")
BG = (10, 12, 18)
RED = (255, 59, 74)
GREEN = (0, 229, 160)
YELLOW = (255, 205, 42)


def _font(size):
    try:
        return ImageFont.truetype(FONT_BOLD, size)
    except Exception:
        return ImageFont.load_default()


def make_thumbnail(slug: str, script: dict) -> Path:
    W, H = 1280, 720
    th = script.get("thumbnail", {})
    style = th.get("style", "alarm")
    accent = {"alarm": RED, "money": GREEN, "shock": YELLOW}.get(style, RED)

    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)

    # radial glow
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([W * 0.45, -H * 0.3, W * 1.4, H * 1.3], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img.paste(Image.new("RGB", (W, H), accent), (0, 0), glow)
    dr = ImageDraw.Draw(img)

    # screenshot tilted on right side (the "evidence")
    dossier_path = WORK_DIR / slug / "dossier.json"
    shot_file = None
    if dossier_path.exists():
        d = json.loads(dossier_path.read_text(encoding="utf-8"))
        for s in d.get("screenshots", []):
            if s["name"] == "official_site" and Path(s["path"]).exists():
                shot_file = s["path"]; break
        if not shot_file and d.get("screenshots"):
            p = d["screenshots"][0]["path"]
            shot_file = p if Path(p).exists() else None
    if shot_file:
        shot = Image.open(shot_file).convert("RGB")
        sw = int(W * 0.52)
        shot = shot.resize((sw, int(shot.height * sw / shot.width)))
        shot = shot.crop((0, 0, sw, min(shot.height, int(H * 0.72))))
        bordered = Image.new("RGB", (shot.width + 16, shot.height + 16), (255, 255, 255))
        bordered.paste(shot, (8, 8))
        rot = bordered.rotate(-6, expand=True, fillcolor=BG)
        mask = Image.new("L", bordered.size, 255).rotate(-6, expand=True)
        img.paste(rot, (int(W * 0.47), int(H * 0.16)), mask)

    # big verdict text left
    big = th.get("big_text", "LEGIT?").upper()
    small = th.get("small_text", "we checked").upper()
    f_big = _font(150 if len(big) <= 8 else 116)
    f_small = _font(56)
    x, y = 46, int(H * 0.20)
    for word in big.split():
        # shadow + fill
        dr.text((x + 6, y + 6), word, font=f_big, fill=(0, 0, 0))
        dr.text((x, y), word, font=f_big,
                fill=accent if word.rstrip("?!") in ("SCAM", "FAKE", "BUSTED",
                                                     "PAYS", "LEGIT", "REAL") else (255, 255, 255))
        y += int(f_big.size * 1.02)
    dr.rounded_rectangle([x, y + 14, x + dr.textlength(small, font=f_small) + 36,
                          y + 88], radius=14, fill=(255, 255, 255))
    dr.text((x + 18, y + 22), small, font=f_small, fill=(0, 0, 0))

    # arrow pointing at the screenshot
    ax, ay = int(W * 0.40), int(H * 0.62)
    dr.line([(ax - 110, ay + 80), (ax + 40, ay)], fill=accent, width=22)
    dr.polygon([(ax + 70, ay - 14), (ax + 18, ay - 34), (ax + 34, ay + 40)],
               fill=accent)

    # brand chip
    chip = "ACTUALLY CHECKED"
    f_chip = _font(34)
    cw = dr.textlength(chip, font=f_chip)
    dr.rounded_rectangle([W - cw - 60, H - 74, W - 20, H - 20], radius=12,
                         fill=(0, 0, 0))
    dr.text((W - cw - 40, H - 64), chip, font=f_chip, fill=GREEN)

    out = WORK_DIR / slug / "thumbnail.jpg"
    img.save(out, quality=90)
    return out
