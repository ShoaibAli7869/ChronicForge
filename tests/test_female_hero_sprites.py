import importlib.util, pathlib, sys, pytest
from PIL import Image as PILImage

SPRITES = pathlib.Path("assets/sprites")

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
    ("combo_1",     384),
    ("combo_1_end", 512),
    ("combo_2",     768),
    ("combo_2_end", 512),
    ("combo_3",    1536),
    ("combo_3_end", 768),
])
def test_combat_strips(name, expected_w):
    path = SPRITES / f"female_hero-{name}.png"
    assert path.exists(), f"{path.name} not found"
    img = PILImage.open(path)
    assert img.size == (expected_w, 128), f"{path.name}: expected {expected_w}x128, got {img.size}"


@pytest.mark.parametrize("name,expected_w", [
    ("run_to_idle",  896),
    ("idle_turn",    512),
    ("walk_turn",    512),
    ("run_turn",     512),
])
def test_transition_strips(name, expected_w):
    path = SPRITES / f"female_hero-{name}.png"
    assert path.exists(), f"{path.name} not found"
    img = PILImage.open(path)
    assert img.size == (expected_w, 128), f"{path.name}: expected {expected_w}x128, got {img.size}"


@pytest.mark.parametrize("name,expected_w", [
    ("ledge_hang",  896),
    ("ledge_climb", 1408),
    ("wall_slide",  512),
    ("wall_jump",   512),
])
def test_platformer_strips(name, expected_w):
    path = SPRITES / f"female_hero-{name}.png"
    assert path.exists(), f"{path.name} not found"
    img = PILImage.open(path)
    assert img.size == (expected_w, 128), f"{path.name}: expected {expected_w}x128, got {img.size}"


@pytest.mark.parametrize("name,expected_w", [
    ("dash",  640),
    ("slide", 1024),
    ("hurt",  768),
    ("death", 2944),
])
def test_action_strips(name, expected_w):
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


ALL_SPRITES = [
    ("design",       128),
    ("idle",        1280),
    ("idle_turn",    512),
    ("walk",        1280),
    ("walk_turn",    512),
    ("run",         1280),
    ("run_turn",     512),
    ("run_to_idle",  896),
    ("jump",         768),
    ("fall",         512),
    ("fall_loop",    384),
    ("dash",         640),
    ("slide",       1024),
    ("hurt",         768),
    ("death",       2944),
    ("ledge_hang",   896),
    ("ledge_climb", 1408),
    ("wall_slide",   512),
    ("wall_jump",    512),
    ("combo_1",      384),
    ("combo_1_end",  512),
    ("combo_2",      768),
    ("combo_2_end",  512),
    ("combo_3",     1536),
    ("combo_3_end",  768),
]

def test_all_sprites_exist_and_correct_dimensions():
    missing, wrong = [], []
    for name, expected_w in ALL_SPRITES:
        path = SPRITES / f"female_hero-{name}.png"
        if not path.exists():
            missing.append(name)
            continue
        img = PILImage.open(path)
        if img.size != (expected_w, 128):
            wrong.append(f"{name}: got {img.size}, expected ({expected_w}, 128)")
    assert not missing, f"Missing sprites: {missing}"
    assert not wrong, f"Wrong dimensions: {wrong}"

def test_all_sprites_are_rgba():
    for name, _ in ALL_SPRITES:
        path = SPRITES / f"female_hero-{name}.png"
        if path.exists():
            img = PILImage.open(path)
            assert img.mode == 'RGBA', f"{name}.png is not RGBA (got {img.mode})"
