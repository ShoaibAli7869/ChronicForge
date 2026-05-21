"""
ChronicForge — Shared Theme Module  (v6 — Illuminated Parchment)

Palette, font helpers, common widgets, and global stylesheet.
Matches the reference image: warm ecru ground, crimson + cobalt + amber
accent triad, humanist serif display, pill seals, flat stat bars.
"""

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygon,
)
from PySide6.QtWidgets import QFrame, QLabel, QWidget

# ── Illuminated Parchment Palette ─────────────────────────────────────────────
C_BG = "#e8e0cc"  # ecru — main content ground
C_SIDEBAR = "#2a1f12"  # walnut — sidebar (unchanged dark-mode sidebar)
C_SIDEBAR_HI = "#3a2e1e"  # walnut lighter — hover / active bg
C_SIDEBAR_DK = "#1e160c"  # walnut darkest — logo block
C_SURFACE = "#ddd5b5"  # parchment — elevated surfaces
C_RULE = "#c0b488"  # aged — light rules / separators
C_RULE_GOLD = "#a89060"  # foxed — dividers / prominent borders
C_TOPBAR = "#e8e0cc"  # vellum — topbar matches content

# Accent triad
C_CRIMSON = "#8b1a1a"  # crimson — primary accent (XP, dividers, portrait)
C_CRIMSON_DIM = "#5a0e0e"  # deep crimson — outer portrait ring
C_COBALT = "#2a4a7a"  # cobalt blue — power / intellect
C_BROWN = "#6b3a10"  # warm brown — streak / charisma
C_TAN = "#9a7c3a"  # antique gold — achievements seal

# Gold / ink hierarchy
C_GOLD = "#c8820a"  # amber gold — hero name
C_GOLD_DIM = "#a06808"  # gold dim — sub-labels / badge borders
C_GOLD_BRIGHT = "#d49010"  # gold bright — highlights
C_GOLD_PALE = "#f0e8d8"  # pale gold — seal text on crimson bg

C_INK = "#3a2a18"  # dark ink — primary text
C_INK_MID = "#6b5030"  # ink mid — secondary labels / title
C_INK_DIM = "#8a7050"  # ink dim — muted / placeholder
C_INK_FAINT = "#a89060"  # ink faint — dividers / inactive

# Semantic / legacy aliases so other tabs that import these keep working
C_VERMILLION = C_CRIMSON  # alias — was vermillion, now crimson
C_VERM_DIM = C_CRIMSON_DIM  # alias
C_VERM_BRIGHT = "#c84040"  # slightly lighter crimson for hit states
C_GREEN = "#2a6a30"  # verdigris — success / vitality
C_RED = C_CRIMSON  # error — same crimson
C_PLUM = "#4a2860"  # plum — discipline
C_COBALT = C_COBALT  # already defined above

# Stat bar fill colours (each stat has its own ink tone)
STAT_COLORS = {
    "strength": "#8b2020",  # deep crimson-red
    "intellect": "#1a3a6a",  # cobalt blue
    "charisma": "#8a6010",  # amber-gold
    "vitality": "#2a6a30",  # forest green
    "discipline": "#4a2a7a",  # deep purple
    "creativity": "#5a6820",  # olive green
    "wealth": "#1a5a6a",  # dark teal
}

# Two-letter codes for tight spaces (unchanged interface)
STAT_CODES = {
    "strength": "ST",
    "intellect": "IN",
    "charisma": "CH",
    "vitality": "VI",
    "discipline": "DI",
    "creativity": "CR",
    "wealth": "WE",
}

# Legacy icon tuples (ui/icons.py may still read these)
STAT_ICONS = {k: (STAT_CODES[k], STAT_COLORS[k]) for k in STAT_CODES}


# ── Font helpers ──────────────────────────────────────────────────────────────
def font_cinzel(size: int, weight=QFont.Weight.Bold) -> QFont:
    """Cinzel — scribe capitals for section headers."""
    f = QFont("Cinzel", size, weight)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


def font_mono(size: int, weight=QFont.Weight.Normal) -> QFont:
    """Caudex — medieval manuscript ledger style for stats and labels."""
    for name in ("Caudex", "Ubuntu Mono", "monospace"):
        f = QFont(name, size, weight)
        f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        # Some loaded fonts report exactMatch=False even when available;
        # trust the family name instead.
        if name in f.family() or name == "monospace":
            return f
    return QFont("monospace", size, weight)


def font_serif(size: int, weight=QFont.Weight.Normal, italic=False) -> QFont:
    """IM FELL English — authentic 17th-century manuscript body text."""
    for name in (
        "IM FELL English",
        "Palatino Linotype",
        "Palatino",
        "Georgia",
        "serif",
    ):
        f = QFont(name, size, weight)
        f.setItalic(italic)
        f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        # Loaded fonts may report exactMatch=False; trust family name.
        if name in f.family() or name == "serif":
            return f
    return QFont("serif", size, weight)


def font_blackletter(size: int, weight=QFont.Weight.Normal) -> QFont:
    """UnifrakturMaguntia — gothic blackletter for decorative accents."""
    f = QFont("UnifrakturMaguntia", size, weight)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


def font_prompt(size: int) -> QFont:
    """IM FELL English Italic — for daily prompts and quoted text."""
    return font_serif(size, QFont.Weight.Normal, italic=True)


# ── Ornamental Divider ────────────────────────────────────────────────────────
class Divider(QWidget):
    """
    Manuscript rule: thin line, flanking dots, centred lozenge diamond.

    variant="primary"   → crimson line + bright diamond  (major sections)
    variant="secondary" → foxed/faint line + dim diamond  (sub-sections)
    color=<hex>         → override both line and diamond colour
    """

    def __init__(self, variant: str = "secondary", color: str = None, parent=None):
        super().__init__(parent)
        self._variant = variant
        self._override = color
        self.setFixedHeight(16)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._override:
            line_col = QColor(self._override)
            gem_col = QColor(self._override)
        elif self._variant == "primary":
            line_col = QColor(C_CRIMSON)
            gem_col = QColor(C_CRIMSON)
        else:
            line_col = QColor(C_RULE_GOLD)
            gem_col = QColor(C_INK_FAINT)

        mid = self.height() // 2
        w = self.width()
        cx = w // 2
        gap = 26  # half-width of the centre cluster

        # Main rule lines
        p.setPen(QPen(line_col, 1))
        p.drawLine(0, mid, cx - gap, mid)
        p.drawLine(cx + gap, mid, w, mid)

        # Subtle shadow line (offset +2px, 35% opacity)
        shadow = QColor(line_col)
        shadow.setAlphaF(0.25)
        p.setPen(QPen(shadow, 1))
        p.drawLine(0, mid + 2, cx - gap + 2, mid + 2)
        p.drawLine(cx + gap - 2, mid + 2, w, mid + 2)

        # Flanking small dots
        p.setPen(Qt.PenStyle.NoPen)
        dot_col = QColor(gem_col)
        dot_col.setAlphaF(0.65)
        p.setBrush(QBrush(dot_col))
        for dx in (gap - 9, gap - 14):
            p.drawEllipse(QPoint(cx - dx, mid), 2, 2)
            p.drawEllipse(QPoint(cx + dx, mid), 2, 2)

        # Centre lozenge diamond
        sz = 4
        p.setBrush(QBrush(gem_col))
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


# ── Thin horizontal rule ──────────────────────────────────────────────────────
def make_rule(color: str = C_RULE, height: int = 1) -> QFrame:
    """Simple 1px horizontal rule."""
    f = QFrame()
    f.setFixedHeight(height)
    f.setStyleSheet(f"background:{color}; border:none;")
    return f


# ── Section header label ──────────────────────────────────────────────────────
def make_section_header(text: str, color: str = C_INK_FAINT) -> QLabel:
    """Small spaced-caps section header (Cinzel)."""
    lbl = QLabel(text)
    lbl.setFont(font_cinzel(7, QFont.Weight.Bold))
    lbl.setStyleSheet(f"color:{color}; background:transparent; letter-spacing:4px;")
    return lbl


# ── Global stylesheet ─────────────────────────────────────────────────────────
GLOBAL_STYLE = f"""
* {{ font-family: 'Caudex', 'Ubuntu Mono', monospace; }}
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
    background: {C_SURFACE};
    color: {C_INK};
    border: 1px solid {C_RULE_GOLD};
    font-size: 10px;
    padding: 5px 8px;
}}

QLineEdit, QTextEdit {{
    background: {C_SURFACE};
    color: {C_INK};
    border: none;
    border-bottom: 1px solid {C_RULE_GOLD};
    padding: 6px 10px;
    font-size: 11px;
    selection-background-color: {C_RULE};
}}
QLineEdit:focus, QTextEdit:focus {{
    border-bottom-color: {C_CRIMSON};
    background: {C_BG};
}}

QComboBox {{
    background: {C_SURFACE};
    color: {C_INK_MID};
    border: 1px solid {C_RULE_GOLD};
    border-radius: 0px;
    padding: 6px 12px;
    font-size: 10px;
}}
QComboBox QAbstractItemView {{
    background: {C_SURFACE};
    color: {C_INK_MID};
    border: 1px solid {C_RULE_GOLD};
    selection-background-color: {C_RULE};
}}
"""
