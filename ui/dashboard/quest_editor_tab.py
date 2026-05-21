"""
ChronicForge — Quest Editor Tab
Two panels:
  Left  — Quest editor: create / edit / delete custom quests
  Right — Habit bundles: browse and import pre-built quest packs
"""

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.quest_editor import (
    HABIT_BUNDLES,
    create_custom_quest,
    delete_quest,
    get_all_active_quests_for_editor,
    get_bundle_names,
    import_bundle,
    update_custom_quest,
)
from utils.signals import event_bus

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG = "#e8e0cc"
C_SURFACE = "#ddd5b5"
C_RULE = "#c0b488"
C_RULE_GOLD = "#a89060"
C_GOLD = "#c8820a"
C_GOLD_B = "#6b3a10"
C_GOLD_PALE = "#f0e8d8"
C_INK = "#3a2a18"
C_INK_DIM = "#8a7050"
C_INK_FAINT = "#a89060"
C_GREEN = "#2a6a30"
C_RED = "#8b1a1a"

STATS = [
    "strength",
    "intellect",
    "charisma",
    "vitality",
    "discipline",
    "creativity",
    "wealth",
]
STAT_ICONS = {
    "strength": "⚔",
    "intellect": "📜",
    "charisma": "🎭",
    "vitality": "🌿",
    "discipline": "🛡",
    "creativity": "✒",
    "wealth": "⚖",
}
TYPES = ["custom", "life"]  # Only safe types (daily/weekly are auto-generated only)
TYPE_COLOR = {
    "daily": "#c8820a",
    "weekly": "#4a2860",
    "life": "#8b1a1a",
    "custom": "#2a6a30",
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


def _lbl(text, size=7, bold=True, color=C_INK_FAINT) -> QLabel:
    l = QLabel(text)
    w = QFont.Weight.Bold if bold else QFont.Weight.Normal
    l.setFont(QFont("monospace", size, w))
    l.setStyleSheet(f"color:{color}; background:transparent; letter-spacing:3px;")
    return l


def _input(placeholder="", password=False) -> QLineEdit:
    f = QLineEdit()
    f.setPlaceholderText(placeholder)
    if password:
        f.setEchoMode(QLineEdit.EchoMode.Password)
    f.setFont(QFont("IM Fell English", 10))
    f.setStyleSheet(f"""
        QLineEdit {{
            background:{C_SURFACE}; color:{C_INK};
            border:none; border-bottom:1px solid {C_RULE_GOLD};
            padding:6px 4px;
        }}
        QLineEdit:focus {{ border-bottom-color:{C_GOLD}; }}
    """)
    return f


def _combo(items: list[str]) -> QComboBox:
    c = QComboBox()
    c.addItems(items)
    c.setFont(QFont("Share Tech Mono", 9))
    c.setStyleSheet(f"""
        QComboBox {{
            background:{C_SURFACE}; color:{C_GOLD};
            border:1px solid {C_RULE}; padding:5px 10px;
        }}
        QComboBox QAbstractItemView {{
            background:{C_SURFACE}; color:{C_GOLD};
            border:1px solid {C_RULE};
            selection-background-color:{C_RULE};
        }}
    """)
    return c


def _action_btn(text, color=C_GOLD, border=C_RULE_GOLD) -> QPushButton:
    b = QPushButton(text)
    b.setFont(QFont("IM Fell English", 9, QFont.Weight.Bold))
    b.setStyleSheet(f"""
        QPushButton {{
            background:{C_SURFACE}; color:{color};
            border:1px solid {border}; padding:8px 16px;
            letter-spacing:1px;
        }}
        QPushButton:hover {{ background:#d5cca8; border-color:{color}; }}
        QPushButton:pressed {{ background:{C_BG}; }}
    """)
    return b


# ── Quest row in editor list ──────────────────────────────────────────────────


class _QuestEditorRow(QWidget):
    """Single quest row with edit + delete buttons."""

    edit_clicked = Signal(dict)
    delete_clicked = Signal(int)

    def __init__(self, quest: dict, parent=None):
        super().__init__(parent)
        self._q = quest
        self.setStyleSheet("background:transparent;")
        self.setMaximumHeight(36)

        hl = QHBoxLayout(self)
        hl.setContentsMargins(0, 4, 0, 4)
        hl.setSpacing(8)

        # Type badge
        qtype = quest["type"]
        col = TYPE_COLOR.get(qtype, C_INK_FAINT)
        type_lbl = QLabel(qtype[:3].upper())
        type_lbl.setFixedWidth(32)
        type_lbl.setFont(QFont("Cinzel", 7, QFont.Weight.Bold))
        type_lbl.setStyleSheet(
            f"color:{col}; background:transparent; letter-spacing:1px;"
        )

        # Stat icon
        icon_lbl = QLabel(STAT_ICONS.get(quest["stat"], "·"))
        icon_lbl.setFixedWidth(16)
        icon_lbl.setFont(QFont("IM Fell English", 10))
        icon_lbl.setStyleSheet("background:transparent;")

        # Title
        title = QLabel(quest["title"][:48] + ("…" if len(quest["title"]) > 48 else ""))
        title.setFont(QFont("Share Tech Mono", 9))
        col_title = C_INK_DIM if not quest["completed"] else C_INK_FAINT
        strike = "text-decoration:line-through;" if quest["completed"] else ""
        title.setStyleSheet(f"color:{col_title}; background:transparent; {strike}")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title.setToolTip(quest["description"])

        # XP
        xp_lbl = QLabel(f"+{quest['xp_reward']}")
        xp_lbl.setFont(QFont("Share Tech Mono", 8))
        xp_lbl.setFixedWidth(44)
        xp_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        xp_lbl.setStyleSheet(f"color:{C_GOLD}; background:transparent;")

        # Edit / Delete (only for incomplete quests)
        if not quest["completed"]:
            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(20, 20)
            edit_btn.setFont(QFont("Share Tech Mono", 9))
            edit_btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{C_INK_FAINT};
                    border:none; padding:0; }}
                QPushButton:hover {{ color:{C_GOLD}; }}
            """)
            edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._q))

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(20, 20)
            del_btn.setFont(QFont("Share Tech Mono", 9))
            del_btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{C_INK_FAINT};
                    border:none; padding:0; }}
                QPushButton:hover {{ color:{C_RED}; }}
            """)
            del_btn.clicked.connect(lambda: self.delete_clicked.emit(self._q["id"]))
        else:
            edit_btn = QLabel("")
            edit_btn.setFixedSize(20, 20)
            del_btn = QLabel("")
            del_btn.setFixedSize(20, 20)

        hl.addWidget(type_lbl)
        hl.addWidget(icon_lbl)
        hl.addWidget(title, stretch=1)
        hl.addWidget(xp_lbl)
        hl.addWidget(edit_btn)
        hl.addWidget(del_btn)


# ── Quest create / edit form ──────────────────────────────────────────────────


class _QuestForm(QWidget):
    """Inline form for creating or editing a quest."""

    saved = Signal(dict)  # emits result dict
    cancelled = Signal()

    def __init__(self, quest: dict = None, parent=None):
        super().__init__(parent)
        self._quest = quest  # None = create mode
        self._build()
        if quest:
            self._populate(quest)

    def _build(self):
        self.setStyleSheet(f"background:{C_SURFACE}; border:1px solid {C_RULE_GOLD};")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        mode = "EDIT QUEST" if self._quest else "CREATE QUEST"
        root.addWidget(_lbl(mode, color=C_GOLD_B))

        root.addWidget(_lbl("Title"))
        self._title = _input("Quest title")
        root.addWidget(self._title)

        root.addWidget(_lbl("Description"))
        self._desc = QTextEdit()
        self._desc.setFont(QFont("Share Tech Mono", 9))
        self._desc.setFixedHeight(56)
        self._desc.setStyleSheet(f"""
            QTextEdit {{
                background:{C_BG}; color:{C_INK};
                border:1px solid {C_RULE}; padding:4px;
            }}
        """)
        root.addWidget(self._desc)

        row = QHBoxLayout()
        row.setSpacing(10)

        stat_col = QVBoxLayout()
        stat_col.addWidget(_lbl("Stat"))
        self._stat = _combo(STATS)
        stat_col.addWidget(self._stat)
        row.addLayout(stat_col)

        type_col = QVBoxLayout()
        type_col.addWidget(_lbl("Type"))
        self._type = _combo(TYPES)
        type_col.addWidget(self._type)
        row.addLayout(type_col)

        xp_col = QVBoxLayout()
        xp_col.addWidget(_lbl("XP Reward"))
        self._xp = _input("100")
        self._xp.setFixedWidth(80)
        xp_col.addWidget(self._xp)
        row.addLayout(xp_col)

        root.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        save_btn = _action_btn("✦  Save", C_GOLD, C_RULE_GOLD)
        cancel_btn = _action_btn("Cancel", C_INK_FAINT, C_RULE)
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.cancelled.emit)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _populate(self, q: dict):
        self._title.setText(q["title"])
        self._desc.setPlainText(q["description"])
        if q["stat"] in STATS:
            self._stat.setCurrentIndex(STATS.index(q["stat"]))
        if q["type"] in TYPES:
            self._type.setCurrentIndex(TYPES.index(q["type"]))
        self._xp.setText(str(q["xp_reward"]))

    def _save(self):
        title = self._title.text().strip()
        desc = self._desc.toPlainText().strip()
        stat = self._stat.currentText()
        qtype = self._type.currentText()
        try:
            xp = int(self._xp.text().strip() or "100")
        except ValueError:
            xp = 100

        if not title:
            self._title.setFocus()
            return

        if self._quest:
            result = update_custom_quest(
                self._quest["id"],
                title=title,
                description=desc,
                stat=stat,
                xp_reward=xp,
            )
        else:
            result = create_custom_quest(
                title=title, description=desc, stat=stat, xp_reward=xp, quest_type=qtype
            )

        self.saved.emit(result)


# ── Bundle card ───────────────────────────────────────────────────────────────


class _BundleCard(QWidget):
    import_clicked = Signal(str)  # emits bundle key

    def __init__(self, bundle_meta: dict, parent=None):
        super().__init__(parent)
        self._key = bundle_meta["key"]
        col = bundle_meta["color"]
        self.setStyleSheet(
            f"QWidget {{ background:{C_SURFACE};"
            f"border:1px solid {C_RULE};"
            f"border-left:4px solid {col};"
            f"border-top:1px solid {C_RULE}; }}"
        )
        self.setMaximumHeight(100)

        vl = QVBoxLayout(self)
        vl.setContentsMargins(14, 10, 14, 10)
        vl.setSpacing(6)

        # Header row: icon + name + count + import button
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        # Icon in a colored circle
        icon_lbl = QLabel(bundle_meta["icon"])
        icon_lbl.setFont(QFont("serif", 14))
        icon_lbl.setFixedSize(32, 32)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"background:{C_BG}; border:1px solid {col};"
            f"border-radius:16px; color:{col};"
        )

        # Name in Cinzel + quest count
        name_col = QVBoxLayout()
        name_col.setSpacing(1)
        name = QLabel(bundle_meta["name"].upper())
        name.setFont(QFont("Cinzel", 8, QFont.Weight.Bold))
        name.setStyleSheet(f"color:{col}; background:transparent; letter-spacing:2px;")
        count = QLabel(f"{bundle_meta['count']} quests")
        count.setFont(QFont("Share Tech Mono", 7))
        count.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
        name_col.addWidget(name)
        name_col.addWidget(count)

        # Import button — crimson seal style
        import_btn = QPushButton("+ Import")
        import_btn.setFont(QFont("Cinzel", 7, QFont.Weight.Bold))
        import_btn.setFixedWidth(76)
        import_btn.setFixedHeight(28)
        import_btn.setStyleSheet(f"""
            QPushButton {{
                background:{col}; color:{C_GOLD_PALE};
                border:none; border-radius:0px;
                padding:4px 8px; letter-spacing:1px;
            }}
            QPushButton:hover {{
                background:{C_INK}; color:{C_GOLD_PALE};
            }}
        """)
        import_btn.clicked.connect(lambda: self.import_clicked.emit(self._key))

        hdr.addWidget(icon_lbl)
        hdr.addLayout(name_col, stretch=1)
        hdr.addWidget(import_btn)
        vl.addLayout(hdr)

        # Description in serif italic
        desc = QLabel(bundle_meta["description"])
        desc.setFont(QFont("IM Fell English", 9))
        desc.setStyleSheet(
            f"color:{C_INK_DIM}; background:transparent;padding-left:42px;"
        )
        desc.setWordWrap(True)
        vl.addWidget(desc)


# ── Main Quest Editor Tab ─────────────────────────────────────────────────────


class QuestEditorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._form: _QuestForm = None
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet(f"background:{C_BG};")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left panel: quest list + editor form ──────────────────────────────
        left = QWidget()
        left.setStyleSheet(f"background:{C_BG};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(24, 20, 16, 16)
        ll.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(_lbl("QUEST EDITOR", size=10, color=C_GOLD_B))
        hdr.addStretch()
        create_btn = _action_btn("+ New Quest", C_GREEN, "#1a5020")
        create_btn.clicked.connect(self._show_create_form)
        hdr.addWidget(create_btn)
        ll.addLayout(hdr)
        ll.addSpacing(8)
        ll.addWidget(_Divider(C_GOLD))
        ll.addSpacing(6)

        # Form area (hidden until create/edit)
        self._form_container = QWidget()
        self._form_container.setStyleSheet("background:transparent;")
        self._form_layout = QVBoxLayout(self._form_container)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_container.hide()
        ll.addWidget(self._form_container)

        # Quest list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        ll.addWidget(scroll, stretch=1)

        # Status bar
        self._status = QLabel("")
        self._status.setFont(QFont("Share Tech Mono", 8))
        self._status.setStyleSheet("color:#2a6a30; background:transparent;")
        ll.addWidget(self._status)

        root.addWidget(left, stretch=3)

        # Thin separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background:{C_RULE}; border:none;")
        sep.setFixedWidth(1)
        root.addWidget(sep)

        # ── Right panel: habit bundles ─────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet(f"background:{C_BG};")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 20, 24, 16)
        rl.setSpacing(0)

        rl.addWidget(_lbl("HABIT BUNDLES", size=10, color=C_GOLD_B))
        rl.addSpacing(4)
        rl.addWidget(
            _lbl(
                "One-click quest packs. Import all or choose types.",
                size=8,
                bold=False,
                color=C_INK_FAINT,
            )
        )
        rl.addSpacing(8)
        rl.addWidget(_Divider(C_GOLD))
        rl.addSpacing(8)

        # Type filter chips
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self._type_filters = {}
        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(False)

        filter_row.addWidget(_lbl("IMPORT:", size=7, color=C_INK_FAINT))
        for label, types in [
            ("All", None),
            ("Daily", ["daily"]),
            ("Weekly", ["weekly"]),
            ("Life", ["life"]),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(label == "All")
            btn.setFont(QFont("Share Tech Mono", 8))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{C_INK_FAINT};
                    border:1px solid {C_RULE}; padding:4px 12px;
                }}
                QPushButton:checked {{
                    color:{C_GOLD}; border-color:{C_RULE_GOLD};
                    background:{C_SURFACE};
                }}
                QPushButton:hover {{ color:{C_GOLD}; border-color:{C_RULE_GOLD}; }}
            """)
            self._type_filters[label] = (btn, types)
            self._filter_group.addButton(btn)
            filter_row.addWidget(btn)
        filter_row.addStretch()
        rl.addLayout(filter_row)
        rl.addSpacing(10)

        # Bundle cards scroll
        bundle_scroll = QScrollArea()
        bundle_scroll.setWidgetResizable(True)
        bundle_scroll.setFrameShape(QFrame.Shape.NoFrame)
        bundle_scroll.setStyleSheet("background:transparent; border:none;")

        self._bundle_widget = QWidget()
        self._bundle_widget.setStyleSheet("background:transparent;")
        self._bundle_layout = QVBoxLayout(self._bundle_widget)
        self._bundle_layout.setContentsMargins(0, 0, 4, 0)
        self._bundle_layout.setSpacing(8)

        for meta in get_bundle_names():
            card = _BundleCard(meta)
            card.import_clicked.connect(self._import_bundle)
            self._bundle_layout.addWidget(card)

        self._bundle_layout.addStretch()
        bundle_scroll.setWidget(self._bundle_widget)
        rl.addWidget(bundle_scroll, stretch=1)

        # Bundle status
        self._bundle_status = QLabel("")
        self._bundle_status.setFont(QFont("Share Tech Mono", 8))
        self._bundle_status.setStyleSheet("background:transparent;")
        self._bundle_status.setWordWrap(True)
        rl.addWidget(self._bundle_status)

        root.addWidget(right, stretch=2)

    # ── Quest list management ─────────────────────────────────────────────────

    def refresh(self):
        self._clear_list()
        quests = get_all_active_quests_for_editor()

        if not quests:
            empty = QLabel("No quests yet. Create one or import a bundle.")
            empty.setStyleSheet(
                f"color:{C_INK_FAINT}; font-family: 'Share Tech Mono', monospace; font-size:9px;"
            )
            self._list_layout.insertWidget(0, empty)
            return

        # Group by type
        groups = {"daily": [], "weekly": [], "life": [], "custom": []}
        for q in quests:
            groups.setdefault(q["type"], []).append(q)

        idx = 0
        for qtype in ["custom", "daily", "weekly", "life"]:
            qs = groups.get(qtype, [])
            if not qs:
                continue

            # Section header
            col = TYPE_COLOR.get(qtype, C_INK_FAINT)
            hdr = QLabel(qtype.upper())
            hdr.setFont(QFont("Cinzel", 7, QFont.Weight.Bold))
            hdr.setStyleSheet(
                f"color:{col}; background:transparent; letter-spacing:3px; padding:8px 0 4px 0;"
            )
            self._list_layout.insertWidget(idx, hdr)
            idx += 1

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{C_RULE}; border:none;")
            self._list_layout.insertWidget(idx, sep)
            idx += 1

            for q in qs:
                row = _QuestEditorRow(q)
                row.edit_clicked.connect(self._show_edit_form)
                row.delete_clicked.connect(self._delete_quest)
                self._list_layout.insertWidget(idx, row)
                idx += 1

                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedHeight(1)
                line.setStyleSheet(f"background:{C_RULE}; border:none; margin:0;")
                self._list_layout.insertWidget(idx, line)
                idx += 1

    def _clear_list(self):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()

    # ── Form management ───────────────────────────────────────────────────────

    def _show_create_form(self):
        self._clear_form()
        form = _QuestForm(quest=None)
        form.saved.connect(self._on_form_saved)
        form.cancelled.connect(self._clear_form)
        self._form_layout.addWidget(form)
        self._form = form
        self._form_container.show()

    def _show_edit_form(self, quest: dict):
        self._clear_form()
        form = _QuestForm(quest=quest)
        form.saved.connect(self._on_form_saved)
        form.cancelled.connect(self._clear_form)
        self._form_layout.addWidget(form)
        self._form = form
        self._form_container.show()

    def _clear_form(self):
        if self._form:
            self._form.setParent(None)
            self._form.deleteLater()
            self._form = None
        self._form_container.hide()

    def _on_form_saved(self, result: dict):
        if "error" not in result:
            action = "updated" if self._form and self._form._quest else "created"
            self._set_status(f"✦  Quest {action}: {result.get('title', '')}")
            self._clear_form()
            self.refresh()
            event_bus.quests_updated.emit()

    def _delete_quest(self, quest_id: int):
        ok = delete_quest(quest_id)
        if ok:
            self._set_status("·  Quest deleted.")
            self.refresh()
            event_bus.quests_updated.emit()

    def _set_status(self, text: str, color: str = C_GREEN):
        self._status.setText(text)
        self._status.setStyleSheet(f"color:{color}; background:transparent;")
        QTimer.singleShot(4000, lambda: self._status.setText(""))

    # ── Bundle import ─────────────────────────────────────────────────────────

    def _get_active_types(self):
        """Return currently selected import type filter."""
        for label, (btn, types) in self._type_filters.items():
            if btn.isChecked():
                return types
        return None

    def _import_bundle(self, bundle_key: str):
        types = self._get_active_types()
        result = import_bundle(bundle_key, quest_types=types)

        if "error" in result:
            self._bundle_status.setText(f"✗  {result['error']}")
            self._bundle_status.setStyleSheet(f"color:{C_RED}; background:transparent;")
            return

        total = result["total"]
        skipped = result["skipped"]
        imp = result["imported"]

        parts = []
        for t, n in imp.items():
            if n > 0:
                parts.append(f"{n} {t}")
        summary = ", ".join(parts) if parts else "0"

        msg = f"✦  {result['bundle']}: imported {summary}"
        if skipped:
            msg += f"  ({skipped} skipped — already exist)"

        self._bundle_status.setText(msg)
        self._bundle_status.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
        QTimer.singleShot(6000, lambda: self._bundle_status.setText(""))

        self.refresh()
        event_bus.quests_updated.emit()
