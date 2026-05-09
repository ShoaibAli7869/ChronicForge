"""
ChronicForge — Stat Bar & XP Bar Widgets
Animated progress bars drawn with QPainter — no QProgressBar stylesheet hacks.
"""

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QWidget

STAT_COLORS = {
    "strength": ("#dc4646", "#ff8080"),
    "intellect": ("#3a7dd4", "#80b8ff"),
    "charisma": ("#d47820", "#ffb860"),
    "vitality": ("#34b870", "#80ffb0"),
    "discipline": ("#a040cc", "#cc80ff"),
    "creativity": ("#c8c020", "#ffee60"),
    "wealth": ("#30b8b8", "#80eeff"),
}


class StatBar(QWidget):
    """Single animated stat bar: [LABEL ████████░░░░ 42.3]"""

    def __init__(
        self, stat_name: str, value: float = 10.0, max_val: float = 200.0, parent=None
    ):
        super().__init__(parent)
        self._stat = stat_name
        self._value = value
        self._target = value
        self._max = max_val
        self._anim_v = value  # animated display value
        self.setFixedHeight(28)
        self.setMinimumWidth(200)

    def set_value(self, value: float, animate: bool = True):
        self._target = value
        if animate:
            # Simple timer-based smooth animation
            from PySide6.QtCore import QTimer

            self._anim_step = (value - self._anim_v) / 20
            self._anim_timer = QTimer(self)
            self._anim_timer.setInterval(16)
            self._anim_timer.timeout.connect(self._step_anim)
            self._anim_timer.start()
        else:
            self._anim_v = value
            self._value = value
            self.update()

    def _step_anim(self):
        if abs(self._anim_v - self._target) < abs(self._anim_step) + 0.01:
            self._anim_v = self._target
            self._value = self._target
            self._anim_timer.stop()
        else:
            self._anim_v += self._anim_step
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        label_w = 32
        val_w = 38
        bar_x = label_w + 6
        bar_w = w - label_w - val_w - 14
        bar_h = 10
        bar_y = (h - bar_h) // 2

        # Label
        font = QFont("monospace", 8, QFont.Weight.Bold)
        p.setFont(font)
        col1, col2 = STAT_COLORS.get(self._stat, ("#aaa", "#ccc"))
        p.setPen(QColor(col1))
        p.drawText(
            0, 0, label_w, h, Qt.AlignmentFlag.AlignVCenter, self._stat[:3].upper()
        )

        # Track
        p.setBrush(QBrush(QColor(30, 18, 8)))
        p.setPen(QPen(QColor(60, 40, 15), 1))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)

        # Fill
        fill_w = int(bar_w * min(self._anim_v, self._max) / self._max)
        if fill_w > 2:
            grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
            grad.setColorAt(0.0, QColor(col1))
            grad.setColorAt(1.0, QColor(col2))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 4, 4)

        # Value text
        p.setPen(QColor(220, 200, 140))
        p.setFont(QFont("monospace", 8))
        p.drawText(
            bar_x + bar_w + 6,
            0,
            val_w,
            h,
            Qt.AlignmentFlag.AlignVCenter,
            f"{self._anim_v:.1f}",
        )
        p.end()


class XPBar(QWidget):
    """XP progress bar with level info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 1
        self._xp = 0
        self._xp_next = 100
        self._pct = 0.0
        self._anim_pct = 0.0
        self.setFixedHeight(22)

    def set_xp(self, level: int, xp: int, xp_next: int, animate: bool = True):
        self._level = level
        self._xp = xp
        self._xp_next = max(xp_next, 1)
        target_pct = min(xp / self._xp_next, 1.0)
        if animate:
            from PySide6.QtCore import QTimer

            self._pct_step = (target_pct - self._anim_pct) / 25
            self._pct_target = target_pct
            self._xp_timer = QTimer(self)
            self._xp_timer.setInterval(16)
            self._xp_timer.timeout.connect(self._step_xp)
            self._xp_timer.start()
        else:
            self._pct = self._anim_pct = target_pct
            self.update()

    def _step_xp(self):
        if abs(self._anim_pct - self._pct_target) < 0.005:
            self._anim_pct = self._pct_target
            self._xp_timer.stop()
        else:
            self._anim_pct += self._pct_step
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        bar_h = 8
        bar_y = (h - bar_h) // 2

        # Track
        p.setBrush(QBrush(QColor(20, 12, 5)))
        p.setPen(QPen(QColor(80, 60, 20), 1))
        p.drawRoundedRect(0, bar_y, w, bar_h, 4, 4)

        # Fill (golden gradient)
        fill_w = int(w * max(0, self._anim_pct))
        if fill_w > 2:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor("#8b5e10"))
            grad.setColorAt(0.5, QColor("#d4a017"))
            grad.setColorAt(1.0, QColor("#f5c842"))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, bar_y, fill_w, bar_h, 4, 4)

            # Shimmer highlight
            p.setBrush(QBrush(QColor(255, 255, 200, 40)))
            p.drawRoundedRect(0, bar_y, fill_w, bar_h // 2, 4, 4)

        # XP text overlay
        font = QFont("monospace", 7)
        p.setFont(font)
        p.setPen(QColor(240, 210, 130))
        pct_text = f"LV{self._level}  {int(self._anim_pct * 100)}%  {self._xp}/{self._xp_next} XP"
        p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, pct_text)
        p.end()
