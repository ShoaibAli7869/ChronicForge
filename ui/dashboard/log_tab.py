"""
ChronicForge — Log Tab  (v3 — Medieval Codex)

Design:
  - Parchment entry form at top, ruled like a manuscript page
  - Quick-add runes (small flat chips below field)
  - Intensity: three flat labelled tiers, not dropdown
  - History: timeline ruled ledger matching quest tab aesthetic
"""

from PySide6.QtCore import QObject, QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ui.widgets.edit_entry_dialog import EditEntryDialog

from core.game_logic import detect_stat, get_recent_logs, log_activity
from core.roast_engine import get_roast
from core.voice_input import VoiceRecorder, is_voice_available
from utils.signals import event_bus

C_BG = "#0d0802"
C_SURFACE = "#110a03"
C_RULE = "#2a1a08"
C_RULE_GOLD = "#4a3010"
C_GOLD = "#c8a020"
C_GOLD_DIM = "#7a5c10"
C_GOLD_BRIGHT = "#f5c842"
C_INK = "#d4b870"
C_INK_DIM = "#7a5a30"
C_INK_FAINT = "#3a2810"
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

QUICK_CHIPS = [
    ("⚔  Gym", "went to the gym", "strength"),
    ("📜  Read", "read today", "intellect"),
    ("😴  Sleep", "slept well", "vitality"),
    ("🧘  Meditate", "meditated", "vitality"),
    ("💻  Code", "coded on project", "creativity"),
    ("🎭  Social", "met with people", "charisma"),
    ("📋  Tasks", "completed my tasks today", "discipline"),
    ("⚖  Finance", "reviewed finances", "wealth"),
]


class _Divider(QWidget):
    def __init__(self, color=C_RULE_GOLD, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedHeight(12)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(self._color, 1))
        mid, w = self.height() // 2, self.width()
        p.drawLine(0, mid, w // 2 - 18, mid)
        p.drawLine(w // 2 + 18, mid, w, mid)
        p.setBrush(QBrush(self._color))
        cx, cy, sz = w // 2, mid, 4
        p.drawPolygon(
            QPolygon(
                [
                    QPoint(cx, cy - sz),
                    QPoint(cx + sz, cy),
                    QPoint(cx, cy + sz),
                    QPoint(cx - sz, cy),
                ]
            )
        )
        p.end()


class _Worker(QObject):
    done = Signal(dict)

    def run(self, activity, intensity, notes, stat_override):
        result = log_activity(
            activity,
            intensity,
            notes or None,
            stat_override if stat_override != "auto" else None,
        )
        self.done.emit(result)


class LogTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._intensity = 2
        self._thread = QThread()
        self._worker = _Worker()
        self._worker.moveToThread(self._thread)
        self._thread.start()
        self._worker.done.connect(self._on_done)
        self._recorder = VoiceRecorder(on_transcript=self._on_transcript)
        # FIX 5: register Whisper model loading callbacks
        from core.voice_input import register_loading_callback

        register_loading_callback(
            on_loading=self._on_whisper_loading,
            on_ready=self._on_whisper_ready,
        )
        self._build()
        self._load_history()

    def _build(self):
        self.setStyleSheet(f"background:{C_BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 16)
        root.setSpacing(0)

        # Page title
        title_row = QHBoxLayout()
        page_title = QLabel("CHRONICLE ENTRY")
        page_title.setFont(QFont("monospace", 14, QFont.Weight.Bold))
        page_title.setStyleSheet(
            f"color:{C_GOLD_BRIGHT}; background:transparent; letter-spacing:4px;"
        )
        self._today_lbl = QLabel("")
        self._today_lbl.setFont(QFont("monospace", 8))
        self._today_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
        title_row.addWidget(page_title)
        title_row.addSpacing(12)
        title_row.addWidget(self._today_lbl)
        title_row.addStretch()
        root.addLayout(title_row)
        root.addSpacing(10)
        root.addWidget(_Divider(C_GOLD))
        root.addSpacing(12)

        # ── Quick add runes ────────────────────────────────────────────────────
        rune_lbl = QLabel("QUICK ENTRY")
        rune_lbl.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        rune_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:3px;"
        )
        root.addWidget(rune_lbl)
        root.addSpacing(6)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        for label, text, stat in QUICK_CHIPS:
            col = STAT_COLORS.get(stat, C_GOLD_DIM)
            btn = QPushButton(label)
            btn.setFont(QFont("monospace", 8))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{C_INK_FAINT};
                    border:1px solid {C_RULE}; padding:5px 10px;
                }}
                QPushButton:hover {{
                    color:{col}; border-color:{C_RULE_GOLD};
                    background:{C_SURFACE};
                }}
            """)
            btn.clicked.connect(lambda _, t=text, s=stat: self._quick_fill(t, s))
            chips_row.addWidget(btn)
        chips_row.addStretch()
        root.addLayout(chips_row)
        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(10)

        # ── Main entry form ────────────────────────────────────────────────────
        entry_lbl = QLabel("WHAT DID YOU DO?")
        entry_lbl.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        entry_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:3px;"
        )
        root.addWidget(entry_lbl)
        root.addSpacing(6)

        self._activity = QLineEdit()
        self._activity.setPlaceholderText(
            "Describe the deed. The chronicle remembers all."
        )
        self._activity.setFont(QFont("monospace", 12))
        self._activity.setFixedHeight(42)
        self._activity.setStyleSheet(f"""
            QLineEdit {{
                background:{C_SURFACE}; color:{C_INK};
                border:none; border-bottom:1px solid {C_RULE_GOLD};
                padding:0 4px; font-size:12px;
            }}
            QLineEdit:focus {{ border-bottom-color:{C_GOLD}; }}
        """)
        self._activity.returnPressed.connect(self._submit)
        self._activity.textChanged.connect(self._on_text_change)
        root.addWidget(self._activity)

        self._detect_lbl = QLabel("")
        self._detect_lbl.setFont(QFont("monospace", 8))
        self._detect_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
        root.addWidget(self._detect_lbl)
        root.addSpacing(12)

        # ── Intensity selector ─────────────────────────────────────────────────
        int_lbl = QLabel("INTENSITY")
        int_lbl.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        int_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:3px;"
        )
        root.addWidget(int_lbl)
        root.addSpacing(6)

        self._int_group = QButtonGroup(self)
        self._int_group.setExclusive(True)
        int_row = QHBoxLayout()
        int_row.setSpacing(0)

        defs = [
            (1, "·  LIGHT", "+30 XP   Light effort", "#2a5020", "#50a030"),
            (2, "·· NORMAL", "+75 XP   Solid session", C_RULE_GOLD, C_GOLD),
            (3, "··· INTENSE", "+150 XP  Max effort", "#4a1010", "#c04040"),
        ]
        for val, label, sub, border, color in defs:
            w = QWidget()
            w.setStyleSheet(f"background:{C_SURFACE}; border:1px solid {border};")
            wl = QVBoxLayout(w)
            wl.setContentsMargins(14, 10, 14, 10)
            wl.setSpacing(2)

            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(val == 2)
            btn.setFont(QFont("monospace", 9, QFont.Weight.Bold))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{color};
                    border:none; text-align:left; padding:0;
                }}
                QPushButton:checked {{ color:{C_GOLD_BRIGHT}; }}
            """)
            btn.clicked.connect(lambda _, v=val: setattr(self, "_intensity", v))
            self._int_group.addButton(btn, val)

            sub_lbl = QLabel(sub)
            sub_lbl.setFont(QFont("monospace", 7))
            sub_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")

            wl.addWidget(btn)
            wl.addWidget(sub_lbl)
            int_row.addWidget(w)
        root.addLayout(int_row)
        root.addSpacing(10)

        # ── Notes + submit ─────────────────────────────────────────────────────
        bot = QHBoxLayout()
        bot.setSpacing(12)
        self._notes = QLineEdit()
        self._notes.setPlaceholderText("Notes (optional)")
        self._notes.setStyleSheet(f"""
            QLineEdit {{
                background:transparent; color:{C_INK_DIM};
                border:none; border-bottom:1px solid {C_RULE};
                padding:0 4px; font-family:monospace; font-size:9px;
            }}
            QLineEdit:focus {{ border-bottom-color:{C_RULE_GOLD}; }}
        """)
        self._submit_btn = QPushButton("✦  Record the Deed")
        self._submit_btn.setFont(QFont("monospace", 10, QFont.Weight.Bold))
        self._submit_btn.setFixedWidth(180)
        self._submit_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_SURFACE}; color:{C_GOLD};
                border:1px solid {C_RULE_GOLD}; padding:9px 0;
                letter-spacing:1px;
            }}
            QPushButton:hover {{ background:#1e1206; border-color:{C_GOLD};
                color:{C_GOLD_BRIGHT}; }}
            QPushButton:disabled {{ color:{C_INK_FAINT}; border-color:{C_RULE}; }}
        """)
        self._submit_btn.clicked.connect(self._submit)
        # Mic button (voice input)
        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFont(QFont("monospace", 14))
        self._mic_btn.setFixedWidth(46)
        self._mic_btn.setCheckable(True)
        self._mic_btn.setToolTip(
            "Hold: record voice entry (requires sounddevice + libportaudio2)"
        )
        self._mic_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_SURFACE}; color:{C_INK_FAINT};
                border:1px solid {C_RULE}; padding:0;
            }}
            QPushButton:checked {{ color:#c04040; border-color:#c04040;
                background:#1e0808; }}
            QPushButton:hover {{ border-color:{C_RULE_GOLD}; color:{C_GOLD}; }}
        """)
        self._mic_btn.pressed.connect(self._start_voice)
        self._mic_btn.released.connect(self._stop_voice)
        if not is_voice_available():
            self._mic_btn.setEnabled(False)
            self._mic_btn.setToolTip(
                "Voice unavailable: install sounddevice + libportaudio2"
            )
        bot.addWidget(self._notes, stretch=1)
        bot.addWidget(self._mic_btn)
        bot.addWidget(self._submit_btn)
        root.addLayout(bot)

        self._feedback = QLabel("")
        self._feedback.setFont(QFont("monospace", 9))
        self._feedback.setStyleSheet(f"background:transparent;")
        root.addWidget(self._feedback)
        root.addSpacing(16)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(8)

        # ── History ledger ─────────────────────────────────────────────────────
        hist_lbl = QLabel("PAST DEEDS")
        hist_lbl.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        hist_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:3px;"
        )
        root.addWidget(hist_lbl)
        root.addSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")
        self._hist_inner = QWidget()
        self._hist_inner.setStyleSheet("background:transparent;")
        self._hist_layout = QVBoxLayout(self._hist_inner)
        self._hist_layout.setContentsMargins(0, 0, 4, 0)
        self._hist_layout.setSpacing(0)
        self._hist_layout.addStretch()
        scroll.setWidget(self._hist_inner)
        root.addWidget(scroll, stretch=1)

    def _quick_fill(self, text, stat):
        self._activity.setText(text)
        self._activity.setFocus()
        col = STAT_COLORS.get(stat, C_GOLD_DIM)
        icon = STAT_ICONS.get(stat, "")
        self._detect_lbl.setText(f"  {icon}  {stat.upper()}")
        self._detect_lbl.setStyleSheet(f"color:{col}; background:transparent;")

    def _on_text_change(self, text):
        if len(text) > 4:
            stat = detect_stat(text)
            col = STAT_COLORS.get(stat, C_GOLD_DIM)
            self._detect_lbl.setText(
                f"  {STAT_ICONS.get(stat, '')}  {stat.upper()} detected"
            )
            self._detect_lbl.setStyleSheet(f"color:{col}; background:transparent;")
        else:
            self._detect_lbl.setText("")

    def _submit(self):
        activity = self._activity.text().strip()
        if not activity:
            self._feedback.setText("⚠  Enter the deed first.")
            self._feedback.setStyleSheet(f"color:{C_RED}; background:transparent;")
            return
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Recording...")
        self._feedback.setText("")
        self._worker.run(activity, self._intensity, self._notes.text().strip(), "auto")

    def _on_done(self, result):
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("✦  Record the Deed")
        if "error" in result:
            self._feedback.setText(f"✗  {result['error']}")
            self._feedback.setStyleSheet(f"color:{C_RED}; background:transparent;")
            return
        stat = result["stat"]
        xp = result["xp_awarded"]
        col = STAT_COLORS.get(stat, C_GREEN)
        bonus = (
            f"  (+{result['streak_bonus']}% streak)"
            if result.get("streak_bonus")
            else ""
        )
        self._feedback.setText(f"✦  +{xp} XP  ·  {stat.upper()}{bonus}")
        self._feedback.setStyleSheet(f"color:{col}; background:transparent;")
        self._activity.clear()
        self._notes.clear()
        self._detect_lbl.setText("")

        event_bus.xp_gained.emit(xp)
        if result.get("levelled_up"):
            event_bus.level_up.emit(result["new_level"])
        get_roast("activity_done", "praise", stat=stat, speak=True)
        event_bus.stats_updated.emit()
        self._load_history()

    def _on_whisper_loading(self):
        """Called from background thread when Whisper model starts loading."""
        # Must update UI from main thread
        from PySide6.QtCore import QMetaObject
        from PySide6.QtCore import Qt as _Qt

        QMetaObject.invokeMethod(
            self, "_whisper_loading_ui", _Qt.ConnectionType.QueuedConnection
        )

    def _on_whisper_ready(self):
        """Called from background thread when Whisper model is ready."""
        from PySide6.QtCore import QMetaObject
        from PySide6.QtCore import Qt as _Qt

        QMetaObject.invokeMethod(
            self, "_whisper_ready_ui", _Qt.ConnectionType.QueuedConnection
        )

    from PySide6.QtCore import Slot

    @Slot()
    def _whisper_loading_ui(self):
        if hasattr(self, "_mic_btn"):
            self._mic_btn.setEnabled(False)
            self._mic_btn.setToolTip("Loading Whisper model... (~75MB, one-time)")
        self._feedback.setText("⏳  Loading voice model for the first time...")
        self._feedback.setStyleSheet(f"color:{C_GOLD}; background:transparent;")

    @Slot()
    def _whisper_ready_ui(self):
        if hasattr(self, "_mic_btn"):
            self._mic_btn.setEnabled(True)
            self._mic_btn.setToolTip("Hold to record, release to transcribe")
        if "Loading" in self._feedback.text():
            self._feedback.setText("✦  Voice model ready.")
            self._feedback.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
            from PySide6.QtCore import QTimer

            QTimer.singleShot(2500, lambda: self._feedback.setText(""))

    def _start_voice(self):
        started = self._recorder.start_recording()
        if not started:
            self._mic_btn.setChecked(False)
            self._feedback.setText(
                "⚠  Voice unavailable. Install sounddevice + libportaudio2."
            )
            self._feedback.setStyleSheet(f"color:{C_RED}; background:transparent;")

    def _stop_voice(self):
        self._mic_btn.setChecked(False)
        self._feedback.setText("Transcribing...")
        self._feedback.setStyleSheet(f"color:{C_GOLD}; background:transparent;")
        self._recorder.stop_and_transcribe_async(self._on_transcript)

    def _on_transcript(self, text: str):
        if text:
            # Update UI from main thread
            from PySide6.QtCore import QMetaObject
            from PySide6.QtCore import Qt as _Qt

            self._activity.setText(text)
            from core.game_logic import detect_stat

            stat = detect_stat(text)
            col = STAT_COLORS.get(stat, C_GOLD_DIM)
            icon = STAT_ICONS.get(stat, "")
            self._detect_lbl.setText(f"  {icon}  {stat.upper()} detected")
            self._detect_lbl.setStyleSheet(f"color:{col}; background:transparent;")
            self._feedback.setText(f'✦  Transcribed: "{text[:60]}"')
            self._feedback.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
        else:
            self._feedback.setText("⚠  Could not transcribe. Try again.")
            self._feedback.setStyleSheet(f"color:{C_RED}; background:transparent;")

    def _load_history(self):
        from datetime import date

        today_logs = [
            l for l in get_recent_logs(1) if l["date"] == date.today().isoformat()
        ]
        total_xp = sum(l["xp"] for l in today_logs)
        icons = " ".join(STAT_ICONS.get(l["stat"], "") for l in today_logs[:6])
        self._today_lbl.setText(
            f"Today: {len(today_logs)} deeds  ·  +{total_xp} XP  ·  {icons}"
            if today_logs
            else "No deeds recorded today."
        )

        while self._hist_layout.count() > 1:
            item = self._hist_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        logs = get_recent_logs(days=14)
        if not logs:
            e = QLabel("The past deeds ledger is empty.")
            e.setStyleSheet(
                f"color:{C_INK_FAINT}; font-family:monospace; font-size:9px;"
            )
            self._hist_layout.insertWidget(0, e)
            return

        prev_date = None
        for i, entry in enumerate(logs[:60]):
            col = STAT_COLORS.get(entry["stat"], C_INK_DIM)
            icon = STAT_ICONS.get(entry["stat"], "·")

            if entry["date"] != prev_date:
                if i > 0:
                    sep = QFrame()
                    sep.setFixedHeight(1)
                    sep.setStyleSheet(f"background:{C_RULE}; border:none;")
                    self._hist_layout.insertWidget(self._hist_layout.count() - 1, sep)
                date_lbl = QLabel(entry["date"])
                date_lbl.setFont(QFont("monospace", 7, QFont.Weight.Bold))
                date_lbl.setStyleSheet(
                    f"color:{C_INK_FAINT}; background:transparent; "
                    f"letter-spacing:2px; padding:6px 0 2px 0;"
                )
                self._hist_layout.insertWidget(self._hist_layout.count() - 1, date_lbl)
                prev_date = entry["date"]

            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row_w.setMaximumHeight(24)
            hl = QHBoxLayout(row_w)
            hl.setContentsMargins(0, 2, 0, 2)
            hl.setSpacing(8)

            dot = QLabel("·")
            dot.setFixedWidth(12)
            dot.setFont(QFont("monospace", 14))
            dot.setStyleSheet(f"color:{col}; background:transparent;")

            act = QLabel(
                entry["activity"][:70] + ("…" if len(entry["activity"]) > 70 else "")
            )
            act.setFont(QFont("monospace", 9))
            act.setStyleSheet(f"color:{C_INK_DIM}; background:transparent;")
            act.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )

            xp_lbl = QLabel(f"{icon} +{entry['xp']}")
            xp_lbl.setFont(QFont("monospace", 8))
            xp_lbl.setStyleSheet(f"color:{col}; background:transparent;")
            xp_lbl.setFixedWidth(64)
            xp_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            hl.addWidget(dot)
            hl.addWidget(act, stretch=1)
            hl.addWidget(xp_lbl)

            # Edit button
            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(18, 18)
            edit_btn.setFont(QFont("monospace", 9))
            edit_btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{C_INK_FAINT};
                    border:none; padding:0; }}
                QPushButton:hover {{ color:{C_GOLD}; }}
            """)
            entry_id = entry.get("id")
            edit_btn.clicked.connect(lambda _, e=dict(entry): self._edit_entry(e))
            hl.addWidget(edit_btn)

            # Delete button
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(18, 18)
            del_btn.setFont(QFont("monospace", 8))
            del_btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{C_INK_FAINT};
                    border:none; padding:0; }}
                QPushButton:hover {{ color:{C_RED}; }}
            """)
            del_btn.clicked.connect(lambda _, eid=entry_id: self._delete_entry(eid))
            hl.addWidget(del_btn)
            self._hist_layout.insertWidget(self._hist_layout.count() - 1, row_w)

    def _edit_entry(self, entry: dict):
        """FIX 4: Open edit dialog for a log entry."""
        dlg = EditEntryDialog(entry, self)
        dlg.entry_saved.connect(self._apply_edit)
        dlg.exec()

    def _apply_edit(self, updated: dict):
        """Apply the edited values to the DB entry."""
        entry_id = updated.get("id")
        if not entry_id:
            return
        try:
            from core.database import LogEntry, SessionFactory

            with SessionFactory() as session:
                entry = session.get(LogEntry, entry_id)
                if entry:
                    entry.activity = updated["activity"]
                    entry.category = updated["stat"]
                    entry.intensity = updated["intensity"]
                    entry.notes = updated.get("notes")
                    session.commit()
            self._load_history()
            event_bus.stats_updated.emit()
            self._feedback.setText("✦  Entry updated.")
            self._feedback.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
        except Exception as e:
            print(f"[ChronicForge] Edit entry failed: {e}")

    def _delete_entry(self, entry_id: int):
        """Delete a log entry by ID and refresh history."""
        if entry_id is None:
            return
        try:
            from sqlalchemy import select

            from core.database import LogEntry, SessionFactory

            with SessionFactory() as session:
                entry = session.get(LogEntry, entry_id)
                if entry:
                    session.delete(entry)
                    session.commit()
            self._load_history()
            event_bus.stats_updated.emit()
        except Exception as e:
            print(f"[ChronicForge] Delete entry failed: {e}")

    def closeEvent(self, e):
        self._thread.quit()
        self._thread.wait()
        super().closeEvent(e)
