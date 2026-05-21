import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


class RadarChart(QWidget):
    """A spider/radar chart for visualizing the 7 core stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats = {
            "strength": 10.0,
            "intellect": 10.0,
            "charisma": 10.0,
            "vitality": 10.0,
            "discipline": 10.0,
            "creativity": 10.0,
            "wealth": 10.0,
        }
        self._max_val = 100.0
        self.setMinimumSize(200, 200)

    def set_stats(self, stats: dict[str, float], max_val: float):
        self._stats.update(stats)
        self._max_val = max(max_val, 1.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        center = QPointF(width / 2.0, height / 2.0)
        radius = min(width, height) / 2.0 - 30.0

        labels = list(self._stats.keys())
        num_stats = len(labels)
        if num_stats == 0:
            return

        angle_step = 2 * math.pi / num_stats

        # Draw grid (concentric polygons)
        painter.setPen(QPen(QColor(192, 180, 136), 1))
        for step in range(1, 6):
            r = radius * (step / 5.0)
            poly = QPolygonF()
            for i in range(num_stats):
                angle = i * angle_step - math.pi / 2.0
                x = center.x() + r * math.cos(angle)
                y = center.y() + r * math.sin(angle)
                poly.append(QPointF(x, y))
            painter.drawPolygon(poly)

        # Draw axes and labels
        painter.setFont(QFont("Share Tech Mono", 8))
        for i in range(num_stats):
            angle = i * angle_step - math.pi / 2.0
            x = center.x() + radius * math.cos(angle)
            y = center.y() + radius * math.sin(angle)
            painter.setPen(QPen(QColor(192, 180, 136), 1))
            painter.drawLine(center, QPointF(x, y))

            # Labels
            label = labels[i][:3].upper()
            lx = center.x() + (radius + 15) * math.cos(angle)
            ly = center.y() + (radius + 15) * math.sin(angle)
            painter.setPen(QColor(58, 42, 24))
            # Rough centering
            painter.drawText(int(lx - 10), int(ly + 5), label)

        # Draw actual stat polygon
        data_poly = QPolygonF()
        for i in range(num_stats):
            val = min(self._stats.get(labels[i], 0.0), self._max_val)
            r = radius * (val / self._max_val)
            angle = i * angle_step - math.pi / 2.0
            x = center.x() + r * math.cos(angle)
            y = center.y() + r * math.sin(angle)
            data_poly.append(QPointF(x, y))

        painter.setPen(QPen(QColor(139, 26, 26), 2))
        painter.setBrush(QBrush(QColor(139, 26, 26, 60)))
        painter.drawPolygon(data_poly)

        # Draw points
        painter.setBrush(QBrush(QColor(139, 26, 26)))
        for point in data_poly:
            painter.drawEllipse(point, 3, 3)

        painter.end()
