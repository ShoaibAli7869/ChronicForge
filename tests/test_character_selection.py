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
    from config.settings import Config, save_config
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
