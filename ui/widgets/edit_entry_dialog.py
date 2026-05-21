"""
ChronicForge — Edit Log Entry Dialog  (FIX 4)
Inline edit dialog for a log entry: activity text, stat, intensity, notes.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

C_BG = "#e8e0cc"
C_SURFACE = "#ddd5b5"
C_RULE = "#c0b488"
C_GOLD = "#c8820a"
C_GOLD_B = "#6b3a10"
C_INK = "#3a2a18"
C_DIM = "#8a7050"
C_FAINT = "#a89060"
C_GREEN = "#2a6a30"
C_RED = "#8b1a1a"

STATS = [
    "strength",
    "intellect",
    "charisma",
    "vitality",
    "discipline",
    "creativity",
    "wealth",
]

INT_BTN = """
QPushButton {{
    background:{C_SURFACE}; color:{color};
    border:1px solid {border}; font-family: 'Share Tech Mono', monospace;
    font-size:9px; padding:8px 10px;
}}
QPushButton:checked {{ background:#d5cca8; border-color:{color}; }}
QPushButton:hover   {{ background:#d5cca8; }}
"""

FIELD_STYLE = f"""
QLineEdit {{
    background:{C_SURFACE}; color:{C_INK};
    border:none; border-bottom:1px solid #a89060;
    font-family: 'Share Tech Mono', monospace; font-size:11px; padding:8px 4px;
}}
QLineEdit:focus {{ border-bottom-color:{C_GOLD}; }}
"""

COMBO_STYLE = f"""
QComboBox {{
    background:{C_SURFACE}; color:{C_GOLD};
    border:1px solid {C_RULE}; font-family: 'Share Tech Mono', monospace;
    font-size:10px; padding:6px 10px;
}}
QComboBox QAbstractItemView {{
    background:{C_SURFACE}; color:{C_GOLD};
    border:1px solid {C_RULE};
    selection-background-color:#c0b488;
}}
"""


class EditEntryDialog(QDialog):
    """
    Modal dialog to edit a log entry.
    On accept emits entry_saved with updated dict.
    """

    entry_saved = Signal(dict)

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self._entry = entry
        self._intensity = entry.get("intensity", 2)

        self.setWindowTitle("Edit Entry")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet(f"QDialog {{ background:{C_BG}; }}")
        self.setFixedWidth(480)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        # Title
        title = QLabel("EDIT CHRONICLE ENTRY")
        title.setFont(QFont("Cinzel", 10, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{C_GOLD_B}; background:transparent; letter-spacing:3px;"
        )
        root.addWidget(title)

        # Activity
        root.addWidget(self._lbl("Activity"))
        self._act = QLineEdit(self._entry.get("activity", ""))
        self._act.setStyleSheet(FIELD_STYLE)
        root.addWidget(self._act)

        # Stat
        root.addWidget(self._lbl("Stat"))
        self._stat = QComboBox()
        self._stat.setStyleSheet(COMBO_STYLE)
        self._stat.addItems(STATS)
        cur_stat = self._entry.get("stat", "discipline")
        if cur_stat in STATS:
            self._stat.setCurrentIndex(STATS.index(cur_stat))
        root.addWidget(self._stat)

        # Intensity
        root.addWidget(self._lbl("Intensity"))
        int_row = QHBoxLayout()
        int_row.setSpacing(0)
        self._int_group = QButtonGroup(self)
        self._int_group.setExclusive(True)
        for val, label, col, border in [
            (1, "·  LIGHT", "#2a6a30", "#1a5020"),
            (2, "·· NORMAL", C_GOLD, "#a89060"),
            (3, "··· INTENSE", "#c04040", "#6a1818"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(val == self._intensity)
            btn.setFont(QFont("IM Fell English", 9, QFont.Weight.Bold))
            btn.setStyleSheet(
                INT_BTN.format(C_SURFACE=C_SURFACE, color=col, border=border)
            )
            btn.clicked.connect(lambda _, v=val: setattr(self, "_intensity", v))
            self._int_group.addButton(btn, val)
            int_row.addWidget(btn)
        root.addLayout(int_row)

        # Notes
        root.addWidget(self._lbl("Notes (optional)"))
        self._notes = QLineEdit(self._entry.get("notes") or "")
        self._notes.setStyleSheet(FIELD_STYLE)
        root.addWidget(self._notes)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setFont(QFont("Share Tech Mono", 9))
        cancel.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{C_FAINT};
                border:1px solid {C_RULE}; padding:8px 20px;
            }}
            QPushButton:hover {{ color:{C_INK}; border-color:{C_DIM}; }}
        """)
        cancel.clicked.connect(self.reject)

        save = QPushButton("✦  Save Changes")
        save.setFont(QFont("IM Fell English", 9, QFont.Weight.Bold))
        save.setStyleSheet(f"""
            QPushButton {{
                background:{C_SURFACE}; color:{C_GOLD};
                border:1px solid #a89060; padding:8px 20px;
                letter-spacing:1px;
            }}
            QPushButton:hover {{
                background:#d5cca8; border-color:{C_GOLD}; color:{C_GOLD_B};
            }}
        """)
        save.clicked.connect(self._save)

        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        root.addLayout(btn_row)

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text.upper())
        l.setFont(QFont("Cinzel", 7, QFont.Weight.Bold))
        l.setStyleSheet(f"color:{C_FAINT}; background:transparent; letter-spacing:3px;")
        return l

    def _save(self):
        updated = dict(self._entry)
        updated["activity"] = self._act.text().strip() or self._entry.get(
            "activity", ""
        )
        updated["stat"] = self._stat.currentText()
        updated["intensity"] = self._intensity
        updated["notes"] = self._notes.text().strip() or None
        self.entry_saved.emit(updated)
        self.accept()
