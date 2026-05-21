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
    "daily": "#c8820a",
    "weekly": "#4a2860",
    "life": "#8b1a1a",
}

CARD_STYLE = """
QWidget#QuestCard {{
    background: #ddd5b5;
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px;
}}
"""

BTN_STYLE = """
QPushButton {
    background: #c0b488;
    color: #c8820a;
    border: 1px solid #a89060;
    border-radius: 4px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    padding: 4px 10px;
}
QPushButton:hover { background: #d5cca8; color: #6b3a10; border-color: #c8820a; }
QPushButton:pressed { background: #ddd5b5; }
"""


class QuestCard(QWidget):
    completed = Signal(int)  # emits quest id

    def __init__(self, quest: dict, parent=None):
        super().__init__(parent)
        self._quest = quest
        self._build()

    def _build(self):
        q = self._quest
        border = TYPE_COLORS.get(q["type"], "#a89060")
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
        title.setFont(QFont("IM Fell English", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {border};")

        desc = QLabel(q["description"])
        desc.setFont(QFont("Share Tech Mono", 8))
        desc.setStyleSheet("color: #6b5030;")
        desc.setWordWrap(True)

        meta = QLabel(
            f"{q['type'].upper()}  ·  {q['xp_reward']} XP  ·  {q['stat'].upper()}"
        )
        meta.setFont(QFont("Share Tech Mono", 7))
        meta.setStyleSheet("color: #8a7050;")

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
