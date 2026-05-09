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


def sounds_enabled() -> bool:
    try:
        from config.settings import load_config

        return getattr(load_config(), "sounds_enabled", True)
    except Exception:
        return True
        """
        ChronicForge — Sound Engine
        Plays short audio cues using ffplay (already on most Linux systems).
        Falls back to silent if ffplay is unavailable.

        Sound files are generated programmatically with ffmpeg — no asset files needed.
        Generated once and cached in ~/.local/share/chronicforge/sounds/

        Sounds:
          level_up    — rising arpeggio, medieval fanfare feel
          quest_done  — short positive chime
          xp_gain     — subtle tick/ding
          roast       — low dramatic hit
        """

        import os
        import shutil
        import subprocess
        import threading
        from typing import Optional

        SOUND_DIR = os.path.expanduser("~/.local/share/chronicforge/sounds")

        # Frequency sequences for each sound (tone, duration_ms, volume)
        SOUND_DEFS = {
            "level_up": [
                # Rising arpeggio — C4 E4 G4 C5
                (261, 120, 0.6),
                (329, 120, 0.7),
                (392, 120, 0.8),
                (523, 280, 0.9),
            ],
            "quest_done": [
                # Short bright chime — E4 G4
                (329, 100, 0.5),
                (392, 200, 0.6),
            ],
            "xp_gain": [
                # Single soft ding
                (440, 80, 0.3),
            ],
            "roast": [
                # Low dramatic hit — D2
                (73, 180, 0.7),
                (65, 120, 0.5),
            ],
        }

        def _generate_sound(name: str) -> Optional[str]:
            """
            Generate a sound file using ffmpeg sine wave synthesis.
            Returns path to generated WAV file.
            """
            if not shutil.which("ffmpeg"):
                return None

            os.makedirs(SOUND_DIR, exist_ok=True)
            out_path = os.path.join(SOUND_DIR, f"{name}.wav")

            if os.path.exists(out_path):
                return out_path

            tones = SOUND_DEFS.get(name, [])
            if not tones:
                return None

            # Build ffmpeg filter chain for each tone then concat
            # Each tone: sine wave at frequency Hz for duration ms
            parts = []
            labels = []
            for i, (freq, dur_ms, vol) in enumerate(tones):
                dur_s = dur_ms / 1000.0
                label = f"[t{i}]"
                # sine wave + volume + duration
                parts.append(f"sine=frequency={freq}:duration={dur_s},volume={vol}")
                labels.append(label)

            # Build filter complex: generate each tone, concat them
            filter_parts = []
            for i, part in enumerate(parts):
                filter_parts.append(
                    f"aevalsrc={parts[i].replace('sine=', 'sin(2*PI*')}"
                )

            # Simpler approach: generate each tone as a separate temp file and concat
            tmp_files = []
            try:
                for i, (freq, dur_ms, vol) in enumerate(tones):
                    dur_s = dur_ms / 1000.0
                    tmp = os.path.join(SOUND_DIR, f"_tmp_{name}_{i}.wav")
                    cmd = [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        f"sine=frequency={freq}:duration={dur_s}",
                        "-af",
                        f"volume={vol},afade=t=out:st={max(0, dur_s - 0.05)}:d=0.05",
                        "-ar",
                        "44100",
                        "-ac",
                        "1",
                        tmp,
                    ]
                    subprocess.run(cmd, capture_output=True, timeout=5)
                    if os.path.exists(tmp):
                        tmp_files.append(tmp)

                if not tmp_files:
                    return None

                if len(tmp_files) == 1:
                    os.rename(tmp_files[0], out_path)
                else:
                    # Concat all tones
                    inputs = []
                    for f in tmp_files:
                        inputs += ["-i", f]
                    filter_c = "".join(f"[{i}:a]" for i in range(len(tmp_files)))
                    filter_c += f"concat=n={len(tmp_files)}:v=0:a=1[out]"
                    cmd = (
                        ["ffmpeg", "-y"]
                        + inputs
                        + ["-filter_complex", filter_c, "-map", "[out]", out_path]
                    )
                    subprocess.run(cmd, capture_output=True, timeout=10)

            finally:
                for f in tmp_files:
                    if os.path.exists(f):
                        os.unlink(f)

            return out_path if os.path.exists(out_path) else None

        def _play_file(path: str):
            """Play a WAV file with ffplay (silent, no window, no output)."""
            if not shutil.which("ffplay"):
                return
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                    timeout=5,
                )
            except Exception:
                pass

        def play(sound_name: str, enabled: bool = True):
            """
            Play a named sound in a background thread.
            sound_name: 'level_up' | 'quest_done' | 'xp_gain' | 'roast'
            enabled: respect the user's sound toggle from settings
            """
            if not enabled:
                return
            if not shutil.which("ffplay"):
                return

            def _run():
                path = _generate_sound(sound_name)
                if path:
                    _play_file(path)

            threading.Thread(target=_run, daemon=True).start()

        def pregenerate_sounds():
            """Generate all sound files at startup so first play is instant."""

            def _gen():
                for name in SOUND_DEFS:
                    _generate_sound(name)

            threading.Thread(target=_gen, daemon=True).start()

        def sounds_enabled() -> bool:
            """Check config for sound toggle — reads proper TOML field."""
            try:
                from config.settings import load_config

                return load_config().sounds_enabled
            except Exception:
                return True
