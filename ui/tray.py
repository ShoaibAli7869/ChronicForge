"""
ChronicForge — System Tray
Persistent tray icon for quick access and sprite toggle.
"""

import os

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TraySignals(QObject):
    toggle_sprite = Signal()
    open_dashboard = Signal()
    open_log = Signal()
    quit_app = Signal()


class ChronicForgeTray(QSystemTrayIcon):
    """System tray icon with right-click menu."""

    def __init__(self, assets_dir: str, parent=None):
        super().__init__(parent)
        self.signals = TraySignals()
        self._sprite_visible = True

        # Build icon from design sheet or fallback
        icon = self._make_icon(assets_dir)
        self.setIcon(icon)
        self.setToolTip("ChronicForge — Your Realm Awaits")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #1a0f08;
                color: #e8d5a3;
                border: 1px solid #8b6914;
                font-family: monospace;
                font-size: 11px;
                padding: 4px;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background: #3d2a0a; color: #f5c842; }
            QMenu::separator { height: 1px; background: #5a3d0a; margin: 3px 8px; }
        """)

        self._toggle_action = menu.addAction("👁  Hide Companion")
        self._toggle_action.triggered.connect(self._toggle_sprite)
        menu.addAction("⚔  Open Chronicle").triggered.connect(
            self.signals.open_dashboard.emit
        )
        menu.addAction("📜  Daily Log").triggered.connect(self.signals.open_log.emit)
        menu.addSeparator()
        menu.addAction("✕  Quit").triggered.connect(QApplication.quit)

        self.setContextMenu(menu)
        self.show()

    def _make_icon(self, assets_dir: str) -> QIcon:
        """Use the design sheet as tray icon (first 128×128 frame)."""
        design = os.path.join(assets_dir, "male_hero-design.png")
        if os.path.exists(design):
            px = QPixmap(design).scaled(
                32,
                32,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            return QIcon(px)
        # Fallback: golden sword emoji-style square
        px = QPixmap(32, 32)
        px.fill(QColor("#1a0f08"))
        p = QPainter(px)
        p.setPen(QColor("#f5c842"))
        p.setFont(QFont("monospace", 16))
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "⚔")
        p.end()
        return QIcon(px)

    def _toggle_sprite(self):
        self._sprite_visible = not self._sprite_visible
        self._toggle_action.setText(
            "👁  Hide Companion" if self._sprite_visible else "👁  Show Companion"
        )
        self.signals.toggle_sprite.emit()
