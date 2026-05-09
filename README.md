```
╔═══════════════════════════════════════════════════════╗
║           C H R O N I C F O R G E                    ║
║     Forge thy legend. One day at a time.              ║
╚═══════════════════════════════════════════════════════╝
```

A medieval RPG gamified life tracker with a living desktop companion.
Linux Mint · KDE Plasma 5 · X11 · Python · PySide6

---

## Phase 1 — Sprite Engine (current)

### Install

```bash
pip install PySide6 tomli_w
```

### Run

```bash
python3 main.py
```

### What works in Phase 1

- Transparent, frameless, always-on-top sprite window (X11/KDE compatible)
- 7-animation state machine: idle · idle_turn · walk · walk_turn · run_to_idle · jump
- Autonomous wandering across the screen with direction flipping
- Idle variety (random glance animations)
- Speech bubbles with fade-out
- Right-click context menu on sprite
- System tray icon (hide/show, quit)
- Event bus (PySide6 Signals) — other modules can trigger sprite reactions
- Config system (TOML at ~/.config/chronicforge/config.toml)
- Test roasts/XP/level-up via right-click menu

### Project structure

```
chronicforge/
├── main.py                  ← entry point
├── requirements.txt
├── chronicforge.desktop     ← KDE autostart
├── assets/
│   └── sprites/
│       ├── male_hero-design.png
│       ├── male_hero-idle.png
│       ├── male_hero-idle_turn.png
│       ├── male_hero-jump.png
│       ├── male_hero-run_to_idle.png
│       ├── male_hero-walk_turn.png
│       └── male_hero-walk.png
├── core/
│   ├── sprite_engine.py     ← sprite widget + state machine + event bus
│   └── config.py            ← TOML config loader/saver
└── ui/
    └── tray.py              ← system tray icon
```

### KDE Autostart

```bash
cp chronicforge.desktop ~/.config/autostart/
# Edit Exec= path to match your install location
```

### Event bus — connect from your own code

```python
from core.sprite_engine import event_bus

event_bus.xp_gained.emit(240)           # sprite jumps + "+240 XP" bubble
event_bus.level_up.emit(5)              # big jump + level bubble
event_bus.roast_ready.emit("...")       # glance + speech bubble
event_bus.quest_complete.emit("Gym")    # jump + quest bubble
```

---

## Roadmap

| Phase | Status | Contents |
|-------|--------|----------|
| 1 | ✅ Done | Sprite engine, state machine, wandering, tray |
| 2 | 🔜 Next | SQLite schema, game logic core (XP/stats/quests) |
| 3 | 📋 Planned | Dashboard UI (character sheet, radar chart, quest board) |
| 4 | 📋 Planned | Groq API roasts + template bank |
| 5 | 📋 Planned | Voice (faster-whisper in, Cartesia out) |
| 6 | 📋 Planned | KDE Plasma widget + monthly recap |
