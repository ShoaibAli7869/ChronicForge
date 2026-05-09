"""
ChronicForge — Journal Tab  (v3 — Medieval Codex)

Design:
  - Left: Chronicle of Shame & Glory — roast ledger with source rune
  - Right: Achievement seals — unlocked as gilded crests, locked as redacted
  - All ruled, all flat, all parchment-dark
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.database import Character, SessionFactory
from core.game_logic import ACHIEVEMENT_DEFS
from core.roast_engine import get_roast_journal

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
C_RED = "#a03020"
C_GREEN = "#306020"
C_PURPLE = "#503080"

TYPE_ACCENT = {
    "roast": ("#a03020", "·"),
    "praise": ("#306020", "✦"),
    "neutral": ("#4a3010", "·"),
}
SOURCE_LABELS = {
    "groq": "GROQ",
    "template": "SOLDIER BOY",
}


class _Divider(QWidget):
    def __init__(self, color=C_RULE_GOLD, parent=None):
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


class JournalTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet(f"background:{C_BG};")
        root = QHBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 16)
        root.setSpacing(28)

        # ── Left: Chronicle ────────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(0)

        jh = QLabel("CHRONICLE OF SHAME & GLORY")
        jh.setFont(QFont("monospace", 8, QFont.Weight.Bold))
        jh.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px;"
        )
        left.addWidget(jh)
        left.addSpacing(4)
        left.addWidget(_Divider(C_GOLD))
        left.addSpacing(4)

        # Column header row
        col_hdr = QHBoxLayout()
        col_hdr.setContentsMargins(0, 2, 0, 6)
        col_hdr.setSpacing(8)
        for txt, w in [("", 14), ("ENTRY", 0), ("SOURCE", 70), ("DATE", 90)]:
            l = QLabel(txt)
            l.setFont(QFont("monospace", 7, QFont.Weight.Bold))
            l.setStyleSheet(
                f"color:{C_INK_FAINT}; background:transparent; letter-spacing:2px;"
            )
            if w:
                l.setFixedWidth(w)
            else:
                l.setSizePolicy(
                    __import__(
                        "PySide6.QtWidgets", fromlist=["QSizePolicy"]
                    ).QSizePolicy.Policy.Expanding,
                    __import__(
                        "PySide6.QtWidgets", fromlist=["QSizePolicy"]
                    ).QSizePolicy.Policy.Preferred,
                )
            if txt in ("SOURCE", "DATE"):
                l.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            col_hdr.addWidget(l)
        left.addLayout(col_hdr)
        left.addWidget(
            QFrame(
                frameShape=QFrame.Shape.HLine,
                styleSheet=f"background:{C_RULE}; border:none;",
            )
        )

        j_scroll = QScrollArea()
        j_scroll.setWidgetResizable(True)
        j_scroll.setFrameShape(QFrame.Shape.NoFrame)
        j_scroll.setStyleSheet("background:transparent; border:none;")
        self._journal_inner = QWidget()
        self._journal_inner.setStyleSheet("background:transparent;")
        self._jl = QVBoxLayout(self._journal_inner)
        self._jl.setContentsMargins(0, 0, 4, 0)
        self._jl.setSpacing(0)
        self._jl.addStretch()
        j_scroll.setWidget(self._journal_inner)
        left.addWidget(j_scroll, stretch=1)
        root.addLayout(left, stretch=3)

        # ── Right: Achievements ────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(0)

        ah = QLabel("SEALS OF ACHIEVEMENT")
        ah.setFont(QFont("monospace", 8, QFont.Weight.Bold))
        ah.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px;"
        )
        right.addWidget(ah)
        right.addSpacing(4)
        right.addWidget(_Divider(C_GOLD))
        right.addSpacing(6)

        a_scroll = QScrollArea()
        a_scroll.setWidgetResizable(True)
        a_scroll.setFrameShape(QFrame.Shape.NoFrame)
        a_scroll.setStyleSheet("background:transparent; border:none;")
        self._ach_inner = QWidget()
        self._ach_inner.setStyleSheet("background:transparent;")
        self._al = QGridLayout(self._ach_inner)
        self._al.setContentsMargins(0, 0, 0, 0)
        self._al.setSpacing(6)
        a_scroll.setWidget(self._ach_inner)
        right.addWidget(a_scroll, stretch=1)
        root.addLayout(right, stretch=2)

    def refresh(self):
        self._load_journal()
        self._load_achievements()

    def _load_journal(self):
        while self._jl.count() > 1:
            item = self._jl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = get_roast_journal(limit=60)
        if not entries:
            e = QLabel("The chronicle is silent.\nSpeak thy deeds.")
            e.setStyleSheet(
                f"color:{C_INK_FAINT}; font-family:monospace; font-size:9px;"
            )
            e.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._jl.insertWidget(0, e)
            return

        for i, entry in enumerate(entries):
            t_col, t_glyph = TYPE_ACCENT.get(entry["type"], TYPE_ACCENT["neutral"])
            src_label = SOURCE_LABELS.get(entry["source"], entry["source"])

            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            hl = QHBoxLayout(row_w)
            hl.setContentsMargins(0, 7, 0, 7)
            hl.setSpacing(8)

            glyph = QLabel(t_glyph)
            glyph.setFixedWidth(14)
            glyph.setFont(QFont("monospace", 10))
            glyph.setStyleSheet(f"color:{t_col}; background:transparent;")
            glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Quote text
            text_lbl = QLabel(f'"{entry["text"]}"')
            text_lbl.setFont(QFont("monospace", 9))
            text_lbl.setStyleSheet(f"color:{C_INK}; background:transparent;")
            text_lbl.setWordWrap(True)
            text_lbl.setSizePolicy(
                __import__(
                    "PySide6.QtWidgets", fromlist=["QSizePolicy"]
                ).QSizePolicy.Policy.Expanding,
                __import__(
                    "PySide6.QtWidgets", fromlist=["QSizePolicy"]
                ).QSizePolicy.Policy.Preferred,
            )

            src_lbl = QLabel(src_label)
            src_lbl.setFont(QFont("monospace", 7, QFont.Weight.Bold))
            src_lbl.setFixedWidth(70)
            src_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            src_color = C_GOLD_DIM if entry["source"] == "template" else "#4080d0"
            src_lbl.setStyleSheet(
                f"color:{src_color}; background:transparent; letter-spacing:1px;"
            )

            date_lbl = QLabel(entry["date"][:10])
            date_lbl.setFont(QFont("monospace", 7))
            date_lbl.setFixedWidth(90)
            date_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            date_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")

            hl.addWidget(glyph)
            hl.addWidget(text_lbl, stretch=1)
            hl.addWidget(src_lbl)
            hl.addWidget(date_lbl)

            self._jl.insertWidget(i * 2, row_w)

            if i < len(entries) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{C_RULE}; border:none;")
                self._jl.insertWidget(i * 2 + 1, sep)

    def _load_achievements(self):
        while self._al.count():
            item = self._al.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        with SessionFactory() as session:
            char = session.get(Character, 1)
            if not char:
                return
            unlocked = {a.key: a for a in char.achievements}

        cols = 2
        for idx, (key, title, desc) in enumerate(ACHIEVEMENT_DEFS):
            row, col = divmod(idx, cols)
            is_unlocked = key in unlocked

            card = QWidget()
            card.setFixedHeight(76)

            if is_unlocked:
                card.setStyleSheet(
                    f"background:{C_SURFACE}; border:1px solid {C_RULE_GOLD};"
                )
                cl = QHBoxLayout(card)
                cl.setContentsMargins(10, 8, 10, 8)
                cl.setSpacing(8)

                seal = QLabel("✦")
                seal.setFont(QFont("monospace", 16))
                seal.setStyleSheet(f"color:{C_GOLD}; background:transparent;")
                seal.setFixedWidth(20)

                txt = QVBoxLayout()
                txt.setSpacing(2)
                t_lbl = QLabel(title.upper())
                t_lbl.setFont(QFont("monospace", 8, QFont.Weight.Bold))
                t_lbl.setStyleSheet(
                    f"color:{C_GOLD}; background:transparent; letter-spacing:1px;"
                )
                d_lbl = QLabel(desc)
                d_lbl.setFont(QFont("monospace", 7))
                d_lbl.setStyleSheet(f"color:{C_INK_DIM}; background:transparent;")
                d_lbl.setWordWrap(True)
                dt = unlocked[key].unlocked_at.strftime("%Y-%m-%d")
                dt_lbl = QLabel(dt)
                dt_lbl.setStyleSheet(
                    f"color:{C_INK_FAINT}; background:transparent; font-size:7px;"
                )

                txt.addWidget(t_lbl)
                txt.addWidget(d_lbl)
                txt.addWidget(dt_lbl)
                cl.addWidget(seal)
                cl.addLayout(txt)
            else:
                card.setStyleSheet(f"background:{C_BG}; border:1px solid {C_RULE};")
                cl = QVBoxLayout(card)
                cl.setContentsMargins(12, 10, 12, 10)
                cl.setSpacing(3)
                lock = QLabel("— redacted —")
                lock.setFont(QFont("monospace", 8))
                lock.setStyleSheet(
                    f"color:{C_INK_FAINT}; background:transparent; font-style:italic;"
                )
                hint = QLabel(desc[:42] + ("…" if len(desc) > 42 else ""))
                hint.setFont(QFont("monospace", 7))
                hint.setStyleSheet(f"color:{C_RULE_GOLD}; background:transparent;")
                hint.setWordWrap(True)
                cl.addWidget(lock)
                cl.addWidget(hint)

            self._al.addWidget(card, row, col)
