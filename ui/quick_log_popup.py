"""
ChronicForge — Quick Log Popup
Triggered by global hotkey (Ctrl+Shift+L).
Frameless popup that appears at screen center.
Log an activity, see the stat preview, press Enter to submit.
No need to open the dashboard at all.
"""

import threading

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPen,
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
from utils.signals import event_bus

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG = "#0d0802"
C_SURFACE = "#110a03"
C_RULE = "#2a1a08"
C_GOLD = "#c8a020"
C_GOLD_B = "#f5c842"
C_INK = "#d4b870"
C_INK_DIM = "#7a5a30"
C_FAINT = "#3a2810"
C_GREEN = "#50a030"
C_RED = "#b03020"

STAT_ICONS = {
    "strength": "⚔",
    "intellect": "📜",
    "charisma": "🎭",
    "vitality": "🌿",
    "discipline": "🛡",
    "creativity": "✒",
    "wealth": "⚖",
}
STAT_COLORS = {
    "strength": "#c84040",
    "intellect": "#4080d0",
    "charisma": "#c07820",
    "vitality": "#30a060",
    "discipline": "#8050b0",
    "creativity": "#a0a020",
    "wealth": "#30a0a0",
}

INT_LABELS = {1: "·  Light   +30 XP", 2: "·· Normal  +75 XP", 3: "··· Intense +150 XP"}


class _LogWorker(QObject):
    done = Signal(dict)

    def run(self, activity: str, intensity: int):
        result = log_activity(activity, intensity)
        self.done.emit(result)


class QuickLogPopup(QWidget):
    """
    A compact floating log widget.
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
        self._worker_thread = threading.Thread(target=lambda: None)

        # Log worker
        from PySide6.QtCore import QThread

        self._thread = QThread()
        self._worker = _LogWorker()
        self._worker.moveToThread(self._thread)
        self._thread.start()
        self._worker.done.connect(self._on_done)

        self._build()
        self._position()

    def _build(self):
        self.setFixedWidth(480)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Main container (painted with rounded dark bg)
        self._container = QFrame()
        self._container.setStyleSheet(f"""
            QFrame {{
                background:{C_BG};
                border:1px solid {C_GOLD};
                border-radius:10px;
            }}
        """)
        cl = QVBoxLayout(self._container)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("⚔  QUICK LOG")
        title.setFont(QFont("monospace", 10, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{C_GOLD_B}; background:transparent; letter-spacing:3px;"
        )
        hint = QLabel("Ctrl+Shift+L  ·  Esc to dismiss")
        hint.setFont(QFont("monospace", 7))
        hint.setStyleSheet(f"color:{C_FAINT}; background:transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(hint)
        cl.addLayout(hdr)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background:{C_RULE}; border:none;")
        div.setFixedHeight(1)
        cl.addWidget(div)

        # Activity input — large, prominent
        self._input = QLineEdit()
        self._input.setPlaceholderText("What did you do? (press Enter to log)")
        self._input.setFont(QFont("monospace", 13))
        self._input.setFixedHeight(46)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background:transparent; color:{C_INK};
                border:none; border-bottom:1px solid {C_RULE};
                padding:0 4px;
            }}
            QLineEdit:focus {{ border-bottom-color:{C_GOLD}; }}
        """)
        self._input.textChanged.connect(self._on_text_change)
        self._input.returnPressed.connect(self._submit)
        cl.addWidget(self._input)

        # Stat detection preview
        self._stat_preview = QLabel("  Start typing to detect stat...")
        self._stat_preview.setFont(QFont("monospace", 9))
        self._stat_preview.setStyleSheet(f"color:{C_FAINT}; background:transparent;")
        cl.addWidget(self._stat_preview)

        # Intensity row (compact)
        int_row = QHBoxLayout()
        int_row.setSpacing(0)
        self._int_group = QButtonGroup(self)
        self._int_group.setExclusive(True)

        for val, label, col, border in [
            (1, "·  Light", "#50a030", "#1a3010"),
            (2, "·· Normal", C_GOLD, "#4a3010"),
            (3, "··· Intense", "#c04040", "#4a1010"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(val == 2)
            btn.setFont(QFont("monospace", 8, QFont.Weight.Bold))
            btn.setFixedHeight(30)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{C_SURFACE}; color:{col};
                    border:1px solid {border};
                    font-family:monospace; font-size:8px;
                    padding:0 12px;
                }}
                QPushButton:checked {{
                    background:#1e1204; border-color:{col};
                    border-width:2px;
                }}
                QPushButton:hover {{ background:#1a0f04; }}
            """)
            btn.clicked.connect(lambda _, v=val: setattr(self, "_intensity", v))
            self._int_group.addButton(btn, val)
            int_row.addWidget(btn)

        cl.addLayout(int_row)

        # Submit row
        sub_row = QHBoxLayout()
        sub_row.setSpacing(10)
        self._feedback = QLabel("")
        self._feedback.setFont(QFont("monospace", 9))
        self._feedback.setStyleSheet(f"color:{C_FAINT}; background:transparent;")
        self._feedback.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._submit_btn = QPushButton("⚔  Log It")
        self._submit_btn.setFont(QFont("monospace", 10, QFont.Weight.Bold))
        self._submit_btn.setFixedWidth(110)
        self._submit_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_SURFACE}; color:{C_GOLD};
                border:1px solid #4a3010; padding:8px 0;
                letter-spacing:1px;
            }}
            QPushButton:hover {{
                background:#1e1206; border-color:{C_GOLD}; color:{C_GOLD_B};
            }}
            QPushButton:disabled {{ color:{C_FAINT}; border-color:{C_RULE}; }}
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
                mic.setFont(QFont("monospace", 8))
                mic.setCheckable(True)
                mic.setStyleSheet(f"""
                    QPushButton {{
                        background:transparent; color:{C_FAINT};
                        border:none; padding:2px 0;
                    }}
                    QPushButton:checked {{ color:#c04040; }}
                    QPushButton:hover   {{ color:{C_GOLD}; }}
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

    def _position(self):
        """Centre horizontally, sit above taskbar."""
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.width() // 2
        y = screen.bottom() - self.sizeHint().height() - 80
        self.move(x, y)

    def _on_text_change(self, text: str):
        if len(text) < 4:
            self._stat_preview.setText("  Start typing to detect stat...")
            self._stat_preview.setStyleSheet(
                f"color:{C_FAINT}; background:transparent;"
            )
            return
        stat = detect_stat(text)
        col = STAT_COLORS.get(stat, C_GOLD)
        icon = STAT_ICONS.get(stat, "")
        xp = {1: 30, 2: 75, 3: 150}[self._intensity]
        self._stat_preview.setText(
            f"  {icon}  {stat.upper()}  ·  +{xp} XP  ·  Enter to submit"
        )
        self._stat_preview.setStyleSheet(f"color:{col}; background:transparent;")

    def _submit(self):
        text = self._input.text().strip()
        if not text:
            self._input.setFocus()
            return
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Logging...")
        self._worker.run(text, self._intensity)

    def _on_done(self, result: dict):
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("⚔  Log It")

        if "error" in result:
            self._feedback.setText(f"✗  {result['error']}")
            self._feedback.setStyleSheet(f"color:{C_RED}; background:transparent;")
            return

        stat = result["stat"]
        xp = result["xp_awarded"]
        col = STAT_COLORS.get(stat, C_GREEN)

        # Fire events
        event_bus.xp_gained.emit(xp)
        if result.get("levelled_up"):
            event_bus.level_up.emit(result["new_level"])

        # Show success briefly then close
        self._feedback.setText(f"✦  +{xp} XP  ·  {stat.upper()}")
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
        self._stat_preview.setText("  Start typing to detect stat...")

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
