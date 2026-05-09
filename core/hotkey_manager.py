"""
ChronicForge — Global Hotkey Manager
Listens for Ctrl+Shift+L anywhere on the desktop using pynput.
Runs in a daemon QThread. Emits a Qt signal to the main thread.
Falls back gracefully if pynput / X11 display is unavailable.

Default hotkey: Ctrl+Shift+L
Configurable in config.toml as hotkey = "<ctrl>+<shift>+l"

Install: pip install pynput
Needs:   DISPLAY environment variable set (X11 session)
"""

import threading
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal


class HotkeySignals(QObject):
    triggered = Signal()  # emitted when hotkey is pressed


class HotkeyManager(QThread):
    """
    Background thread that listens for a global hotkey.
    Emits signals.triggered when the combo is pressed.
    Starts/stops cleanly without blocking the Qt event loop.
    """

    DEFAULT_HOTKEY = "<ctrl>+<shift>+l"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = HotkeySignals()
        self._hotkey_str = self.DEFAULT_HOTKEY
        self._listener = None
        self._available = False
        self.setDaemon(True)

    def set_hotkey(self, combo: str):
        """Set a new hotkey combo string e.g. '<ctrl>+<shift>+l'"""
        self._hotkey_str = combo

    def is_available(self) -> bool:
        return self._available

    def run(self):
        """Runs in background thread — blocks on pynput listener."""
        try:
            from pynput import keyboard

            def on_activate():
                self.signals.triggered.emit()

            # pynput HotKey parses e.g. "<ctrl>+<shift>+l"
            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse(self._hotkey_str), on_activate
            )

            def on_press(key):
                try:
                    hotkey.press(listener.canonical(key))
                except Exception:
                    pass

            def on_release(key):
                try:
                    hotkey.release(listener.canonical(key))
                except Exception:
                    pass

            self._available = True
            print(f"[ChronicForge] Hotkey active: {self._hotkey_str}")

            with keyboard.Listener(
                on_press=on_press,
                on_release=on_release,
            ) as listener:
                self._listener = listener
                listener.join()  # blocks until stopped

        except ImportError:
            print("[ChronicForge] pynput not installed — global hotkey disabled.")
            print("  Install: pip install pynput")
        except Exception as e:
            if "display" in str(e).lower() or "connection" in str(e).lower():
                print(f"[ChronicForge] Hotkey unavailable (X11 not connected): {e}")
            else:
                print(f"[ChronicForge] Hotkey error: {e}")

    def stop_listener(self):
        """Stop the pynput listener cleanly."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        self.quit()
        self.wait(1000)


# ── Singleton ─────────────────────────────────────────────────────────────────

_manager: Optional[HotkeyManager] = None


def setup_hotkey(on_trigger: Callable, combo: str = "<ctrl>+<shift>+l") -> bool:
    """
    Initialise and start the global hotkey listener.
    on_trigger: callable fired on main thread when hotkey is pressed.
    Returns True if hotkey was registered successfully.
    """
    global _manager
    _manager = HotkeyManager()
    _manager.set_hotkey(combo)
    _manager.signals.triggered.connect(on_trigger)
    _manager.start()
    return True


def teardown_hotkey():
    """Stop the listener cleanly on app exit."""
    global _manager
    if _manager:
        _manager.stop_listener()
        _manager = None
