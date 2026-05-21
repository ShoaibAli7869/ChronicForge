# ChronicForge — Packaging & Distribution Guide

This document explains how to build ChronicForge into a standalone Linux binary,
how to distribute it, and how end-users should set it up.

---

## What this is

ChronicForge is packaged using [PyInstaller](https://pyinstaller.org/) in
`--onedir` mode. The result is a `dist/ChronicForge/` folder containing the
`ChronicForge` executable and all required Python libraries. **No Python
installation is required on the recipient's machine.**

The packaging uses `--onedir` (not `--onefile`) because PySide6/Qt requires
the plugin directory layout to be present on disk for the app to start
correctly. `--onefile` causes startup delays of 10–30 seconds and Qt plugin
resolution failures.

---

## System prerequisites

These system packages are **not** bundled by PyInstaller and must be installed
separately:

| Package | Why | Install |
|---------|-----|---------|
| `ffmpeg` | Required by `pydub` for audio playback (TTS voice, sound effects) | `sudo apt install ffmpeg` |
| `libportaudio2` | Optional — required only if voice input (microphone) is used | `sudo apt install libportaudio2` |
| `xdotool` | Optional — improves window-title detection for activity tracking | `sudo apt install xdotool` |

The app will launch without `libportaudio2` and `xdotool`, but the relevant
features will be silently disabled.

---

## Building from source

**Requirements:** Python 3.10+, all packages from `requirements.txt`, and a
working X11 display.

```bash
# From the ChronicForge project root:
./build.sh
```

The script:
1. Checks that `ffmpeg` and `upx` are available (warns if missing; does not fail).
2. Installs PyInstaller if not already present in the active virtualenv.
3. Removes any previous `build/` and `dist/ChronicForge/` directories.
4. Runs `pyinstaller --clean chronicforge.spec`.

Output is written to `dist/ChronicForge/`.

To run the built app locally:

```bash
./dist/ChronicForge/ChronicForge
```

---

## Distributing the app

Zip the entire output directory:

```bash
zip -r ChronicForge-linux-x86_64.zip dist/ChronicForge/
```

Send `ChronicForge-linux-x86_64.zip` to the recipient. They unzip it and run:

```bash
unzip ChronicForge-linux-x86_64.zip
cd ChronicForge/
./ChronicForge
```

The folder must stay intact — do not move just the `ChronicForge` binary on its
own; it depends on the libraries in the same directory.

---

## API keys

ChronicForge reads API keys from a `.env` file located **beside the
`ChronicForge` executable** (i.e. inside the `dist/ChronicForge/` folder or
wherever the recipient places it).

Create a file named `.env` with the following variables (only set the ones you
use):

```dotenv
# Groq — used for AI roast / journal generation
GROQ_API_KEY=gsk_...

# Cartesia TTS — optional voice output
CARTESIA_API_KEY=...
CARTESIA_VOICE_ID=dded70d9-73b5-4c77-b76c-97e3c86a6705
CARTESIA_VERSION=2024-11-13

# ElevenLabs TTS — alternative voice output
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=pNInz6obbfDQGcgMyIGb
```

The app will start without any keys set; AI features that require them will be
disabled or will show an error when triggered.

---

## User data locations

All user data is stored in the home directory and persists across app updates:

| Data | Location |
|------|----------|
| SQLite save database | `~/.local/share/chronicforge/save.db` |
| Config / settings TOML | `~/.local/share/chronicforge/config.toml` |
| Legacy onboarding flag | `~/.config/chronicforge/.onboarding_done` |

These paths are hard-coded in the app and are independent of where the binary
lives. Deleting or replacing the `dist/ChronicForge/` folder does **not** touch
user data.

---

## Updating

1. Build or download the new version's `ChronicForge-linux-x86_64.zip`.
2. Remove the old `ChronicForge/` folder: `rm -rf ChronicForge/`
3. Unzip the new archive: `unzip ChronicForge-linux-x86_64.zip`
4. Copy your `.env` file into the new folder if you kept it outside.

User data in `~/.local/share/chronicforge/` and `~/.config/chronicforge/` is
unaffected by this process.

---

## Known limitations

- **Linux/X11 only.** The app uses X11 APIs (`python-xlib`, `xdotool`) and
  `xdg-open` for file handling. Wayland is partially supported through XWayland
  but has not been tested.
- **ffmpeg must be installed system-wide.** PyInstaller cannot bundle `ffmpeg`
  because it is a native executable, not a Python package.
- **Global hotkeys require an X11 display.** The hotkey manager uses
  `python-xlib` and will silently fail if `DISPLAY` is not set (e.g. in a
  headless SSH session).
- **No macOS or Windows support** at this stage of the project.
- **UPX compression** (`upx` package) reduces binary size by ~30% but requires
  `upx` to be installed at build time (`sudo apt install upx`). The build
  succeeds without it.

---

## Troubleshooting

**App opens and immediately closes with no error window**

Run from a terminal to see the error output:
```bash
./dist/ChronicForge/ChronicForge
```

**"cannot find Qt platform plugin" error**

This means the Qt plugins directory is missing. Do not move the `ChronicForge`
binary out of its folder — always distribute and run the entire directory.

**Audio does not play**

Ensure `ffmpeg` is installed: `sudo apt install ffmpeg`

**Activity tracking shows wrong app names**

Install `xdotool` for more accurate window-title detection:
`sudo apt install xdotool`
