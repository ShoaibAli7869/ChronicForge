"""
ChronicForge — Character Tab  (v3 — Medieval Codex)

Design language:
  - Hero banner: name as the dominant element, badges as seals beneath
  - Stat ledger: ruled rows with icon, name, filled bar, numeric value
  - Radar: right-aligned, contained in a parchment frame with ornament header
  - XP bar: full-width, milestone markers, no decorative clutter
  - All dividers match quest tab ornamental style for cross-tab consistency
"""

import os

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.game_logic import get_character
from ui.widgets.radar_chart import RadarChart
from ui.widgets.stat_bar import StatBar, XPBar

# ── Palette (matches quest tab) ───────────────────────────────────────────────
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

STAT_ICONS = {
    "strength": ("⚔", "#c84040"),
    "intellect": ("📜", "#4080d0"),
    "charisma": ("🎭", "#c07820"),
    "vitality": ("🌿", "#30a060"),
    "discipline": ("🛡", "#8050b0"),
    "creativity": ("✒", "#a0a020"),
    "wealth": ("⚖", "#30a0a0"),
}


# ── Shared ornamental divider (same as quest tab) ─────────────────────────────
class _Divider(QWidget):
    def __init__(self, color: str = C_RULE_GOLD, parent=None):
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
        p.setPen(QPen(self._color, 1))
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


# ── Single stat row ───────────────────────────────────────────────────────────
class _StatRow(QWidget):
    """
    Ledger row:  [icon]  STAT NAME      [████████░░░░░░░░]  42.3
    """

    def __init__(self, stat: str, parent=None):
        super().__init__(parent)
        self._stat = stat
        icon_s, col = STAT_ICONS.get(stat, ("·", C_GOLD))
        self._bar = None
        self._val_lbl = None

        hl = QHBoxLayout(self)
        hl.setContentsMargins(0, 5, 0, 5)
        hl.setSpacing(10)

        icon = QLabel(icon_s)
        icon.setFixedWidth(18)
        icon.setFont(QFont("monospace", 11))
        icon.setStyleSheet(f"color:{col}; background:transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name = QLabel(stat.upper())
        name.setFixedWidth(80)
        name.setFont(QFont("monospace", 8, QFont.Weight.Bold))
        name.setStyleSheet(
            f"color:{C_INK_DIM}; background:transparent; letter-spacing:2px;"
        )

        self._bar = StatBar(stat)
        self._bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        hl.addWidget(icon)
        hl.addWidget(name)
        hl.addWidget(self._bar, stretch=1)

    def set_value(self, v: float):
        if self._bar:
            self._bar.set_value(v)


# ── Character Tab ─────────────────────────────────────────────────────────────
class CharacterTab(QWidget):
    def __init__(self, assets_dir: str, parent=None):
        super().__init__(parent)
        self._assets = assets_dir
        self._stat_rows: dict[str, _StatRow] = {}
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
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(0)

        # ── Grand banner: name + title + seals ───────────────────────────────
        root.addWidget(_Divider(C_GOLD))
        root.addSpacing(10)

        banner_row = QHBoxLayout()
        banner_row.setSpacing(20)

        # Portrait seal
        self._portrait = QLabel()
        self._portrait.setFixedSize(88, 88)
        self._portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._portrait.setStyleSheet(
            f"border:2px solid {C_RULE_GOLD}; background:{C_SURFACE};"
        )
        self._load_portrait()
        banner_row.addWidget(self._portrait)

        # Identity column
        id_col = QVBoxLayout()
        id_col.setSpacing(4)

        self._name_lbl = QLabel("Hero")
        self._name_lbl.setFont(QFont("monospace", 26, QFont.Weight.Bold))
        self._name_lbl.setStyleSheet(
            f"color:{C_GOLD_BRIGHT}; background:transparent; letter-spacing:2px;"
        )

        self._title_lbl = QLabel("The Wanderer")
        self._title_lbl.setFont(QFont("monospace", 10))
        self._title_lbl.setStyleSheet(
            f"color:{C_INK_DIM}; background:transparent; font-style:italic;"
        )

        # Badge row — styled as wax seals / manuscript stamps
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)

        def _seal(text: str, col: str) -> QLabel:
            l = QLabel(text)
            l.setFont(QFont("monospace", 8, QFont.Weight.Bold))
            l.setStyleSheet(
                f"color:{col}; background:{C_SURFACE}; border:1px solid {C_RULE_GOLD};"
                f"padding:3px 10px; letter-spacing:1px;"
            )
            return l

        self._class_seal = _seal("WANDERER", C_GOLD)
        self._power_seal = _seal("PWR 0", "#4090b0")
        self._streak_seal = _seal("STREAK 0d", "#b06030")
        self._ach_seal = _seal("0 SEALS", C_INK_DIM)

        for s in (
            self._class_seal,
            self._power_seal,
            self._streak_seal,
            self._ach_seal,
        ):
            badge_row.addWidget(s)
        badge_row.addStretch()

        id_col.addWidget(self._name_lbl)
        id_col.addWidget(self._title_lbl)
        id_col.addLayout(badge_row)
        banner_row.addLayout(id_col, stretch=1)
        root.addLayout(banner_row)

        root.addSpacing(12)
        root.addWidget(_Divider(C_RULE_GOLD))
        root.addSpacing(6)

        # ── XP bar (full width) ───────────────────────────────────────────────
        xp_row = QHBoxLayout()
        xp_lbl = QLabel("XP")
        xp_lbl.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        xp_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:3px;"
        )
        xp_lbl.setFixedWidth(24)
        self._xp_bar = XPBar()
        xp_row.addWidget(xp_lbl)
        xp_row.addWidget(self._xp_bar, stretch=1)
        root.addLayout(xp_row)

        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(10)

        # ── Bottom split: stat ledger + radar ─────────────────────────────────
        split = QHBoxLayout()
        split.setSpacing(28)

        # Left: stat ledger
        left = QVBoxLayout()
        left.setSpacing(0)

        stats_hdr = QLabel("ATTRIBUTES")
        stats_hdr.setFont(QFont("monospace", 8, QFont.Weight.Bold))
        stats_hdr.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; "
            f"letter-spacing:4px; padding-bottom:6px;"
        )
        left.addWidget(stats_hdr)
        left.addWidget(_Divider(C_RULE))

        for stat in [
            "strength",
            "intellect",
            "charisma",
            "vitality",
            "discipline",
            "creativity",
            "wealth",
        ]:
            row = _StatRow(stat)
            self._stat_rows[stat] = row
            left.addWidget(row)

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{C_RULE}; border:none;")
            left.addWidget(sep)

        split.addLayout(left, stretch=3)

        # Right: radar chart in parchment frame
        right = QVBoxLayout()
        right.setSpacing(0)

        radar_hdr = QLabel("STAT OVERVIEW")
        radar_hdr.setFont(QFont("monospace", 8, QFont.Weight.Bold))
        radar_hdr.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; "
            f"letter-spacing:4px; padding-bottom:6px;"
        )
        right.addWidget(radar_hdr)
        right.addWidget(_Divider(C_RULE))
        right.addSpacing(8)

        self._radar = RadarChart()
        self._radar.setMinimumHeight(260)
        right.addWidget(self._radar, stretch=1)

        split.addLayout(right, stretch=2)
        root.addLayout(split)
        root.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _load_portrait(self):
        path = os.path.join(self._assets, "male_hero-design.png")
        if os.path.exists(path):
            px = QPixmap(path).scaled(
                84,
                84,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self._portrait.setPixmap(px)
        else:
            self._portrait.setText("⚔")
            self._portrait.setFont(QFont("monospace", 36))
            self._portrait.setStyleSheet(f"color:{C_GOLD};")

    def refresh(self):
        char = get_character()
        if not char:
            return

        self._name_lbl.setText(char.get("name", "Hero"))
        self._title_lbl.setText(char.get("title", "The Wanderer"))
        self._class_seal.setText(char.get("class", "Wanderer").upper()[:14])
        self._power_seal.setText(f"PWR {char.get('total_power', 0):.0f}")
        self._streak_seal.setText(f"STREAK {char.get('streak', 0)}d")
        self._ach_seal.setText(f"{char.get('achievements', 0)} SEALS")

        xp = char.get("xp", 0)
        xp_next = char.get("xp_to_next", 100)
        self._xp_bar.set_xp(char.get("level", 1), xp % max(xp_next, 1), xp_next)

        stats = char.get("stats", {})
        max_val = max(max(stats.values(), default=10.0), 100.0)
        self._radar.set_stats(stats, max_val)
        for stat, row in self._stat_rows.items():
            row.set_value(stats.get(stat, 10.0))
