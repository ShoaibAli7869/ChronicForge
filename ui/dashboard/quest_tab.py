"""
ChronicForge — Quest Tab  (v3 — Medieval Codex)

Design language:
  - Parchment-style scroll sections, not floating cards
  - Heavy horizontal rules with ornamental dividers between sections
  - Quest rows use a table-like ledger layout: icon | title | stat | reward | action
  - Three clearly separated sections: Daily Edicts / Weekly Campaign / Life Oaths
  - Muted obsidian background, warm gold ink for active text
  - No border-radius clutter — flat ruled sections feel medieval
  - Completion marks quests with a strike and seal glyph instead of removal
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.quest_system import (
    complete_quest,
    generate_daily_quests,
    generate_weekly_quest,
    get_active_quests,
)
from utils.signals import event_bus

# ── Palette ───────────────────────────────────────────────────────────────────
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
C_PURPLE = "#8060c0"
C_RED = "#b03820"
C_GREEN_DIM = "#2a5a18"
C_GREEN = "#50a030"

STAT_ICONS = {
    "strength": "⚔",
    "intellect": "📜",
    "charisma": "🎭",
    "vitality": "🌿",
    "discipline": "🛡",
    "creativity": "✒",
    "wealth": "⚖",
}

SECTION_META = {
    "daily": {
        "glyph": "✦",
        "title": "Daily Edicts",
        "sub": "Renew at dawn",
        "color": C_GOLD,
    },
    "weekly": {
        "glyph": "⚜",
        "title": "Weekly Campaign",
        "sub": "Reset each sennight",
        "color": C_PURPLE,
    },
    "life": {
        "glyph": "♾",
        "title": "Life Oaths",
        "sub": "Sworn unto completion",
        "color": C_RED,
    },
}

INTENSITY_GLYPHS = {1: "·", 2: "··", 3: "···"}  # Low / Normal / High


# ── Ornamental divider ────────────────────────────────────────────────────────


class _Divider(QWidget):
    """Horizontal rule with a centre ornament — hand-drawn medieval feel."""

    def __init__(self, color: str = C_RULE_GOLD, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedHeight(12)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color, 1)
        p.setPen(pen)
        mid = self.height() // 2
        w = self.width()
        # Left rule
        p.drawLine(0, mid, w // 2 - 18, mid)
        # Right rule
        p.drawLine(w // 2 + 18, mid, w, mid)
        # Centre diamond
        cx, cy = w // 2, mid
        sz = 4
        p.setBrush(QColor(self._color))
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QPolygon

        diamond = QPolygon(
            [
                QPoint(cx, cy - sz),
                QPoint(cx + sz, cy),
                QPoint(cx, cy + sz),
                QPoint(cx - sz, cy),
            ]
        )
        p.drawPolygon(diamond)
        p.end()


# ── Single quest row ──────────────────────────────────────────────────────────


class _QuestRow(QWidget):
    """
    One quest as a ledger row:
    [glyph]  Title text                    [STAT]  ···  [+120 XP]  [Complete]
    [faint]  Description sub-text
    """

    def __init__(self, q: dict, section_color: str, on_done=None, parent=None):
        super().__init__(parent)
        self._q = q
        self._done = q.get("completed", False)
        self.setStyleSheet(f"background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 8, 0, 8)
        vl.setSpacing(3)

        # ── Main row ──────────────────────────────────────────────────────────
        main = QHBoxLayout()
        main.setSpacing(10)

        # Left glyph (stat icon or ✓ if done)
        glyph = QLabel("✓" if self._done else STAT_ICONS.get(q["stat"], "·"))
        glyph.setFixedWidth(18)
        glyph.setFont(QFont("monospace", 11))
        glyph.setStyleSheet(
            f"color: {C_GREEN if self._done else section_color};"
            "background: transparent;"
        )
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        title_text = q["title"]
        title = QLabel(title_text)
        title.setFont(
            QFont(
                "monospace",
                10,
                QFont.Weight.Bold if not self._done else QFont.Weight.Normal,
            )
        )
        title_style = f"color: {C_INK_FAINT};" if self._done else f"color: {C_INK};"
        if self._done:
            title_style += "text-decoration: line-through;"
        title.setStyleSheet(title_style + "background: transparent;")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Stat tag
        stat_tag = QLabel(q["stat"][:3].upper())
        stat_tag.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        stat_tag.setFixedWidth(30)
        stat_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stat_tag.setStyleSheet(
            f"color: {C_INK_FAINT}; background: transparent; letter-spacing: 1px;"
        )

        # Intensity dots
        dots = QLabel(INTENSITY_GLYPHS.get(q.get("intensity", 2), "··"))
        dots.setFont(QFont("monospace", 11))
        dots.setFixedWidth(24)
        dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dots.setStyleSheet(
            f"color: {section_color if not self._done else C_INK_FAINT};"
            "background: transparent;"
        )

        # XP reward
        xp_lbl = QLabel(f"+{q['xp_reward']}")
        xp_lbl.setFont(QFont("monospace", 9, QFont.Weight.Bold))
        xp_lbl.setFixedWidth(44)
        xp_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        xp_lbl.setStyleSheet(
            f"color: {C_GOLD_DIM if self._done else C_GOLD}; background: transparent;"
        )

        main.addWidget(glyph)
        main.addWidget(title, stretch=1)
        main.addWidget(stat_tag)
        main.addWidget(dots)
        main.addWidget(xp_lbl)

        # Complete button — only for non-life, non-done quests
        if q["type"] in ("daily", "weekly") and not self._done:
            btn = QPushButton("Mark Done")
            btn.setFont(QFont("monospace", 8))
            btn.setFixedWidth(84)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C_GOLD_DIM};
                    border: 1px solid {C_RULE_GOLD};
                    border-radius: 0px;
                    padding: 4px 0px;
                    letter-spacing: 1px;
                }}
                QPushButton:hover {{
                    color: {C_GOLD_BRIGHT};
                    border-color: {C_GOLD};
                    background: #1e1206;
                }}
                QPushButton:pressed {{
                    background: #2a1a08;
                }}
            """)
            btn.clicked.connect(lambda: on_done and on_done(q["id"]))
            main.addWidget(btn)
        elif self._done:
            seal = QLabel("— sealed —")
            seal.setFont(QFont("monospace", 8))
            seal.setFixedWidth(84)
            seal.setAlignment(Qt.AlignmentFlag.AlignCenter)
            seal.setStyleSheet(f"color: {C_INK_FAINT}; background: transparent;")
            main.addWidget(seal)
        else:
            # Life quest — no button, show ongoing indicator
            ongoing = QLabel("ongoing")
            ongoing.setFont(QFont("monospace", 8))
            ongoing.setFixedWidth(84)
            ongoing.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ongoing.setStyleSheet(f"color: {C_INK_FAINT}; background: transparent;")
            main.addWidget(ongoing)

        vl.addLayout(main)

        # ── Description sub-row ───────────────────────────────────────────────
        desc = QLabel(q["description"])
        desc.setFont(QFont("monospace", 8))
        desc.setStyleSheet(
            f"color: {C_INK_FAINT}; background: transparent; padding-left: 28px;"
        )
        desc.setWordWrap(True)
        vl.addWidget(desc)


# ── Section (Daily / Weekly / Life) ──────────────────────────────────────────


class _Section(QWidget):
    """
    One parchment section:
      ══ ✦ DAILY EDICTS ─ Renew at dawn ══
      [quest rows separated by thin rules]
      [empty state if no quests]
    """

    def __init__(self, quest_type: str, on_done=None, parent=None):
        super().__init__(parent)
        self._type = quest_type
        self._on_done = on_done
        self._meta = SECTION_META[quest_type]
        self._rows = []

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # Section header
        self._build_header(vl)

        # Quest list area
        self._list_layout = QVBoxLayout()
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        vl.addLayout(self._list_layout)

        # Bottom padding
        vl.addSpacing(8)

    def _build_header(self, parent_vl: QVBoxLayout):
        _Divider(self._meta["color"])  # unused — using widget version below

        # Top divider
        top_div = _Divider(self._meta["color"])
        parent_vl.addWidget(top_div)

        # Header row
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(4, 6, 4, 6)
        hdr_row.setSpacing(10)

        glyph = QLabel(self._meta["glyph"])
        glyph.setFont(QFont("monospace", 14))
        glyph.setStyleSheet(f"color: {self._meta['color']}; background: transparent;")

        title = QLabel(self._meta["title"].upper())
        title.setFont(QFont("monospace", 11, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {self._meta['color']}; background: transparent; letter-spacing: 3px;"
        )

        sub = QLabel(self._meta["sub"])
        sub.setFont(QFont("monospace", 8))
        sub.setStyleSheet(f"color: {C_INK_FAINT}; background: transparent;")

        self._count_lbl = QLabel("")
        self._count_lbl.setFont(QFont("monospace", 8))
        self._count_lbl.setStyleSheet(f"color: {C_INK_FAINT}; background: transparent;")

        hdr_row.addWidget(glyph)
        hdr_row.addWidget(title)
        hdr_row.addSpacing(8)
        hdr_row.addWidget(sub)
        hdr_row.addStretch()
        hdr_row.addWidget(self._count_lbl)

        parent_vl.addLayout(hdr_row)

        # Bottom header rule
        bot_div = _Divider(C_RULE)
        parent_vl.addWidget(bot_div)
        parent_vl.addSpacing(4)

    def load(self, quests: list[dict]):
        # Clear existing rows and separators
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total = len(quests)
        done = sum(1 for q in quests if q.get("completed"))
        pending = total - done
        self._count_lbl.setText(f"{done}/{total} complete" if total else "none issued")

        if not quests:
            empty = QLabel(
                "No edicts today. Return at dawn."
                if self._type == "daily"
                else "No oaths sworn yet."
            )
            empty.setFont(QFont("monospace", 9))
            empty.setStyleSheet(
                f"color: {C_INK_FAINT}; background: transparent; padding: 10px 28px;"
            )
            self._list_layout.addWidget(empty)
            return

        # Pending quests first, completed after
        sorted_quests = [q for q in quests if not q.get("completed")] + [
            q for q in quests if q.get("completed")
        ]

        for i, q in enumerate(sorted_quests):
            row = _QuestRow(q, self._meta["color"], self._on_done)
            self._rows.append(row)
            self._list_layout.addWidget(row)

            # Thin separator between rows (not after last)
            if i < len(sorted_quests) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: {C_RULE}; border: none;")
                self._list_layout.addWidget(sep)


# ── Column header (ledger legend) ─────────────────────────────────────────────


class _LedgerHeader(QWidget):
    """The column labels that sit above all quest rows — one per tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 0, 4, 6)
        row.setSpacing(10)

        def col(text, width=None, align=Qt.AlignmentFlag.AlignLeft):
            l = QLabel(text)
            l.setFont(QFont("monospace", 7, QFont.Weight.Bold))
            l.setStyleSheet(
                f"color: {C_INK_FAINT}; background: transparent; letter-spacing: 2px;"
            )
            l.setAlignment(align)
            if width:
                l.setFixedWidth(width)
            return l

        row.addWidget(col("", 18))  # glyph
        row.addWidget(col("QUEST"), 1)  # stretch
        row.addWidget(col("STAT", 30, Qt.AlignmentFlag.AlignCenter))
        row.addWidget(col("DIFF", 24, Qt.AlignmentFlag.AlignCenter))
        row.addWidget(
            col(
                "REWARD",
                44,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
        )
        row.addWidget(col("", 84))  # action


# ── Main Quest Tab ────────────────────────────────────────────────────────────


class QuestTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet(f"background: {C_BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 16)
        root.setSpacing(0)

        # ── Page title ────────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        page_title = QLabel("QUEST BOARD")
        page_title.setFont(QFont("monospace", 14, QFont.Weight.Bold))
        page_title.setStyleSheet(
            f"color: {C_GOLD_BRIGHT}; background: transparent; letter-spacing: 4px;"
        )

        self._summary_lbl = QLabel("")
        self._summary_lbl.setFont(QFont("monospace", 8))
        self._summary_lbl.setStyleSheet(
            f"color: {C_INK_FAINT}; background: transparent;"
        )
        self._summary_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setFont(QFont("monospace", 8))
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_INK_FAINT};
                border: 1px solid {C_RULE}; border-radius: 0px;
                padding: 5px 14px; letter-spacing: 1px;
            }}
            QPushButton:hover {{
                color: {C_GOLD}; border-color: {C_RULE_GOLD};
            }}
        """)
        refresh_btn.clicked.connect(self.refresh)

        title_row.addWidget(page_title)
        title_row.addSpacing(12)
        title_row.addWidget(self._summary_lbl)
        title_row.addStretch()
        title_row.addWidget(refresh_btn)
        root.addLayout(title_row)
        root.addSpacing(12)

        # ── Grand divider ─────────────────────────────────────────────────────
        root.addWidget(_Divider(C_GOLD))
        root.addSpacing(4)

        # ── Ledger column header ──────────────────────────────────────────────
        root.addWidget(_LedgerHeader())

        # ── Scrollable body ───────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_vl = QVBoxLayout(body)
        body_vl.setContentsMargins(0, 0, 8, 0)
        body_vl.setSpacing(16)

        self._daily_section = _Section("daily", self._on_done)
        self._weekly_section = _Section("weekly", self._on_done)
        self._life_section = _Section("life", None)

        body_vl.addWidget(self._daily_section)
        body_vl.addWidget(self._weekly_section)
        body_vl.addWidget(self._life_section)
        body_vl.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def refresh(self):
        generate_daily_quests(3)
        generate_weekly_quest()
        q = get_active_quests()

        self._daily_section.load(q.get("daily", []))
        self._weekly_section.load(q.get("weekly", []))
        self._life_section.load(q.get("life", []))

        # Summary line
        all_quests = q.get("daily", []) + q.get("weekly", [])
        total = len(all_quests)
        done = sum(1 for x in all_quests if x.get("completed"))
        life_n = len(q.get("life", []))
        self._summary_lbl.setText(
            f"{done}/{total} edicts complete  ·  {life_n} life oaths sworn"
        )

    def _on_done(self, quest_id: int):
        result = complete_quest(quest_id)
        if "error" not in result:
            event_bus.xp_gained.emit(result.get("xp_awarded", 0))
            event_bus.quest_complete.emit(result.get("quest", ""))
            if result.get("levelled_up"):
                event_bus.level_up.emit(result["new_level"])
                if result.get("stat_bonuses"):
                    event_bus.stat_bonus_awarded.emit(result["stat_bonuses"])
            event_bus.quests_updated.emit()
            event_bus.stats_updated.emit()
            QTimer.singleShot(150, self.refresh)
