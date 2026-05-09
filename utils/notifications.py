"""
ChronicForge — KDE Notification Manager
Sends native KDE/desktop notifications via D-Bus.
Falls back to notify-send subprocess if D-Bus binding fails.
Connects to event_bus.notify signal — wired in main.py.

Usage:
    from utils.notifications import setup_notifications
    setup_notifications()   # call once after QApplication exists
"""

import os
import shutil
import subprocess
import threading
from typing import Optional

from utils.signals import event_bus


class _Notifier:
    """
    Tries three methods in order:
    1. python-dbus / dbus-python  (best — native KDE integration)
    2. notify-send subprocess     (fallback — works on any desktop)
    3. Silent (log to console)
    """

    ICON = os.path.expanduser(
        "~/.local/share/chronicforge/icon.png"  # set during setup
    )
    APP = "ChronicForge"

    def __init__(self):
        self._method = self._detect_method()
        print(f"[ChronicForge] Notification method: {self._method}")

    def _detect_method(self) -> str:
        # Try dbus-python
        try:
            import dbus  # noqa

            return "dbus"
        except ImportError:
            pass
        # Try notify-send
        if shutil.which("notify-send"):
            return "notify-send"
        # Try dbus-send (always available)
        if shutil.which("dbus-send"):
            return "dbus-send"
        return "silent"

    def send(
        self, title: str, body: str, urgency: str = "normal", timeout_ms: int = 5000
    ):
        """Non-blocking notification send."""
        threading.Thread(
            target=self._send_sync,
            args=(title, body, urgency, timeout_ms),
            daemon=True,
        ).start()

    def _send_sync(self, title: str, body: str, urgency: str, timeout_ms: int):
        try:
            if self._method == "dbus":
                self._send_dbus(title, body, urgency, timeout_ms)
            elif self._method == "notify-send":
                self._send_notify_send(title, body, urgency, timeout_ms)
            elif self._method == "dbus-send":
                self._send_dbus_send(title, body, timeout_ms)
            else:
                print(f"[Notify] {title}: {body}")
        except Exception as e:
            # Final fallback: console
            print(f"[Notify] {title}: {body}  (send failed: {e})")

    def _send_dbus(self, title, body, urgency, timeout_ms):
        import dbus

        urgency_map = {"low": 0, "normal": 1, "critical": 2}
        bus = dbus.SessionBus()
        obj = bus.get_object(
            "org.freedesktop.Notifications", "/org/freedesktop/Notifications"
        )
        iface = dbus.Interface(obj, "org.freedesktop.Notifications")
        hints = {"urgency": dbus.Byte(urgency_map.get(urgency, 1))}
        iface.Notify(self.APP, 0, "", title, body, [], hints, timeout_ms)

    def _send_notify_send(self, title, body, urgency, timeout_ms):
        cmd = [
            "notify-send",
            f"--urgency={urgency}",
            f"--expire-time={timeout_ms}",
            f"--app-name={self.APP}",
            title,
            body,
        ]
        subprocess.run(cmd, capture_output=True, timeout=3)

    def _send_dbus_send(self, title, body, timeout_ms):
        # Using dbus-send as last resort — works on KDE without dbus-python
        cmd = [
            "dbus-send",
            "--session",
            "--type=method_call",
            "--dest=org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications.Notify",
            f"string:{self.APP}",
            "uint32:0",
            "string:",  # icon
            f"string:{title}",
            f"string:{body}",
            "array:string:",  # actions
            "dict:string:variant:",  # hints
            f"int32:{timeout_ms}",
        ]
        subprocess.run(cmd, capture_output=True, timeout=3)


# ── Preset notifications ──────────────────────────────────────────────────────

_notifier: Optional[_Notifier] = None


def setup_notifications():
    """
    Initialise notifier and wire event_bus.notify signal.
    Also wire level_up and quest_complete to auto-notify.
    Call once from main.py after QApplication is created.
    """
    global _notifier
    _notifier = _Notifier()

    # Generic notify signal
    event_bus.notify.connect(lambda title, body: _notifier.send(title, body))

    # Level-up notification
    event_bus.level_up.connect(
        lambda lvl: _notifier.send(
            "⬆  Level Up!",
            f"Thou hast reached Level {lvl}. The realm takes notice.",
            urgency="normal",
            timeout_ms=6000,
        )
    )

    # Quest complete notification
    event_bus.quest_complete.connect(
        lambda name: _notifier.send(
            "✦  Quest Complete",
            f"{name} — sealed in the chronicle.",
            urgency="low",
            timeout_ms=4000,
        )
    )

    # Streak danger (fired from activity tracker / proactive check)
    # Wired via roast_ready when context = streak_danger
    # (roasts already appear as sprite bubbles; notification adds desktop popup)


def send_notification(
    title: str, body: str, urgency: str = "normal", timeout_ms: int = 5000
):
    """Direct call — usable anywhere without going through event_bus."""
    if _notifier:
        _notifier.send(title, body, urgency, timeout_ms)
    else:
        print(f"[Notify] {title}: {body}")
