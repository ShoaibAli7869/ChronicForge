"""
ChronicForge — Activity Tab
Live session monitor + browser/app category breakdown.
Shows what the activity tracker is seeing right now.
"""

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.activity_tracker import Category, get_tracker
from utils.signals import event_bus

C_BG = "#e8e0cc"
C_SURFACE = "#ddd5b5"
C_RULE = "#c0b488"
C_RULE_GOLD = "#a89060"
C_GOLD = "#c8820a"
C_GOLD_BRIGHT = "#6b3a10"
C_INK = "#3a2a18"
C_INK_DIM = "#8a7050"
C_INK_FAINT = "#a89060"
C_GREEN = "#2a6a30"
C_RED = "#8b1a1a"
C_PURPLE = "#4a2860"
C_BLUE = "#2a4a7a"

# Category → display colour
CAT_COLORS = {
    Category.PRODUCTIVE: ("#2a6a30", "⚒"),
    Category.ENTERTAINMENT: ("#8b1a1a", "🎮"),
    Category.BROWSER_PRO: ("#2a4a7a", "🔍"),
    Category.BROWSER_ENT: ("#6a2040", "📺"),
    Category.BROWSER_OTHER: ("#8a7050", "🌐"),
    Category.COMMUNICATION: ("#4a2860", "💬"),
    Category.SYSTEM: ("#a89060", "⚙"),
    Category.IDLE: ("#c0b488", "·"),
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


class _SessionBar(QWidget):
    """
    Horizontal stacked bar showing time breakdown by category.
    Productive (green) | Browser-pro (blue) | Entertainment (red) | etc.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: list[tuple[float, str]] = []  # (fraction, color)
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_segments(self, segments: list[tuple[float, str]]):
        self._segments = segments
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Background
        p.fillRect(0, 0, W, H, QColor(C_RULE))

        x = 0
        for frac, color in self._segments:
            w = int(frac * W)
            if w > 0:
                p.fillRect(x, 0, w, H, QColor(color))
                x += w
        p.end()


class ActivityTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

        # Refresh every 30s to match tracker poll interval
        self._timer = QTimer(self)
        self._timer.setInterval(30_000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def _build(self):
        self.setStyleSheet(f"background:{C_BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 16)
        root.setSpacing(0)

        # Page title
        title_row = QHBoxLayout()
        title = QLabel("ACTIVITY MONITOR")
        title.setFont(QFont("Cinzel", 13, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{C_GOLD_BRIGHT}; background:transparent; letter-spacing:4px;"
        )
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setFont(QFont("IM Fell English", 11))
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{C_INK_FAINT};
                border:1px solid {C_RULE}; border-radius:0;
            }}
            QPushButton:hover {{ color:{C_GOLD}; border-color:{C_RULE_GOLD}; }}
        """)
        refresh_btn.clicked.connect(self.refresh)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(refresh_btn)
        root.addLayout(title_row)
        root.addSpacing(10)
        root.addWidget(_Divider(C_GOLD))
        root.addSpacing(14)

        # ── Live status ───────────────────────────────────────────────────────
        root.addWidget(self._label("CURRENTLY TRACKING"))
        root.addSpacing(8)

        status_row = QHBoxLayout()
        status_row.setSpacing(16)

        self._cur_app_lbl = QLabel("—")
        self._cur_app_lbl.setFont(QFont("Cinzel", 11, QFont.Weight.Bold))
        self._cur_app_lbl.setStyleSheet(f"color:{C_INK}; background:transparent;")

        self._cur_cat_lbl = QLabel("")
        self._cur_cat_lbl.setFont(QFont("Share Tech Mono", 9))
        self._cur_cat_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")

        self._cur_win_lbl = QLabel("")
        self._cur_win_lbl.setFont(QFont("Share Tech Mono", 8))
        self._cur_win_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
        self._cur_win_lbl.setWordWrap(True)

        status_row.addWidget(self._cur_app_lbl)
        status_row.addStretch()
        status_row.addWidget(self._cur_cat_lbl)
        root.addLayout(status_row)
        root.addSpacing(4)
        root.addWidget(self._cur_win_lbl)
        root.addSpacing(10)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(12)

        # ── Session summary ────────────────────────────────────────────────────
        root.addWidget(self._label("TODAY'S SESSION"))
        root.addSpacing(8)

        # Productive vs Entertainment headline
        headline_row = QHBoxLayout()
        headline_row.setSpacing(24)

        self._pro_lbl = self._stat_block("PRODUCTIVE", "0m", C_GREEN)
        self._ent_lbl = self._stat_block("ENTERTAINMENT", "0m", C_RED)
        self._idle_lbl = self._stat_block("IDLE / SYSTEM", "0m", C_INK_FAINT)

        headline_row.addWidget(self._pro_lbl)
        headline_row.addWidget(self._ent_lbl)
        headline_row.addWidget(self._idle_lbl)
        headline_row.addStretch()
        root.addLayout(headline_row)
        root.addSpacing(12)

        # Stacked bar
        bar_lbl = QLabel("TIME BREAKDOWN")
        bar_lbl.setFont(QFont("Cinzel", 7, QFont.Weight.Bold))
        bar_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:3px;"
        )
        root.addWidget(bar_lbl)
        root.addSpacing(4)
        self._session_bar = _SessionBar()
        root.addWidget(self._session_bar)
        root.addSpacing(6)

        # Legend for stacked bar
        self._legend_row = QHBoxLayout()
        self._legend_row.setSpacing(14)
        self._legend_row.addStretch()
        root.addLayout(self._legend_row)

        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(12)

        # ── Category breakdown table ───────────────────────────────────────────
        root.addWidget(self._label("CATEGORY BREAKDOWN"))
        root.addSpacing(8)

        self._cat_layout = QVBoxLayout()
        self._cat_layout.setSpacing(4)
        root.addLayout(self._cat_layout)
        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(12)

        # ── Roast threshold control ────────────────────────────────────────────
        root.addWidget(self._label("SOLDIER BOY TRIGGER THRESHOLD"))
        root.addSpacing(8)

        thresh_row = QHBoxLayout()
        thresh_lbl = QLabel("Roast after")
        thresh_lbl.setFont(QFont("Share Tech Mono", 8))
        thresh_lbl.setStyleSheet(f"color:{C_INK_DIM}; background:transparent;")
        thresh_lbl.setFixedWidth(80)

        self._thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self._thresh_slider.setRange(15, 120)
        self._thresh_slider.setValue(45)
        self._thresh_slider.setTickInterval(15)
        self._thresh_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background:{C_RULE}; height:2px; }}
            QSlider::handle:horizontal {{
                background:{C_GOLD}; width:14px; height:14px;
                border-radius:7px; margin:-6px 0;
            }}
            QSlider::sub-page:horizontal {{ background:{C_RULE_GOLD}; }}
        """)
        self._thresh_val = QLabel("45 min")
        self._thresh_val.setFont(QFont("Share Tech Mono", 8))
        self._thresh_val.setStyleSheet(f"color:{C_GOLD}; background:transparent;")
        self._thresh_val.setFixedWidth(50)
        self._thresh_slider.valueChanged.connect(self._on_threshold_change)

        thresh_row.addWidget(thresh_lbl)
        thresh_row.addWidget(self._thresh_slider, stretch=1)
        thresh_row.addWidget(self._thresh_val)
        root.addLayout(thresh_row)

        # Load persisted threshold from config
        try:
            from config.settings import load_config

            cfg = load_config()
            self._thresh_slider.setValue(cfg.roast_ent_threshold)
            from core.activity_tracker import get_tracker

            get_tracker().ENT_ROAST_THRESHOLD = cfg.roast_ent_threshold
        except Exception:
            pass

        root.addStretch()

    def _label(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setFont(QFont("Cinzel", 7, QFont.Weight.Bold))
        l.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px;"
        )
        return l

    def _stat_block(self, title: str, value: str, color: str) -> QWidget:
        """A small stat block: title above, big value below."""
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(2)

        t = QLabel(title)
        t.setFont(QFont("Cinzel", 7, QFont.Weight.Bold))
        t.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:2px;"
        )

        v = QLabel(value)
        v.setFont(QFont("monospace", 16, QFont.Weight.Bold))
        v.setStyleSheet(f"color:{color}; background:transparent;")
        v.setObjectName(f"val_{title}")

        vl.addWidget(t)
        vl.addWidget(v)
        return w

    def _on_threshold_change(self, val: int):
        self._thresh_val.setText(f"{val} min")
        try:
            from config.settings import load_config, save_config

            cfg = load_config()
            cfg.roast_ent_threshold = val
            save_config(cfg)
            from core.activity_tracker import get_tracker

            get_tracker().ENT_ROAST_THRESHOLD = val
        except Exception:
            pass

    def refresh(self):
        """Pull live data from the activity tracker and update all widgets."""
        try:
            tracker = get_tracker()
            summary = tracker.get_summary()
        except Exception:
            return

        cats = summary.get("categories", {})
        cur_cat = summary.get("current_category", Category.IDLE)
        cur_app = summary.get("current_app", "")
        cur_win = tracker.session.last_window

        # Live status
        col_info = CAT_COLORS.get(cur_cat, ("#8a7050", "·"))
        icon = col_info[1]
        cat_name = Category.display(cur_cat)
        self._cur_app_lbl.setText(cur_app[:40] or "No active app detected")
        self._cur_cat_lbl.setText(f"{icon}  {cat_name.upper()}")
        self._cur_cat_lbl.setStyleSheet(
            f"color:{col_info[0]}; background:transparent; font-family: 'Share Tech Mono', monospace; font-size:9px;"
        )
        self._cur_win_lbl.setText(cur_win[:80] if cur_win else "")

        # Totals
        pro_sec = cats.get(Category.PRODUCTIVE, 0) + cats.get(Category.BROWSER_PRO, 0)
        ent_sec = cats.get(Category.ENTERTAINMENT, 0) + cats.get(
            Category.BROWSER_ENT, 0
        )
        idle_sec = cats.get(Category.IDLE, 0) + cats.get(Category.SYSTEM, 0)
        total_sec = sum(cats.values()) or 1

        def fmt(s):
            return (
                f"{int(s) // 3600}h {(int(s) % 3600) // 60}m"
                if s >= 3600
                else f"{int(s) // 60}m"
            )

        # Update stat block values
        for w in (self._pro_lbl, self._ent_lbl, self._idle_lbl):
            vals = {
                "PRODUCTIVE": fmt(pro_sec),
                "ENTERTAINMENT": fmt(ent_sec),
                "IDLE / SYSTEM": fmt(idle_sec),
            }
            for child in w.findChildren(QLabel):
                if child.objectName().startswith("val_"):
                    key = child.objectName()[4:]
                    if key in vals:
                        child.setText(vals[key])

        # Stacked bar segments
        segments = []
        cat_order = [
            (Category.PRODUCTIVE, "#2a6a30"),
            (Category.BROWSER_PRO, "#2a4a7a"),
            (Category.BROWSER_OTHER, "#3a5070"),
            (Category.COMMUNICATION, "#7050a0"),
            (Category.ENTERTAINMENT, "#8b1a1a"),
            (Category.BROWSER_ENT, "#6a2040"),
            (Category.IDLE, "#ccc4a0"),
            (Category.SYSTEM, "#ccc4a0"),
        ]
        for cat, color in cat_order:
            sec = cats.get(cat, 0)
            frac = sec / total_sec
            if frac > 0.01:
                segments.append((frac, color))
        self._session_bar.set_segments(segments)

        # Category breakdown rows
        while self._cat_layout.count():
            item = self._cat_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
        for cat, sec in sorted_cats:
            if sec < 30:
                continue  # skip noise
            col_info = CAT_COLORS.get(cat, ("#8a7050", "·"))
            minutes = int(sec) // 60
            frac = sec / total_sec

            row = QHBoxLayout()
            row.setSpacing(10)

            icon_lbl = QLabel(col_info[1])
            icon_lbl.setFixedWidth(18)
            icon_lbl.setFont(QFont("IM Fell English", 10))
            icon_lbl.setStyleSheet(f"color:{col_info[0]}; background:transparent;")

            name_lbl = QLabel(Category.display(cat).upper())
            name_lbl.setFont(QFont("Cinzel", 8, QFont.Weight.Bold))
            name_lbl.setStyleSheet(
                f"color:{col_info[0]}; background:transparent; letter-spacing:1px;"
            )
            name_lbl.setFixedWidth(160)

            # Mini bar
            bar_w = QWidget()
            bar_w.setFixedHeight(8)
            bar_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar_w.setStyleSheet(f"background:{C_RULE}; border:none;")
            bar_inner = QWidget(bar_w)
            bar_inner.setFixedHeight(8)
            bar_inner.setFixedWidth(max(2, int(frac * 200)))
            bar_inner.setStyleSheet(f"background:{col_info[0]}; border:none;")

            time_lbl = QLabel(f"{minutes}m")
            time_lbl.setFont(QFont("Share Tech Mono", 8))
            time_lbl.setStyleSheet(f"color:{col_info[0]}; background:transparent;")
            time_lbl.setFixedWidth(40)
            time_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            pct_lbl = QLabel(f"{int(frac * 100)}%")
            pct_lbl.setFont(QFont("Share Tech Mono", 7))
            pct_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
            pct_lbl.setFixedWidth(32)
            pct_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            row.addWidget(icon_lbl)
            row.addWidget(name_lbl)
            row.addWidget(bar_w, stretch=1)
            row.addWidget(time_lbl)
            row.addWidget(pct_lbl)

            container = QWidget()
            container.setStyleSheet("background:transparent;")
            container.setLayout(row)
            container.setMaximumHeight(22)
            self._cat_layout.addWidget(container)
