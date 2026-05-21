#!/usr/bin/env python3
"""
ChronicForge — main.py  (Tier 1 fixes applied)
Thin orchestrator. All wiring in one place.

Usage:
  python3 main.py                         # GUI
  python3 main.py log "went to gym" -i 3  # CLI log
  python3 main.py status                  # CLI status
  python3 main.py quests                  # CLI quests
  python3 main.py roast                   # CLI roast
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(ROOT_DIR, "assets", "sprites")
sys.path.insert(0, ROOT_DIR)

# ── CLI mode ──────────────────────────────────────────────────────────────────
if len(sys.argv) > 1 and sys.argv[1] in ("log", "status", "quests", "roast"):
    import argparse

    from core.database import init_db
    from core.game_logic import get_character, log_activity
    from core.quest_system import (
        expire_old_daily_quests,
        generate_daily_quests,
        generate_weekly_quest,
        get_active_quests,
        seed_life_quests,
    )
    from core.roast_engine import get_roast

    init_db()
    seed_life_quests()
    expire_old_daily_quests()

    p = argparse.ArgumentParser(prog="chronicforge")
    sub = p.add_subparsers(dest="cmd")
    lp = sub.add_parser("log")
    lp.add_argument("activity")
    lp.add_argument("--intensity", "-i", type=int, default=2, choices=[1, 2, 3])
    lp.add_argument("--notes", "-n", default="")
    sub.add_parser("status")
    sub.add_parser("quests")
    sub.add_parser("roast")
    args = p.parse_args(sys.argv[1:])

    if args.cmd == "log":
        r = log_activity(args.activity, args.intensity, args.notes or None)
        print(f"\n✦  {args.activity}")
        print(
            f"   Stat : {r['stat']}  |  XP: +{r['xp_awarded']}"
            + (f"  (+{r['streak_bonus']}% streak)" if r.get("streak_bonus") else "")
        )
        if r.get("levelled_up"):
            print(f"   ⬆  LEVEL UP → Lv{r['new_level']} {r['new_class']}!")
        for _, t in r.get("achievements", []):
            print(f"   🏆  {t}")
        print(
            f'\n   "{get_roast("activity_done", "praise", stat=r["stat"], speak=False)}"\n'
        )

    elif args.cmd == "status":
        c = get_character()
        bar = lambda v: "█" * int(v // 5) + "░" * (20 - int(v // 5))
        print(f"\n{'═' * 50}")
        print(f"  {c['title']} {c['name']}")
        print(f"  Lv{c['level']} {c['class']}  |  Power {c['total_power']}")
        print(f"  XP {c['xp']}/{c['xp'] + c['xp_to_next']}  ({c['xp_percent']}%)")
        print(f"  Streak {c['streak']}d  (best {c['longest_streak']}d)\n")
        for stat, val in c["stats"].items():
            print(f"  {stat:12s} [{bar(val)}] {val:.1f}")
        print(f"{'═' * 50}\n")

    elif args.cmd == "quests":
        expire_old_daily_quests()
        generate_daily_quests(3)
        generate_weekly_quest()
        for t, qs in get_active_quests().items():
            if qs:
                print(f"\n  {t.upper()}")
                for q in qs:
                    status = "✓" if q["completed"] else "·"
                    print(
                        f"  {status} [{q['id']:3d}] {q['title']}  ({q['xp_reward']} XP)"
                    )

    elif args.cmd == "roast":
        print(f'\n  "{get_roast("general", "roast", use_groq=True, speak=False)}"\n')

    sys.exit(0)


# ── GUI mode ──────────────────────────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication

from core.activity_tracker import start_tracking, stop_tracking
from core.backup import create_backup
from core.database import init_db
from core.game_logic import check_daily_login_bonus, get_character
from core.hotkey_manager import setup_hotkey, teardown_hotkey
from core.quest_system import (
    expire_old_daily_quests,
    generate_daily_quests,
    generate_weekly_quest,
    seed_life_quests,
)
from core.roast_engine import end_of_day_review, get_roast
from core.sound_engine import play as play_sound
from core.sound_engine import pregenerate_sounds, sounds_enabled
from core.streak_mechanics import check_and_apply_freeze
from ui.dashboard.window import DashboardWindow
from ui.onboarding import OnboardingDialog
from ui.quick_log_popup import QuickLogPopup
from ui.sprite_engine import SpriteWidget
from ui.tray import ChronicForgeTray
from utils.notifications import send_notification, setup_notifications
from utils.signals import event_bus


# ── Background worker ─────────────────────────────────────────────────────────
class _Worker(QObject):
    quests_ready = Signal(dict)

    def fetch_quests(self):
        expire_old_daily_quests()
        generate_daily_quests(3)
        generate_weekly_quest()
        from core.quest_system import get_active_quests

        self.quests_ready.emit(get_active_quests())


# ── App ───────────────────────────────────────────────────────────────────────
class ChronicForgeApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("ChronicForge")
        self.app.setQuitOnLastWindowClosed(False)

        # ── Core init ─────────────────────────────────────────────────────────
        init_db()
        seed_life_quests()
        expire_old_daily_quests()  # FIX: expire stale daily quests on startup

        # Check streak freeze (bridges one missed day if freeze available)
        from core.database import Character as _Char
        from core.database import SessionFactory as _SF

        with _SF() as _sess:
            _char = _sess.get(_Char, 1)
            if _char and check_and_apply_freeze(_char):
                _sess.commit()
                send_notification(
                    "🧊 Streak Freeze Used",
                    f"Streak protected! {getattr(_char, 'streak_freezes', 0)} freezes remaining.",
                )

        # Auto-backup today's DB (silent, once per day)
        create_backup()

        # Pre-generate sound effects in background
        pregenerate_sounds()

        # ── KDE notifications ─────────────────────────────────────────────────
        setup_notifications()  # FIX: now properly wired

        # ── Activity tracking ─────────────────────────────────────────────────
        start_tracking()

        # ── Onboarding (first run only) ───────────────────────────────────────
        if not OnboardingDialog.is_done():
            dlg = OnboardingDialog(ASSETS_DIR)
            dlg.exec()

        # ── Dashboard ─────────────────────────────────────────────────────────
        self.dashboard = DashboardWindow(ASSETS_DIR)

        # ── Sprite (with guaranteed fn references) ────────────────────────────
        # FIX: always pass open_dashboard_fn and open_log_fn — no None risk
        self.sprite = SpriteWidget(
            ASSETS_DIR,
            open_dashboard_fn=self._open_dashboard,
            open_log_fn=self.dashboard.open_log,
        )

        # ── Quick log popup (triggered by global hotkey) ────────────────────
        self._popup = QuickLogPopup()
        self._popup.closed.connect(self._on_popup_closed)

        # Wire global hotkey
        try:
            from config.settings import load_config

            hotkey_combo = load_config().hotkey
        except Exception:
            hotkey_combo = "<ctrl>+<shift>+l"
        setup_hotkey(self._show_popup, hotkey_combo)
        print(f"[ChronicForge] Hotkey: {hotkey_combo}  →  Quick Log")

        # Reconnect config_saved to restart hotkey with new combo
        event_bus.config_saved.connect(self._reload_hotkey)

        # ── Tray ──────────────────────────────────────────────────────────────
        self.tray = ChronicForgeTray(ASSETS_DIR)
        self.tray.signals.toggle_sprite.connect(
            lambda: self.sprite.setVisible(not self.sprite.isVisible())
        )
        self.tray.signals.open_dashboard.connect(self._open_dashboard)
        self.tray.signals.open_log.connect(self.dashboard.open_log)

        # ── Worker thread ─────────────────────────────────────────────────────
        self._thread = QThread()
        self._worker = _Worker()
        self._worker.moveToThread(self._thread)
        self._thread.start()

        # ── Streak danger notification at 9pm if nothing logged ───────────────
        self._last_day = None
        self._streak_warn = False
        QTimer(self.app, interval=3_600_000, timeout=self._hour_tick).start()
        # Also check at startup for any missed daily warnings
        QTimer.singleShot(10_000, self._hour_tick)

        # ── Startup greeting ──────────────────────────────────────────────────
        # Wire sound effects to events
        event_bus.level_up.connect(lambda _: play_sound("level_up", sounds_enabled()))
        event_bus.quest_complete.connect(
            lambda _: play_sound("quest_done", sounds_enabled())
        )
        event_bus.xp_gained.connect(lambda _: play_sound("xp_gain", sounds_enabled()))

        QTimer.singleShot(1200, self._startup)

    def _startup(self):
        char = get_character()
        name = char.get("name", "Hero")
        level = char.get("level", 1)
        cls = char.get("class", "Wanderer")
        streak = char.get("streak", 0)

        event_bus.roast_ready.emit(
            f"Welcome back, {name}. Lv{level} {cls}. Streak: {streak}d."
        )

        # ── Daily login bonus ─────────────────────────────────────────────────
        _login_bonus = check_daily_login_bonus()
        if _login_bonus.get("awarded"):
            event_bus.xp_gained.emit(25)
            send_notification(
                "Daily Bonus",
                f"+25 XP and +{_login_bonus['stat_delta']:.1f} {_login_bonus['stat'].upper()}. Welcome back.",
            )

        QTimer.singleShot(3000, self._worker.fetch_quests)

        print(f"\n⚔  ChronicForge  |  {name}  Lv{level} {cls}  |  🔥{streak}d\n")

    def _show_popup(self):
        """Show the quick log popup (called from hotkey thread via Qt signal)."""
        if self._popup.isVisible():
            self._popup.hide()
            return
        self._popup._position()
        self._popup.show()
        self._popup.raise_()
        self._popup.activateWindow()

    def _on_popup_closed(self):
        """Popup dismissed — refresh dashboard if open."""
        event_bus.stats_updated.emit()

    def _reload_hotkey(self):
        """Restart hotkey listener with new combo from config."""
        teardown_hotkey()
        try:
            from config.settings import load_config

            combo = load_config().hotkey
        except Exception:
            combo = "<ctrl>+<shift>+l"
        setup_hotkey(self._show_popup, combo)
        print(f"[ChronicForge] Hotkey reloaded: {combo}")

    def _open_dashboard(self):
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def _hour_tick(self):
        """
        Runs every hour:
        - Midnight: expire old quests, generate new ones, end-of-day review
        - 9pm: streak danger notification if nothing logged today
        """
        from datetime import date
        from datetime import datetime as dt

        today = date.today().isoformat()
        hour = dt.now().hour

        # Midnight rollover
        if today != self._last_day:
            self._last_day = today
            self._streak_warn = False
            expire_old_daily_quests()
            self._worker.fetch_quests()
            QTimer.singleShot(2000, lambda: end_of_day_review())

        # 9pm streak check
        if hour == 21 and not self._streak_warn:
            self._streak_warn = True
            self._check_streak_danger()

    def _check_streak_danger(self):
        from datetime import date

        from core.game_logic import get_character, get_recent_logs

        today = date.today().isoformat()
        today_logs = [l for l in get_recent_logs(1) if l["date"] == today]
        char = get_character()
        streak = char.get("streak", 0)

        if not today_logs and streak > 0:
            send_notification(
                "⚠  Streak in danger!",
                f"Nothing logged today. {streak}-day streak at risk. "
                "Open ChronicForge and log something.",
                urgency="critical",
                timeout_ms=10000,
            )
            event_bus.sprite_remark.emit(
                f"Streak danger. {streak} days on the line. "
                "Log something before midnight or Soldier Boy will be very disappointed."
            )

    def run(self) -> int:
        print("╔══════════════════════════════════════════╗")
        print("║  ChronicForge  v2  (Tier 1 fixes)        ║")
        print("║  Double-click sprite → Log Activity      ║")
        print("║  Right-click sprite → Menu               ║")
        print("╚══════════════════════════════════════════╝")
        rc = self.app.exec()
        teardown_hotkey()
        stop_tracking()
        self._thread.quit()
        self._thread.wait()
        return rc


if __name__ == "__main__":
    sys.exit(ChronicForgeApp().run())
