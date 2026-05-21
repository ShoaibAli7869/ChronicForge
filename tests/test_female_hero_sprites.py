import importlib.util, pathlib, sys
from PIL import Image as PILImage
from pathlib import Path

SPRITES = Path("assets/sprites")

def _load():
    spec = importlib.util.spec_from_file_location(
        'gen', pathlib.Path('tools/generate_female_hero.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_palette_constants():
    mod = _load()
    for key in ('hair', 'skin', 'eye', 'jacket', 'pants', 'boot', 'scarf', 'outline'):
        assert key in mod.C, f"missing palette key: {key}"

def test_new_frame_size():
    mod = _load()
    img = mod.new_frame()
    assert img.size == (128, 128)
    assert img.mode == 'RGBA'

def test_make_strip_width():
    mod = _load()
    frames = [mod.new_frame() for _ in range(5)]
    strip = mod.make_strip(frames)
    assert strip.size == (640, 128)

def test_draw_frame_has_pixels():
    mod = _load()
    frame = mod.draw_frame({})
    assert frame.size == (128, 128)
    assert frame.mode == 'RGBA'
    # character must have non-transparent pixels in torso area
    pixels = [frame.getpixel((x, 40)) for x in range(56, 73)]
    assert any(p[3] > 0 for p in pixels), "torso row is fully transparent"

def test_draw_frame_bottom_transparent():
    mod = _load()
    frame = mod.draw_frame({})
    # bottom 28 rows should be transparent
    pixels = [frame.getpixel((64, y)) for y in range(101, 128)]
    assert all(p[3] == 0 for p in pixels), "bottom padding has pixels"


import pytest


def test_design_sheet_exists():
    path = SPRITES / "female_hero-design.png"
    assert path.exists(), "female_hero-design.png not found"
    img = PILImage.open(path)
    assert img.size == (128, 128), f"expected 128x128, got {img.size}"
    assert img.mode == 'RGBA'


@pytest.mark.parametrize("name,expected_w", [
    ("idle",  1280),
    ("walk",  1280),
    ("run",   1280),
])
def test_locomotion_strips(name, expected_w):
    path = SPRITES / f"female_hero-{name}.png"
    assert path.exists(), f"{path.name} not found"
    img = PILImage.open(path)
    assert img.size == (expected_w, 128), f"{path.name}: expected {expected_w}x128, got {img.size}"


@pytest.mark.parametrize("name,expected_w", [
    ("jump",      768),
    ("fall",      512),
    ("fall_loop", 384),
])
def test_air_strips(name, expected_w):
    path = SPRITES / f"female_hero-{name}.png"
    assert path.exists(), f"{path.name} not found"
    img = PILImage.open(path)
    assert img.size == (expected_w, 128), f"{path.name}: expected {expected_w}x128, got {img.size}"
