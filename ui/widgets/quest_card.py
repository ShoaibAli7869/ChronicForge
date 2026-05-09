"""
ChronicForge — Quest Card Widget
A single quest rendered as a dark parchment card with complete button.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

STAT_ICONS = {
    "strength": "⚔",
    "intellect": "📖",
    "charisma": "🗣",
    "vitality": "💚",
    "discipline": "🛡",
    "creativity": "✨",
    "wealth": "💰",
}
TYPE_COLORS = {
    "daily": "#c8a020",
    "weekly": "#8050d0",
    "life": "#d04020",
}

CARD_STYLE = """
QWidget#QuestCard {{
    background: #1a0f05;
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px;
}}
"""

BTN_STYLE = """
QPushButton {
    background: #2a1a08;
    color: #c8a020;
    border: 1px solid #8b6010;
    border-radius: 4px;
    font-family: monospace;
    font-size: 10px;
    padding: 4px 10px;
}
QPushButton:hover { background: #3d2810; color: #f5c842; border-color: #c8a020; }
QPushButton:pressed { background: #1a0f05; }
"""


class QuestCard(QWidget):
    completed = Signal(int)  # emits quest id

    def __init__(self, quest: dict, parent=None):
        super().__init__(parent)
        self._quest = quest
        self._build()

    def _build(self):
        q = self._quest
        border = TYPE_COLORS.get(q["type"], "#8b6010")
        icon = STAT_ICONS.get(q["stat"], "⚔")

        self.setObjectName("QuestCard")
        self.setStyleSheet(CARD_STYLE.format(border=border))
        self.setMaximumHeight(90)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(10)

        # Icon
        ic = QLabel(icon)
        ic.setFont(QFont("monospace", 18))
        ic.setFixedWidth(28)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(ic)

        # Text block
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title = QLabel(q["title"])
        title.setFont(QFont("monospace", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {border};")

        desc = QLabel(q["description"])
        desc.setFont(QFont("monospace", 8))
        desc.setStyleSheet("color: #a08060;")
        desc.setWordWrap(True)

        meta = QLabel(
            f"{q['type'].upper()}  ·  {q['xp_reward']} XP  ·  {q['stat'].upper()}"
        )
        meta.setFont(QFont("monospace", 7))
        meta.setStyleSheet("color: #6a4a2a;")

        text_col.addWidget(title)
        text_col.addWidget(desc)
        text_col.addWidget(meta)
        outer.addLayout(text_col, stretch=1)

        # Complete button (only for daily/weekly)
        if q["type"] in ("daily", "weekly") and not q.get("completed"):
            btn = QPushButton("✓ Done")
            btn.setStyleSheet(BTN_STYLE)
            btn.setFixedWidth(68)
            btn.clicked.connect(lambda: self.completed.emit(q["id"]))
            outer.addWidget(btn)
