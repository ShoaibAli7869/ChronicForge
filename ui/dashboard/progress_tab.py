"""
ChronicForge — Progress Tab
7/30-day XP chart · Heatmap calendar · Best day of week · Stat growth.
All drawn with pure QPainter — no matplotlib.
"""

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.analytics import (
    get_best_day_of_week,
    get_heatmap_data,
    get_stat_history,
    get_today_summary,
    get_xp_by_day,
)
from ui.widgets.bar_chart import BarChart
from ui.widgets.heatmap import HeatmapWidget
from ui.widgets.xp_chart import XPChart

C_BG = "#0d0802"
C_SURFACE = "#110a03"
C_RULE = "#2a1a08"
C_RULE_GOLD = "#4a3010"
C_GOLD = "#c8a020"
C_GOLD_BRIGHT = "#f5c842"
C_INK = "#d4b870"
C_INK_DIM = "#7a5a30"
C_INK_FAINT = "#3a2810"
C_GREEN = "#50a030"

STAT_COLORS = {
    "strength": "#c84040",
    "intellect": "#4080d0",
    "charisma": "#c07820",
    "vitality": "#30a060",
    "discipline": "#8050b0",
    "creativity": "#a0a020",
    "wealth": "#30a0a0",
}


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


def _section_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setFont(QFont("monospace", 7, QFont.Weight.Bold))
    l.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px;")
    return l


def _period_btn(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setCheckable(True)
    b.setFont(QFont("monospace", 8))
    b.setFixedWidth(48)
    b.setStyleSheet(f"""
        QPushButton {{
            background:transparent; color:{C_INK_FAINT};
            border:1px solid {C_RULE}; padding:3px 0;
        }}
        QPushButton:checked {{
            color:{C_GOLD}; border-color:{C_RULE_GOLD};
            background:{C_SURFACE};
        }}
        QPushButton:hover {{ color:{C_GOLD}; border-color:{C_RULE_GOLD}; }}
    """)
    return b


class ProgressTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._xp_days = 30
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet(f"background:{C_BG};")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 20, 28, 24)
        root.setSpacing(0)

        # Page title + today summary
        title_row = QHBoxLayout()
        title = QLabel("CHRONICLES OF PROGRESS")
        title.setFont(QFont("monospace", 14, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{C_GOLD_BRIGHT}; background:transparent; letter-spacing:4px;"
        )
        self._today_lbl = QLabel("")
        self._today_lbl.setFont(QFont("monospace", 8))
        self._today_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
        title_row.addWidget(title)
        title_row.addSpacing(16)
        title_row.addWidget(self._today_lbl)
        title_row.addStretch()
        root.addLayout(title_row)
        root.addSpacing(10)
        root.addWidget(_Divider(C_GOLD))
        root.addSpacing(14)

        # ── XP chart ──────────────────────────────────────────────────────────
        xp_hdr = QHBoxLayout()
        xp_hdr.addWidget(_section_label("EXPERIENCE PER DAY"))
        xp_hdr.addSpacing(16)

        # Period selector
        self._period_group = QButtonGroup(self)
        self._period_group.setExclusive(True)
        for label, days in [("7d", 7), ("14d", 14), ("30d", 30)]:
            btn = _period_btn(label)
            btn.setChecked(days == 30)
            btn.clicked.connect(lambda _, d=days: self._set_xp_period(d))
            self._period_group.addButton(btn)
            xp_hdr.addWidget(btn)
        xp_hdr.addStretch()
        root.addLayout(xp_hdr)
        root.addSpacing(8)

        self._xp_chart = XPChart()
        self._xp_chart.setFixedHeight(150)
        root.addWidget(self._xp_chart)
        root.addSpacing(16)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── Heatmap ────────────────────────────────────────────────────────────
        root.addWidget(_section_label("ACTIVITY HEATMAP  ·  18 WEEKS"))
        root.addSpacing(8)
        self._heatmap = HeatmapWidget()
        root.addWidget(self._heatmap)
        root.addSpacing(16)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── Bottom row: best day + stat bars ──────────────────────────────────
        bottom = QHBoxLayout()
        bottom.setSpacing(24)

        # Best day of week
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(_section_label("BEST DAY OF WEEK"))
        left.addSpacing(6)
        self._dow_chart = BarChart()
        self._dow_chart.setFixedHeight(160)
        left.addWidget(self._dow_chart)
        bottom.addLayout(left, stretch=2)

        # Stat activity breakdown (entries per stat)
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(_section_label("MOST LOGGED STATS  ·  30 DAYS"))
        right.addSpacing(6)
        self._stat_chart = BarChart()
        self._stat_chart.setFixedHeight(160)
        right.addWidget(self._stat_chart)
        bottom.addLayout(right, stretch=2)

        root.addLayout(bottom)
        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── Streak stats row ──────────────────────────────────────────────────
        root.addWidget(_section_label("STREAK RECORD"))
        root.addSpacing(8)

        streak_row = QHBoxLayout()
        streak_row.setSpacing(24)
        self._streak_blocks = {}
        for key, label, color in [
            ("current", "CURRENT STREAK", C_GOLD),
            ("longest", "LONGEST STREAK", C_GREEN),
            ("total", "TOTAL ENTRIES", C_INK_DIM),
            ("total_xp", "TOTAL XP EARNED", C_GOLD),
        ]:
            block = QWidget()
            block.setStyleSheet("background:transparent;")
            bl = QVBoxLayout(block)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(2)
            t = QLabel(label)
            t.setFont(QFont("monospace", 6, QFont.Weight.Bold))
            t.setStyleSheet(
                f"color:{C_INK_FAINT}; background:transparent; letter-spacing:2px;"
            )
            v = QLabel("—")
            v.setFont(QFont("monospace", 20, QFont.Weight.Bold))
            v.setStyleSheet(f"color:{color}; background:transparent;")
            bl.addWidget(t)
            bl.addWidget(v)
            self._streak_blocks[key] = v
            streak_row.addWidget(block)
        streak_row.addStretch()
        root.addLayout(streak_row)
        root.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _set_xp_period(self, days: int):
        self._xp_days = days
        data = get_xp_by_day(days)
        self._xp_chart.set_data(data, f"XP / DAY  ·  LAST {days} DAYS")

    def refresh(self):
        # Today summary
        today = get_today_summary()
        from core.game_logic import STAT_KEYWORDS

        icons = {
            "strength": "⚔",
            "intellect": "📜",
            "charisma": "🎭",
            "vitality": "🌿",
            "discipline": "🛡",
            "creativity": "✒",
            "wealth": "⚖",
        }
        stat_icons = " ".join(icons.get(s, "") for s in today["stats_done"])
        self._today_lbl.setText(
            f"Today: {today['count']} deeds  ·  +{today['total_xp']} XP  ·  {stat_icons}"
            if today["count"]
            else "No deeds recorded today."
        )

        # XP chart
        self._xp_chart.set_data(
            get_xp_by_day(self._xp_days), f"XP / DAY  ·  LAST {self._xp_days} DAYS"
        )

        # Heatmap
        self._heatmap.set_data(get_heatmap_data(days=126))

        # Best day of week
        dow_data = get_best_day_of_week()
        max_dow = max(d["avg_xp"] for d in dow_data) or 1
        self._dow_chart.set_data(
            [
                {
                    "label": d["day"],
                    "value": d["avg_xp"],
                    "color": C_GOLD if d["avg_xp"] == max_dow else C_RULE_GOLD,
                }
                for d in dow_data
            ],
            title="AVG XP",
            unit="",
        )

        # Stat activity (count of entries per stat last 30 days)
        stat_hist = get_stat_history(30)
        stat_totals = {
            stat: sum(d["count"] for d in days) for stat, days in stat_hist.items()
        }
        sorted_stats = sorted(stat_totals.items(), key=lambda x: x[1], reverse=True)
        self._stat_chart.set_data(
            [
                {
                    "label": s[:3].upper(),
                    "value": cnt,
                    "color": STAT_COLORS.get(s, C_GOLD_BRIGHT),
                }
                for s, cnt in sorted_stats
            ],
            title="ENTRIES",
            unit="",
        )

        # Streak blocks
        try:
            from sqlalchemy import func as sqlfunc
            from sqlalchemy import select

            from core.database import LogEntry, SessionFactory
            from core.game_logic import get_character

            char = get_character()
            self._streak_blocks["current"].setText(f"{char.get('streak', 0)}d")
            self._streak_blocks["longest"].setText(f"{char.get('longest_streak', 0)}d")
            with SessionFactory() as session:
                cnt = (
                    session.scalar(
                        select(sqlfunc.count(LogEntry.id)).where(
                            LogEntry.character_id == 1
                        )
                    )
                    or 0
                )
                xp_t = (
                    session.scalar(
                        select(sqlfunc.sum(LogEntry.xp_awarded)).where(
                            LogEntry.character_id == 1
                        )
                    )
                    or 0
                )
            self._streak_blocks["total"].setText(str(cnt))
            self._streak_blocks["total_xp"].setText(f"{xp_t:,}")
        except Exception:
            pass
