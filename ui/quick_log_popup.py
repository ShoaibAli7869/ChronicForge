"""
ChronicForge — Quick Log Popup
Triggered by global hotkey (Ctrl+Shift+L).
Frameless popup that appears above the taskbar, centered horizontally.
Log an activity, see the stat preview, press Enter to submit.

Illuminated Parchment theme matching the rest of the app.
"""

import threading

from PySide6.QtCore import (
    QObject,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QFont,
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.game_logic import detect_stat, log_activity
from ui.theme import (
    C_BG,
    C_CRIMSON,
    C_GOLD,
    C_GOLD_BRIGHT,
    C_GOLD_DIM,
    C_GREEN,
    C_INK,
    C_INK_DIM,
    C_INK_FAINT,
    C_INK_MID,
    C_RULE,
    C_RULE_GOLD,
    C_SURFACE,
    STAT_COLORS,
    font_cinzel,
    font_mono,
    font_serif,
)
from utils.signals import event_bus

STAT_ICONS = {
    "strength": "⚔",
    "intellect": "📜",
    "charisma": "🎭",
    "vitality": "🌿",
    "discipline": "🛡",
    "creativity": "✒",
    "wealth": "⚖",
}


class _LogWorker(QObject):
    done = Signal(dict)

    def run(self, activity: str, intensity: int):
        result = log_activity(activity, intensity)
        self.done.emit(result)


class QuickLogPopup(QWidget):
    """
    A compact floating log widget on a parchment surface.
    Shows above the taskbar, centered horizontally.
    Dismisses on Escape or focus loss.
    """

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.X11BypassWindowManagerHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._intensity = 2
        self._int_buttons: dict[int, QPushButton] = {}

        # Log worker
        from PySide6.QtCore import QThread

        self._thread = QThread()
        self._worker = _LogWorker()
        self._worker.moveToThread(self._thread)
        self._thread.start()
        self._worker.done.connect(self._on_done)

        self._build()
        self._position()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        self.setFixedWidth(520)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Outer parchment card
        self._container = QFrame()
        self._container.setStyleSheet(f"""
            QFrame {{
                background: {C_BG};
                border: 1px solid {C_RULE_GOLD};
                border-radius: 4px;
            }}
        """)
        cl = QVBoxLayout(self._container)
        cl.setContentsMargins(24, 18, 24, 18)
        cl.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("✦  QUICK  LOG")
        title.setFont(font_cinzel(10, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{C_CRIMSON}; background:transparent; letter-spacing:4px;"
        )
        hint = QLabel("Ctrl + Shift + L   ·   Esc to dismiss")
        hint.setFont(font_mono(7))
        hint.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(hint)
        cl.addLayout(hdr)

        # Thin gold rule
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background:{C_RULE_GOLD}; border:none;")
        div.setFixedHeight(1)
        cl.addWidget(div)
        cl.addSpacing(4)

        # Activity input — large, prominent
        self._input = QLineEdit()
        self._input.setPlaceholderText("What didst thou do?  (press Enter to log)")
        self._input.setFont(font_serif(13))
        self._input.setFixedHeight(46)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_SURFACE};
                color: {C_INK};
                border: none;
                border-bottom: 1px solid {C_RULE_GOLD};
                padding: 0 10px;
                selection-background-color: {C_RULE};
            }}
            QLineEdit:focus {{
                border-bottom-color: {C_CRIMSON};
                color: {C_GOLD_BRIGHT};
                background: {C_BG};
            }}
        """)
        self._input.textChanged.connect(self._on_text_change)
        self._input.returnPressed.connect(self._submit)
        cl.addWidget(self._input)

        # Stat detection preview
        self._stat_preview = QLabel("  Start typing to detect stat…")
        self._stat_preview.setFont(font_mono(9))
        self._stat_preview.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent;"
        )
        cl.addWidget(self._stat_preview)

        # Intensity row
        int_row = QHBoxLayout()
        int_row.setSpacing(8)

        self._int_group = QButtonGroup(self)
        self._int_group.setExclusive(True)

        for val, label, accent in [
            (1, "·  Light    +30 XP", C_GREEN),
            (2, "··  Normal  +75 XP", C_GOLD),
            (3, "···  Intense  +150 XP", C_CRIMSON),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(val == 2)
            btn.setFont(font_mono(8, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C_SURFACE};
                    color: {C_INK_MID};
                    border: 1px solid {C_RULE};
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    background: #d5cca8;
                    color: {accent};
                    border-color: {C_RULE_GOLD};
                }}
                QPushButton:checked {{
                    background: #d5cca8;
                    color: {accent};
                    border: 1px solid {accent};
                }}
            """)
            btn.clicked.connect(lambda _, v=val: self._set_intensity(v))
            self._int_group.addButton(btn, val)
            self._int_buttons[val] = btn
            int_row.addWidget(btn)
        cl.addLayout(int_row)

        # Submit row
        sub_row = QHBoxLayout()
        sub_row.setSpacing(10)
        self._feedback = QLabel("")
        self._feedback.setFont(font_mono(9))
        self._feedback.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent;"
        )
        self._feedback.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._submit_btn = QPushButton("✦   Log  It")
        self._submit_btn.setFont(font_serif(10, QFont.Weight.Bold))
        self._submit_btn.setFixedWidth(140)
        self._submit_btn.setFixedHeight(38)
        self._submit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_SURFACE};
                color: {C_CRIMSON};
                border: 1px solid {C_CRIMSON};
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: #d5cca8;
                color: {C_GOLD_BRIGHT};
                border-color: {C_GOLD};
            }}
            QPushButton:disabled {{
                color: {C_INK_FAINT};
                border-color: {C_RULE};
                background: {C_SURFACE};
            }}
        """)
        self._submit_btn.clicked.connect(self._submit)

        sub_row.addWidget(self._feedback, stretch=1)
        sub_row.addWidget(self._submit_btn)
        cl.addLayout(sub_row)

        root.addWidget(self._container)

        # Voice button (if available)
        try:
            from core.voice_input import VoiceRecorder, is_voice_available

            if is_voice_available():
                self._recorder = VoiceRecorder(on_transcript=self._on_transcript)
                mic = QPushButton("🎤  Voice")
                mic.setFont(font_mono(8))
                mic.setCheckable(True)
                mic.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {C_INK_FAINT};
                        border: none;
                        padding: 2px 8px;
                    }}
                    QPushButton:checked {{ color: {C_CRIMSON}; }}
                    QPushButton:hover   {{ color: {C_GOLD_BRIGHT}; }}
                """)
                mic.pressed.connect(lambda: self._recorder.start_recording())
                mic.released.connect(
                    lambda: self._recorder.stop_and_transcribe_async(
                        self._on_transcript
                    )
                )
                hdr_row2 = QHBoxLayout()
                hdr_row2.setContentsMargins(0, 0, 0, 0)
                hdr_row2.addStretch()
                hdr_row2.addWidget(mic)
                root.addLayout(hdr_row2)
        except Exception:
            pass

    # ── Behaviour ─────────────────────────────────────────────────────────────
    def _position(self):
        """Centre horizontally, sit above taskbar."""
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.width() // 2
        y = screen.bottom() - self.sizeHint().height() - 80
        self.move(x, y)

    def _set_intensity(self, val: int):
        self._intensity = val
        # Update XP preview when intensity changes
        self._on_text_change(self._input.text())

    def _on_text_change(self, text: str):
        if len(text) < 4:
            self._stat_preview.setText("  Start typing to detect stat…")
            self._stat_preview.setStyleSheet(
                f"color:{C_INK_FAINT}; background:transparent;"
            )
            return
        stat = detect_stat(text)
        col = STAT_COLORS.get(stat, C_GOLD)
        icon = STAT_ICONS.get(stat, "")
        xp = {1: 30, 2: 75, 3: 150}[self._intensity]
        self._stat_preview.setText(
            f"  {icon}   {stat.upper()}   ·   +{xp} XP   ·   Enter to submit"
        )
        self._stat_preview.setStyleSheet(f"color:{col}; background:transparent;")

    def _submit(self):
        text = self._input.text().strip()
        if not text:
            self._input.setFocus()
            return
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Logging…")
        self._worker.run(text, self._intensity)

    def _on_done(self, result: dict):
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("✦   Log  It")

        if "error" in result:
            self._feedback.setText(f"✗  {result['error']}")
            self._feedback.setStyleSheet(
                f"color:{C_CRIMSON}; background:transparent;"
            )
            return

        stat = result["stat"]
        xp = result["xp_awarded"]
        col = STAT_COLORS.get(stat, C_GREEN)

        # Fire events
        event_bus.xp_gained.emit(xp)
        if result.get("levelled_up"):
            event_bus.level_up.emit(result["new_level"])

        # Show success briefly then close
        self._feedback.setText(f"✦  +{xp} XP   ·   {stat.upper()}")
        self._feedback.setStyleSheet(f"color:{col}; background:transparent;")
        self._input.clear()

        # Trigger Soldier Boy praise (async)
        try:
            from core.roast_engine import get_roast

            get_roast("activity_done", "praise", stat=stat, speak=True)
        except Exception:
            pass

        # Auto-close after 1.5s
        QTimer.singleShot(1500, self._dismiss)

    def _on_transcript(self, text: str):
        if text:
            self._input.setText(text)
            self._on_text_change(text)

    def _dismiss(self):
        self.hide()
        self.closed.emit()
        self._thread.quit()
        self._thread.wait()

    def showEvent(self, e):
        super().showEvent(e)
        self._input.setFocus()
        self._input.clear()
        self._feedback.setText("")
        self._stat_preview.setText("  Start typing to detect stat…")

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Escape:
            self._dismiss()
        else:
            super().keyPressEvent(e)

    def focusOutEvent(self, e):
        # Dismiss on focus loss (clicked elsewhere)
        QTimer.singleShot(150, self._check_focus)
        super().focusOutEvent(e)

    def _check_focus(self):
        if not self.isActiveWindow():
            self._dismiss()
