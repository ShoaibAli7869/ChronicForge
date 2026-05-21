"""
ChronicForge — Character Tab  (v6 — Illuminated Parchment)

Design language exactly matching the reference image:
  - Warm ecru/cream parchment ground (#e8e0cc)
  - Crimson + cobalt + amber accent triad
  - Humanist serif (IM Fell English / Palatino / Georgia fallback) for name
  - Pill-shaped filled wax seals (crimson, cobalt, brown, tan)
  - Thin crimson rules with diamond-dot ornament (· · ♦ · ·)
  - Double-ring oval portrait frame with cardinal crimson dots
  - Stat bars: per-stat color on tan track, no border-radius (flat ends)
  - XP bar: crimson fill, right-aligned level annotation
  - Radar: parchment bg, crimson semi-transparent polygon

All functionality preserved from v5; only palette, fonts, geometry changed.
"""

import os

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygon,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.game_logic import check_neglected_stats, get_character
from ui.widgets.radar_chart import RadarChart
from ui.widgets.stat_bar import StatBar, XPBar

# ── Illuminated Parchment Palette ─────────────────────────────────────────────
C_BG = "#e8e0cc"  # ecru — outer background
C_SURFACE = "#ddd5b5"  # parchment — elevated surfaces (radar bg, portrait)
C_TRACK = "#ccc4a0"  # aged tan — stat bar / XP tracks
C_RULE = "#c8b890"  # foxed — faint horizontal rules

C_CRIMSON = "#8b1a1a"  # crimson — primary accent, XP fill, dividers
C_CRIMSON_DIM = "#5a0e0e"  # deep crimson — portrait outer ring
C_CRIMSON_PALE = "#c84040"  # vermillion — lighter hit

C_COBALT = "#2a4a7a"  # cobalt blue — power seal, intellect bar
C_BROWN = "#6b3a10"  # warm brown — streak seal, charisma bar
C_TAN = "#9a7c3a"  # antique gold — seals text, misc

C_GOLD = "#c8820a"  # amber gold — hero name
C_GOLD_BRIGHT = "#d49010"  # warm gold bright

C_INK = "#3a2a18"  # dark ink — body text
C_INK_DIM = "#6b5030"  # muted ink — labels, title
C_INK_FAINT = "#a89060"  # faint ink — separators, faint labels

# Per-stat bar colours (matching the image exactly)
STAT_COLORS = {
    "strength": "#8b2020",  # deep crimson-red
    "intellect": "#1a3a6a",  # cobalt blue
    "charisma": "#8a6010",  # amber-gold
    "vitality": "#2a6a30",  # forest green
    "discipline": "#4a2a7a",  # deep purple
    "creativity": "#5a6820",  # olive green
    "wealth": "#1a5a6a",  # dark teal
}

STAT_ICONS = {
    "strength": ("⚔", "#8b2020"),
    "intellect": ("📜", "#1a3a6a"),
    "charisma": ("🎭", "#8a6010"),
    "vitality": ("🌿", "#2a6a30"),
    "discipline": ("🛡", "#4a2a7a"),
    "creativity": ("✒", "#5a6820"),
    "wealth": ("⚖", "#1a5a6a"),
}


# ── Font helpers ──────────────────────────────────────────────────────────────
def _serif(size: int, weight=QFont.Weight.Normal, italic=False) -> QFont:
    """IM Fell English → Palatino → Georgia — warm humanist serif."""
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
            return f
    return QFont("serif", size, weight)


def _mono(size: int, weight=QFont.Weight.Normal) -> QFont:
    for name in ("Share Tech Mono", "Courier New", "monospace"):
        f = QFont(name, size, weight)
        if f.exactMatch() or name == "monospace":
            return f
    return QFont("monospace", size, weight)


def _caps(size: int) -> QFont:
    """Small-caps feel: serif bold, slightly smaller."""
    f = _serif(size, QFont.Weight.Bold)
    return f


# ── Ornamental divider: ── ── · · ♦ · · ── ── ────────────────────────────────
class _Divider(QWidget):
    """
    Thin crimson rule with centred diamond and flanking dots.
    style: "primary" (crimson) or "secondary" (faint ink)
    """

    def __init__(self, style: str = "primary", parent=None):
        super().__init__(parent)
        self._primary = style == "primary"
        self.setFixedHeight(16)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        col = QColor(C_CRIMSON if self._primary else C_INK_FAINT)
        dim = QColor(C_CRIMSON_DIM if self._primary else C_RULE)

        mid = self.height() // 2
        w = self.width()
        cx = w // 2

        # Main lines — split around centre cluster
        gap = 26
        p.setPen(QPen(col, 1))
        p.drawLine(0, mid, cx - gap, mid)
        p.drawLine(cx + gap, mid, w, mid)

        # Flanking small dots
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col))
        for dx in (-gap + 8, gap - 8):
            p.drawEllipse(QPoint(cx + dx, mid), 2, 2)

        # Centre diamond
        sz = 4
        p.setBrush(QBrush(col if self._primary else QColor(C_INK_FAINT)))
        p.drawPolygon(
            QPolygon(
                [
                    QPoint(cx, mid - sz),
                    QPoint(cx + sz, mid),
                    QPoint(cx, mid + sz),
                    QPoint(cx - sz, mid),
                ]
            )
        )

        p.end()


# ── Single stat row ───────────────────────────────────────────────────────────
class _StatRow(QWidget):
    """
    Ledger row:  [icon]  STAT NAME   [████████░░░░░░░░]
    Flat stat bar on parchment track, per-stat colour fill.
    """

    def __init__(self, stat: str, parent=None):
        super().__init__(parent)
        self._stat = stat
        icon_s, _ = STAT_ICONS.get(stat, ("·", C_CRIMSON))
        col = STAT_COLORS.get(stat, C_CRIMSON)
        self._bar = None

        hl = QHBoxLayout(self)
        hl.setContentsMargins(0, 4, 0, 4)
        hl.setSpacing(8)

        icon = QLabel(icon_s)
        icon.setFixedWidth(20)
        icon.setFont(_mono(11))
        icon.setStyleSheet(f"color:{col}; background:transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name = QLabel(stat.upper())
        name.setFixedWidth(80)
        name.setFont(_mono(7, QFont.Weight.Bold))
        name.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:2px;"
        )

        self._bar = StatBar(stat)
        self._bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        # Parchment track, flat ends, per-stat colour fill
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C_TRACK};
                border: none;
                border-radius: 0px;
                max-height: 7px;
                min-height: 7px;
            }}
            QProgressBar::chunk {{
                background: {col};
                border-radius: 0px;
            }}
        """)

        self._neglect_label = QLabel("⚠")
        self._neglect_label.setFont(QFont("monospace", 10, QFont.Weight.Bold))
        self._neglect_label.setStyleSheet(
            "color:#cc2020; background:transparent;"
        )
        self._neglect_label.setToolTip(f"{stat.upper()} has not been trained in 7+ days!")
        self._neglect_label.setFixedWidth(16)
        self._neglect_label.hide()

        hl.addWidget(icon)
        hl.addWidget(name)
        hl.addWidget(self._bar, stretch=1)
        hl.addWidget(self._neglect_label)

    def set_value(self, v: float):
        if self._bar:
            self._bar.set_value(v)

    def set_neglected(self, is_neglected: bool) -> None:
        """Show or hide the neglect warning badge."""
        self._neglect_label.setVisible(is_neglected)


# ── Portrait: double-ring oval with cardinal dots ─────────────────────────────
class _PortraitFrame(QWidget):
    """
    Oval portrait clipped to circle, double-ring border in dark brown/crimson,
    four cardinal red dots — matches reference image exactly.
    Falls back to 'CF' glyph in serif if no image found.
    """

    SIZE = 88

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._pixmap: QPixmap | None = None

    def set_pixmap(self, px: QPixmap):
        self._pixmap = px
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        S = self.SIZE
        cx = cy = S // 2

        # ── Parchment fill circle ─────────────────────────────────────────
        path = QPainterPath()
        path.addEllipse(QRectF(4, 4, S - 8, S - 8))
        p.setClipPath(path)
        p.fillRect(0, 0, S, S, QColor(C_SURFACE))

        if self._pixmap:
            p.drawPixmap(
                4,
                4,
                self._pixmap.scaled(
                    S - 8,
                    S - 8,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )
        else:
            # Glyph fallback — crossed-swords motif in crimson
            p.setPen(QColor(C_CRIMSON))
            p.setFont(_serif(26, QFont.Weight.Bold))
            p.drawText(QRect(0, 0, S, S), Qt.AlignmentFlag.AlignCenter, "⚔")

        p.setClipping(False)

        # ── Outer thick ring (dark brown) ─────────────────────────────────
        p.setPen(QPen(QColor(C_CRIMSON_DIM), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPoint(cx, cy), cx - 2, cy - 2)

        # ── Inner thin ring (crimson) ─────────────────────────────────────
        p.setPen(QPen(QColor(C_CRIMSON), 1))
        p.drawEllipse(QPoint(cx, cy), cx - 7, cy - 7)

        # ── Cardinal dots (crimson filled) ────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(C_CRIMSON)))
        r = cx - 2  # on the outer ring radius
        for ox, oy in (
            (cx, cy - r),  # top
            (cx, cy + r),  # bottom
            (cx - r, cy),  # left
            (cx + r, cy),  # right
        ):
            p.drawEllipse(QPoint(ox, oy), 4, 4)

        p.end()


# ── Pill seal (filled, rounded-rect) ─────────────────────────────────────────
class _Seal(QWidget):
    """
    Filled pill-shaped badge matching the image:
    RANGER=crimson, PWR=cobalt, STREAK=brown, SEALS=tan.
    """

    def __init__(self, text: str, fg: str, bg: str, parent=None):
        super().__init__(parent)
        self._text = text
        self._fg = QColor(fg)
        self._bg = QColor(bg)
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def setText(self, t: str):
        self._text = t
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._text

    def sizeHint(self):
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self._text)
        return self.minimumSizeHint().__class__(tw + 28, 24)

    def minimumSizeHint(self):
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self._text)
        from PySide6.QtCore import QSize

        return QSize(tw + 28, 24)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h // 2

        # Fill pill
        p.setBrush(QBrush(self._bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        # Text
        p.setPen(self._fg)
        p.setFont(_mono(8, QFont.Weight.Bold))
        p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()


# ── Character Tab ─────────────────────────────────────────────────────────────
class CharacterTab(QWidget):
    def __init__(self, assets_dir: str, parent=None):
        super().__init__(parent)
        self._assets = assets_dir
        self._stat_rows: dict[str, _StatRow] = {}
        self._editing_name = False
        self._build()
        self.refresh()

    # ─────────────────────────────────────────────────────────────────────────
    def _build(self):
        self.setStyleSheet(f"background:{C_BG};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:{C_BG}; border:none; }}
            QScrollBar:vertical {{
                background:{C_SURFACE}; width:7px; border:none;
            }}
            QScrollBar::handle:vertical {{
                background:{C_INK_FAINT}; border-radius:3px; min-height:20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height:0;
            }}
        """)

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 16, 28, 16)
        root.setSpacing(0)

        # ── Top crimson rule ──────────────────────────────────────────────────
        root.addWidget(_Divider("primary"))
        root.addSpacing(12)

        # ── Grand banner ──────────────────────────────────────────────────────
        banner_row = QHBoxLayout()
        banner_row.setSpacing(20)

        self._portrait = _PortraitFrame()
        self._load_portrait()
        banner_row.addWidget(self._portrait, alignment=Qt.AlignmentFlag.AlignTop)

        id_col = QVBoxLayout()
        id_col.setSpacing(3)

        # Hero name — warm amber gold serif, double-click to edit
        self._name_lbl = QLabel("Hero")
        self._name_lbl.setFont(_serif(24, QFont.Weight.Bold))
        self._name_lbl.setStyleSheet(f"color:{C_GOLD}; background:transparent;")
        self._name_lbl.setToolTip("Double-click to rename your hero")
        self._name_lbl.mouseDoubleClickEvent = lambda _: self._start_name_edit()

        self._name_edit = QLineEdit()
        self._name_edit.setFont(_serif(22, QFont.Weight.Bold))
        self._name_edit.setStyleSheet(f"""
            QLineEdit {{
                color:{C_GOLD}; background:transparent;
                border:none; border-bottom:1px solid {C_CRIMSON};
                padding:0;
            }}
        """)
        self._name_edit.hide()
        self._name_edit.returnPressed.connect(self._finish_name_edit)
        self._name_edit.editingFinished.connect(self._finish_name_edit)

        # Subtitle/title — italic muted brown
        self._title_lbl = QLabel("The Wanderer")
        self._title_lbl.setFont(_serif(10, italic=True))
        self._title_lbl.setStyleSheet(f"color:{C_INK_DIM}; background:transparent;")

        # Seals — filled pills: RANGER/crimson, PWR/cobalt, STREAK/brown, SEALS/tan
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)

        self._class_seal = _Seal("WANDERER", "#f0e8d8", C_CRIMSON)
        self._power_seal = _Seal("PWR 0", "#c8dff8", C_COBALT)
        self._streak_seal = _Seal("STREAK 0d", "#f8dfc0", C_BROWN)
        self._ach_seal = _Seal("0 SEALS", "#f0e8d0", C_TAN)

        for s in (
            self._class_seal,
            self._power_seal,
            self._streak_seal,
            self._ach_seal,
        ):
            badge_row.addWidget(s)
        badge_row.addStretch()

        id_col.addWidget(self._name_lbl)
        id_col.addWidget(self._name_edit)
        id_col.addWidget(self._title_lbl)
        id_col.addSpacing(8)
        id_col.addLayout(badge_row)

        banner_row.addLayout(id_col, stretch=1)
        root.addLayout(banner_row)

        root.addSpacing(14)
        root.addWidget(_Divider("primary"))
        root.addSpacing(6)

        # ── XP bar ───────────────────────────────────────────────────────────
        xp_row = QHBoxLayout()

        xp_lbl = QLabel("XP")
        xp_lbl.setFont(_mono(7, QFont.Weight.Bold))
        xp_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:3px;"
        )
        xp_lbl.setFixedWidth(22)

        self._xp_bar = XPBar()
        self._xp_bar.setStyleSheet(f"""
            QProgressBar {{
                background:{C_TRACK};
                border:none;
                border-radius:0px;
                max-height:10px;
                min-height:10px;
            }}
            QProgressBar::chunk {{
                background:{C_CRIMSON};
                border-radius:0px;
            }}
        """)

        # Right-side level annotation (matches "LVL 6 · 640/1000" in image)
        self._xp_meta = QLabel("LVL 1 · 0/100")
        self._xp_meta.setFont(_mono(7))
        self._xp_meta.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:1px;"
        )

        xp_row.addWidget(xp_lbl)
        xp_row.addWidget(self._xp_bar, stretch=1)
        xp_row.addSpacing(8)
        xp_row.addWidget(self._xp_meta)
        root.addLayout(xp_row)

        root.addSpacing(10)
        root.addWidget(_Divider("secondary"))
        root.addSpacing(12)

        # ── Bottom split: stat ledger (left) + radar (right) ──────────────────
        split = QHBoxLayout()
        split.setSpacing(28)

        # ── Left: attribute ledger ────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(0)

        stats_hdr = QLabel("ATTRIBUTES")
        stats_hdr.setFont(_mono(7, QFont.Weight.Bold))
        stats_hdr.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px; padding-bottom:6px;"
        )
        left.addWidget(stats_hdr)
        left.addWidget(_Divider("secondary"))

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

        # ── Right: radar panel ────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(0)

        radar_hdr = QLabel("STAT OVERVIEW")
        radar_hdr.setFont(_mono(7, QFont.Weight.Bold))
        radar_hdr.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px; padding-bottom:6px;"
        )
        right.addWidget(radar_hdr)
        right.addWidget(_Divider("secondary"))
        right.addSpacing(8)

        self._radar = RadarChart()
        self._radar.setMinimumHeight(240)
        self._radar.setStyleSheet(f"background:{C_SURFACE}; border:1px solid {C_RULE};")
        right.addWidget(self._radar, stretch=1)

        split.addLayout(right, stretch=2)
        root.addLayout(split)
        root.addStretch()

        # ── Bottom crimson rule ───────────────────────────────────────────────
        root.addSpacing(12)
        root.addWidget(_Divider("primary"))

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ─────────────────────────────────────────────────────────────────────────
    def _load_portrait(self):
        path = os.path.join(self._assets, "male_hero-design.png")
        if os.path.exists(path):
            px = QPixmap(path).scaled(
                _PortraitFrame.SIZE,
                _PortraitFrame.SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._portrait.set_pixmap(px)

    def _start_name_edit(self):
        self._name_edit.setText(self._name_lbl.text())
        self._name_lbl.hide()
        self._name_edit.show()
        self._name_edit.selectAll()
        self._name_edit.setFocus()
        self._editing_name = True

    def _finish_name_edit(self):
        if not self._editing_name:
            return
        self._editing_name = False
        name = self._name_edit.text().strip() or self._name_lbl.text()
        self._name_lbl.setText(name)
        self._name_edit.hide()
        self._name_lbl.show()
        try:
            from core.game_logic import set_character_name

            set_character_name(name)
            from utils.signals import event_bus

            event_bus.stats_updated.emit()
        except Exception as e:
            print(f"[ChronicForge] Name save failed: {e}")

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
        level = char.get("level", 1)
        xp_cur = xp % max(xp_next, 1)
        self._xp_bar.set_xp(level, xp_cur, xp_next)
        self._xp_meta.setText(f"LVL {level} · {xp_cur}/{xp_next}")

        stats = char.get("stats", {})
        max_val = max(max(stats.values(), default=10.0), 100.0)
        self._radar.set_stats(stats, max_val)

        try:
            neglected = set(check_neglected_stats())
        except Exception:
            neglected = set()

        for stat, row in self._stat_rows.items():
            row.set_value(stats.get(stat, 10.0))
            row.set_neglected(stat in neglected)
