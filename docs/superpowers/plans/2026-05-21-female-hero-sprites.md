# Female Hero Sprite Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate all 25 `female_hero` sprite sheets (166 frames total) for ChronicForge using a Pillow-based Python script, matching male_hero frame counts and dimensions with a Mikasa-inspired military aesthetic.

**Architecture:** `tools/generate_female_hero.py` defines the character as pixel regions in a neutral pose, each animation as a list of pose dicts (offsets from neutral), renders 128×128 RGBA frames with Pillow, assembles horizontal PNG strips, and saves to `assets/sprites/`. Tests verify every output exists with correct dimensions. A final step imports PNGs into Aseprite to produce `.aseprite` source files.

**Tech Stack:** Python 3, Pillow (PIL 10.2), pytest, Aseprite CLI (`/usr/bin/aseprite`)

---

## File Map

| File | Role |
|---|---|
| `tools/generate_female_hero.py` | Full generation script — palette, drawing, all animations, `main()` |
| `tests/test_female_hero_sprites.py` | Dimension + existence verification for all 25 PNGs |

---

## Task 1: Scaffold — palette, frame helpers, strip assembly

**Files:**
- Create: `tools/generate_female_hero.py`
- Create: `tests/test_female_hero_sprites.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_female_hero_sprites.py
import importlib.util, pathlib, sys

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError` or `FileNotFoundError`

- [ ] **Step 3: Create scaffold**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py::test_palette_constants tests/test_female_hero_sprites.py::test_new_frame_size tests/test_female_hero_sprites.py::test_make_strip_width -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tools/generate_female_hero.py tests/test_female_hero_sprites.py
git commit -m "feat: scaffold female hero sprite generator with palette and frame helpers"
```

---

## Task 2: Implement `draw_frame()` — full character body

**Files:**
- Modify: `tools/generate_female_hero.py`

The character is drawn bottom-to-top so overlapping parts layer correctly. All coordinates are for the neutral standing pose; the `pose` dict carries per-frame offsets.

**Neutral pose anchor points (128×128 canvas):**
- Head center: (64, 17); face y=14–26
- Torso: x=56–72, y=30–56
- Arms at sides: x=46–54 (left), x=74–82 (right), y=30–56
- Legs: left x=56–63, right x=65–72, y=62–90
- Boots: left x=54–64, right x=64–74, y=90–100
- Bottom transparent: y=100–127

**Pose dict keys:**
| Key | Meaning |
|---|---|
| `body_y` | Whole-body vertical shift (negative = up/bob) |
| `body_lean` | Whole-body X shift (lean/dash) |
| `l_leg_x`, `r_leg_x` | Leg horizontal swing offset |
| `l_leg_raise`, `r_leg_raise` | Leg raised (positive = bent up, shortens shin/boot) |
| `l_arm_x`, `r_arm_x` | Arm swing offset |
| `l_arm_y`, `r_arm_y` | Arm vertical offset |
| `crouch` | Compress body (whole body shift down) |
| `flip` | Mirror horizontally (for turn animations) |

- [ ] **Step 1: Write the failing test**

Append to `tests/test_female_hero_sprites.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py::test_draw_frame_has_pixels -v 2>&1 | head -10
```

Expected: `AttributeError: module has no attribute 'draw_frame'`

- [ ] **Step 3: Implement `draw_frame()`**

Append to `tools/generate_female_hero.py` after `save_strip`:

```python
def _px(img: Image.Image, x: int, y: int, color: tuple):
    """Safe single-pixel write."""
    if 0 <= x <= 127 and 0 <= y <= 127:
        img.putpixel((x, y), color)

def _rect(d: ImageDraw.ImageDraw, x1, y1, x2, y2, fill):
    """Safe filled rectangle."""
    d.rectangle([max(0, x1), max(0, y1), min(127, x2), min(127, y2)], fill=fill)

def draw_frame(pose: dict | None = None) -> Image.Image:
    """Draw one 128×128 RGBA frame for the neutral/standing female hero pose.

    pose dict keys: body_y, body_lean, crouch, l_leg_x, r_leg_x,
                    l_leg_raise, r_leg_raise, l_arm_x, r_arm_x,
                    l_arm_y, r_arm_y, flip.
    All offsets are in pixels; absent keys default to 0 / False.
    """
    if pose is None:
        pose = {}

    img = new_frame()
    d   = ImageDraw.Draw(img)

    by  = int(pose.get('body_y',      0))
    bx  = int(pose.get('body_lean',   0))
    cr  = int(pose.get('crouch',      0))
    llx = int(pose.get('l_leg_x',     0))
    rlx = int(pose.get('r_leg_x',     0))
    llr = int(pose.get('l_leg_raise', 0))
    rlr = int(pose.get('r_leg_raise', 0))
    lax = int(pose.get('l_arm_x',     0))
    rax = int(pose.get('r_arm_x',     0))
    lay = int(pose.get('l_arm_y',     0))
    ray = int(pose.get('r_arm_y',     0))

    # ── BOOTS ─────────────────────────────────────────────────
    _rect(d, 54+llx+bx, 90+by-llr, 64+llx+bx, 100+by-llr, C['boot'])
    _rect(d, 64+rlx+bx, 90+by-rlr, 74+rlx+bx, 100+by-rlr, C['boot'])

    # ── SHINS ─────────────────────────────────────────────────
    _rect(d, 56+llx+bx, 76+by-llr, 63+llx+bx, 90+by-llr,  C['pnt_sh'])
    _rect(d, 65+rlx+bx, 76+by-rlr, 72+rlx+bx, 90+by-rlr,  C['pnt_sh'])

    # ── THIGHS ────────────────────────────────────────────────
    _rect(d, 56+llx+bx, 62+by-cr,  63+llx+bx, 76+by,       C['pants'])
    _rect(d, 65+rlx+bx, 62+by-cr,  72+rlx+bx, 76+by,       C['pants'])

    # ── BELT ──────────────────────────────────────────────────
    _rect(d, 55+bx, 56+by-cr, 73+bx, 62+by-cr, C['strap'])

    # ── TORSO (jacket) ────────────────────────────────────────
    _rect(d, 56+bx, 30+by-cr, 72+bx, 56+by-cr, C['jacket'])
    _rect(d, 50+bx, 30+by-cr, 56+bx, 40+by-cr, C['jacket'])   # L shoulder
    _rect(d, 72+bx, 30+by-cr, 78+bx, 40+by-cr, C['jacket'])   # R shoulder
    _rect(d, 56+bx, 44+by-cr, 72+bx, 56+by-cr, C['jkt_sh'])   # lower shadow
    _rect(d, 60+bx, 30+by-cr, 68+bx, 34+by-cr, C['shirt'])    # collar

    # diagonal straps across torso
    torso_top = 32+by-cr
    for i in range(24):
        t = i / 23.0
        _px(img, int(58+bx + t*7),  torso_top+i, C['strap'])   # left strap
        _px(img, int(70+bx - t*7),  torso_top+i, C['strap'])   # right strap

    # ── ARMS ──────────────────────────────────────────────────
    _rect(d, 46+lax+bx, 30+lay+by-cr, 54+lax+bx, 44+lay+by-cr, C['jacket'])
    _rect(d, 46+lax+bx, 44+lay+by-cr, 54+lax+bx, 58+lay+by-cr, C['jkt_sh'])
    _rect(d, 74+rax+bx, 30+ray+by-cr, 82+rax+bx, 44+ray+by-cr, C['jacket'])
    _rect(d, 74+rax+bx, 44+ray+by-cr, 82+rax+bx, 58+ray+by-cr, C['jkt_sh'])

    # ── SCARF ─────────────────────────────────────────────────
    _rect(d, 57+bx, 24+by-cr, 71+bx, 33+by-cr, C['scarf'])
    _rect(d, 57+bx, 33+by-cr, 71+bx, 37+by-cr, C['scarf_sh'])

    # ── NECK ──────────────────────────────────────────────────
    _rect(d, 62+bx, 26+by-cr, 66+bx, 30+by-cr, C['skin'])

    # ── HEAD ──────────────────────────────────────────────────
    _rect(d, 55+bx, 8+by,  73+bx, 20+by, C['hair'])         # hair bulk
    _rect(d, 57+bx, 8+by,  63+bx, 13+by, C['hair_hi'])      # hair highlight
    _rect(d, 58+bx, 14+by, 70+bx, 26+by, C['skin'])         # face
    _rect(d, 55+bx, 10+by, 59+bx, 23+by, C['hair'])         # L hair side
    _rect(d, 69+bx, 10+by, 73+bx, 23+by, C['hair'])         # R hair side
    _rect(d, 59+bx, 22+by, 69+bx, 26+by, C['skin_sh'])      # chin shadow
    _px(img, 62+bx, 19+by, C['eye'])                         # left eye
    _px(img, 66+bx, 19+by, C['eye'])                         # right eye

    # ── OUTLINE (key silhouette edges) ────────────────────────
    for x in range(55+bx, 74+bx):
        _px(img, x, 7+by, C['outline'])                      # hair top
    for y in range(8+by, 100+by):
        _px(img, 45+bx, y, C['outline'])                     # left edge
        _px(img, 83+bx, y, C['outline'])                     # right edge
    for x in range(54+bx, 75+bx):
        _px(img, x, 100+by, C['outline'])                    # feet bottom

    if pose.get('flip', False):
        img = img.transpose(Image.FLIP_LEFT_RIGHT)

    return img
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py -v -k "draw_frame"
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tools/generate_female_hero.py tests/test_female_hero_sprites.py
git commit -m "feat: implement draw_frame with full character body drawing"
```

---

## Task 3: Design reference sheet

**Files:**
- Modify: `tools/generate_female_hero.py`
- Modify: `tests/test_female_hero_sprites.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_female_hero_sprites.py`:

```python
from PIL import Image as PILImage
from pathlib import Path

SPRITES = Path("assets/sprites")

def test_design_sheet_exists():
    path = SPRITES / "female_hero-design.png"
    assert path.exists(), "female_hero-design.png not found"
    img = PILImage.open(path)
    assert img.size == (128, 128), f"expected 128x128, got {img.size}"
    assert img.mode == 'RGBA'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py::test_design_sheet_exists -v
```

Expected: `AssertionError: female_hero-design.png not found`

- [ ] **Step 3: Implement `gen_design()` and call it**

Append to `tools/generate_female_hero.py`:

```python
def gen_design() -> None:
    """Reference sheet — neutral front-facing pose."""
    save_strip([draw_frame({})], 'design')
```

Add `main()` and entrypoint at the bottom:

```python
def main():
    SPRITES.mkdir(parents=True, exist_ok=True)
    gen_design()

if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run generator and test**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python tools/generate_female_hero.py && python -m pytest tests/test_female_hero_sprites.py::test_design_sheet_exists -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add tools/generate_female_hero.py tests/test_female_hero_sprites.py
git commit -m "feat: add design reference sheet generation"
```

---

## Task 4: Locomotion animations — idle, walk, run

**Files:**
- Modify: `tools/generate_female_hero.py`
- Modify: `tests/test_female_hero_sprites.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_female_hero_sprites.py`:

```python
import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py::test_locomotion_strips -v
```

Expected: 3 failed (files not found)

- [ ] **Step 3: Implement `gen_idle()`, `gen_walk()`, `gen_run()`**

Append to `tools/generate_female_hero.py` before `main()`:

```python
def gen_idle() -> None:
    """10-frame breathing cycle — 1-2px vertical bob."""
    # body_y: 0 → -1 → -2 → -2 → -1 → 0 → 0 → -1 → -1 → 0
    bobs = [0, -1, -2, -2, -1, 0, 0, -1, -1, 0]
    frames = [draw_frame({'body_y': b}) for b in bobs]
    save_strip(frames, 'idle')


def gen_walk() -> None:
    """10-frame walk cycle — pendulum legs, counter-swing arms, 2px bob."""
    # (body_y, l_leg_x, r_leg_x, l_leg_raise, r_leg_raise, l_arm_x, r_arm_x)
    poses = [
        (0,  -3, +3,  0,  0, +3, -3),
        (-1, -5, +1,  0,  4, +5, -5),
        (-2, -4, -1,  0,  7, +4, -4),
        (-1, -2, -3,  3,  4, +2, -2),
        (0,   0, -4,  5,  0,  0,  0),
        (0,  +3, -3,  0,  0, -3, +3),
        (-1, +1, -5,  4,  0, -5, +5),
        (-2, +1, -4,  7,  0, -4, +4),
        (-1, +3, -2,  4,  3, -2, +2),
        (0,  +4,  0,  0,  5,  0,  0),
    ]
    frames = [draw_frame({
        'body_y':      p[0],
        'l_leg_x':     p[1], 'r_leg_x':     p[2],
        'l_leg_raise': p[3], 'r_leg_raise': p[4],
        'l_arm_x':     p[5], 'r_arm_x':     p[6],
    }) for p in poses]
    save_strip(frames, 'walk')


def gen_run() -> None:
    """10-frame run cycle — more exaggerated than walk, forward lean."""
    poses = [
        (0,  -6, +6,  0,  0, +6, -6),
        (-2, -8, +2,  0,  7, +8, -8),
        (-3, -6,  0,  0,  9, +6, -6),
        (-2, -3, -4,  4,  6, +4, -4),
        (0,   0, -7,  8,  0,  0,  0),
        (0,  +6, -6,  0,  0, -6, +6),
        (-2, +2, -8,  7,  0, -8, +8),
        (-3,  0, -6,  9,  0, -6, +6),
        (-2, +4, -3,  6,  4, -4, +4),
        (0,  +7,  0,  0,  8,  0,  0),
    ]
    frames = [draw_frame({
        'body_y': p[0], 'body_lean': 2,
        'l_leg_x': p[1], 'r_leg_x': p[2],
        'l_leg_raise': p[3], 'r_leg_raise': p[4],
        'l_arm_x': p[5], 'r_arm_x': p[6],
    }) for p in poses]
    save_strip(frames, 'run')
```

Update `main()`:

```python
def main():
    SPRITES.mkdir(parents=True, exist_ok=True)
    gen_design()
    gen_idle()
    gen_walk()
    gen_run()
```

- [ ] **Step 4: Run generator and tests**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python tools/generate_female_hero.py && python -m pytest tests/test_female_hero_sprites.py::test_locomotion_strips -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tools/generate_female_hero.py tests/test_female_hero_sprites.py
git commit -m "feat: add idle, walk, run animation generation"
```

---

## Task 5: Air animations — jump, fall, fall_loop

**Files:**
- Modify: `tools/generate_female_hero.py`
- Modify: `tests/test_female_hero_sprites.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_female_hero_sprites.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py::test_air_strips -v
```

Expected: 3 failed

- [ ] **Step 3: Implement air animations**

Append to `tools/generate_female_hero.py` before `main()`:

```python
def gen_jump() -> None:
    """6-frame jump: crouch → push → rise → peak tuck → spread → fall entry."""
    poses = [
        {'body_y':  4, 'crouch': 3, 'l_leg_raise': 0, 'r_leg_raise': 0},   # f0 crouch
        {'body_y':  0, 'crouch': 0, 'l_leg_raise': 0, 'r_leg_raise': 0},   # f1 push
        {'body_y': -4, 'l_leg_raise': 3, 'r_leg_raise': 3, 'l_arm_y': -4, 'r_arm_y': -4},  # f2 rising
        {'body_y': -6, 'l_leg_raise': 7, 'r_leg_raise': 7, 'l_arm_y': -6, 'r_arm_y': -6},  # f3 peak
        {'body_y': -4, 'l_leg_raise': 5, 'r_leg_raise': 5, 'l_arm_y': -2, 'r_arm_y': -2},  # f4 apex
        {'body_y': -2, 'l_leg_raise': 2, 'r_leg_raise': 2},                  # f5 descent start
    ]
    save_strip([draw_frame(p) for p in poses], 'jump')


def gen_fall() -> None:
    """4-frame fall: arms spread, body tilt forward."""
    poses = [
        {'body_y': 0,  'l_arm_x': -3, 'r_arm_x': +3, 'l_arm_y': -2, 'r_arm_y': -2},
        {'body_y': 0,  'l_arm_x': -5, 'r_arm_x': +5, 'l_arm_y': -4, 'r_arm_y': -4, 'body_lean': 1},
        {'body_y': 1,  'l_arm_x': -5, 'r_arm_x': +5, 'l_arm_y': -3, 'r_arm_y': -3, 'body_lean': 2},
        {'body_y': 2,  'l_arm_x': -4, 'r_arm_x': +4, 'l_arm_y': -2, 'r_arm_y': -2, 'body_lean': 2},
    ]
    save_strip([draw_frame(p) for p in poses], 'fall')


def gen_fall_loop() -> None:
    """3-frame looping fall — repeating descent pose."""
    poses = [
        {'body_y': 0, 'l_arm_x': -4, 'r_arm_x': +4, 'l_arm_y': -3, 'r_arm_y': -3, 'body_lean': 2},
        {'body_y': 1, 'l_arm_x': -5, 'r_arm_x': +5, 'l_arm_y': -4, 'r_arm_y': -4, 'body_lean': 2},
        {'body_y': 0, 'l_arm_x': -4, 'r_arm_x': +4, 'l_arm_y': -3, 'r_arm_y': -3, 'body_lean': 2},
    ]
    save_strip([draw_frame(p) for p in poses], 'fall_loop')
```

Update `main()` to add:

```python
    gen_jump()
    gen_fall()
    gen_fall_loop()
```

- [ ] **Step 4: Run and verify**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python tools/generate_female_hero.py && python -m pytest tests/test_female_hero_sprites.py::test_air_strips -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tools/generate_female_hero.py tests/test_female_hero_sprites.py
git commit -m "feat: add jump, fall, fall_loop animation generation"
```

---

## Task 6: Action animations — dash, slide, hurt, death

**Files:**
- Modify: `tools/generate_female_hero.py`
- Modify: `tests/test_female_hero_sprites.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_female_hero_sprites.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py::test_action_strips -v
```

Expected: 4 failed

- [ ] **Step 3: Implement action animations**

Append to `tools/generate_female_hero.py` before `main()`:

```python
def gen_dash() -> None:
    """5-frame dash: extreme forward lean, legs extended back."""
    poses = [
        {'body_lean':  2, 'body_y': -1, 'l_leg_x': -2, 'r_leg_x': +2},
        {'body_lean':  5, 'body_y': -2, 'l_leg_x': -4, 'r_leg_x': +6, 'l_arm_y': -3, 'r_arm_y': -1},
        {'body_lean':  8, 'body_y': -2, 'l_leg_x': -6, 'r_leg_x': +8, 'l_arm_y': -4, 'r_arm_y':  0},
        {'body_lean':  6, 'body_y': -1, 'l_leg_x': -4, 'r_leg_x': +6, 'l_arm_y': -3, 'r_arm_y': -1},
        {'body_lean':  3, 'body_y':  0, 'l_leg_x': -2, 'r_leg_x': +3},
    ]
    save_strip([draw_frame(p) for p in poses], 'dash')


def gen_slide() -> None:
    """8-frame slide: crouch into horizontal glide, then recover."""
    poses = [
        {'body_y': 2,  'crouch': 1},
        {'body_y': 5,  'crouch': 4,  'body_lean': 3},
        {'body_y': 8,  'crouch': 8,  'body_lean': 6,  'l_leg_x': -4, 'r_leg_x': +4},
        {'body_y': 10, 'crouch': 10, 'body_lean': 8,  'l_leg_x': -6, 'r_leg_x': +8},
        {'body_y': 10, 'crouch': 10, 'body_lean': 8,  'l_leg_x': -6, 'r_leg_x': +8},
        {'body_y': 8,  'crouch': 8,  'body_lean': 6,  'l_leg_x': -4, 'r_leg_x': +6},
        {'body_y': 5,  'crouch': 4,  'body_lean': 3},
        {'body_y': 2,  'crouch': 1},
    ]
    save_strip([draw_frame(p) for p in poses], 'slide')


def gen_hurt() -> None:
    """6-frame hurt: recoil back, arms fly out, recover."""
    poses = [
        {'body_lean': -2, 'l_arm_x': -3, 'r_arm_x': +3},
        {'body_lean': -5, 'body_y': -1, 'l_arm_x': -6, 'r_arm_x': +6, 'l_arm_y': -3, 'r_arm_y': -3},
        {'body_lean': -6, 'body_y': -2, 'l_arm_x': -7, 'r_arm_x': +7, 'l_arm_y': -4, 'r_arm_y': -4},
        {'body_lean': -5, 'body_y': -1, 'l_arm_x': -5, 'r_arm_x': +5, 'l_arm_y': -2, 'r_arm_y': -2},
        {'body_lean': -3, 'l_arm_x': -3, 'r_arm_x': +3},
        {'body_lean':  0},
    ]
    save_strip([draw_frame(p) for p in poses], 'hurt')


def gen_death() -> None:
    """23-frame death: stagger (4) → kneel (6) → collapse (7) → settle (6)."""
    # stagger: reel back
    stagger = [
        {'body_lean': -3, 'body_y': -1},
        {'body_lean': -5, 'body_y': -2, 'l_arm_x': -4, 'r_arm_x': +4},
        {'body_lean': -4, 'body_y': -1, 'l_arm_x': -3, 'r_arm_x': +3},
        {'body_lean': -2, 'body_y':  0},
    ]
    # kneel: body dropping, legs buckling
    kneel = [
        {'body_y':  2, 'crouch': 2,  'l_leg_raise': 2,  'r_leg_raise': 0},
        {'body_y':  5, 'crouch': 5,  'l_leg_raise': 5,  'r_leg_raise': 2},
        {'body_y':  8, 'crouch': 8,  'l_leg_raise': 8,  'r_leg_raise': 5},
        {'body_y': 10, 'crouch': 10, 'l_leg_raise': 10, 'r_leg_raise': 8},
        {'body_y': 12, 'crouch': 12, 'l_leg_raise': 12, 'r_leg_raise': 10},
        {'body_y': 14, 'crouch': 14, 'l_leg_raise': 14, 'r_leg_raise': 12},
    ]
    # collapse: full fall forward
    collapse = [
        {'body_y': 16, 'crouch': 16, 'body_lean': 3,  'l_arm_x': -4, 'r_arm_x': +4},
        {'body_y': 18, 'crouch': 18, 'body_lean': 6,  'l_arm_x': -6, 'r_arm_x': +6},
        {'body_y': 20, 'crouch': 20, 'body_lean': 9,  'l_arm_x': -7, 'r_arm_x': +7},
        {'body_y': 22, 'crouch': 22, 'body_lean': 12, 'l_arm_x': -7, 'r_arm_x': +7},
        {'body_y': 24, 'crouch': 24, 'body_lean': 14, 'l_arm_x': -6, 'r_arm_x': +6},
        {'body_y': 25, 'crouch': 25, 'body_lean': 15, 'l_arm_x': -5, 'r_arm_x': +5},
        {'body_y': 26, 'crouch': 26, 'body_lean': 16, 'l_arm_x': -4, 'r_arm_x': +4},
    ]
    # settle: final rest pose (repeat last frame with micro-adjustment)
    settle = [
        {'body_y': 26, 'crouch': 26, 'body_lean': 16, 'l_arm_x': -4, 'r_arm_x': +4},
        {'body_y': 27, 'crouch': 26, 'body_lean': 16, 'l_arm_x': -4, 'r_arm_x': +3},
        {'body_y': 27, 'crouch': 26, 'body_lean': 16, 'l_arm_x': -3, 'r_arm_x': +3},
        {'body_y': 27, 'crouch': 26, 'body_lean': 16, 'l_arm_x': -3, 'r_arm_x': +3},
        {'body_y': 27, 'crouch': 26, 'body_lean': 16, 'l_arm_x': -3, 'r_arm_x': +3},
        {'body_y': 27, 'crouch': 26, 'body_lean': 16, 'l_arm_x': -3, 'r_arm_x': +3},
    ]
    all_poses = stagger + kneel + collapse + settle
    assert len(all_poses) == 23
    save_strip([draw_frame(p) for p in all_poses], 'death')
```

Update `main()`:

```python
    gen_dash()
    gen_slide()
    gen_hurt()
    gen_death()
```

- [ ] **Step 4: Run and verify**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python tools/generate_female_hero.py && python -m pytest tests/test_female_hero_sprites.py::test_action_strips -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tools/generate_female_hero.py tests/test_female_hero_sprites.py
git commit -m "feat: add dash, slide, hurt, death animation generation"
```

---

## Task 7: Platformer animations — ledge_hang, ledge_climb, wall_slide, wall_jump

**Files:**
- Modify: `tools/generate_female_hero.py`
- Modify: `tests/test_female_hero_sprites.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_female_hero_sprites.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py::test_platformer_strips -v
```

Expected: 4 failed

- [ ] **Step 3: Implement platformer animations**

Append to `tools/generate_female_hero.py` before `main()`:

```python
def gen_ledge_hang() -> None:
    """7-frame ledge hang: arms raised, legs dangling."""
    poses = [
        {'body_y':  0, 'l_arm_y': -8, 'r_arm_y': -8, 'l_leg_raise': -3, 'r_leg_raise': -3},
        {'body_y':  1, 'l_arm_y': -8, 'r_arm_y': -8, 'l_leg_raise': -3, 'r_leg_raise': -3},
        {'body_y':  0, 'l_arm_y': -9, 'r_arm_y': -9, 'l_leg_raise': -4, 'r_leg_raise': -4},
        {'body_y':  1, 'l_arm_y': -9, 'r_arm_y': -9, 'l_leg_raise': -4, 'r_leg_raise': -4},
        {'body_y':  0, 'l_arm_y': -8, 'r_arm_y': -8, 'l_leg_raise': -3, 'r_leg_raise': -3},
        {'body_y':  1, 'l_arm_y': -8, 'r_arm_y': -8, 'l_leg_raise': -4, 'r_leg_raise': -3},
        {'body_y':  0, 'l_arm_y': -8, 'r_arm_y': -8, 'l_leg_raise': -3, 'r_leg_raise': -3},
    ]
    save_strip([draw_frame(p) for p in poses], 'ledge_hang')


def gen_ledge_climb() -> None:
    """11-frame ledge climb: pull up, swing leg over, stand."""
    poses = [
        {'body_y':  2, 'l_arm_y': -10, 'r_arm_y': -10},                           # f0 hanging high
        {'body_y':  0, 'l_arm_y': -10, 'r_arm_y': -10, 'l_leg_raise': 5},         # f1 leg swing
        {'body_y': -2, 'l_arm_y': -10, 'r_arm_y': -10, 'l_leg_raise': 10},        # f2 leg high
        {'body_y': -4, 'l_arm_y':  -8, 'r_arm_y':  -8, 'l_leg_raise': 14},        # f3 body rising
        {'body_y': -6, 'l_arm_y':  -6, 'r_arm_y':  -6, 'l_leg_raise': 14},        # f4 upper body up
        {'body_y': -8, 'l_arm_y':  -4, 'r_arm_y':  -4, 'l_leg_raise': 10},        # f5 almost over
        {'body_y': -8, 'l_arm_y':  -2, 'r_arm_y':  -2, 'l_leg_raise':  6},        # f6 leg over ledge
        {'body_y': -6, 'crouch': 2},                                                # f7 crouch land
        {'body_y': -4, 'crouch': 1},                                                # f8 rising
        {'body_y': -2},                                                             # f9 almost stand
        {'body_y':  0},                                                             # f10 stand
    ]
    save_strip([draw_frame(p) for p in poses], 'ledge_climb')


def gen_wall_slide() -> None:
    """4-frame wall slide: leaning into wall, slow descend."""
    poses = [
        {'body_lean': 4, 'l_arm_x': 4, 'r_arm_x': 4, 'l_arm_y': -4, 'r_arm_y': -6},
        {'body_lean': 4, 'body_y': 1, 'l_arm_x': 4, 'r_arm_x': 4, 'l_arm_y': -3, 'r_arm_y': -5},
        {'body_lean': 4, 'body_y': 2, 'l_arm_x': 4, 'r_arm_x': 4, 'l_arm_y': -4, 'r_arm_y': -6},
        {'body_lean': 4, 'body_y': 3, 'l_arm_x': 4, 'r_arm_x': 4, 'l_arm_y': -3, 'r_arm_y': -5},
    ]
    save_strip([draw_frame(p) for p in poses], 'wall_slide')


def gen_wall_jump() -> None:
    """4-frame wall jump: push off, airborne."""
    poses = [
        {'body_lean':  4, 'l_arm_x': 4, 'r_arm_x': 4, 'l_arm_y': -4, 'r_arm_y': -6},
        {'body_lean':  0, 'body_y': -2, 'l_arm_x': -4, 'r_arm_x': -2, 'l_arm_y': -6, 'r_arm_y': -4},
        {'body_lean': -3, 'body_y': -4, 'l_arm_x': -6, 'r_arm_x': -4, 'l_arm_y': -8, 'r_arm_y': -6},
        {'body_lean': -4, 'body_y': -5, 'l_arm_x': -6, 'r_arm_x': -4, 'l_arm_y': -7, 'r_arm_y': -5},
    ]
    save_strip([draw_frame(p) for p in poses], 'wall_jump')
```

Update `main()`:

```python
    gen_ledge_hang()
    gen_ledge_climb()
    gen_wall_slide()
    gen_wall_jump()
```

- [ ] **Step 4: Run and verify**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python tools/generate_female_hero.py && python -m pytest tests/test_female_hero_sprites.py::test_platformer_strips -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tools/generate_female_hero.py tests/test_female_hero_sprites.py
git commit -m "feat: add ledge_hang, ledge_climb, wall_slide, wall_jump animation generation"
```

---

## Task 8: Transition animations — run_to_idle, idle_turn, walk_turn, run_turn

**Files:**
- Modify: `tools/generate_female_hero.py`
- Modify: `tests/test_female_hero_sprites.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_female_hero_sprites.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py::test_transition_strips -v
```

Expected: 4 failed

- [ ] **Step 3: Implement transition animations**

Append to `tools/generate_female_hero.py` before `main()`:

```python
def gen_run_to_idle() -> None:
    """7-frame deceleration from run to idle — lean reduces, stance widens."""
    poses = [
        {'body_lean': 6, 'l_leg_x': -5, 'r_leg_x': +7, 'l_arm_x': +7, 'r_arm_x': -7},
        {'body_lean': 4, 'l_leg_x': -3, 'r_leg_x': +5, 'l_arm_x': +5, 'r_arm_x': -5},
        {'body_lean': 3, 'l_leg_x': -2, 'r_leg_x': +3, 'l_arm_x': +3, 'r_arm_x': -3},
        {'body_lean': 2, 'l_leg_x': -1, 'r_leg_x': +2},
        {'body_lean': 1, 'l_leg_x':  0, 'r_leg_x': +1},
        {'body_lean': 0, 'body_y': -1},
        {'body_lean': 0, 'body_y':  0},
    ]
    save_strip([draw_frame(p) for p in poses], 'run_to_idle')


def gen_idle_turn() -> None:
    """4-frame 180° turn from idle: squash, profile, expand, flipped."""
    poses = [
        {},                             # f0 facing right (normal)
        {'body_lean': 3},               # f1 begin turn — lean into turn
        {'body_lean': 3, 'flip': True}, # f2 past profile — mirrored
        {'flip': True},                 # f3 fully turned
    ]
    save_strip([draw_frame(p) for p in poses], 'idle_turn')


def gen_walk_turn() -> None:
    """4-frame walk turn."""
    poses = [
        {'l_leg_x': -3, 'r_leg_x': +3, 'l_arm_x': +2, 'r_arm_x': -2},
        {'body_lean': 3, 'l_leg_x': -2, 'r_leg_x': +2},
        {'body_lean': 3, 'flip': True, 'l_leg_x': -2, 'r_leg_x': +2},
        {'flip': True, 'l_leg_x': -3, 'r_leg_x': +3, 'l_arm_x': -2, 'r_arm_x': +2},
    ]
    save_strip([draw_frame(p) for p in poses], 'walk_turn')


def gen_run_turn() -> None:
    """4-frame run turn — more aggressive lean than walk_turn."""
    poses = [
        {'body_lean':  4, 'l_leg_x': -5, 'r_leg_x': +5, 'l_arm_x': +5, 'r_arm_x': -5},
        {'body_lean':  6},
        {'body_lean':  6, 'flip': True},
        {'body_lean': -4, 'flip': True, 'l_leg_x': -5, 'r_leg_x': +5, 'l_arm_x': -5, 'r_arm_x': +5},
    ]
    save_strip([draw_frame(p) for p in poses], 'run_turn')
```

Update `main()`:

```python
    gen_run_to_idle()
    gen_idle_turn()
    gen_walk_turn()
    gen_run_turn()
```

- [ ] **Step 4: Run and verify**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python tools/generate_female_hero.py && python -m pytest tests/test_female_hero_sprites.py::test_transition_strips -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tools/generate_female_hero.py tests/test_female_hero_sprites.py
git commit -m "feat: add run_to_idle, idle_turn, walk_turn, run_turn transition generation"
```

---

## Task 9: Combat animations — combo_1, combo_2, combo_3 and their end frames

**Files:**
- Modify: `tools/generate_female_hero.py`
- Modify: `tests/test_female_hero_sprites.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_female_hero_sprites.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py::test_combat_strips -v
```

Expected: 6 failed

- [ ] **Step 3: Implement combat animations**

Append to `tools/generate_female_hero.py` before `main()`:

```python
def gen_combo_1() -> None:
    """3-frame quick jab: windup → strike → follow-through."""
    poses = [
        {'body_lean':  2, 'r_arm_x': -3, 'r_arm_y': -2},
        {'body_lean':  8, 'r_arm_x': +8, 'r_arm_y': -4},
        {'body_lean':  6, 'r_arm_x': +6, 'r_arm_y': -2},
    ]
    save_strip([draw_frame(p) for p in poses], 'combo_1')


def gen_combo_1_end() -> None:
    """4-frame combo_1 recovery: return to guard."""
    poses = [
        {'body_lean':  5, 'r_arm_x': +5, 'r_arm_y': -2},
        {'body_lean':  3, 'r_arm_x': +3, 'r_arm_y': -1},
        {'body_lean':  1, 'r_arm_x': +1},
        {},
    ]
    save_strip([draw_frame(p) for p in poses], 'combo_1_end')


def gen_combo_2() -> None:
    """6-frame sweep kick: step forward → sweep low → recover."""
    poses = [
        {'body_lean': 2, 'l_leg_x': +2},
        {'body_lean': 4, 'l_leg_x': +4, 'l_leg_raise': -4, 'body_y': 2},
        {'body_lean': 6, 'l_leg_x': +8, 'l_leg_raise': -6, 'body_y': 3},
        {'body_lean': 5, 'l_leg_x': +6, 'l_leg_raise': -4, 'body_y': 2},
        {'body_lean': 3, 'l_leg_x': +3, 'l_leg_raise': -2, 'body_y': 1},
        {'body_lean': 1},
    ]
    save_strip([draw_frame(p) for p in poses], 'combo_2')


def gen_combo_2_end() -> None:
    """4-frame combo_2 recovery."""
    poses = [
        {'body_lean': 4, 'body_y': 1},
        {'body_lean': 2},
        {'body_lean': 1},
        {},
    ]
    save_strip([draw_frame(p) for p in poses], 'combo_2_end')


def gen_combo_3() -> None:
    """12-frame heavy combo: windup → 3 hits → spin → finish."""
    # windup (2)
    windup = [
        {'body_lean': -3, 'l_arm_x': -5, 'r_arm_x': -5, 'l_arm_y': -4, 'r_arm_y': -4},
        {'body_lean': -4, 'l_arm_x': -7, 'r_arm_x': -7, 'l_arm_y': -6, 'r_arm_y': -6},
    ]
    # hits (6 - two jabs + one heavy)
    hits = [
        {'body_lean':  4, 'r_arm_x': +6, 'r_arm_y': -4},
        {'body_lean':  7, 'r_arm_x': +9, 'r_arm_y': -5},
        {'body_lean':  5, 'r_arm_x': +7, 'r_arm_y': -3},
        {'body_lean':  3, 'l_arm_x': +5, 'l_arm_y': -3},
        {'body_lean':  6, 'l_arm_x': +8, 'l_arm_y': -5},
        {'body_lean': 10, 'l_arm_x': +10, 'r_arm_x': +6, 'l_arm_y': -6, 'r_arm_y': -3},
    ]
    # spin (2)
    spin = [
        {'body_lean':  5, 'flip': False, 'l_arm_x': +4, 'r_arm_x': +4},
        {'body_lean':  5, 'flip': True,  'l_arm_x': +4, 'r_arm_x': +4},
    ]
    # finish (2)
    finish = [
        {'body_lean':  8, 'r_arm_x': +10, 'r_arm_y': -7, 'body_y': -2},
        {'body_lean':  6, 'r_arm_x': +8,  'r_arm_y': -5},
    ]
    all_poses = windup + hits + spin + finish
    assert len(all_poses) == 12
    save_strip([draw_frame(p) for p in all_poses], 'combo_3')


def gen_combo_3_end() -> None:
    """6-frame combo_3 recovery: catch breath, return to guard."""
    poses = [
        {'body_lean': 5, 'body_y': -1, 'r_arm_x': +6},
        {'body_lean': 4, 'r_arm_x': +4},
        {'body_lean': 3, 'r_arm_x': +3},
        {'body_lean': 2},
        {'body_lean': 1, 'body_y': -1},
        {},
    ]
    save_strip([draw_frame(p) for p in poses], 'combo_3_end')
```

Update `main()`:

```python
    gen_combo_1()
    gen_combo_1_end()
    gen_combo_2()
    gen_combo_2_end()
    gen_combo_3()
    gen_combo_3_end()
```

- [ ] **Step 4: Run and verify**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python tools/generate_female_hero.py && python -m pytest tests/test_female_hero_sprites.py::test_combat_strips -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add tools/generate_female_hero.py tests/test_female_hero_sprites.py
git commit -m "feat: add all combat combo animation generation"
```

---

## Task 10: Full generation run — verify all 25 outputs

**Files:**
- Modify: `tests/test_female_hero_sprites.py`

- [ ] **Step 1: Write comprehensive verification test**

Append to `tests/test_female_hero_sprites.py`:

```python
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
```

- [ ] **Step 2: Run full generator**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python tools/generate_female_hero.py
```

Expected output (25 lines):
```
  saved female_hero-design.png  (1 frames)
  saved female_hero-idle.png  (10 frames)
  saved female_hero-idle_turn.png  (4 frames)
  saved female_hero-walk.png  (10 frames)
  ...
  saved female_hero-combo_3_end.png  (6 frames)
```

- [ ] **Step 3: Run all tests**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py -v
```

Expected: All tests pass (25+ tests)

- [ ] **Step 4: Commit**

```bash
git add tests/test_female_hero_sprites.py
git commit -m "feat: add full sprite suite verification test"
```

---

## Task 11: Import PNGs into Aseprite as `.aseprite` source files

> **Note:** Aseprite trial version (`1.3.16.1-x64-trial`) does not support the `--save-as` CLI flag. This task requires a purchased Aseprite license. If unavailable, skip this task — the PNG strips are fully functional for the sprite engine.

**Files:**
- Create: `tools/png_to_aseprite.sh`

- [ ] **Step 1: Write conversion script**

```bash
#!/usr/bin/env bash
# tools/png_to_aseprite.sh
# Converts all female_hero PNG strips to .aseprite source files.
# Requires full Aseprite license (trial blocks --save-as).
set -e
SPRITES="assets/sprites"
ASEPRITE="/usr/bin/aseprite"

for png in "$SPRITES"/female_hero-*.png; do
    base="${png%.png}"
    ase="${base}.aseprite"
    echo "Converting $(basename $png) → $(basename $ase)"
    "$ASEPRITE" --batch "$png" --save-as "$ase"
done
echo "Done. $(ls "$SPRITES"/female_hero-*.aseprite 2>/dev/null | wc -l) .aseprite files created."
```

- [ ] **Step 2: Make executable and attempt run**

```bash
chmod +x /home/angelus_mortis/Projects/ChronicForge/tools/png_to_aseprite.sh
cd /home/angelus_mortis/Projects/ChronicForge && bash tools/png_to_aseprite.sh 2>&1 | head -5
```

If trial limitation appears (`Save operation is not supported`), skip to Step 4.

- [ ] **Step 3: Verify .aseprite files (if license available)**

```bash
ls assets/sprites/female_hero-*.aseprite | wc -l
```

Expected: 25

- [ ] **Step 4: Commit script regardless**

```bash
git add tools/png_to_aseprite.sh
git commit -m "feat: add PNG-to-aseprite batch conversion script (requires full license)"
```

---

## Task 12: Final integration check

- [ ] **Step 1: Confirm all PNG strips are present**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && ls assets/sprites/female_hero-*.png | wc -l
```

Expected: `25`

- [ ] **Step 2: Spot-check dimensions**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python3 -c "
from PIL import Image
import os
folder = 'assets/sprites'
errors = []
for f in sorted(os.listdir(folder)):
    if f.startswith('female_hero') and f.endswith('.png'):
        img = Image.open(os.path.join(folder, f))
        w, h = img.size
        if h != 128 or w % 128 != 0:
            errors.append(f'{f}: {w}x{h}')
        else:
            print(f'OK  {f}: {w}x{h} ({w//128} frames)')
if errors:
    print('ERRORS:', errors)
else:
    print('All sprites valid.')
"
```

Expected: 25 lines of `OK`, no errors.

- [ ] **Step 3: Run full test suite**

```bash
cd /home/angelus_mortis/Projects/ChronicForge && python -m pytest tests/test_female_hero_sprites.py -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 4: Final commit**

```bash
git add assets/sprites/female_hero-*.png
git commit -m "feat: add all 25 female_hero sprite sheets (166 frames, Mikasa-inspired)"
```
