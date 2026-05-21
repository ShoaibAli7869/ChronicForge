"""
ChronicForge — Configuration Model
Loads/saves settings from ~/.local/share/chronicforge/config.toml
"""

import os
from dataclasses import dataclass, field

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

CONFIG_DIR = os.path.expanduser("~/.local/share/chronicforge")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.toml")


@dataclass
class AIConfig:
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    roast_intensity: int = 2  # 1=mild, 2=savage, 3=nuclear


@dataclass
class SpriteConfig:
    scale: int = 3
    character: str = "male_hero"   # "male_hero" | "female_hero"


@dataclass
class Config:
    ai: AIConfig = field(default_factory=AIConfig)
    sprite: SpriteConfig = field(default_factory=SpriteConfig)
    sounds_enabled: bool = True
    hotkey: str = "<ctrl>+<shift>+l"
    streak_grace_hour: int = 2
    onboarding_done: bool = False


def load_config() -> Config:
    """Load config from TOML file, returning defaults if absent or unreadable."""
    if not os.path.exists(CONFIG_PATH):
        cfg = Config()
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        cfg = Config()
        ai = data.get("ai", {})
        cfg.ai.groq_api_key = ai.get("groq_api_key", "")
        cfg.ai.groq_model = ai.get("groq_model", "llama-3.3-70b-versatile")
        cfg.ai.roast_intensity = ai.get("roast_intensity", 2)
        sprite = data.get("sprite", {})
        cfg.sprite.scale = sprite.get("scale", 3)
        cfg.sprite.character = sprite.get("character", "male_hero")
        cfg.sounds_enabled = data.get("sounds_enabled", True)
        cfg.hotkey = data.get("hotkey", "<ctrl>+<shift>+l")
        cfg.streak_grace_hour = data.get("streak_grace_hour", 2)
        cfg.onboarding_done = data.get("onboarding_done", False)
        return cfg
    except Exception as e:
        print(f"[ChronicForge] Config load error: {e}. Using defaults.")
        return Config()


def save_config(cfg: Config) -> None:
    """Persist config to TOML file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    data = {
        "ai": {
            "groq_api_key": cfg.ai.groq_api_key,
            "groq_model": cfg.ai.groq_model,
            "roast_intensity": cfg.ai.roast_intensity,
        },
        "sprite": {
            "scale": cfg.sprite.scale,
            "character": cfg.sprite.character,
        },
        "sounds_enabled": cfg.sounds_enabled,
        "hotkey": cfg.hotkey,
        "streak_grace_hour": cfg.streak_grace_hour,
        "onboarding_done": cfg.onboarding_done,
    }
    with open(CONFIG_PATH, "wb") as f:
        tomli_w.dump(data, f)


# Legacy flag path (migrated to TOML in current version)
_LEGACY_FLAG = os.path.join(os.path.expanduser("~/.config/chronicforge"), ".onboarding_done")


def is_onboarding_done() -> bool:
    """Return True if onboarding has been completed (checks TOML then legacy flag)."""
    if load_config().onboarding_done:
        return True
    # Migrate legacy flag-file to TOML on first run after upgrade
    if os.path.exists(_LEGACY_FLAG):
        mark_onboarding_done()
        return True
    return False


def mark_onboarding_done() -> None:
    """Persist onboarding completion to TOML config."""
    cfg = load_config()
    cfg.onboarding_done = True
    save_config(cfg)
