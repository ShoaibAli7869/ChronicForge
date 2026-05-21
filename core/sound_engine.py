"""
core/sound_engine.py — generates sine-wave tones with ffmpeg and plays them with ffplay.
Synthesised and cached to ~/.local/share/chronicforge/sounds/ on first play.
"""

import os
import subprocess
import threading

SOUNDS_DIR = os.path.expanduser("~/.local/share/chronicforge/sounds")

# Sound definitions: (name, ffmpeg_filter)
SOUND_DEFS = {
    "level_up": "sine=f=440:d=0.1,afade=t=out:st=0.05:d=0.05[a];sine=f=554.37:d=0.1,afade=t=out:st=0.05:d=0.05[b];sine=f=659.25:d=0.3,afade=t=out:st=0.1:d=0.2[c];[a][b][c]concat=n=3:v=0:a=1",
    "quest_done": "sine=f=880:d=0.1,afade=t=out:st=0.05:d=0.05[a];sine=f=1760:d=0.2,afade=t=out:st=0.1:d=0.1[b];[a][b]concat=n=2:v=0:a=1",
    "xp_gain": "sine=f=1046.50:d=0.1,afade=t=out:st=0.05:d=0.05",
    "roast_hit": "sine=f=110:d=0.3,afade=t=out:st=0.1:d=0.2",
}


def _generate_sound(name: str):
    if name not in SOUND_DEFS:
        return

    os.makedirs(SOUNDS_DIR, exist_ok=True)
    filepath = os.path.join(SOUNDS_DIR, f"{name}.wav")

    if os.path.exists(filepath):
        return filepath

    filter_graph = SOUND_DEFS[name]
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        filter_graph,
        "-acodec",
        "pcm_s16le",
        "-ar",
        "44100",
        filepath,
    ]

    try:
        subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        return filepath
    except Exception as e:
        print(f"[SoundEngine] Failed to generate {name}: {e}")
        return None


def pregenerate_sounds():
    def _worker():
        for name in SOUND_DEFS:
            _generate_sound(name)

    threading.Thread(target=_worker, daemon=True).start()


def play_sound(name: str, enabled: bool = True):
    if not enabled:
        return

    def _worker():
        filepath = _generate_sound(name)
        if filepath:
            try:
                subprocess.run(
                    [
                        "ffplay",
                        "-nodisp",
                        "-autoexit",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        filepath,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                print(f"[SoundEngine] Playback failed: {e}")

    threading.Thread(target=_worker, daemon=True).start()


# Backwards-compatible alias (main imports `play`)
def play(name: str, enabled: bool = True):
    play_sound(name, enabled)


def sounds_enabled() -> bool:
    try:
        from config.settings import load_config

        return getattr(load_config(), "sounds_enabled", True)
    except Exception:
        return True
