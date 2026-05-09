"""
ChronicForge — Dashboard Window  (v2 — Obsidian Luxury)
Left sidebar navigation. Stacked pages. No test buttons.
"""

import os

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.game_logic import get_character
from ui.dashboard.activity_tab import ActivityTab
from ui.dashboard.character_tab import CharacterTab
from ui.dashboard.journal_tab import JournalTab
from ui.dashboard.log_tab import LogTab
from ui.dashboard.progress_tab import ProgressTab
from ui.dashboard.quest_tab import QuestTab
from ui.dashboard.settings_tab import SettingsTab
from utils.signals import event_bus

# ── Global stylesheet ─────────────────────────────────────────────────────────
GLOBAL_STYLE = """
* { font-family: monospace; }
QMainWindow, QWidget { background: #0d0802; color: #e8d5a3; }
QScrollBar:vertical {
    background: #150d04; width: 6px; border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #3a2208; border-radius: 3px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #7a5010; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #150d04; height: 6px; border-radius: 3px; }
QScrollBar::handle:horizontal { background: #3a2208; border-radius: 3px; }
QToolTip {
    background: #1a0f05; color: #f5c842;
    border: 1px solid #5a3a10;
    font-size: 10px; padding: 5px 8px;
    border-radius: 4px;
}
QLineEdit, QTextEdit {
    background: #150d04; color: #e8d5a3;
    border: 1px solid #3a2208; border-radius: 6px;
    padding: 8px 12px; font-size: 11px;
    selection-background-color: #5a3a10;
}
QLineEdit:focus, QTextEdit:focus { border-color: #b8900c; }
QComboBox {
    background: #150d04; color: #c8a020;
    border: 1px solid #3a2208; border-radius: 6px;
    padding: 6px 12px; font-size: 10px;
}
QComboBox QAbstractItemView {
    background: #150d04; color: #c8a020;
    border: 1px solid #3a2208;
    selection-background-color: #3a2208;
}
"""

NAV_BTN_STYLE = """
QPushButton {{
    background: transparent;
    color: {color};
    border: none;
    border-left: 3px solid {accent};
    border-radius: 0px;
    font-size: 11px;
    font-weight: {weight};
    text-align: left;
    padding: 12px 16px 12px 20px;
}}
QPushButton:hover {{ background: #1a0f04; color: #e8d5a3; }}
"""

NAV_ACTIVE = {"color": "#f5c842", "accent": "#c8a020", "weight": "bold"}
NAV_INACTIVE = {"color": "#5a3a18", "accent": "transparent", "weight": "normal"}


class DashboardWindow(QMainWindow):
    def __init__(self, assets_dir: str, parent=None):
        super().__init__(parent)
        self._assets = assets_dir
        self._nav_btns: list[QPushButton] = []
        self._current = 0
        self._drag_pos = None

        self.setWindowTitle("ChronicForge")
        self.setMinimumSize(900, 620)
        self.resize(1020, 700)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)

        self._build()

        event_bus.stats_updated.connect(self._on_stats_updated)
        event_bus.quests_updated.connect(
            lambda: QTimer.singleShot(200, self._refresh_current)
        )
        event_bus.config_saved.connect(self._on_config_saved)

        QTimer(self, interval=30_000, timeout=self._auto_refresh).start()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        hl = QHBoxLayout(root)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        hl.addWidget(self._build_sidebar())

        # Thin divider
        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet("background: #2a1a08;")
        hl.addWidget(div)

        # Main content
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._build_topbar())

        self._stack = QStackedWidget()
        self._char_tab = CharacterTab(self._assets)
        self._quest_tab = QuestTab()
        self._log_tab = LogTab()
        self._journal_tab = JournalTab()
        self._settings_tab = SettingsTab()
        self._activity_tab = ActivityTab()
        self._progress_tab = ProgressTab()
        for w in (
            self._char_tab,
            self._quest_tab,
            self._log_tab,
            self._journal_tab,
            self._settings_tab,
            self._activity_tab,
            self._progress_tab,
        ):
            self._stack.addWidget(w)

        right.addWidget(self._stack, stretch=1)
        right.addWidget(self._build_statusbar())

        right_w = QWidget()
        right_w.setLayout(right)
        hl.addWidget(right_w, stretch=1)

    def _build_sidebar(self) -> QWidget:
        sb = QWidget()
        sb.setFixedWidth(200)
        sb.setStyleSheet("background: #080501;")
        vl = QVBoxLayout(sb)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # Logo block
        logo_w = QWidget()
        logo_w.setFixedHeight(72)
        logo_w.setStyleSheet("background: #080501; border-bottom: 1px solid #1a0f04;")
        ll = QHBoxLayout(logo_w)
        ll.setContentsMargins(18, 0, 12, 0)
        icon = QLabel("⚔")
        icon.setFont(QFont("monospace", 20))
        icon.setStyleSheet("color: #c8a020;")
        brand = QLabel("Chronicle\nForge")
        brand.setFont(QFont("monospace", 11, QFont.Weight.Bold))
        brand.setStyleSheet("color: #f5c842; line-height: 1.3;")
        ll.addWidget(icon)
        ll.addSpacing(8)
        ll.addWidget(brand)
        ll.addStretch()
        vl.addWidget(logo_w)

        # Avatar + name block
        avatar_w = QWidget()
        avatar_w.setStyleSheet("background: #0a0602;")
        al = QVBoxLayout(avatar_w)
        al.setContentsMargins(0, 16, 0, 16)
        al.setSpacing(6)

        self._sidebar_avatar = QLabel()
        self._sidebar_avatar.setFixedSize(64, 64)
        self._sidebar_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sidebar_avatar.setStyleSheet(
            "border: 2px solid #3a2208; border-radius: 32px; background: #150d04;"
        )
        self._load_avatar()

        self._sidebar_name = QLabel("Hero")
        self._sidebar_name.setFont(QFont("monospace", 11, QFont.Weight.Bold))
        self._sidebar_name.setStyleSheet("color: #f5c842;")
        self._sidebar_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._sidebar_badge = QLabel("LV 1  WANDERER")
        self._sidebar_badge.setFont(QFont("monospace", 8))
        self._sidebar_badge.setStyleSheet(
            "color: #c8a020; background: #1a0f04; border: 1px solid #3a2208;"
            "border-radius: 10px; padding: 3px 10px;"
        )
        self._sidebar_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        al.addWidget(self._sidebar_avatar, alignment=Qt.AlignmentFlag.AlignCenter)
        al.addWidget(self._sidebar_name)
        al.addWidget(self._sidebar_badge, alignment=Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(avatar_w)

        # Divider
        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet("background: #1a0f04;")
        vl.addWidget(d)
        vl.addSpacing(8)

        # Nav items
        nav_items = [
            ("⚔", "Character", 0),
            ("📋", "Quests", 1),
            ("📜", "Log", 2),
            ("📖", "Journal", 3),
        ]
        for icon_s, label, idx in nav_items:
            btn = QPushButton(f"  {icon_s}  {label}")
            btn.setFont(QFont("monospace", 11))
            btn.clicked.connect(lambda _, i=idx: self._switch(i))
            self._nav_btns.append(btn)
            vl.addWidget(btn)

        vl.addStretch()

        # Activity + Progress nav items
        for icon_s, label, idx in [("📊", "Activity", 5), ("📈", "Progress", 6)]:
            btn = QPushButton(f"  {icon_s}  {label}")
            btn.setFont(QFont("monospace", 11))
            btn.clicked.connect(lambda checked=False, i=idx: self._switch(i))
            self._nav_btns.append(btn)
            vl.addWidget(btn)

        # Bottom: settings
        d2 = QFrame()
        d2.setFixedHeight(1)
        d2.setStyleSheet("background: #1a0f04;")
        vl.addWidget(d2)

        settings_btn = QPushButton("  ⚙  Settings")
        settings_btn.setFont(QFont("monospace", 11))
        settings_btn.clicked.connect(lambda: self._switch(4))
        self._nav_btns.append(settings_btn)
        vl.addWidget(settings_btn)

        self._apply_nav(0)
        return sb

    def _build_topbar(self) -> QWidget:
        tb = QWidget()
        tb.setFixedHeight(48)
        tb.setStyleSheet("background: #080501; border-bottom: 1px solid #1a0f04;")
        hl = QHBoxLayout(tb)
        hl.setContentsMargins(20, 0, 12, 0)

        self._topbar_title = QLabel("Character")
        self._topbar_title.setFont(QFont("monospace", 13, QFont.Weight.Bold))
        self._topbar_title.setStyleSheet("color: #f5c842;")

        self._topbar_sub = QLabel("")
        self._topbar_sub.setFont(QFont("monospace", 9))
        self._topbar_sub.setStyleSheet("color: #3a2208;")

        hl.addWidget(self._topbar_title)
        hl.addSpacing(12)
        hl.addWidget(self._topbar_sub)
        hl.addStretch()

        for sym, fn in [("—", self.showMinimized), ("✕", self.close)]:
            b = QPushButton(sym)
            b.setFixedSize(34, 30)
            b.setStyleSheet("""
                QPushButton { background:transparent; color:#3a2208;
                    border:none; font-size:14px; }
                QPushButton:hover { color:#f5c842; background:#1a0f04;
                    border-radius:4px; }
            """)
            b.clicked.connect(fn)
            hl.addWidget(b)

        self._update_topbar_sub()
        return tb

    def _build_statusbar(self) -> QWidget:
        sb = QWidget()
        sb.setFixedHeight(22)
        sb.setStyleSheet("background: #080501; border-top: 1px solid #150d04;")
        hl = QHBoxLayout(sb)
        hl.setContentsMargins(20, 0, 20, 0)
        self._status_lbl = QLabel("Ready.")
        self._status_lbl.setStyleSheet("color:#2a1a08; font-size:8px;")
        hl.addWidget(self._status_lbl)
        hl.addStretch()
        hl.addWidget(QLabel("ChronicForge  v2"))
        return sb

    # ── Navigation ────────────────────────────────────────────────────────────

    def _switch(self, idx: int):
        self._current = idx
        self._stack.setCurrentIndex(idx)
        self._apply_nav(idx)
        titles = [
            "Character",
            "Quests",
            "Log",
            "Journal",
            "Settings",
            "Activity",
            "Progress",
        ]
        self._topbar_title.setText(titles[idx])
        self._status_lbl.setText(titles[idx])
        self._refresh_current()

    def _apply_nav(self, active: int):
        for i, btn in enumerate(self._nav_btns):
            s = NAV_ACTIVE if i == active else NAV_INACTIVE
            btn.setStyleSheet(NAV_BTN_STYLE.format(**s))

    def _refresh_current(self):
        idx = self._current
        if idx == 0:
            self._char_tab.refresh()
        if idx == 1:
            self._quest_tab.refresh()
        if idx == 2:
            self._log_tab._load_history()
        if idx == 3:
            self._journal_tab.refresh()
        if idx == 5:
            self._activity_tab.refresh()
        if idx == 6:
            self._progress_tab.refresh()
        self._update_topbar_sub()
        self._update_sidebar()

    def _auto_refresh(self):
        self._update_topbar_sub()
        self._update_sidebar()
        if self._current in (0, 1, 5, 6):
            self._refresh_current()

    # ── Sidebar data ──────────────────────────────────────────────────────────

    def _load_avatar(self):
        path = os.path.join(self._assets, "male_hero-design.png")
        if os.path.exists(path):
            px = QPixmap(path).scaled(
                60,
                60,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self._sidebar_avatar.setPixmap(px)

    def _update_sidebar(self):
        char = get_character()
        if not char:
            return
        self._sidebar_name.setText(char.get("name", "Hero"))
        self._sidebar_badge.setText(
            f"LV {char['level']}  {char.get('class', 'Wanderer').upper()[:10]}"
        )

    def _update_topbar_sub(self):
        char = get_character()
        if char:
            self._topbar_sub.setText(
                f"🔥 {char['streak']}d  ·  {char['xp']} XP  ·  "
                f"Power {char['total_power']:.0f}"
            )

    # ── Public open helpers ───────────────────────────────────────────────────

    def open_log(self):
        self._switch(2)
        self.show()
        self.raise_()
        self.activateWindow()

    def open_quests(self):
        self._switch(1)
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_stats_updated(self):
        """Stats changed — refresh sidebar immediately + current tab after delay."""
        self._update_sidebar()
        self._update_topbar_sub()
        QTimer.singleShot(300, self._refresh_current)

    def _on_config_saved(self):
        self._update_sidebar()
        self._status_lbl.setText("Settings saved.")
        QTimer.singleShot(3000, lambda: self._status_lbl.setText("Ready."))

    # ── Drag to move ──────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.pos().y() < 48:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(self.pos() + e.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
