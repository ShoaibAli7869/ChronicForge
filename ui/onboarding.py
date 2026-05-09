"""
ChronicForge — First Run Onboarding
Uses config.toml for persistence — no hidden flag files.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from config.settings import (
    is_onboarding_done,
    load_config,
    mark_onboarding_done,
    save_config,
)

STYLE = """
QDialog { background:#0d0702; }
QLabel  { color:#e8d5a3; font-family:monospace; }
QLineEdit {
    background:#1a0f05; color:#f5c842;
    border:none; border-bottom:1px solid #4a3010;
    font-family:monospace; font-size:14px; padding:10px 14px;
}
QLineEdit:focus { border-bottom-color:#c8a020; }
"""

INT_BTN = """
QPushButton {{
    background:#110a03; color:{color};
    border:2px solid {border}; font-family:monospace;
    font-size:9px; padding:14px 8px;
}}
QPushButton:checked {{ background:#1e1204; border-color:{color}; }}
QPushButton:hover   {{ background:#1a0f04; }}
"""

CONFIRM = """
QPushButton {
    background:#1e1204; color:#f5c842;
    border:1px solid #8b6010; font-family:monospace;
    font-size:12px; font-weight:bold; padding:12px 32px;
    letter-spacing:1px;
}
QPushButton:hover { background:#2e1e08; border-color:#c8a020; }
"""


class OnboardingDialog(QDialog):
    def __init__(self, assets_dir: str, parent=None):
        super().__init__(parent)
        self._intensity = 2
        self.setWindowTitle("ChronicForge — Begin Thy Legend")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet(STYLE)
        self.setFixedSize(500, 560)
        self._build(assets_dir)

    def _build(self, assets_dir: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(0)

        # Portrait
        portrait = QLabel()
        portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        px_path = os.path.join(assets_dir, "male_hero-design.png")
        if os.path.exists(px_path):
            px = QPixmap(px_path).scaled(
                96,
                96,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            portrait.setPixmap(px)
        else:
            portrait.setText("⚔")
            portrait.setFont(QFont("monospace", 48))
            portrait.setStyleSheet("color:#c8a020;")
        root.addWidget(portrait)
        root.addSpacing(18)

        title = QLabel("FORGE THY LEGEND")
        title.setFont(QFont("monospace", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#f5c842; letter-spacing:4px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        sub = QLabel("Name thy hero. Choose thy Soldier Boy's intensity.")
        sub.setFont(QFont("monospace", 9))
        sub.setStyleSheet("color:#3a2810;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub)
        root.addSpacing(28)

        # Name
        name_lbl = QLabel("HERO NAME")
        name_lbl.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color:#3a2810; letter-spacing:3px;")
        self._name = QLineEdit()
        self._name.setPlaceholderText("What shall the realm call thee?")
        self._name.setText("Hero")
        self._name.selectAll()
        root.addWidget(name_lbl)
        root.addSpacing(6)
        root.addWidget(self._name)
        root.addSpacing(24)

        # Intensity
        int_lbl = QLabel("SOLDIER BOY INTENSITY")
        int_lbl.setFont(QFont("monospace", 7, QFont.Weight.Bold))
        int_lbl.setStyleSheet("color:#3a2810; letter-spacing:3px;")
        root.addWidget(int_lbl)
        root.addSpacing(8)

        self._int_group = QButtonGroup(self)
        self._int_group.setExclusive(True)
        int_row = QHBoxLayout()
        int_row.setSpacing(10)

        for val, label, desc, color, border in [
            (1, "MILD", "Grudging respect.\nSafe for work.", "#50a030", "#1a3010"),
            (2, "SAVAGE", "Full Soldier Boy.\nNo mercy.", "#c8a020", "#4a3010"),
            (3, "NUCLEAR", "Completely unhinged.\nGodspeed.", "#c04040", "#4a1010"),
        ]:
            btn = QPushButton(f"{label}\n\n{desc}")
            btn.setCheckable(True)
            btn.setChecked(val == 2)
            btn.setFont(QFont("monospace", 9))
            btn.setStyleSheet(INT_BTN.format(color=color, border=border))
            btn.clicked.connect(lambda _, v=val: setattr(self, "_intensity", v))
            self._int_group.addButton(btn, val)
            int_row.addWidget(btn)
        root.addLayout(int_row)
        root.addSpacing(30)

        confirm = QPushButton("⚔  BEGIN THE CHRONICLE")
        confirm.setStyleSheet(CONFIRM)
        confirm.clicked.connect(self._confirm)
        root.addWidget(confirm, alignment=Qt.AlignmentFlag.AlignCenter)

    def _confirm(self):
        name = self._name.text().strip() or "Hero"
        try:
            from core.game_logic import set_character_name

            set_character_name(name)
        except Exception:
            pass
        cfg = load_config()
        cfg.ai.roast_intensity = self._intensity
        cfg.onboarding_done = True  # FIX: stored in TOML
        save_config(cfg)
        # Remove legacy flag file if it exists
        old_flag = os.path.join(
            os.path.expanduser("~/.config/chronicforge"), ".onboarding_done"
        )
        if os.path.exists(old_flag):
            os.unlink(old_flag)
        self.accept()

    @staticmethod
    def is_done() -> bool:
        return is_onboarding_done()  # uses TOML + legacy migration
