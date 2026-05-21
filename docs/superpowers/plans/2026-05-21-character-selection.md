# Character Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-time character picker (male / female hero) to the onboarding dialog, persist the choice in config, and drive sprite sheet loading from it — plus a dev right-click toggle to switch mid-session.

**Architecture:** Three isolated changes: (1) add `character` field to `SpriteConfig` dataclass + TOML load/save; (2) replace the hardcoded `ANIM_MAP` constant in sprite engine with a `build_anim_map(prefix)` function stored as `self._anim_map`; (3) add a CHARACTER picker row to `OnboardingDialog` with live portrait swap and save on confirm. The dev toggle uses the existing right-click `QMenu` and reloads sheets in place.

**Tech Stack:** Python 3.10+, PySide6 (Qt6), tomllib / tomli_w, dataclasses, no new dependencies

---

## File Map

| File | Change |
|---|---|
| `config/settings.py` | Add `character: str = "male_hero"` to `SpriteConfig`; read/write in `load_config`/`save_config` |
| `ui/sprite_engine.py` | Replace `ANIM_MAP` constant with `build_anim_map(prefix)`; store as `self._anim_map`; add `_dev_toggle_character` and menu item |
| `ui/onboarding.py` | Add `update_pixmap` to `_PortraitFrame`; add CHARACTER picker row; `_on_character_select`; save in `_confirm` |
| `tests/test_character_selection.py` | Unit tests for new `SpriteConfig` field and `build_anim_map` function |

---

## Task 1: SpriteConfig — add `character` field

**Files:**
- Modify: `config/settings.py:28-109`
- Create: `tests/test_character_selection.py`

---

- [ ] **Step 1: Write failing tests**

Create `tests/test_character_selection.py`:

```python
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def test_sprite_config_default_character():
    from config.settings import SpriteConfig
    cfg = SpriteConfig()
    assert cfg.character == "male_hero"


def test_sprite_config_female_hero():
    from config.settings import SpriteConfig
    cfg = SpriteConfig(character="female_hero")
    assert cfg.character == "female_hero"


def test_load_config_default_character(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.CONFIG_PATH", str(tmp_path / "config.toml"))
    from config.settings import load_config
    cfg = load_config()
    assert cfg.sprite.character == "male_hero"


def test_load_config_reads_character(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_bytes(
        b'[sprite]\nscale = 3\ncharacter = "female_hero"\n'
    )
    monkeypatch.setattr("config.settings.CONFIG_PATH", str(cfg_path))
    from config.settings import load_config
    cfg = load_config()
    assert cfg.sprite.character == "female_hero"


def test_save_config_writes_character(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr("config.settings.CONFIG_DIR", str(tmp_path))
    from config.settings import Config, SpriteConfig, save_config
    cfg = Config()
    cfg.sprite.character = "female_hero"
    save_config(cfg)
    text = (tmp_path / "config.toml").read_text()
    assert 'character = "female_hero"' in text


def test_load_config_missing_character_key_defaults(tmp_path, monkeypatch):
    """Existing configs without character key must default to male_hero."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_bytes(b"[sprite]\nscale = 3\n")  # no character key
    monkeypatch.setattr("config.settings.CONFIG_PATH", str(cfg_path))
    from config.settings import load_config
    cfg = load_config()
    assert cfg.sprite.character == "male_hero"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/angelus_mortis/Projects/ChronicForge
python -m pytest tests/test_character_selection.py -v
```

Expected: 5 failures — `SpriteConfig` has no `character` attribute.

- [ ] **Step 3: Add `character` field to `SpriteConfig`**

In `config/settings.py`, change line 28-29:

```python
@dataclass
class SpriteConfig:
    scale: int = 3
    character: str = "male_hero"   # "male_hero" | "female_hero"
```

- [ ] **Step 4: Read `character` in `load_config()`**

In `config/settings.py`, after line 57 (`cfg.sprite.scale = sprite.get("scale", 3)`), add:

```python
        cfg.sprite.character = sprite.get("character", "male_hero")
```

- [ ] **Step 5: Write `character` in `save_config()`**

In `config/settings.py`, change the `"sprite"` dict at lines 77-79:

```python
        "sprite": {
            "scale": cfg.sprite.scale,
            "character": cfg.sprite.character,
        },
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/test_character_selection.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add config/settings.py tests/test_character_selection.py
git commit -m "feat: add character field to SpriteConfig with load/save support"
```

---

## Task 2: Sprite Engine — `build_anim_map`, instance variable, dev toggle

**Files:**
- Modify: `ui/sprite_engine.py`
- Modify: `tests/test_character_selection.py` (add `build_anim_map` tests)

---

- [ ] **Step 1: Add `build_anim_map` tests to the test file**

Append to `tests/test_character_selection.py`:

```python
def test_build_anim_map_male_hero():
    from ui.sprite_engine import SpriteState, build_anim_map
    amap = build_anim_map("male_hero")
    assert SpriteState.IDLE in amap
    assert amap[SpriteState.IDLE].file == "male_hero-idle.png"
    assert len(amap) == 24


def test_build_anim_map_female_hero():
    from ui.sprite_engine import SpriteState, build_anim_map
    amap = build_anim_map("female_hero")
    assert amap[SpriteState.IDLE].file == "female_hero-idle.png"
    assert amap[SpriteState.COMBO_3].file == "female_hero-combo_3.png"
    assert len(amap) == 24


def test_build_anim_map_preserves_fps_and_loop():
    from ui.sprite_engine import SpriteState, build_anim_map
    amap = build_anim_map("male_hero")
    assert amap[SpriteState.IDLE].fps == 8
    assert amap[SpriteState.IDLE].loop is True
    assert amap[SpriteState.IDLE_TURN].loop is False
    assert amap[SpriteState.FALL_LOOP].loop is True
    assert amap[SpriteState.DASH].fps == 16
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
python -m pytest tests/test_character_selection.py::test_build_anim_map_male_hero tests/test_character_selection.py::test_build_anim_map_female_hero tests/test_character_selection.py::test_build_anim_map_preserves_fps_and_loop -v
```

Expected: 3 failures — `build_anim_map` not defined.

- [ ] **Step 3: Replace `ANIM_MAP` constant with `build_anim_map` function**

In `ui/sprite_engine.py`, replace lines 103-128 (the `ANIM_MAP` dict) with:

```python
def build_anim_map(prefix: str) -> dict["SpriteState", "AnimConfig"]:
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

- [ ] **Step 4: Run `build_anim_map` tests to verify they pass**

```bash
python -m pytest tests/test_character_selection.py::test_build_anim_map_male_hero tests/test_character_selection.py::test_build_anim_map_female_hero tests/test_character_selection.py::test_build_anim_map_preserves_fps_and_loop -v
```

Expected: 3 passed.

- [ ] **Step 5: Initialize `self._anim_map` in `SpriteWidget.__init__`**

In `ui/sprite_engine.py`, in `SpriteWidget.__init__`, add the following after `self._sheets: dict[SpriteState, QPixmap] = {}` (currently line 268). The new lines go immediately after the `self._sheets` declaration:

```python
        from config.settings import load_config as _lc
        _cfg = _lc()
        self._anim_map = build_anim_map(_cfg.sprite.character)
```

- [ ] **Step 6: Replace all 5 `ANIM_MAP` references with `self._anim_map`**

In `ui/sprite_engine.py`, make the following replacements (use search-and-replace carefully — `ANIM_MAP` appears exactly 5 times after removing the constant):

1. `_load_sheets` line 365: `for state, cfg in ANIM_MAP.items():` → `for state, cfg in self._anim_map.items():`
2. `_load_sheets` line 375: `print(f"[ChronicForge] Loaded {ok}/{len(ANIM_MAP)} sprite sheets.")` → `print(f"[ChronicForge] Loaded {ok}/{len(self._anim_map)} sprite sheets.")`
3. `_apply` line 387: `cfg = ANIM_MAP[state]` → `cfg = self._anim_map[state]`
4. `_advance_frame` line 392: `cfg = ANIM_MAP[self._state]` → `cfg = self._anim_map[self._state]`
5. `_get_frame` line 500: `cfg = ANIM_MAP[self._state]` → `cfg = self._anim_map[self._state]`

- [ ] **Step 7: Add `_dev_toggle_character` method to `SpriteWidget`**

In `ui/sprite_engine.py`, add this method to `SpriteWidget` (place it after `_snap_floor` and before `_test_animations`):

```python
    def _dev_toggle_character(self):
        from config.settings import load_config, save_config
        cfg = load_config()
        cfg.sprite.character = (
            "female_hero" if cfg.sprite.character == "male_hero" else "male_hero"
        )
        save_config(cfg)
        self._anim_map = build_anim_map(cfg.sprite.character)
        self._sheets.clear()
        self._load_sheets()
        self._apply(SpriteState.IDLE)
```

- [ ] **Step 8: Add dev toggle item to the right-click menu**

In `ui/sprite_engine.py`, in `contextMenuEvent` (line 706), add the dev toggle after the `"🎬  Test Animations"` item and before the separator before Quit:

```python
        menu.addAction("🎬  Test Animations").triggered.connect(self._test_animations)
        menu.addAction("⚡  Switch Character [DEV]").triggered.connect(self._dev_toggle_character)
        menu.addSeparator()
        menu.addAction("✕  Quit ChronicForge").triggered.connect(QApplication.quit)
```

- [ ] **Step 9: Verify no remaining `ANIM_MAP` references**

```bash
grep -n "ANIM_MAP" /home/angelus_mortis/Projects/ChronicForge/ui/sprite_engine.py
```

Expected: no output (zero matches).

- [ ] **Step 10: Run all character selection tests**

```bash
python -m pytest tests/test_character_selection.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 11: Commit**

```bash
git add ui/sprite_engine.py tests/test_character_selection.py
git commit -m "feat: replace ANIM_MAP with build_anim_map(prefix) and add dev character toggle"
```

---

## Task 3: Onboarding UI — character picker, live portrait swap, save on confirm

**Files:**
- Modify: `ui/onboarding.py`

This task has no isolated unit tests (it's PySide6 UI — tested manually per spec). The manual test plan is in Task 4.

---

- [ ] **Step 1: Add `update_pixmap` to `_PortraitFrame`**

In `ui/onboarding.py`, after `_PortraitFrame.paintEvent` (currently ends at line 156), add:

```python
    def update_pixmap(self, pixmap: "QPixmap | None"):
        if pixmap and not pixmap.isNull():
            self._px = pixmap.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            self._px = None
        self.update()
```

- [ ] **Step 2: Store `_assets_dir` and `_character` on `OnboardingDialog`**

In `ui/onboarding.py`, in `OnboardingDialog.__init__` (line 160), add two instance variables alongside `self._intensity = 2`:

```python
        self._intensity = 2
        self._character = "male_hero"
        self._assets_dir = ""
        self._int_buttons: dict[int, QPushButton] = {}
```

- [ ] **Step 3: Store `assets_dir` and `_portrait` reference in `_build`**

In `ui/onboarding.py`, in `_build(self, assets_dir: str)`, at the very start of the method body (before the `root = QVBoxLayout` line), add:

```python
        self._assets_dir = assets_dir
```

Then change the portrait construction block (lines 175-183) so `portrait` is stored as `self._portrait`:

```python
        # ── Portrait ──────────────────────────────────────────────────────────
        px_path = os.path.join(assets_dir, "male_hero-design.png")
        portrait_pix = QPixmap(px_path) if os.path.exists(px_path) else None
        self._portrait = _PortraitFrame(portrait_pix)
        portrait_row = QHBoxLayout()
        portrait_row.addStretch()
        portrait_row.addWidget(self._portrait)
        portrait_row.addStretch()
        root.addLayout(portrait_row)
        root.addSpacing(18)
```

- [ ] **Step 4: Add CHARACTER picker section between divider and HERO NAME**

In `ui/onboarding.py`, in `_build`, find the block that ends with:

```python
        root.addWidget(Divider(variant="primary"))
        root.addSpacing(22)

        # ── Hero name ─────────────────────────────────────────────────────────
```

Replace it with:

```python
        root.addWidget(Divider(variant="primary"))
        root.addSpacing(16)

        # ── Character ─────────────────────────────────────────────────────────
        char_lbl = QLabel("CHARACTER")
        char_lbl.setFont(font_cinzel(7, QFont.Weight.Bold))
        char_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px;"
        )
        root.addWidget(char_lbl)
        root.addSpacing(10)

        self._char_group = QButtonGroup(self)
        self._char_group.setExclusive(True)
        char_row = QHBoxLayout()
        char_row.setSpacing(12)

        for char_val, char_label in [
            ("male_hero",   "♂   MALE"),
            ("female_hero", "♀   FEMALE"),
        ]:
            btn = QPushButton(char_label)
            btn.setCheckable(True)
            btn.setChecked(char_val == "male_hero")
            btn.setFont(font_mono(10, QFont.Weight.Bold))
            btn.setStyleSheet(_intensity_btn_style(C_GOLD, C_RULE_GOLD))
            btn.setMinimumHeight(52)
            btn.clicked.connect(lambda _, c=char_val: self._on_character_select(c))
            self._char_group.addButton(btn)
            char_row.addWidget(btn)

        root.addLayout(char_row)
        root.addSpacing(16)
        root.addWidget(Divider(variant="secondary"))
        root.addSpacing(16)

        # ── Hero name ─────────────────────────────────────────────────────────
```

- [ ] **Step 5: Add `_on_character_select` method**

In `ui/onboarding.py`, add this method to `OnboardingDialog` after `_build` and before `_confirm`:

```python
    def _on_character_select(self, character: str):
        self._character = character
        px_path = os.path.join(self._assets_dir, f"{character}-design.png")
        pix = QPixmap(px_path) if os.path.exists(px_path) else None
        self._portrait.update_pixmap(pix)
```

- [ ] **Step 6: Save `character` in `_confirm`**

In `ui/onboarding.py`, in `_confirm` (line 270), add `cfg.sprite.character = self._character` after `cfg.ai.roast_intensity = self._intensity`:

```python
        cfg = load_config()
        cfg.ai.roast_intensity = self._intensity
        cfg.sprite.character = self._character
        cfg.onboarding_done = True
        save_config(cfg)
```

- [ ] **Step 7: Increase dialog height to fit the new row**

In `ui/onboarding.py`, in `OnboardingDialog.__init__`, change `setFixedSize(560, 640)` to:

```python
        self.setFixedSize(560, 740)
```

- [ ] **Step 8: Commit**

```bash
git add ui/onboarding.py
git commit -m "feat: add character picker row to onboarding with live portrait swap"
```

---

## Task 4: Manual Integration Test

No automated UI tests — verify by running the app.

---

- [ ] **Step 1: Delete config to force onboarding**

```bash
rm -f ~/.local/share/chronicforge/config.toml
```

- [ ] **Step 2: Launch app**

```bash
cd /home/angelus_mortis/Projects/ChronicForge
python main.py
```

- [ ] **Step 3: Verify character picker appears**

Onboarding dialog should show `CHARACTER` section with `♂ MALE` (checked) and `♀ FEMALE` buttons, between the gold divider and the HERO NAME field. Portrait should show `male_hero-design.png`.

- [ ] **Step 4: Toggle to female**

Click `♀ FEMALE`. Portrait should immediately swap to `female_hero-design.png`. Button highlights gold border on selected state.

- [ ] **Step 5: Confirm and verify config**

Click `✦ BEGIN THE CHRONICLE ✦`. Then inspect:

```bash
grep character ~/.local/share/chronicforge/config.toml
```

Expected: `character = "female_hero"`

- [ ] **Step 6: Verify sprite uses female hero sheets**

The desktop sprite should now walk using `female_hero-*.png` sheets. Confirm by checking the startup console output — it should say `Loaded 24/24 sprite sheets` and the sprite visual should match the female hero palette.

- [ ] **Step 7: Test dev toggle**

Right-click the sprite. Menu should show `⚡  Switch Character [DEV]`. Click it. Sprite should reload with the other character. Right-click and toggle back to verify round-trip.

- [ ] **Step 8: Test backward compatibility**

```bash
# Write a config without character key
cat > ~/.local/share/chronicforge/config.toml << 'EOF'
[sprite]
scale = 3
sounds_enabled = true
hotkey = "<ctrl>+<shift>+l"
streak_grace_hour = 2
onboarding_done = true
EOF
python main.py
```

Expected: sprite loads `male_hero` sheets (default). No crash.

- [ ] **Step 9: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 10: Final commit**

```bash
git add -p  # stage any fixup changes found during testing
git commit -m "fix: integration test fixups for character selection"
```

Only commit if there are actual fixup changes. Skip if tests passed clean.
