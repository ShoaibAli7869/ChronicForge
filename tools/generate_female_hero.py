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

def _px(img: Image.Image, x: int, y: int, color: tuple):
    """Safe single-pixel write."""
    if 0 <= x <= 127 and 0 <= y <= 127:
        img.putpixel((x, y), color)

def _rect(d: ImageDraw.ImageDraw, x1, y1, x2, y2, fill):
    """Safe filled rectangle — silently skips off-canvas rects."""
    cx1, cy1 = max(0, x1), max(0, y1)
    cx2, cy2 = min(127, x2), min(127, y2)
    if cx1 > cx2 or cy1 > cy2:
        return
    d.rectangle([cx1, cy1, cx2, cy2], fill=fill)

def draw_frame(pose: dict = None) -> Image.Image:
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

    # ── THIGHS ─────────────────────────────────────────────────
    # Thighs hinge at hip (no llr/rlr) — raising a leg compresses shin+boot only.
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
        _px(img, int(58+bx + t*7),  torso_top+i, C['strap'])
        _px(img, int(70+bx - t*7),  torso_top+i, C['strap'])

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
    _rect(d, 55+bx, 8+by,  73+bx, 20+by, C['hair'])
    _rect(d, 57+bx, 8+by,  63+bx, 13+by, C['hair_hi'])
    _rect(d, 58+bx, 14+by, 70+bx, 26+by, C['skin'])
    _rect(d, 55+bx, 10+by, 59+bx, 23+by, C['hair'])
    _rect(d, 69+bx, 10+by, 73+bx, 23+by, C['hair'])
    _rect(d, 59+bx, 22+by, 69+bx, 26+by, C['skin_sh'])
    _px(img, 62+bx, 19+by, C['eye'])
    _px(img, 66+bx, 19+by, C['eye'])

    # ── OUTLINE (key silhouette edges) ────────────────────────
    for x in range(55+bx, 74+bx):
        _px(img, x, 7+by, C['outline'])
    for y in range(8+by, 100+by):
        _px(img, 45+bx, y, C['outline'])
        _px(img, 83+bx, y, C['outline'])
    for x in range(54+bx, 75+bx):
        _px(img, x, 100+by, C['outline'])

    if pose.get('flip', False):
        img = img.transpose(Image.FLIP_LEFT_RIGHT)

    return img


def gen_design() -> None:
    """Reference sheet — neutral front-facing pose."""
    save_strip([draw_frame({})], 'design')


def gen_idle() -> None:
    """10-frame breathing cycle — 1-2px vertical bob."""
    bobs = [0, -1, -2, -2, -1, 0, 0, -1, -1, 0]
    frames = [draw_frame({'body_y': b}) for b in bobs]
    save_strip(frames, 'idle')


def gen_walk() -> None:
    """10-frame walk cycle — pendulum legs, counter-swing arms, 2px bob."""
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


def gen_jump() -> None:
    """6-frame jump: crouch → push → rise → peak tuck → spread → fall entry."""
    poses = [
        {'body_y':  4, 'crouch': 3},
        {'body_y':  0, 'crouch': 0},
        {'body_y': -4, 'l_leg_raise': 3, 'r_leg_raise': 3, 'l_arm_y': -4, 'r_arm_y': -4},
        {'body_y': -6, 'l_leg_raise': 7, 'r_leg_raise': 7, 'l_arm_y': -6, 'r_arm_y': -6},
        {'body_y': -4, 'l_leg_raise': 5, 'r_leg_raise': 5, 'l_arm_y': -2, 'r_arm_y': -2},
        {'body_y': -2, 'l_leg_raise': 2, 'r_leg_raise': 2},
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


def main():
    SPRITES.mkdir(parents=True, exist_ok=True)
    gen_design()
    gen_idle()
    gen_walk()
    gen_run()
    gen_jump()
    gen_fall()
    gen_fall_loop()


if __name__ == '__main__':
    main()
