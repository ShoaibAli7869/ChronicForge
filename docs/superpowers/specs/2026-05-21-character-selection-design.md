# Character Selection — Design Spec

**Date:** 2026-05-21
**Project:** ChronicForge
**Status:** Approved

---

## Overview

Add a one-time character selection (male / female hero) to the onboarding dialog. The chosen character persists in config and drives which sprite sheets the engine loads. A temporary dev toggle in the sprite's right-click menu allows switching characters without re-running onboarding.

---

## Scope

**In scope:**
- `SpriteConfig.character` field in config model
- `build_anim_map(prefix)` in sprite engine
- Character picker row in `OnboardingDialog`
- Live portrait swap on picker toggle
- Dev toggle menu item in `SpriteWidget` right-click menu

**Out of scope:**
- Post-onboarding character change via settings tab (future)
- Adding new characters beyond male/female hero

---

## Section 1: Data Model — `config/settings.py`

### Change: `SpriteConfig`

```python
@dataclass
class SpriteConfig:
    scale: int = 3
    character: str = "male_hero"   # "male_hero" | "female_hero"
```

### Change: `load_config()`

Read the new field from the `[sprite]` TOML section:
```python
cfg.sprite.character = sprite.get("character", "male_hero")
```

### Change: `save_config()`

Write it back:
```python
"sprite": {
    "scale": cfg.sprite.scale,
    "character": cfg.sprite.character,
},
```

**Backward compatibility:** Existing configs without `character` key default to `"male_hero"` — no migration needed.

---

## Section 2: Sprite Engine — `ui/sprite_engine.py`

### Change: Replace `ANIM_MAP` constant with `build_anim_map(prefix)`

Remove the hardcoded `ANIM_MAP` dict. Add a function that produces the same structure from a prefix string:

```python
def build_anim_map(prefix: str) -> dict[SpriteState, AnimConfig]:
    def a(name, fps, loop, pingpong=False):
        return AnimConfig(f"{prefix}-{name}.png", 0, fps, loop, pingpong)
    return {
        SpriteState.IDLE:         a("idle",         8,  True),
        SpriteState.IDLE_TURN:    a("idle_turn",     8,  False),
        SpriteState.WALK:         a("walk",          10, True),
        SpriteState.WALK_TURN:    a("walk_turn",     10, False),
        SpriteState.RUN:          a("run",           14, True),
        SpriteState.RUN_TURN:     a("run_turn",      12, False),
        SpriteState.RUN_TO_IDLE:  a("run_to_idle",   10, False),
        SpriteState.JUMP:         a("jump",          10, False),
        SpriteState.FALL:         a("fall",          10, False),
        SpriteState.FALL_LOOP:    a("fall_loop",     8,  True),
        SpriteState.DASH:         a("dash",          16, False),
        SpriteState.SLIDE:        a("slide",         10, False),
        SpriteState.WALL_SLIDE:   a("wall_slide",    8,  True),
        SpriteState.WALL_JUMP:    a("wall_jump",     10, False),
        SpriteState.LEDGE_HANG:   a("ledge_hang",    6,  True),
        SpriteState.LEDGE_CLIMB:  a("ledge_climb",   10, False),
        SpriteState.HURT:         a("hurt",          10, False),
        SpriteState.DEATH:        a("death",         8,  False),
        SpriteState.COMBO_1:      a("combo_1",       13, False),
        SpriteState.COMBO_1_END:  a("combo_1_end",   11, False),
        SpriteState.COMBO_2:      a("combo_2",       13, False),
        SpriteState.COMBO_2_END:  a("combo_2_end",   11, False),
        SpriteState.COMBO_3:      a("combo_3",       13, False),
        SpriteState.COMBO_3_END:  a("combo_3_end",   11, False),
    }
```

### Change: `SpriteWidget.__init__`

Replace the reference to `ANIM_MAP` with a call to `build_anim_map` using the config value:

```python
from config.settings import load_config
cfg = load_config()
self._anim_map = build_anim_map(cfg.sprite.character)
```

Store it as an instance variable (`self._anim_map`) so the dev toggle can reload it without reconstructing the widget.

All existing references to `ANIM_MAP` in `SpriteWidget` methods (`_load_sheets`, `_set_state`, etc.) become `self._anim_map`.

### Change: Dev toggle in right-click menu

In the existing `QMenu` construction inside `SpriteWidget` (the `contextMenuEvent` or equivalent), append:

```python
dev_action = menu.addAction("⚡ Switch Character [DEV]")
dev_action.triggered.connect(self._dev_toggle_character)
```

Add method:

```python
def _dev_toggle_character(self):
    from config.settings import load_config, save_config
    cfg = load_config()
    cfg.sprite.character = (
        "female_hero" if cfg.sprite.character == "male_hero" else "male_hero"
    )
    save_config(cfg)
    self._anim_map = build_anim_map(cfg.sprite.character)
    self._sheets.clear()   # must clear before reload or stale sheets linger
    self._load_sheets()
    self._set_state(SpriteState.IDLE)
```

The test-animations submenu (line ~774 in sprite_engine.py) also iterates `ANIM_MAP` directly — change it to `self._anim_map` along with the other references.

**Note:** Remove `_dev_toggle_character` and the `[DEV]` menu item before shipping.

---

## Section 3: Onboarding UI — `ui/onboarding.py`

### Change: `OnboardingDialog.__init__`

Add `self._character = "male_hero"` to instance state.

### Change: `_build()`

Insert a `CHARACTER` section between the portrait row and the hero name field:

```
┌────────────────────────────────────────┐
│  [portrait — updates on toggle]        │
│  FORGE THY LEGEND                      │
│  ─────────────────                     │
│  CHARACTER                             │  ← new
│  [ ♂  MALE ]  [ ♀  FEMALE ]           │  ← new
│  ─────────────────                     │  ← new
│  HERO NAME                             │
│  [___________________________]         │
│  SOLDIER BOY INTENSITY                 │
│  [MILD] [SAVAGE] [NUCLEAR]             │
│  ─────────────────                     │
│  ✦  BEGIN THE CHRONICLE  ✦             │
└────────────────────────────────────────┘
```

Button style: reuse `_intensity_btn_style` with gold accent/border for the selected state. Buttons are `QButtonGroup` exclusive, `male_hero` checked by default.

### Change: Live portrait swap

Store `_portrait_frame` as `self._portrait`. When character toggles, reload the pixmap:

```python
def _on_character_select(self, character: str):
    self._character = character
    px_path = os.path.join(self._assets_dir, f"{character}-design.png")
    pix = QPixmap(px_path) if os.path.exists(px_path) else None
    self._portrait.update_pixmap(pix)
```

Add `update_pixmap(pix)` method to `_PortraitFrame` that sets `self._px` and calls `self.update()`.

Store `assets_dir` as `self._assets_dir` in `__init__`.

### Change: `_confirm()`

Write the character choice before saving:

```python
cfg.sprite.character = self._character
```

---

## Files Changed

| File | Change |
|---|---|
| `config/settings.py` | Add `character` to `SpriteConfig`, load/save it |
| `ui/sprite_engine.py` | `build_anim_map(prefix)`, `self._anim_map`, dev toggle |
| `ui/onboarding.py` | Character picker row, live portrait swap, save on confirm |

---

## Testing

- Run app with no existing config → onboarding shows character picker
- Select Female → portrait swaps to `female_hero-design.png`
- Confirm → config has `sprite.character = "female_hero"`
- Sprite on desktop uses female hero sheets
- Right-click sprite → "⚡ Switch Character [DEV]" → sprite reloads with other character
- Existing users (config without `character` key) → male hero loads as default
