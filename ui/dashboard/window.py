"""
ChronicForge — Dashboard Window  (v6 — Illuminated Parchment)
Left sidebar navigation. Stacked pages. Warm ecru parchment ground.
Crimson + cobalt + amber accent triad. Medieval serif typography.
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
from ui.dashboard.quest_editor_tab import QuestEditorTab
from ui.dashboard.quest_tab import QuestTab
from ui.dashboard.settings_tab import SettingsTab
from utils.signals import event_bus

# ── Illuminated Parchment Palette ─────────────────────────────────────────────
C_BG = "#e8e0cc"
C_SIDEBAR = "#2a1f12"
C_SIDEBAR_HI = "#3a2e1e"
C_SIDEBAR_DK = "#1e160c"
C_SURFACE = "#ddd5b5"
C_RULE = "#c0b488"
C_RULE_GOLD = "#a89060"
C_TOPBAR = "#e8e0cc"

C_CRIMSON = "#8b1a1a"
C_COBALT = "#2a4a7a"
C_BROWN = "#6b3a10"
C_TAN = "#9a7c3a"

C_GOLD = "#c8820a"
C_GOLD_DIM = "#a06808"
C_GOLD_BRIGHT = "#d49010"
C_GOLD_PALE = "#f0e8d8"

C_INK = "#3a2a18"
C_INK_MID = "#6b5030"
C_INK_DIM = "#8a7050"
C_INK_FAINT = "#a89060"


def _cinzel(size, weight=QFont.Weight.Bold):
    f = QFont("Cinzel", size, weight)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


def _serif(size, weight=QFont.Weight.Normal, italic=False):
    for name in (
        "IM Fell English",
        "Palatino Linotype",
        "Palatino",
        "Georgia",
        "serif",
    ):
        f = QFont(name, size, weight)
        f.setItalic(italic)
        if f.exactMatch() or name == "serif":
            f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            return f
    return QFont("serif", size, weight)


def _mono(size, weight=QFont.Weight.Normal):
    for name in ("Share Tech Mono", "monospace"):
        f = QFont(name, size, weight)
        if f.exactMatch() or name == "monospace":
            return f
    return QFont("monospace", size, weight)


GLOBAL_STYLE = f"""
* {{ font-family: 'Share Tech Mono', monospace; }}
QMainWindow, QWidget {{ background: {C_BG}; color: {C_INK}; }}
QScrollBar:vertical {{
    background: {C_SURFACE}; width: 7px; border: none;
}}
QScrollBar::handle:vertical {{
    background: {C_RULE_GOLD}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {C_GOLD_DIM}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {C_SURFACE}; height: 7px; border: none;
}}
QScrollBar::handle:horizontal {{
    background: {C_RULE_GOLD}; border-radius: 3px;
}}
QToolTip {{
    background: {C_SURFACE}; color: {C_INK};
    border: 1px solid {C_RULE_GOLD};
    font-size: 10px; padding: 5px 8px;
}}
QLineEdit, QTextEdit {{
    background: {C_SURFACE}; color: {C_INK};
    border: none; border-bottom: 1px solid {C_RULE_GOLD};
    padding: 6px 10px; font-size: 11px;
    selection-background-color: {C_RULE};
}}
QLineEdit:focus, QTextEdit:focus {{
    border-bottom-color: {C_CRIMSON}; background: {C_BG};
}}
QComboBox {{
    background: {C_SURFACE}; color: {C_INK_MID};
    border: 1px solid {C_RULE_GOLD}; border-radius: 0px;
    padding: 6px 12px; font-size: 10px;
}}
QComboBox QAbstractItemView {{
    background: {C_SURFACE}; color: {C_INK_MID};
    border: 1px solid {C_RULE_GOLD};
    selection-background-color: {C_RULE};
}}
"""

NAV_BTN_STYLE = """
QPushButton {{
    background: transparent; color: {color};
    border: none; border-left: 3px solid {accent};
    border-radius: 0px; font-size: 11px; font-weight: {weight};
    text-align: left; padding: 12px 16px 12px 20px;
}}
QPushButton:hover {{ background: {hover_bg}; color: {hover_color}; }}
"""

NAV_ACTIVE = {
    "color": "#f0e8d8",
    "accent": C_CRIMSON,
    "weight": "bold",
    "hover_bg": C_SIDEBAR_HI,
    "hover_color": "#f0e8d8",
}
NAV_INACTIVE = {
    "color": "#8a7a60",
    "accent": "transparent",
    "weight": "normal",
    "hover_bg": C_SIDEBAR_HI,
    "hover_color": "#d0c8a8",
}

# ── Nav items: (icon, label, stack_index) ─────────────────────────────────────
# This maps button list position → stack widget index.
# Stack order: 0=Character, 1=Quests, 2=Log, 3=Journal, 4=Settings,
#              5=QuestEditor, 6=Activity, 7=Progress
NAV_ITEMS = [
    ("⛨", "Character", 0),
    ("⛿", "Quests", 1),
    ("▤", "Log", 2),
    ("◫", "Journal", 3),
    ("⚒", "Quest Editor", 5),
    ("⌁", "Activity", 6),
    ("◳", "Progress", 7),
    ("⛭", "Settings", 4),
]

PAGE_TITLES = {
    0: "Character",
    1: "Quests",
    2: "Log",
    3: "Journal",
    4: "Settings",
    5: "Quest Editor",
    6: "Activity",
    7: "Progress",
}


class DashboardWindow(QMainWindow):
    def __init__(self, assets_dir: str, parent=None):
        super().__init__(parent)
        self._assets = assets_dir
        self._nav_btns: list[QPushButton] = []
        self._btn_to_stack: list[int] = []  # btn index → stack index
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
        event_bus.quests_updated.connect(self._on_quests_updated_editor)
        event_bus.config_saved.connect(self._on_config_saved)
        QTimer(self, interval=30_000, timeout=self._auto_refresh).start()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        hl = QHBoxLayout(root)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        hl.addWidget(self._build_sidebar())

        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet(f"background: {C_RULE_GOLD};")
        hl.addWidget(div)

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
        self._quest_editor_tab = QuestEditorTab()
        self._activity_tab = ActivityTab()
        self._progress_tab = ProgressTab()
        for w in (
            self._char_tab,
            self._quest_tab,
            self._log_tab,
            self._journal_tab,
            self._settings_tab,
            self._quest_editor_tab,
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
        sb.setStyleSheet(f"background: {C_SIDEBAR};")
        vl = QVBoxLayout(sb)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # Logo block
        logo_w = QWidget()
        logo_w.setFixedHeight(72)
        logo_w.setStyleSheet(
            f"background: {C_SIDEBAR_DK}; border-bottom: 1px solid {C_SIDEBAR_HI};"
        )
        ll = QHBoxLayout(logo_w)
        ll.setContentsMargins(18, 0, 12, 0)
        icon = QLabel("⚔")
        icon.setFont(_cinzel(18))
        icon.setStyleSheet(f"color: {C_CRIMSON};")
        brand = QLabel("Chronicle\nForge")
        brand.setFont(_cinzel(10))
        brand.setStyleSheet(f"color: {C_GOLD_PALE}; line-height: 1.3;")
        ll.addWidget(icon)
        ll.addSpacing(8)
        ll.addWidget(brand)
        ll.addStretch()
        vl.addWidget(logo_w)

        # Avatar + name
        avatar_w = QWidget()
        avatar_w.setStyleSheet(f"background: {C_SIDEBAR_DK};")
        al = QVBoxLayout(avatar_w)
        al.setContentsMargins(0, 16, 0, 16)
        al.setSpacing(6)

        self._sidebar_avatar = QLabel()
        self._sidebar_avatar.setFixedSize(64, 64)
        self._sidebar_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sidebar_avatar.setStyleSheet(
            f"border: 2px solid {C_CRIMSON}; border-radius: 32px;"
            f"background: {C_SIDEBAR};"
        )
        self._load_avatar()

        self._sidebar_name = QLabel("Hero")
        self._sidebar_name.setFont(_serif(11, QFont.Weight.Bold))
        self._sidebar_name.setStyleSheet(f"color: {C_GOLD_PALE};")
        self._sidebar_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._sidebar_badge = QLabel("LV 1  WANDERER")
        self._sidebar_badge.setFont(_mono(8))
        self._sidebar_badge.setStyleSheet(
            f"color: {C_GOLD_DIM}; background: {C_SIDEBAR};"
            f"border: 1px solid {C_SIDEBAR_HI};"
            f"border-radius: 10px; padding: 3px 10px;"
        )
        self._sidebar_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        al.addWidget(self._sidebar_avatar, alignment=Qt.AlignmentFlag.AlignCenter)
        al.addWidget(self._sidebar_name)
        al.addWidget(self._sidebar_badge, alignment=Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(avatar_w)

        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet(f"background: {C_SIDEBAR_HI};")
        vl.addWidget(d)
        vl.addSpacing(8)

        # ── Build nav buttons from NAV_ITEMS ──────────────────────────────────
        # Top group: first 4 (Character, Quests, Log, Journal)
        for i, (icon_s, label, stack_idx) in enumerate(NAV_ITEMS[:4]):
            btn = QPushButton(f"  {icon_s}  {label}")
            btn.setFont(_serif(10))
            btn.clicked.connect(lambda _, si=stack_idx: self._switch(si))
            self._nav_btns.append(btn)
            self._btn_to_stack.append(stack_idx)
            vl.addWidget(btn)

        vl.addStretch()

        # Bottom group: Quest Editor, Activity, Progress
        for i, (icon_s, label, stack_idx) in enumerate(NAV_ITEMS[4:7]):
            btn = QPushButton(f"  {icon_s}  {label}")
            btn.setFont(_serif(10))
            btn.clicked.connect(lambda _, si=stack_idx: self._switch(si))
            self._nav_btns.append(btn)
            self._btn_to_stack.append(stack_idx)
            vl.addWidget(btn)

        # Divider before settings
        d2 = QFrame()
        d2.setFixedHeight(1)
        d2.setStyleSheet(f"background: {C_SIDEBAR_HI};")
        vl.addWidget(d2)

        # Settings
        icon_s, label, stack_idx = NAV_ITEMS[7]
        settings_btn = QPushButton(f"  {icon_s}  {label}")
        settings_btn.setFont(_serif(10))
        settings_btn.clicked.connect(lambda _, si=stack_idx: self._switch(si))
        self._nav_btns.append(settings_btn)
        self._btn_to_stack.append(stack_idx)
        vl.addWidget(settings_btn)

        self._apply_nav_for_stack(0)
        return sb

    def _build_topbar(self) -> QWidget:
        tb = QWidget()
        tb.setFixedHeight(48)
        tb.setStyleSheet(f"background: {C_TOPBAR}; border-bottom: 1px solid {C_RULE};")
        hl = QHBoxLayout(tb)
        hl.setContentsMargins(20, 0, 12, 0)

        self._topbar_title = QLabel("Character")
        self._topbar_title.setFont(_cinzel(12))
        self._topbar_title.setStyleSheet(f"color: {C_INK};")

        self._topbar_sub = QLabel("")
        self._topbar_sub.setFont(_mono(9))
        self._topbar_sub.setStyleSheet(f"color: {C_INK_DIM};")

        hl.addWidget(self._topbar_title)
        hl.addSpacing(12)
        hl.addWidget(self._topbar_sub)
        hl.addStretch()

        for sym, fn in [("—", self.showMinimized), ("✕", self.close)]:
            b = QPushButton(sym)
            b.setFixedSize(34, 30)
            b.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{C_INK_DIM};
                    border:none; font-size:14px; }}
                QPushButton:hover {{ color:{C_CRIMSON}; background:{C_SURFACE};
                    border-radius:4px; }}
            """)
            b.clicked.connect(fn)
            hl.addWidget(b)

        self._update_topbar_sub()
        return tb

    def _build_statusbar(self) -> QWidget:
        sb = QWidget()
        sb.setFixedHeight(22)
        sb.setStyleSheet(f"background: {C_SURFACE}; border-top: 1px solid {C_RULE};")
        hl = QHBoxLayout(sb)
        hl.setContentsMargins(20, 0, 20, 0)
        self._status_lbl = QLabel("Ready.")
        self._status_lbl.setStyleSheet(f"color:{C_INK_FAINT}; font-size:8px;")
        hl.addWidget(self._status_lbl)
        hl.addStretch()
        ver = QLabel("ChronicForge  v2")
        ver.setStyleSheet(f"color:{C_INK_FAINT}; font-size:8px;")
        hl.addWidget(ver)
        return sb

    # ── Navigation ────────────────────────────────────────────────────────────

    def _switch(self, stack_idx: int):
        """Switch to tab by STACK index (0-7)."""
        self._current = stack_idx
        self._stack.setCurrentIndex(stack_idx)
        self._apply_nav_for_stack(stack_idx)
        self._topbar_title.setText(PAGE_TITLES.get(stack_idx, ""))
        self._status_lbl.setText(PAGE_TITLES.get(stack_idx, ""))
        self._refresh_current()

    def _apply_nav_for_stack(self, stack_idx: int):
        """Highlight the nav button whose stack index matches."""
        for i, btn in enumerate(self._nav_btns):
            is_active = self._btn_to_stack[i] == stack_idx
            s = NAV_ACTIVE if is_active else NAV_INACTIVE
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
            self._quest_editor_tab.refresh()
        if idx == 6:
            self._activity_tab.refresh()
        if idx == 7:
            self._progress_tab.refresh()
        self._update_topbar_sub()
        self._update_sidebar()

    def _auto_refresh(self):
        self._update_topbar_sub()
        self._update_sidebar()
        if self._current in (0, 1, 5, 6, 7):
            self._refresh_current()

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

    def _on_quests_updated_editor(self):
        if self._current == 5:
            QTimer.singleShot(200, self._quest_editor_tab.refresh)

    def _on_stats_updated(self):
        self._update_sidebar()
        self._update_topbar_sub()
        QTimer.singleShot(300, self._refresh_current)

    def _on_config_saved(self):
        self._update_sidebar()
        self._status_lbl.setText("Settings saved.")
        QTimer.singleShot(3000, lambda: self._status_lbl.setText("Ready."))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.pos().y() < 48:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(self.pos() + e.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
