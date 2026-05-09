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

C_BG = "#0d0802"
C_SURFACE = "#110a03"
C_RULE = "#2a1a08"
C_GOLD = "#c8a020"
C_GOLD_B = "#f5c842"
C_INK = "#d4b870"
C_DIM = "#7a5a30"
C_FAINT = "#3a2810"
C_GREEN = "#50a030"
C_RED = "#b03020"

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
    border:1px solid {border}; font-family:monospace;
    font-size:9px; padding:8px 10px;
}}
QPushButton:checked {{ background:#1e1204; border-color:{color}; }}
QPushButton:hover   {{ background:#1a0f04; }}
"""

FIELD_STYLE = f"""
QLineEdit {{
    background:{C_SURFACE}; color:{C_INK};
    border:none; border-bottom:1px solid #4a3010;
    font-family:monospace; font-size:11px; padding:8px 4px;
}}
QLineEdit:focus {{ border-bottom-color:{C_GOLD}; }}
"""

COMBO_STYLE = f"""
QComboBox {{
    background:{C_SURFACE}; color:{C_GOLD};
    border:1px solid {C_RULE}; font-family:monospace;
    font-size:10px; padding:6px 10px;
}}
QComboBox QAbstractItemView {{
    background:{C_SURFACE}; color:{C_GOLD};
    border:1px solid {C_RULE};
    selection-background-color:#2a1a08;
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
        title.setFont(QFont("monospace", 11, QFont.Weight.Bold))
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
            (1, "·  LIGHT", "#50a030", "#1a3010"),
            (2, "·· NORMAL", C_GOLD, "#4a3010"),
            (3, "··· INTENSE", "#c04040", "#4a1010"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(val == self._intensity)
            btn.setFont(QFont("monospace", 9, QFont.Weight.Bold))
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
        cancel.setFont(QFont("monospace", 9))
        cancel.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{C_FAINT};
                border:1px solid {C_RULE}; padding:8px 20px;
            }}
            QPushButton:hover {{ color:{C_INK}; border-color:{C_DIM}; }}
        """)
        cancel.clicked.connect(self.reject)

        save = QPushButton("✦  Save Changes")
        save.setFont(QFont("monospace", 9, QFont.Weight.Bold))
        save.setStyleSheet(f"""
            QPushButton {{
                background:{C_SURFACE}; color:{C_GOLD};
                border:1px solid #4a3010; padding:8px 20px;
                letter-spacing:1px;
            }}
            QPushButton:hover {{
                background:#1e1206; border-color:{C_GOLD}; color:{C_GOLD_B};
            }}
        """)
        save.clicked.connect(self._save)

        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        root.addLayout(btn_row)

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text.upper())
        l.setFont(QFont("monospace", 7, QFont.Weight.Bold))
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
