"""
ChronicForge — Activity Tracker
Monitors what the user is actually doing on their machine.

Data sources (in priority order):
  1. xdotool  — focused window title (most accurate, needs xdotool installed)
  2. psutil   — running process list + CPU usage (always available)
  3. Browser history SQLite — Chrome / Firefox recent URLs

Polling interval: 30 seconds
Session summary: accumulated per-category time since tracker started
Watcher fires roasts/praise via event_bus every 5 minutes if thresholds crossed.

Install dependency:  sudo apt install xdotool
"""

import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from collections import defaultdict
from datetime import date, datetime
from typing import Optional

import psutil

# ── App category maps ─────────────────────────────────────────────────────────

ENTERTAINMENT_APPS = {
    "vlc",
    "mpv",
    "mplayer",
    "smplayer",
    "celluloid",
    "totem",
    "kodi",
    "plex",
    "jellyfin-media-player",
    "steam",
    "lutris",
    "heroic",
    "bottles",
    "wine",
    "spotify",
    "rhythmbox",
    "deadbeef",
    "audacious",
    "clementine",
    "netflix",  # browser tab handled separately
}

PRODUCTIVE_APPS = {
    "code",
    "codium",
    "vscodium",
    "vim",
    "nvim",
    "neovim",
    "emacs",
    "pycharm",
    "idea",
    "clion",
    "goland",
    "webstorm",
    "datagrip",
    "sublime_text",
    "subl",
    "kate",
    "gedit",
    "geany",
    "mousepad",
    "libreoffice",
    "soffice",
    "gimp",
    "inkscape",
    "krita",
    "blender",
    "obs",
    "kdenlive",
    "davinci",
    "resolve",
    "docker",
    "virtualbox",
    "virt-manager",
    "terminal",
    "konsole",
    "alacritty",
    "kitty",
    "gnome-terminal",
    "zsh",
    "bash",
    "python3",
    "python",
    "node",
}

BROWSER_APPS = {
    "chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "firefox",
    "firefox-esr",
    "brave",
    "brave-browser",
    "opera",
    "vivaldi",
    "epiphany",
    "falkon",
}

COMMUNICATION_APPS = {
    "telegram-desktop",
    "telegram",
    "discord",
    "slack",
    "signal-desktop",
    "zoom",
    "zoom-us",
    "teams",
    "ms-teams",
    "thunderbird",
    "evolution",
}

# Browser URL patterns → productive vs entertainment
PRODUCTIVE_URLS = [
    r"github\.com",
    r"gitlab\.com",
    r"stackoverflow\.com",
    r"docs\.",
    r"developer\.",
    r"api\.",
    r"localhost",
    r"leetcode\.com",
    r"hackerrank\.com",
    r"coursera\.org",
    r"udemy\.com",
    r"pluralsight\.com",
    r"linkedin\.com",
    r"notion\.so",
    r"obsidian\.md",
    r"figma\.com",
    r"jira\.",
    r"confluence\.",
    r"trello\.com",
    r"asana\.com",
]
ENTERTAINMENT_URLS = [
    r"youtube\.com",
    r"twitch\.tv",
    r"netflix\.com",
    r"primevideo\.com",
    r"disneyplus\.com",
    r"hulu\.com",
    r"reddit\.com",
    r"twitter\.com",
    r"x\.com",
    r"instagram\.com",
    r"tiktok\.com",
    r"facebook\.com",
    r"9gag\.com",
    r"imgur\.com",
    r"chess\.com",
    r"lichess\.org",
    r"spotify\.com",
    r"soundcloud\.com",
]

# ── Category enum ─────────────────────────────────────────────────────────────


class Category:
    PRODUCTIVE = "productive"
    ENTERTAINMENT = "entertainment"
    BROWSER_PRO = "browser_productive"
    BROWSER_ENT = "browser_entertainment"
    BROWSER_OTHER = "browser_other"
    COMMUNICATION = "communication"
    SYSTEM = "system"
    IDLE = "idle"

    @classmethod
    def display(cls, cat: str) -> str:
        return {
            cls.PRODUCTIVE: "productive work",
            cls.ENTERTAINMENT: "entertainment",
            cls.BROWSER_PRO: "research / learning",
            cls.BROWSER_ENT: "social media / streaming",
            cls.BROWSER_OTHER: "browsing",
            cls.COMMUNICATION: "communication",
            cls.SYSTEM: "system",
            cls.IDLE: "idle",
        }.get(cat, cat)


# ── Session data ──────────────────────────────────────────────────────────────


class ActivitySession:
    """Accumulates time-per-category for the current day."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.date = date.today()
        self.time_by_cat = defaultdict(float)  # category → seconds
        self.app_history = []  # [(timestamp, app, category)]
        self.url_history = []  # [(timestamp, url, category)]
        self.last_app = ""
        self.last_category = Category.IDLE
        self.last_window = ""

    def add(self, seconds: float, category: str, app: str = ""):
        # Auto-reset at midnight
        if date.today() != self.date:
            self.reset()
        self.time_by_cat[category] += seconds
        self.last_category = category
        self.last_app = app
        ts = datetime.now()
        if app:
            self.app_history.append((ts, app, category))

    @property
    def entertainment_minutes(self) -> float:
        return (
            self.time_by_cat.get(Category.ENTERTAINMENT, 0)
            + self.time_by_cat.get(Category.BROWSER_ENT, 0)
        ) / 60

    @property
    def productive_minutes(self) -> float:
        return (
            self.time_by_cat.get(Category.PRODUCTIVE, 0)
            + self.time_by_cat.get(Category.BROWSER_PRO, 0)
        ) / 60

    @property
    def top_entertainment_app(self) -> str:
        """Most-used entertainment app by name."""
        counts = defaultdict(float)
        for ts, app, cat in self.app_history:
            if cat in (Category.ENTERTAINMENT, Category.BROWSER_ENT):
                counts[app] += 1
        if not counts:
            return "VLC"
        return max(counts, key=counts.get)

    def summary(self) -> dict:
        return {
            "entertainment_min": round(self.entertainment_minutes, 1),
            "productive_min": round(self.productive_minutes, 1),
            "top_ent_app": self.top_entertainment_app,
            "current_category": self.last_category,
            "current_app": self.last_app,
            "categories": dict(self.time_by_cat),
        }


# ── Window/process detection ──────────────────────────────────────────────────


def _get_active_window_title() -> str:
    """Try xdotool first, fall back to qdbus, then empty string."""
    if shutil.which("xdotool"):
        try:
            r = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            return r.stdout.strip()
        except Exception:
            pass

    if shutil.which("qdbus"):
        try:
            r = subprocess.run(
                ["qdbus", "org.kde.KWin", "/KWin", "activeWindow"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            win_id = r.stdout.strip()
            if win_id:
                r2 = subprocess.run(
                    ["qdbus", "org.kde.KWin", f"/windows/{win_id}", "caption"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                return r2.stdout.strip()
        except Exception:
            pass

    if shutil.which("xprop"):
        try:
            r = subprocess.run(
                "xprop -root _NET_ACTIVE_WINDOW 2>/dev/null | "
                "xargs -I{} xprop -id {} _NET_WM_NAME 2>/dev/null | "
                "grep -o '\".*\"' | tr -d '\"'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
            return r.stdout.strip()
        except Exception:
            pass

    return ""


def _get_running_processes() -> list[dict]:
    """Return list of {name, pid, cpu_percent} for meaningful processes."""
    procs = []
    try:
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "status"]):
            try:
                info = p.info
                if info["status"] in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                    continue
                name = (info["name"] or "").lower().strip()
                if name and name not in ("kworker", "kthread", "migration"):
                    procs.append(
                        {
                            "name": name,
                            "pid": info["pid"],
                            "cpu": info["cpu_percent"] or 0.0,
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    return procs


def _classify_process(name: str) -> str:
    """Classify a process name into a Category."""
    n = name.lower()
    for app in ENTERTAINMENT_APPS:
        if app in n:
            return Category.ENTERTAINMENT
    for app in PRODUCTIVE_APPS:
        if app in n:
            return Category.PRODUCTIVE
    for app in BROWSER_APPS:
        if app in n:
            return Category.BROWSER_OTHER
    for app in COMMUNICATION_APPS:
        if app in n:
            return Category.COMMUNICATION
    return Category.SYSTEM


def _classify_window_title(title: str) -> Optional[tuple[str, str]]:
    """
    From a window title, attempt to classify the activity.
    Returns (category, detail) or None.
    """
    if not title:
        return None

    title_lower = title.lower()

    # Check entertainment URL patterns in browser title
    for pattern in ENTERTAINMENT_URLS:
        if re.search(pattern, title_lower):
            return Category.BROWSER_ENT, title

    # Check productive URL patterns
    for pattern in PRODUCTIVE_URLS:
        if re.search(pattern, title_lower):
            return Category.BROWSER_PRO, title

    # Common window title keywords
    if any(
        k in title_lower
        for k in [
            "vlc",
            "mpv",
            "movie",
            "episode",
            "s0",
            "x264",
            "x265",
            "1080p",
            "720p",
            "mkv",
            "mp4",
            "playing",
        ]
    ):
        return Category.ENTERTAINMENT, title

    if any(
        k in title_lower
        for k in [
            "visual studio",
            "code - ",
            "vim",
            "nvim",
            "pycharm",
            "terminal",
            "konsole",
            "kate",
            "sublime",
        ]
    ):
        return Category.PRODUCTIVE, title

    return None


def _read_browser_history(max_urls: int = 20) -> list[tuple[str, str]]:
    """
    Read recent browser history from Chrome or Firefox SQLite db.
    Returns list of (url, title) pairs.
    Safe: copies DB to temp file before reading (browser may lock it).
    """
    results = []

    # Chrome / Chromium
    for chrome_path in [
        os.path.expanduser("~/.config/google-chrome/Default/History"),
        os.path.expanduser("~/.config/chromium/Default/History"),
        os.path.expanduser("~/.config/brave-browser/Default/History"),
    ]:
        if os.path.exists(chrome_path):
            try:
                tmp = tempfile.mktemp(suffix=".db")
                import shutil as sh

                sh.copy2(chrome_path, tmp)
                conn = sqlite3.connect(tmp)
                rows = conn.execute(
                    "SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT ?",
                    (max_urls,),
                ).fetchall()
                conn.close()
                os.unlink(tmp)
                results.extend(rows)
                break
            except Exception:
                pass

    # Firefox
    ff_dir = os.path.expanduser("~/.mozilla/firefox")
    if os.path.isdir(ff_dir) and not results:
        for entry in os.scandir(ff_dir):
            places = os.path.join(entry.path, "places.sqlite")
            if os.path.exists(places):
                try:
                    tmp = tempfile.mktemp(suffix=".db")
                    import shutil as sh

                    sh.copy2(places, tmp)
                    conn = sqlite3.connect(tmp)
                    rows = conn.execute(
                        "SELECT url, title FROM moz_places "
                        "ORDER BY last_visit_date DESC LIMIT ?",
                        (max_urls,),
                    ).fetchall()
                    conn.close()
                    os.unlink(tmp)
                    results.extend(r for r in rows if r[0])
                    break
                except Exception:
                    pass

    return results[:max_urls]


def _classify_url(url: str) -> str:
    if not url:
        return Category.BROWSER_OTHER
    for p in ENTERTAINMENT_URLS:
        if re.search(p, url):
            return Category.BROWSER_ENT
    for p in PRODUCTIVE_URLS:
        if re.search(p, url):
            return Category.BROWSER_PRO
    return Category.BROWSER_OTHER


# ── Main tracker ──────────────────────────────────────────────────────────────


class ActivityTracker:
    """
    Background thread that polls system state every 30 seconds.
    Updates ActivitySession. Fires Soldier Boy remarks via the watcher.
    """

    POLL_INTERVAL = 30  # seconds between polls
    ROAST_INTERVAL = 5 * 60  # seconds between potential roast checks
    ENT_ROAST_THRESHOLD = 45  # minutes of entertainment before roast
    ENT_PRAISE_THRESHOLD = 60  # minutes of productive work before praise

    def __init__(self):
        self.session = ActivitySession()
        self._running = False
        self._thread = None
        self._last_roast_check = 0.0
        self._last_ent_roast = 0.0  # prevent spamming
        self._ent_roast_count = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[ChronicForge] Activity tracker started.")

    def stop(self):
        self._running = False

    def _loop(self):
        # First poll: calibrate CPU percentages
        try:
            _get_running_processes()
            time.sleep(1)
        except Exception:
            pass

        while self._running:
            try:
                self._poll()
            except Exception as exc:
                print(f"[ActivityTracker] Poll error: {exc}")
            time.sleep(self.POLL_INTERVAL)

    def _poll(self):
        """Single 30-second poll cycle."""
        # Active window title
        window_title = _get_active_window_title()
        window_cat = None
        if window_title:
            result = _classify_window_title(window_title)
            if result:
                window_cat, _ = result

        # Running processes — find highest-priority category
        processes = _get_running_processes()
        cat_counts = defaultdict(int)
        for p in processes:
            c = _classify_process(p["name"])
            if c != Category.SYSTEM:
                cat_counts[c] += 1

        # Determine dominant category
        if window_cat and window_cat != Category.BROWSER_OTHER:
            dominant_cat = window_cat
            dominant_app = window_title
        elif cat_counts:
            # Most common non-system category
            dominant_cat = max(cat_counts, key=cat_counts.get)
            # Find representative app name
            dominant_app = next(
                (
                    p["name"]
                    for p in processes
                    if _classify_process(p["name"]) == dominant_cat
                ),
                dominant_cat,
            )
        else:
            dominant_cat = Category.IDLE
            dominant_app = ""

        # Recent browser URLs
        if dominant_cat in (Category.BROWSER_OTHER, Category.SYSTEM, Category.IDLE):
            urls = _read_browser_history(10)
            if urls:
                url_cats = [_classify_url(u) for u, _ in urls[:5]]
                if Category.BROWSER_ENT in url_cats:
                    dominant_cat = Category.BROWSER_ENT
                    dominant_app = urls[0][0][:60]
                elif Category.BROWSER_PRO in url_cats:
                    dominant_cat = Category.BROWSER_PRO
                    dominant_app = urls[0][0][:60]

        self.session.add(self.POLL_INTERVAL, dominant_cat, dominant_app)
        self.session.last_window = window_title

        # Check if we should fire a remark
        now = time.time()
        if now - self._last_roast_check >= self.ROAST_INTERVAL:
            self._last_roast_check = now
            self._check_and_remark()

    def _check_and_remark(self):
        """Decide whether to fire a Soldier Boy remark based on session data."""
        from core.game_logic import get_recent_logs
        from core.roast_engine import get_roast

        summary = self.session.summary()
        ent_min = summary["entertainment_min"]
        pro_min = summary["productive_min"]
        top_app = summary["top_ent_app"]
        cur_cat = summary["current_category"]

        # Check if anything was logged today
        today_logs = []
        try:
            from datetime import date as _date

            today_logs = [
                l for l in get_recent_logs(1) if l["date"] == _date.today().isoformat()
            ]
        except Exception:
            pass

        logged_today = len(today_logs) > 0
        now = time.time()

        # ── Roast: entertainment without productive work ───────────────────────
        if (
            ent_min >= self.ENT_ROAST_THRESHOLD
            and not logged_today
            and now - self._last_ent_roast > 20 * 60
        ):  # max once per 20 min
            self._last_ent_roast = now
            self._ent_roast_count += 1

            # Escalate roast intensity with each successive roast
            text = _build_ent_roast(ent_min, top_app, self._ent_roast_count)
            _emit_remark(text)

        # ── Roast: still on entertainment after previous roast ────────────────
        elif (
            self._ent_roast_count > 0
            and cur_cat in (Category.ENTERTAINMENT, Category.BROWSER_ENT)
            and now - self._last_ent_roast > 15 * 60
        ):
            self._last_ent_roast = now
            text = _build_followup_roast(ent_min, top_app)
            _emit_remark(text)

        # ── Praise: solid productive session ─────────────────────────────────
        elif (
            pro_min >= self.ENT_PRAISE_THRESHOLD
            and logged_today
            and self._ent_roast_count == 0
        ):
            text = _build_productivity_praise(pro_min)
            _emit_remark(text)
            self._ent_roast_count = -99  # prevent praise spam

    def get_summary(self) -> dict:
        return self.session.summary()


# ── Remark builders ───────────────────────────────────────────────────────────


def _build_ent_roast(ent_min: float, app: str, count: int) -> str:
    """Escalating Soldier Boy roasts for entertainment procrastination."""
    h = int(ent_min) // 60
    m = int(ent_min) % 60
    time_str = f"{h}h {m}m" if h else f"{m} minutes"

    app_clean = _friendly_app_name(app)

    roasts_tier1 = [
        f"{time_str} on {app_clean}. Nothing logged. Soldier Boy is disappointed but not surprised.",
        f"Half an hour of {app_clean} and you haven't logged a single thing. Classic.",
        f"{time_str} of screen time. Zero productive output. The quest board weeps.",
        f"I spent 40 years in a Russian lab. You can't put down {app_clean} for one hour?",
        f"{app_clean} for {time_str}. Your future self is already writing the apology letter.",
    ]
    roasts_tier2 = [
        f"Still on {app_clean}? {time_str} gone. Nothing done. You're embarrassing the whole bloodline.",
        f"{time_str} of {app_clean} and counting. This isn't a break. This is a lifestyle.",
        f"Soldier Boy checked in. {app_clean} is still running. Shame is also running.",
        f"You haven't moved from {app_clean} in {time_str}. The goblins are literally laughing.",
        f"{time_str}. {app_clean}. No log. You are the procrastination.",
    ]
    roasts_tier3 = [
        f"{time_str} of {app_clean}. At this point you're not procrastinating, you're committed to failure.",
        f"I'm going to start billing you for disappointment. {time_str} on {app_clean}. Unbelievable.",
        f"{app_clean}? For {time_str}?? Pick up the fucking quest log or admit you've given up.",
        f"This is beyond procrastination. This is a character flaw. {time_str} on {app_clean}.",
        f"Your ancestors are watching you spend {time_str} on {app_clean}. They're not proud.",
    ]

    import random

    if count == 1:
        pool = roasts_tier1
    elif count == 2:
        pool = roasts_tier2
    else:
        pool = roasts_tier3

    return random.choice(pool)


def _build_followup_roast(ent_min: float, app: str) -> str:
    """Called when still on entertainment after the first roast — no improvement."""
    import random

    h = int(ent_min) // 60
    m = int(ent_min) % 60
    time_str = f"{h}h {m}m" if h else f"{m} minutes"
    app_clean = _friendly_app_name(app)

    pool = [
        f"Soldier Boy checked back in. You're still on {app_clean}. {time_str} total. Nothing has changed.",
        f"I told you {15} minutes ago to do something. You're still watching {app_clean}. Remarkable.",
        f"The quest board checked itself. Nothing new. {app_clean} is still winning against your future.",
        f"I'm running out of ways to say this: close {app_clean} and log something. Anything.",
        f"Still here. Still watching. Still doing nothing. {time_str} on {app_clean}. Good job.",
    ]
    return random.choice(pool)


def _build_productivity_praise(pro_min: float) -> str:
    """Soldier Boy grudging praise for actual productive session."""
    import random

    h = int(pro_min) // 60
    m = int(pro_min) % 60
    time_str = f"{h}h {m}m" if h else f"{m} minutes"

    pool = [
        f"{time_str} of actual work. I'm almost impressed. Almost. Don't ruin it.",
        f"Productive for {time_str}? Soldier Boy notices. Don't let it go to your head.",
        f"{time_str} of grind. That's the version of you I can work with.",
        f"You worked for {time_str} without stopping. That's the first thing today that didn't disappoint me.",
    ]
    return random.choice(pool)


def _friendly_app_name(app: str) -> str:
    """Convert process/URL to a human-readable name."""
    mappings = {
        "vlc": "VLC",
        "mpv": "the video player",
        "steam": "Steam",
        "spotify": "Spotify",
        "discord": "Discord",
        "youtube.com": "YouTube",
        "twitch.tv": "Twitch",
        "netflix.com": "Netflix",
        "reddit.com": "Reddit",
        "twitter.com": "Twitter",
        "x.com": "X / Twitter",
        "instagram.com": "Instagram",
        "tiktok.com": "TikTok",
        "chess.com": "Chess.com",
        "lichess.org": "Lichess",
    }
    app_lower = app.lower()
    for key, display in mappings.items():
        if key in app_lower:
            return display
    # Clean up URL
    if "http" in app_lower:
        try:
            from urllib.parse import urlparse

            return urlparse(app).netloc or app[:30]
        except Exception:
            pass
    return app.split("/")[0][:20].strip() or "that app"


def _emit_remark(text: str):
    """Fire text through the event bus → sprite bubble + optional TTS."""
    try:
        from utils.signals import event_bus

        # Use sprite_remark so the sprite walks to center first
        event_bus.sprite_remark.emit(text)
        # Also play TTS in background
        from core.roast_engine import _speak_soldier_boy

        threading.Thread(
            target=_speak_soldier_boy,
            args=(text, None),
            daemon=True,
        ).start()
    except Exception as e:
        print(f"[ActivityTracker] Emit error: {e}")


# ── Singleton ─────────────────────────────────────────────────────────────────

_tracker: Optional[ActivityTracker] = None


def get_tracker() -> ActivityTracker:
    global _tracker
    if _tracker is None:
        _tracker = ActivityTracker()
    return _tracker


def start_tracking():
    get_tracker().start()


def stop_tracking():
    global _tracker
    if _tracker:
        _tracker.stop()


def get_activity_summary() -> dict:
    return get_tracker().get_summary()
