"""
ChronicForge — Settings
TOML config at ~/.config/chronicforge/config.toml
All fields stored in TOML — no hidden flag files.
"""

import os
from dataclasses import asdict, dataclass, field

import tomllib

CONFIG_DIR = os.path.expanduser("~/.config/chronicforge")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.toml")


@dataclass
class SpriteConfig:
    scale: int = 3
    enabled: bool = True


@dataclass
class AIConfig:
    groq_api_key: str = ""
    groq_model: str = "llama3-70b-8192"
    tts_provider: str = "cartesia"
    tts_api_key: str = ""
    roast_intensity: int = 2
    offline_fallback: bool = True


@dataclass
class AppConfig:
    sprite: SpriteConfig = field(default_factory=SpriteConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    onboarding_done: bool = False
    streak_grace_hour: int = 2
    roast_ent_threshold: int = 45
    sounds_enabled: bool = True
    hotkey: str = "<ctrl>+<shift>+l"  # global log hotkey


def load_config() -> AppConfig:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = AppConfig()
    if not os.path.exists(CONFIG_FILE):
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        for k, v in data.get("sprite", {}).items():
            if hasattr(cfg.sprite, k):
                setattr(cfg.sprite, k, v)
        for k, v in data.get("ai", {}).items():
            if hasattr(cfg.ai, k):
                setattr(cfg.ai, k, v)
        for k in (
            "onboarding_done",
            "streak_grace_hour",
            "roast_ent_threshold",
            "sounds_enabled",
            "hotkey",
        ):
            if k in data:
                setattr(cfg, k, data[k])
    except Exception as e:
        print(f"[ChronicForge] Config load error: {e} — using defaults.")
    return cfg


def save_config(cfg: AppConfig):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    data = {
        "sprite": asdict(cfg.sprite),
        "ai": asdict(cfg.ai),
        "onboarding_done": cfg.onboarding_done,
        "streak_grace_hour": cfg.streak_grace_hour,
        "roast_ent_threshold": cfg.roast_ent_threshold,
        "sounds_enabled": cfg.sounds_enabled,
        "hotkey": cfg.hotkey,
    }
    try:
        import tomli_w

        with open(CONFIG_FILE, "wb") as f:
            tomli_w.dump(data, f)
    except ImportError:
        # Fallback manual writer
        with open(CONFIG_FILE, "w") as f:
            f.write("[sprite]\n")
            for k, v in asdict(cfg.sprite).items():
                f.write(f"{k} = {repr(v)}\n")
            f.write("\n[ai]\n")
            for k, v in asdict(cfg.ai).items():
                f.write(f"{k} = {repr(v)}\n")
            f.write(f"\nonboarding_done = {str(cfg.onboarding_done).lower()}\n")
            f.write(f"streak_grace_hour = {cfg.streak_grace_hour}\n")
            f.write(f"roast_ent_threshold = {cfg.roast_ent_threshold}\n")


def mark_onboarding_done():
    """Mark onboarding complete in config — replaces the flag file approach."""
    cfg = load_config()
    cfg.onboarding_done = True
    save_config(cfg)
    # Also remove old flag file if it exists (migration)
    old_flag = os.path.join(CONFIG_DIR, ".onboarding_done")
    if os.path.exists(old_flag):
        os.unlink(old_flag)


def is_onboarding_done() -> bool:
    """Check TOML first, then legacy flag file."""
    # Legacy flag file
    if os.path.exists(os.path.join(CONFIG_DIR, ".onboarding_done")):
        mark_onboarding_done()  # migrate it
        return True
    return load_config().onboarding_done
