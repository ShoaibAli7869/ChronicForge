#!/usr/bin/env python3
"""Generate all female_hero sprite sheets for ChronicForge."""
from pathlib import Path
from PIL import Image, ImageDraw

SPRITES = Path("assets/sprites")

# Palette — all RGBA
C = {
    'hair':     (28,  18,  18,  255),
    'hair_hi':  (61,  32,  32,  255),
    'skin':     (240, 200, 160, 255),
    'skin_sh':  (212, 160, 112, 255),
    'eye':      (74,  78,  90,  255),
    'jacket':   (46,  74,  58,  255),
    'jkt_sh':   (30,  48,  40,  255),
    'shirt':    (216, 208, 192, 255),
    'pants':    (138, 120, 80,  255),
    'pnt_sh':   (106, 92,  56,  255),
    'boot':     (42,  26,  16,  255),
    'strap':    (90,  56,  32,  255),
    'scarf':    (160, 32,  32,  255),
    'scarf_sh': (122, 24,  24,  255),
    'outline':  (10,  8,   8,   255),
}

def new_frame() -> Image.Image:
    """Blank 128×128 RGBA frame."""
    return Image.new('RGBA', (128, 128), (0, 0, 0, 0))

def make_strip(frames: list) -> Image.Image:
    """Assemble frames into a horizontal strip."""
    strip = Image.new('RGBA', (128 * len(frames), 128), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f, (i * 128, 0))
    return strip

def save_strip(frames: list, name: str) -> Path:
    path = SPRITES / f"female_hero-{name}.png"
    make_strip(frames).save(path)
    print(f"  saved {path.name}  ({len(frames)} frames)")
    return path
