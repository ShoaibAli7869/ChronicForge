"""
ChronicForge — Bar Chart Widget
Pure QPainter horizontal or vertical bar chart.
Used for: best day of week, stat comparison, category breakdown.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

C_BG = "#0d0802"
C_GRID = "#1a1005"
C_INK_FAINT = "#3a2810"


class BarChart(QWidget):
    """
    Vertical bar chart.
    bars: [{'label': str, 'value': float, 'color': '#rrggbb'}]
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bars: list[dict] = []
        self._title: str = ""
        self._unit: str = ""
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background:{C_BG};")

    def set_data(self, bars: list[dict], title: str = "", unit: str = ""):
        self._bars = bars
        self._title = title
        self._unit = unit
        self.update()

    def paintEvent(self, _):
        if not self._bars:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        pad_l = 8
        pad_r = 8
        pad_t = 20
        pad_b = 28

        chart_w = W - pad_l - pad_r
        chart_h = H - pad_t - pad_b
        n = len(self._bars)
        max_v = max(b["value"] for b in self._bars) or 1

        bar_w = max(6, chart_w // n - 6)
        spacing = (chart_w - bar_w * n) // (n + 1)

        # Title
        p.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        p.setPen(QColor(C_INK_FAINT))
        p.drawText(
            QRectF(pad_l, 4, chart_w, 14), Qt.AlignmentFlag.AlignLeft, self._title
        )

        # Grid line at top
        p.setPen(QPen(QColor(C_GRID), 1))
        p.drawLine(pad_l, pad_t + chart_h, W - pad_r, pad_t + chart_h)

        for i, bar in enumerate(self._bars):
            bx = pad_l + spacing + i * (bar_w + spacing)
            bh = int((bar["value"] / max_v) * chart_h)
            by = pad_t + chart_h - bh
            col = QColor(bar.get("color", "#c8a020"))

            # Bar fill with gradient
            if bh > 0:
                grad = QLinearGradient(bx, by, bx, by + bh)
                c1 = QColor(col)
                c1.setAlpha(200)
                c2 = QColor(col)
                c2.setAlpha(90)
                grad.setColorAt(0.0, c1)
                grad.setColorAt(1.0, c2)
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(QRectF(bx, by, bar_w, bh))

            # Value above bar
            if bar["value"] > 0:
                val_str = (
                    f"{int(bar['value'])}{self._unit}"
                    if self._unit
                    else str(int(bar["value"]))
                )
                p.setFont(QFont("monospace", 7))
                p.setPen(QColor(col))
                p.drawText(
                    QRectF(bx - 4, max(by - 16, pad_t), bar_w + 8, 14),
                    Qt.AlignmentFlag.AlignHCenter,
                    val_str,
                )

            # Label below bar
            p.setFont(QFont("monospace", 7))
            p.setPen(QColor(C_INK_FAINT))
            p.drawText(
                QRectF(bx - 4, pad_t + chart_h + 4, bar_w + 8, 20),
                Qt.AlignmentFlag.AlignHCenter,
                bar["label"],
            )

        p.end()
