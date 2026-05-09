"""
ChronicForge — Activity Heatmap Widget
GitHub-style contribution calendar drawn with QPainter.
Shows 18 weeks × 7 days = 126 days of activity at a glance.
"""

from datetime import date, datetime, timedelta

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

# Activity level colours — dark parchment → burnished gold
LEVEL_COLORS = [
    "#1a1005",  # 0 — no activity
    "#3a2808",  # 1 — light
    "#7a5010",  # 2 — moderate
    "#b08020",  # 3 — good
    "#f5c842",  # 4 — excellent
]

C_BG = "#0d0802"
C_INK_FAINT = "#3a2810"
C_BORDER = "#2a1a08"

DAYS = ["M", "T", "W", "T", "F", "S", "S"]


class HeatmapWidget(QWidget):
    """
    18-week activity heatmap.
    data: list of {'date': 'YYYY-MM-DD', 'xp': int, 'count': int, 'level': 0-4}
    Ordered oldest → newest (left → right).
    """

    CELL = 13  # cell size in px
    GAP = 3  # gap between cells
    PAD_L = 20  # left padding for day labels
    PAD_T = 20  # top padding for month labels
    PAD_B = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []
        self._data_map: dict[str, dict] = {}
        self._hover: str = ""
        self.setMouseTracking(True)
        self.setStyleSheet(f"background:{C_BG};")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, data: list[dict]):
        self._data = data
        self._data_map = {d["date"]: d for d in data}
        self._calc_size()
        self.update()

    def _calc_size(self):
        weeks = 18
        h = self.PAD_T + 7 * (self.CELL + self.GAP) + self.PAD_B
        w = self.PAD_L + weeks * (self.CELL + self.GAP) + 20
        self.setFixedHeight(h)
        self.setMinimumWidth(w)

    def _cell_rect(self, week: int, dow: int) -> QRect:
        x = self.PAD_L + week * (self.CELL + self.GAP)
        y = self.PAD_T + dow * (self.CELL + self.GAP)
        return QRect(x, y, self.CELL, self.CELL)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Build 18-week grid aligned to today
        today = date.today()
        # Start from Monday of the week 17 weeks ago
        start = today - timedelta(weeks=17)
        start = start - timedelta(days=start.weekday())  # back to Monday

        font7 = QFont("monospace", 7)
        p.setFont(font7)
        p.setPen(QColor(C_INK_FAINT))

        # Day labels (left)
        for dow, label in enumerate(DAYS):
            y = self.PAD_T + dow * (self.CELL + self.GAP) + self.CELL // 2 + 3
            p.drawText(
                QRect(0, y - 8, self.PAD_L - 4, 16), Qt.AlignmentFlag.AlignRight, label
            )

        prev_month = ""
        for week in range(18):
            for dow in range(7):
                d = start + timedelta(weeks=week, days=dow)
                ds = d.isoformat()
                entry = self._data_map.get(ds)
                level = entry["level"] if entry else 0
                color = QColor(LEVEL_COLORS[level])

                rect = self._cell_rect(week, dow)
                p.fillRect(rect, QColor(C_BORDER))
                inner = rect.adjusted(1, 1, -1, -1)
                p.fillRect(inner, color)

                # Month label on first day of month
                if dow == 0 and d.day <= 7:
                    month_lbl = d.strftime("%b")
                    if month_lbl != prev_month:
                        prev_month = month_lbl
                        p.setPen(QColor(C_INK_FAINT))
                        p.drawText(
                            QRect(
                                self.PAD_L + week * (self.CELL + self.GAP), 2, 30, 16
                            ),
                            Qt.AlignmentFlag.AlignLeft,
                            month_lbl,
                        )

        # Legend
        lx = self.PAD_L
        ly = self.height() - self.PAD_B - 2
        p.setPen(QColor(C_INK_FAINT))
        p.drawText(QRect(lx, ly - 10, 30, 14), Qt.AlignmentFlag.AlignLeft, "Less")
        lx += 34
        for level in range(5):
            p.fillRect(
                QRect(
                    lx + level * (self.CELL - 2 + self.GAP),
                    ly - 8,
                    self.CELL - 2,
                    self.CELL - 2,
                ),
                QColor(LEVEL_COLORS[level]),
            )
        lx += 5 * (self.CELL - 2 + self.GAP) + 4
        p.drawText(QRect(lx, ly - 10, 30, 14), Qt.AlignmentFlag.AlignLeft, "More")
        p.end()

    def mouseMoveEvent(self, e):
        # Find which cell is under cursor
        today = date.today()
        start = today - timedelta(weeks=17)
        start = start - timedelta(days=start.weekday())

        for week in range(18):
            for dow in range(7):
                if self._cell_rect(week, dow).contains(e.pos()):
                    d = start + timedelta(weeks=week, days=dow)
                    ds = d.isoformat()
                    entry = self._data_map.get(ds)
                    if entry and entry["xp"] > 0:
                        QToolTip.showText(
                            e.globalPosition().toPoint(),
                            f"{ds}\n+{entry['xp']} XP  ·  "
                            f"{entry['count']} deed{'s' if entry['count'] != 1 else ''}",
                            self,
                        )
                    else:
                        QToolTip.showText(
                            e.globalPosition().toPoint(), f"{ds}\nNo activity", self
                        )
                    return
        QToolTip.hideText()
