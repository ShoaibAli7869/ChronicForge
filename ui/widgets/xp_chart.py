"""
ChronicForge — XP Line Chart Widget
Pure QPainter — no matplotlib dependency.
Draws a filled area chart of daily XP over the last 7/14/30 days.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

C_BG = "#0d0802"
C_GOLD = "#c8a020"
C_GOLD_DIM = "#4a3010"
C_INK_FAINT = "#3a2810"
C_GRID = "#1a1005"


class XPChart(QWidget):
    """Filled area line chart for daily XP data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []  # [{'date': str, 'xp': int}]
        self._label = "XP / DAY"
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background:{C_BG};")

    def set_data(self, data: list[dict], label: str = "XP / DAY"):
        self._data = data
        self._label = label
        self.update()

    def paintEvent(self, _):
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        pad_l = 44  # left padding for y-axis labels
        pad_r = 12
        pad_t = 22
        pad_b = 24  # bottom for x-axis labels

        chart_w = W - pad_l - pad_r
        chart_h = H - pad_t - pad_b

        values = [d["xp"] for d in self._data]
        max_v = max(values) if max(values) > 0 else 1
        n = len(values)

        def x(i: int) -> float:
            return pad_l + i * chart_w / max(n - 1, 1)

        def y(v: float) -> float:
            return pad_t + chart_h - (v / max_v) * chart_h

        # ── Grid lines ────────────────────────────────────────────────────────
        p.setPen(QPen(QColor(C_GRID), 1))
        for level in [0, 0.25, 0.5, 0.75, 1.0]:
            gy = pad_t + chart_h - level * chart_h
            p.drawLine(QPointF(pad_l, gy), QPointF(W - pad_r, gy))

        # ── Y-axis labels ─────────────────────────────────────────────────────
        font = QFont("monospace", 7)
        p.setFont(font)
        p.setPen(QColor(C_INK_FAINT))
        fm = QFontMetrics(font)
        for level in [0, 0.5, 1.0]:
            val = int(max_v * level)
            lbl = str(val)
            gy = pad_t + chart_h - level * chart_h
            p.drawText(
                QRectF(0, gy - 8, pad_l - 4, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                lbl,
            )

        # ── X-axis date labels (show every ~7 days) ───────────────────────────
        step = max(1, n // 6)
        for i in range(0, n, step):
            lbl = self._data[i]["date"][5:]  # MM-DD
            gx = x(i)
            p.drawText(
                QRectF(gx - 20, H - pad_b + 4, 40, 16),
                Qt.AlignmentFlag.AlignHCenter,
                lbl,
            )

        # ── Filled area ───────────────────────────────────────────────────────
        if n > 1:
            path = QPainterPath()
            path.moveTo(x(0), pad_t + chart_h)
            for i, d in enumerate(self._data):
                path.lineTo(x(i), y(d["xp"]))
            path.lineTo(x(n - 1), pad_t + chart_h)
            path.closeSubpath()

            grad = QLinearGradient(0, pad_t, 0, pad_t + chart_h)
            grad.setColorAt(0.0, QColor(200, 160, 32, 90))
            grad.setColorAt(1.0, QColor(200, 160, 32, 8))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)

            # ── Line ──────────────────────────────────────────────────────────
            p.setPen(QPen(QColor(C_GOLD), 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            line = QPainterPath()
            line.moveTo(x(0), y(self._data[0]["xp"]))
            for i, d in enumerate(self._data[1:], 1):
                line.lineTo(x(i), y(d["xp"]))
            p.drawPath(line)

            # ── Data points ───────────────────────────────────────────────────
            p.setBrush(QBrush(QColor(C_GOLD)))
            p.setPen(QPen(QColor(C_BG), 1))
            for i, d in enumerate(self._data):
                if d["xp"] > 0:
                    p.drawEllipse(QPointF(x(i), y(d["xp"])), 3, 3)

        # ── Chart label ───────────────────────────────────────────────────────
        p.setPen(QColor(C_INK_FAINT))
        p.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        p.drawText(
            QRectF(pad_l, 4, chart_w, 16), Qt.AlignmentFlag.AlignLeft, self._label
        )

        p.end()
