"""
ChronicForge — Settings Tab  (v3 — Medieval Codex)
Same ruled parchment aesthetic as the other tabs.
"""

import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from config.settings import load_config, save_config
from utils.signals import event_bus

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
C_GREEN = "#50a030"
C_RED = "#b03020"


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


def _section_header(text: str) -> QLabel:
    l = QLabel(text)
    l.setFont(QFont("monospace", 7, QFont.Weight.Bold))
    l.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px;")
    return l


def _field_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setFont(QFont("monospace", 8))
    l.setStyleSheet(f"color:{C_INK_DIM}; background:transparent;")
    return l


def _input(placeholder="", password=False) -> QLineEdit:
    f = QLineEdit()
    f.setPlaceholderText(placeholder)
    if password:
        f.setEchoMode(QLineEdit.EchoMode.Password)
    f.setFont(QFont("monospace", 10))
    f.setFixedHeight(36)
    f.setStyleSheet(f"""
        QLineEdit {{
            background:{C_SURFACE}; color:{C_INK};
            border:none; border-bottom:1px solid {C_RULE_GOLD};
            padding:0 6px;
        }}
        QLineEdit:focus {{ border-bottom-color:{C_GOLD}; color:{C_GOLD_BRIGHT}; }}
    """)
    return f


class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = load_config()
        self._int_btns = {}
        self._build()
        self._load_values()

    def _build(self):
        self.setStyleSheet(f"background:{C_BG};")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 20, 28, 28)
        root.setSpacing(0)

        # Page title
        title = QLabel("CONFIGURATION SCROLL")
        title.setFont(QFont("monospace", 14, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{C_GOLD_BRIGHT}; background:transparent; letter-spacing:4px;"
        )
        root.addWidget(title)
        root.addSpacing(10)
        root.addWidget(_Divider(C_GOLD))
        root.addSpacing(16)

        # ── CHARACTER ─────────────────────────────────────────────────────────
        root.addWidget(_section_header("CHARACTER"))
        root.addSpacing(8)
        root.addWidget(_field_label("Hero Name"))
        self._name_field = _input("What the realm calls thee")
        root.addWidget(self._name_field)
        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── GROQ ──────────────────────────────────────────────────────────────
        root.addWidget(_section_header("GROQ  ·  DYNAMIC ROASTS"))
        root.addSpacing(8)

        for lbl, attr, ph, pw in [
            ("API Key", "_groq_key", "gsk_...", True),
            ("Model", "_groq_model", "llama3-70b-8192", False),
        ]:
            root.addWidget(_field_label(lbl))
            inp = _input(ph, pw)
            setattr(self, attr, inp)
            root.addWidget(inp)
            root.addSpacing(8)

        root.addSpacing(6)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── VOICE ─────────────────────────────────────────────────────────────
        root.addWidget(_section_header("VOICE  ·  CARTESIA → ELEVENLABS FALLBACK"))
        root.addSpacing(8)

        for lbl, attr, ph, pw in [
            ("Cartesia API Key", "_cartesia_key", "sk_car_...", True),
            (
                "Cartesia Voice ID",
                "_cartesia_voice_id",
                "dded70d9-73b5-4c77-b76c-97e3c86a6705",
                False,
            ),
            ("ElevenLabs API Key", "_eleven_key", "...", True),
            ("ElevenLabs Voice ID", "_eleven_voice_id", "pNInz6obbfDQGcgMyIGb", False),
        ]:
            root.addWidget(_field_label(lbl))
            inp = _input(ph, pw)
            setattr(self, attr, inp)
            root.addWidget(inp)
            root.addSpacing(8)

        root.addSpacing(6)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── ROAST INTENSITY ───────────────────────────────────────────────────
        root.addWidget(_section_header("SOLDIER BOY INTENSITY"))
        root.addSpacing(8)

        self._int_group = QButtonGroup(self)
        self._int_group.setExclusive(True)
        int_row = QHBoxLayout()
        int_row.setSpacing(0)

        for val, label, sub, border, col in [
            (1, "·  MILD", "Grudging respect. Safe-ish.", C_RULE, C_GREEN),
            (2, "·· SAVAGE", "Full Soldier Boy. No filter.", C_RULE_GOLD, C_GOLD),
            (3, "··· NUCLEAR", "Completely unhinged. Godspeed.", "#4a1010", C_RED),
        ]:
            tile = QWidget()
            tile.setStyleSheet(f"background:{C_SURFACE}; border:1px solid {border};")
            tl = QVBoxLayout(tile)
            tl.setContentsMargins(14, 10, 14, 10)
            tl.setSpacing(2)

            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFont(QFont("monospace", 9, QFont.Weight.Bold))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{col};
                    border:none; text-align:left; padding:0;
                }}
                QPushButton:checked {{ color:{C_GOLD_BRIGHT}; }}
            """)
            btn.clicked.connect(
                lambda _, v=val: self._cfg.ai.__setattr__("roast_intensity", v)
            )
            self._int_group.addButton(btn, val)
            self._int_btns[val] = btn

            s = QLabel(sub)
            s.setFont(QFont("monospace", 7))
            s.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")

            tl.addWidget(btn)
            tl.addWidget(s)
            int_row.addWidget(tile)

        root.addLayout(int_row)
        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── SPRITE ────────────────────────────────────────────────────────────
        root.addWidget(_section_header("SPRITE SCALE"))
        root.addSpacing(8)

        scale_row = QHBoxLayout()
        scale_row.setSpacing(12)
        scale_lbl = _field_label("Display Scale")
        scale_lbl.setFixedWidth(100)
        self._scale_slider = QSlider(Qt.Orientation.Horizontal)
        self._scale_slider.setRange(2, 5)
        self._scale_slider.setTickInterval(1)
        self._scale_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background:{C_RULE}; height:2px;
            }}
            QSlider::handle:horizontal {{
                background:{C_GOLD}; width:14px; height:14px;
                border-radius:7px; margin:-6px 0;
            }}
            QSlider::sub-page:horizontal {{ background:{C_GOLD_DIM}; }}
        """)
        self._scale_val = QLabel("3×")
        self._scale_val.setFont(QFont("monospace", 9))
        self._scale_val.setStyleSheet(f"color:{C_GOLD}; background:transparent;")
        self._scale_val.setFixedWidth(28)
        self._scale_slider.valueChanged.connect(
            lambda v: self._scale_val.setText(f"{v}×")
        )
        scale_row.addWidget(scale_lbl)
        scale_row.addWidget(self._scale_slider, stretch=1)
        scale_row.addWidget(self._scale_val)
        root.addLayout(scale_row)
        root.addSpacing(24)
        root.addWidget(_Divider(C_RULE_GOLD))
        root.addSpacing(16)

        # ── BACKUP & EXPORT ───────────────────────────────────────────────────
        root.addWidget(_section_header("DATA  ·  BACKUP & EXPORT"))
        root.addSpacing(8)

        # Action buttons row
        backup_row = QHBoxLayout()
        backup_row.setSpacing(10)
        for label, fn_name in [
            ("💾  Backup Now", "_do_backup"),
            ("📤  Export JSON", "_do_export_json"),
            ("📊  Export CSV", "_do_export_csv"),
        ]:
            btn = QPushButton(label)
            btn.setFont(QFont("monospace", 9))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{C_SURFACE}; color:{C_INK_DIM};
                    border:1px solid {C_RULE}; padding:8px 14px;
                }}
                QPushButton:hover {{
                    color:{C_GOLD}; border-color:{C_RULE_GOLD};
                    background:#1e1206;
                }}
            """)
            btn.clicked.connect(getattr(self, fn_name))
            backup_row.addWidget(btn)
        backup_row.addStretch()
        root.addLayout(backup_row)

        self._backup_status = QLabel("")
        self._backup_status.setFont(QFont("monospace", 8))
        self._backup_status.setStyleSheet(f"background:transparent;")
        root.addWidget(self._backup_status)
        root.addSpacing(12)

        # FIX 2: Backup restore list
        restore_lbl = _field_label("Restore from backup  (click to restore)")
        root.addWidget(restore_lbl)
        root.addSpacing(4)

        self._backup_list_layout = QVBoxLayout()
        self._backup_list_layout.setSpacing(3)
        root.addLayout(self._backup_list_layout)
        self._refresh_backup_list()
        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── SOUNDS ────────────────────────────────────────────────────────────
        root.addWidget(_section_header("SOUNDS"))
        root.addSpacing(8)

        sounds_row = QHBoxLayout()
        sounds_row.setSpacing(10)
        self._sounds_btn = QPushButton("✦  Sounds Enabled")
        self._sounds_btn.setCheckable(True)
        self._sounds_btn.setChecked(True)
        self._sounds_btn.setFont(QFont("monospace", 9))
        self._sounds_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_SURFACE}; color:{C_INK_FAINT};
                border:1px solid {C_RULE}; padding:8px 18px;
            }}
            QPushButton:checked {{
                color:{C_GOLD}; border-color:{C_RULE_GOLD};
                background:#1e1206;
            }}
        """)
        self._sounds_btn.toggled.connect(self._toggle_sounds)
        sounds_row.addWidget(self._sounds_btn)
        sounds_row.addStretch()
        root.addLayout(sounds_row)
        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── HOTKEY ────────────────────────────────────────────────────────────
        root.addWidget(_section_header("GLOBAL HOTKEY"))
        root.addSpacing(8)

        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(12)
        hotkey_lbl = _field_label("Trigger combo  (default: Ctrl+Shift+L)")
        hotkey_lbl.setFixedWidth(260)
        self._hotkey_field = _input("<ctrl>+<shift>+l")
        self._hotkey_field.setFixedWidth(200)
        hotkey_hint = QLabel("Requires pynput · pip install pynput")
        hotkey_hint.setFont(QFont("monospace", 7))
        hotkey_hint.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
        hotkey_row.addWidget(hotkey_lbl)
        hotkey_row.addWidget(self._hotkey_field)
        hotkey_row.addWidget(hotkey_hint)
        hotkey_row.addStretch()
        root.addLayout(hotkey_row)
        root.addSpacing(14)
        root.addWidget(_Divider(C_RULE))
        root.addSpacing(14)

        # ── SAVE ──────────────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.setSpacing(14)
        self._save_btn = QPushButton("✦  Inscribe the Configuration")
        self._save_btn.setFont(QFont("monospace", 10, QFont.Weight.Bold))
        self._save_btn.setFixedWidth(260)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_SURFACE}; color:{C_GOLD};
                border:1px solid {C_RULE_GOLD}; padding:10px 0;
                letter-spacing:1px;
            }}
            QPushButton:hover {{
                background:#1e1206; border-color:{C_GOLD}; color:{C_GOLD_BRIGHT};
            }}
        """)
        self._save_btn.clicked.connect(self._save)

        self._save_status = QLabel("")
        self._save_status.setFont(QFont("monospace", 9))
        self._save_status.setStyleSheet(f"background:transparent;")

        save_row.addWidget(self._save_btn)
        save_row.addWidget(self._save_status)
        save_row.addStretch()
        root.addLayout(save_row)
        root.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _do_backup(self):
        from core.backup import create_backup

        bpath = create_backup("manual")
        if bpath:
            self._backup_status.setText(f"✦  Backup: {os.path.basename(bpath)}")
            self._backup_status.setStyleSheet(
                f"color:{C_GREEN}; background:transparent;"
            )
            self._refresh_backup_list()
        else:
            self._backup_status.setText("✗  Backup failed.")
            self._backup_status.setStyleSheet(f"color:{C_RED}; background:transparent;")
        from PySide6.QtCore import QTimer

        QTimer.singleShot(4000, lambda: self._backup_status.setText(""))

    def _do_export_json(self):
        import subprocess

        from core.backup import export_json

        export_dir = os.path.expanduser(
            f"~/ChronicForge_export_{__import__('datetime').date.today().isoformat()}"
        )
        bpath = export_json(export_dir)
        self._backup_status.setText(f"✦  JSON saved")
        self._backup_status.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
        self._show_open_folder(export_dir)

    def _do_export_csv(self):
        from core.backup import export_csv

        export_dir = os.path.expanduser(
            f"~/ChronicForge_export_{__import__('datetime').date.today().isoformat()}"
        )
        bpath = export_csv(export_dir)
        self._backup_status.setText(f"✦  CSV saved")
        self._backup_status.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
        self._show_open_folder(export_dir)

    def _show_open_folder(self, folder_path: str):
        """FIX 3: Show open-folder button after export."""
        from PySide6.QtCore import QTimer

        btn = QPushButton(f"📁  Open: {os.path.basename(folder_path)}")
        btn.setFont(QFont("monospace", 8))
        btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{C_GOLD_DIM};
                border:1px solid {C_RULE}; padding:4px 12px;
            }}
            QPushButton:hover {{ color:{C_GOLD}; border-color:{C_RULE_GOLD}; }}
        """)
        btn.clicked.connect(
            lambda: __import__("subprocess").run(["xdg-open", folder_path], check=False)
        )
        # Insert below backup_status label
        idx = self._backup_list_layout.count()
        self._backup_list_layout.insertWidget(idx, btn)
        # Auto-remove after 30s
        QTimer.singleShot(30_000, lambda: (btn.setParent(None), btn.deleteLater()))

    def _refresh_backup_list(self):
        """FIX 2: Show clickable restore list of available backups."""
        # Clear existing items
        while self._backup_list_layout.count():
            item = self._backup_list_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()

        from core.backup import list_backups, restore_backup

        backups = list_backups()[:8]  # show last 8

        if not backups:
            empty = QLabel("No backups yet. Create one above.")
            empty.setFont(QFont("monospace", 8))
            empty.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
            self._backup_list_layout.addWidget(empty)
            return

        for b in backups:
            row = QHBoxLayout()
            row.setSpacing(10)

            name_lbl = QLabel(
                b["filename"].replace("chronicforge_", "").replace(".db", "")
            )
            name_lbl.setFont(QFont("monospace", 8))
            name_lbl.setStyleSheet(f"color:{C_INK_DIM}; background:transparent;")
            name_lbl.setFixedWidth(200)

            size_lbl = QLabel(f"{b['size_kb']} KB")
            size_lbl.setFont(QFont("monospace", 8))
            size_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
            size_lbl.setFixedWidth(60)

            restore_btn = QPushButton("Restore")
            restore_btn.setFont(QFont("monospace", 8))
            restore_btn.setFixedWidth(70)
            restore_btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{C_INK_FAINT};
                    border:1px solid {C_RULE}; padding:3px 0;
                }}
                QPushButton:hover {{
                    color:{C_RED}; border-color:{C_RED};
                    background:#1e0808;
                }}
            """)
            bpath = b["path"]
            restore_btn.clicked.connect(lambda _, p=bpath: self._do_restore(p))

            row.addWidget(name_lbl)
            row.addWidget(size_lbl)
            row.addStretch()
            row.addWidget(restore_btn)

            container = QWidget()
            container.setStyleSheet("background:transparent;")
            container.setMaximumHeight(24)
            container.setLayout(row)
            self._backup_list_layout.addWidget(container)

    def _do_restore(self, backup_path: str):
        """Restore from a backup file with confirmation."""
        from PySide6.QtWidgets import QMessageBox

        from core.backup import restore_backup

        msg = QMessageBox(self)
        msg.setWindowTitle("Restore Backup")
        msg.setText(
            f"Restore from:\n{os.path.basename(backup_path)}\n\nCurrent data will be backed up first."
        )
        msg.setStyleSheet(f"background:{C_BG}; color:{C_INK};")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            ok = restore_backup(backup_path)
            self._backup_status.setText(
                "✦  Restored. Restart ChronicForge to apply."
                if ok
                else "✗  Restore failed."
            )
            col = C_GREEN if ok else C_RED
            self._backup_status.setStyleSheet(f"color:{col}; background:transparent;")

    def _toggle_sounds(self, enabled: bool):
        self._sounds_btn.setText(
            "✦  Sounds Enabled" if enabled else "·  Sounds Disabled"
        )
        try:
            from config.settings import load_config, save_config

            cfg = load_config()
            cfg.sounds_enabled = enabled  # FIX 1: proper dataclass field
            save_config(cfg)
        except Exception:
            pass

    def _load_values(self):
        try:
            from core.game_logic import get_character

            self._name_field.setText(get_character().get("name", "Hero"))
        except Exception:
            self._name_field.setText("Hero")

        self._groq_key.setText(
            os.environ.get("GROQ_API_KEY", "") or self._cfg.ai.groq_api_key
        )
        self._groq_model.setText(self._cfg.ai.groq_model)
        self._cartesia_key.setText(os.environ.get("CARTESIA_API_KEY", ""))
        self._cartesia_voice_id.setText(
            os.environ.get("CARTESIA_VOICE_ID", "dded70d9-73b5-4c77-b76c-97e3c86a6705")
        )
        self._eleven_key.setText(os.environ.get("ELEVENLABS_API_KEY", ""))
        self._eleven_voice_id.setText(
            os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obbfDQGcgMyIGb")
        )

        btn = self._int_btns.get(self._cfg.ai.roast_intensity)
        if btn:
            btn.setChecked(True)

        self._scale_slider.setValue(self._cfg.sprite.scale)
        self._scale_val.setText(f"{self._cfg.sprite.scale}×")
        self._sounds_btn.setChecked(self._cfg.sounds_enabled)
        self._sounds_btn.setText(
            "✦  Sounds Enabled" if self._cfg.sounds_enabled else "·  Sounds Disabled"
        )
        if hasattr(self, "_hotkey_field"):
            self._hotkey_field.setText(getattr(self._cfg, "hotkey", "<ctrl>+<shift>+l"))

    def _save(self):
        name = self._name_field.text().strip() or "Hero"
        try:
            from core.game_logic import set_character_name

            set_character_name(name)
        except Exception:
            pass

        self._cfg.ai.groq_api_key = self._groq_key.text().strip()
        self._cfg.ai.groq_model = self._groq_model.text().strip() or "llama3-70b-8192"
        self._cfg.sprite.scale = self._scale_slider.value()
        if hasattr(self, "_hotkey_field"):
            self._cfg.hotkey = self._hotkey_field.text().strip() or "<ctrl>+<shift>+l"

        for env_key, widget in [
            ("CARTESIA_API_KEY", self._cartesia_key),
            ("CARTESIA_VOICE_ID", self._cartesia_voice_id),
            ("ELEVENLABS_API_KEY", self._eleven_key),
            ("ELEVENLABS_VOICE_ID", self._eleven_voice_id),
            ("GROQ_API_KEY", self._groq_key),
        ]:
            v = widget.text().strip()
            if v:
                os.environ[env_key] = v

        save_config(self._cfg)
        event_bus.config_saved.emit()

        self._save_status.setText("✦  Configuration inscribed.")
        self._save_status.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
        QTimer_ref = __import__("PySide6.QtCore", fromlist=["QTimer"]).QTimer
        QTimer_ref.singleShot(3000, lambda: self._save_status.setText(""))
