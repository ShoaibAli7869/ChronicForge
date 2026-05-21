# Female Hero Sprite Sheet — Design Spec

**Date:** 2026-05-21  
**Project:** ChronicForge  
**Status:** Approved

---

## Overview

Create a complete `female_hero` sprite set for ChronicForge matching all 24 animations of the existing `male_hero`. The character is Mikasa-inspired (Attack on Titan) — a military fighter with a muted, dark palette and athletic silhouette. Files are drop-in compatible with the existing sprite engine.

---

## Character Design

### Visual Style
- Military fighter aesthetic, no bright fantasy colors
- Short dark hair, athletic female build
- Survey Corps-style uniform: dark teal jacket, off-white shirt, tan pants, dark boots
- Signature red scarf as accent
- 1px near-black outline throughout

### Palette

| Element | Base | Shadow |
|---|---|---|
| Hair | `#1c1212` | `#3d2020` |
| Skin | `#f0c8a0` | `#d4a070` |
| Eyes | `#4a4e5a` | — |
| Jacket | `#2e4a3a` | `#1e3028` |
| Shirt | `#d8d0c0` | — |
| Pants | `#8a7850` | `#6a5c38` |
| Boots | `#2a1a10` | — |
| Straps/belt | `#5a3820` | — |
| Red scarf | `#a02020` | `#7a1818` |
| Outline | `#0a0808` | — |

### Canvas
- **Frame size:** 128×128 px, RGBA
- **Character area:** ~60×100 px centered
- **Bottom padding:** 28px transparent (matches male_hero convention)

---

## Layers (per Aseprite file)

| Layer | Purpose |
|---|---|
| `outline` | 1px near-black border |
| `body` | Torso, jacket, straps |
| `limbs` | Arms and legs (repositioned per frame) |
| `head` | Hair, face, scarf |
| `details` | Belt buckles, boot trim, highlights |

---

## Animation Specifications

All animations are horizontal PNG strips (1 row × N frames). Frame counts are identical to `male_hero`.

| File | Frames | Strip size |
|---|---|---|
| `female_hero-design.png` | 1 | 128×128 |
| `female_hero-idle.png` | 10 | 1280×128 |
| `female_hero-idle_turn.png` | 4 | 512×128 |
| `female_hero-walk.png` | 10 | 1280×128 |
| `female_hero-walk_turn.png` | 4 | 512×128 |
| `female_hero-run.png` | 10 | 1280×128 |
| `female_hero-run_turn.png` | 4 | 512×128 |
| `female_hero-run_to_idle.png` | 7 | 896×128 |
| `female_hero-jump.png` | 6 | 768×128 |
| `female_hero-fall.png` | 4 | 512×128 |
| `female_hero-fall_loop.png` | 3 | 384×128 |
| `female_hero-dash.png` | 5 | 640×128 |
| `female_hero-slide.png` | 8 | 1024×128 |
| `female_hero-hurt.png` | 6 | 768×128 |
| `female_hero-death.png` | 23 | 2944×128 |
| `female_hero-ledge_hang.png` | 7 | 896×128 |
| `female_hero-ledge_climb.png` | 11 | 1408×128 |
| `female_hero-wall_slide.png` | 4 | 512×128 |
| `female_hero-wall_jump.png` | 4 | 512×128 |
| `female_hero-combo_1.png` | 3 | 384×128 |
| `female_hero-combo_1_end.png` | 4 | 512×128 |
| `female_hero-combo_2.png` | 6 | 768×128 |
| `female_hero-combo_2_end.png` | 4 | 512×128 |
| `female_hero-combo_3.png` | 12 | 1536×128 |
| `female_hero-combo_3_end.png` | 6 | 768×128 |

**Total:** 25 sheets, 166 frames

---

## Animation Motion Principles

### Locomotion (walk/run)
- Legs stride in opposite phase, arms counter-swing
- Slight vertical bob: +2px at mid-stride
- Run has more exaggerated lean and limb extension than walk

### Idle
- 1–2px vertical breathe cycle over 10 frames
- Subtle hair and scarf micro-movement on frames 5–10

### Jump / Fall
- Jump: body tuck on ascent, arms raised
- Fall: arms out, slight forward lean
- Fall loop: compressed 3-frame repeat of peak fall pose

### Combat (combo_1/2/3)
- Exaggerated limb extension into strikes
- Body lean forward into attack
- combo_3 is the longest — includes windup, multi-hit, recovery

### Reactions (hurt/death)
- Hurt: recoil backward, frames 1–2 impact flash
- Death: full 23-frame sequence — stagger, kneel, collapse, settle

---

## Asset Pipeline

For each animation:
1. `create_canvas` — 128×128, N frames in Aseprite
2. Draw each frame via `draw_pixels` / `draw_rectangle`
3. `export_spritesheet` — horizontal strip → `assets/sprites/female_hero-<name>.png`
4. `save_as` — source file → `assets/sprites/female_hero-<name>.aseprite`

### Creation Order
1. `design` — lock character look
2. `idle` — establish neutral reference pose
3. `walk` → `run` → `jump` → `fall` → `fall_loop` — core locomotion
4. `dash` → `slide` → `hurt` → `death` — reactions
5. `ledge_hang` → `ledge_climb` → `wall_slide` → `wall_jump` — platformer
6. `run_to_idle` → `idle_turn` → `walk_turn` → `run_turn` — transitions
7. `combo_1` → `combo_1_end` → `combo_2` → `combo_2_end` → `combo_3` → `combo_3_end` — combat

---

## Integration

The sprite engine in `ui/sprite_engine.py` auto-detects frame counts from strip width. No engine changes required — set character to `female_hero` in config/settings to switch.

---

## Out of Scope

- Sprite engine modifications
- New animation states not present in male_hero
- Sound or VFX changes
