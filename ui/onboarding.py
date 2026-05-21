"""
ChronicForge — First Run Onboarding
Illuminated Parchment theme matching the rest of the app.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
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
    save_config,
)
from ui.theme import (
    C_BG,
    C_CRIMSON,
    C_GOLD,
    C_GOLD_BRIGHT,
    C_INK,
    C_INK_FAINT,
    C_INK_MID,
    C_RULE,
    C_RULE_GOLD,
    C_SURFACE,
    Divider,
    font_cinzel,
    font_mono,
    font_serif,
)


# ── Stylesheets ───────────────────────────────────────────────────────────────
DIALOG_STYLE = f"""
QDialog {{
    background: {C_BG};
    border: 1px solid {C_RULE_GOLD};
}}
QLabel {{
    color: {C_INK};
    background: transparent;
}}
QLineEdit {{
    background: {C_SURFACE};
    color: {C_INK};
    border: none;
    border-bottom: 1px solid {C_RULE_GOLD};
    padding: 8px 12px;
    selection-background-color: {C_RULE};
}}
QLineEdit:focus {{
    border-bottom-color: {C_CRIMSON};
    background: {C_BG};
    color: {C_GOLD_BRIGHT};
}}
"""


def _intensity_btn_style(accent: str, border: str) -> str:
    return f"""
    QPushButton {{
        background: {C_SURFACE};
        color: {accent};
        border: 1px solid {border};
        padding: 18px 10px;
        text-align: center;
    }}
    QPushButton:hover {{
        background: #d5cca8;
        border-color: {accent};
    }}
    QPushButton:checked {{
        background: #d5cca8;
        border: 2px solid {accent};
        color: {C_GOLD_BRIGHT};
    }}
    """


CONFIRM_STYLE = f"""
QPushButton {{
    background: {C_SURFACE};
    color: {C_CRIMSON};
    border: 1px solid {C_CRIMSON};
    padding: 14px 36px;
    letter-spacing: 2px;
}}
QPushButton:hover {{
    background: #d5cca8;
    color: {C_GOLD_BRIGHT};
    border-color: {C_GOLD};
}}
QPushButton:pressed {{
    background: {C_RULE};
}}
"""


class _PortraitFrame(QLabel):
    """Round portrait surrounded by a thin double-ring border."""

    def __init__(self, pixmap: QPixmap | None, size: int = 110, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size + 8, size + 8)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if pixmap and not pixmap.isNull():
            self._px = pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            self._px = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2
        r_outer = self._size // 2 + 3
        r_inner = self._size // 2

        # Outer crimson ring
        p.setPen(QPen(QColor(C_CRIMSON), 1))
        p.drawEllipse(cx - r_outer, cy - r_outer, r_outer * 2, r_outer * 2)
        # Inner gold ring
        p.setPen(QPen(QColor(C_RULE_GOLD), 1))
        p.drawEllipse(cx - r_inner, cy - r_inner, r_inner * 2, r_inner * 2)

        if self._px:
            x = cx - self._px.width() // 2
            y = cy - self._px.height() // 2
            p.drawPixmap(x, y, self._px)
        else:
            p.setPen(QPen(QColor(C_GOLD), 1))
            p.setFont(font_serif(34, QFont.Weight.Bold))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "⚔")
        p.end()

    def update_pixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            self._px = pixmap.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            self._px = None
        self.update()


class OnboardingDialog(QDialog):
    def __init__(self, assets_dir: str, parent=None):
        super().__init__(parent)
        self._intensity = 2
        self._character = "male_hero"
        self._assets_dir = ""
        self._int_buttons: dict[int, QPushButton] = {}
        self.setWindowTitle("ChronicForge — Begin Thy Legend")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet(DIALOG_STYLE)
        self.setFixedSize(560, 740)
        self._build(assets_dir)

    def _build(self, assets_dir: str):
        self._assets_dir = assets_dir
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 40, 48, 36)
        root.setSpacing(0)

        # ── Portrait ──────────────────────────────────────────────────────────
        px_path = os.path.join(assets_dir, "male_hero-design.png")
        portrait_pix = QPixmap(px_path) if os.path.exists(px_path) else None
        self._portrait = _PortraitFrame(portrait_pix)
        portrait_row = QHBoxLayout()
        portrait_row.addStretch()
        portrait_row.addWidget(self._portrait)
        portrait_row.addStretch()
        root.addLayout(portrait_row)
        root.addSpacing(18)

        # ── Title + subtitle ──────────────────────────────────────────────────
        title = QLabel("FORGE THY LEGEND")
        title.setFont(font_cinzel(15, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{C_CRIMSON}; background:transparent; letter-spacing:6px;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        root.addSpacing(6)

        sub = QLabel("Name thy hero. Choose thy Soldier Boy's intensity.")
        sub.setFont(font_serif(10, italic=True))
        sub.setStyleSheet(f"color:{C_INK_MID}; background:transparent;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub)
        root.addSpacing(10)
        root.addWidget(Divider(variant="primary"))
        root.addSpacing(16)

        # ── Character ─────────────────────────────────────────────────────────
        char_lbl = QLabel("CHARACTER")
        char_lbl.setFont(font_cinzel(7, QFont.Weight.Bold))
        char_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px;"
        )
        root.addWidget(char_lbl)
        root.addSpacing(10)

        self._char_group = QButtonGroup(self)
        self._char_group.setExclusive(True)
        char_row = QHBoxLayout()
        char_row.setSpacing(12)

        for char_val, char_label in [
            ("male_hero",   "♂   MALE"),
            ("female_hero", "♀   FEMALE"),
        ]:
            btn = QPushButton(char_label)
            btn.setCheckable(True)
            btn.setChecked(char_val == "male_hero")
            btn.setFont(font_mono(10, QFont.Weight.Bold))
            btn.setStyleSheet(_intensity_btn_style(C_GOLD, C_RULE_GOLD))
            btn.setMinimumHeight(52)
            btn.clicked.connect(lambda _, c=char_val: self._on_character_select(c))
            self._char_group.addButton(btn)
            char_row.addWidget(btn)

        root.addLayout(char_row)
        root.addSpacing(16)
        root.addWidget(Divider(variant="secondary"))
        root.addSpacing(16)

        # ── Hero name ─────────────────────────────────────────────────────────
        name_lbl = QLabel("HERO NAME")
        name_lbl.setFont(font_cinzel(7, QFont.Weight.Bold))
        name_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px;"
        )
        root.addWidget(name_lbl)
        root.addSpacing(8)

        self._name = QLineEdit()
        self._name.setPlaceholderText("What shall the realm call thee?")
        self._name.setText("Hero")
        self._name.setFont(font_serif(13))
        self._name.setFixedHeight(40)
        self._name.selectAll()
        root.addWidget(self._name)
        root.addSpacing(26)

        # ── Intensity ─────────────────────────────────────────────────────────
        int_lbl = QLabel("SOLDIER BOY INTENSITY")
        int_lbl.setFont(font_cinzel(7, QFont.Weight.Bold))
        int_lbl.setStyleSheet(
            f"color:{C_INK_FAINT}; background:transparent; letter-spacing:4px;"
        )
        root.addWidget(int_lbl)
        root.addSpacing(10)

        self._int_group = QButtonGroup(self)
        self._int_group.setExclusive(True)
        int_row = QHBoxLayout()
        int_row.setSpacing(12)

        for val, label, desc, accent, border in [
            (1, "·  MILD", "Grudging respect.\nSafe for work.", "#2a6a30", C_RULE),
            (2, "··  SAVAGE", "Full Soldier Boy.\nNo mercy.", C_GOLD, C_RULE_GOLD),
            (3, "···  NUCLEAR", "Completely unhinged.\nGodspeed.", C_CRIMSON, "#6a1818"),
        ]:
            btn = QPushButton(f"{label}\n\n{desc}")
            btn.setCheckable(True)
            btn.setChecked(val == 2)
            btn.setFont(font_mono(9, QFont.Weight.Bold))
            btn.setStyleSheet(_intensity_btn_style(accent, border))
            btn.setMinimumHeight(96)
            btn.clicked.connect(lambda _, v=val: setattr(self, "_intensity", v))
            self._int_group.addButton(btn, val)
            self._int_buttons[val] = btn
            int_row.addWidget(btn)
        root.addLayout(int_row)
        root.addSpacing(28)
        root.addWidget(Divider(variant="secondary"))
        root.addSpacing(20)

        # ── Confirm button ────────────────────────────────────────────────────
        confirm = QPushButton("✦   BEGIN  THE  CHRONICLE   ✦")
        confirm.setFont(font_serif(11, QFont.Weight.Bold))
        confirm.setStyleSheet(CONFIRM_STYLE)
        confirm.setMinimumWidth(320)
        confirm.clicked.connect(self._confirm)
        confirm_row = QHBoxLayout()
        confirm_row.addStretch()
        confirm_row.addWidget(confirm)
        confirm_row.addStretch()
        root.addLayout(confirm_row)
        root.addStretch()

    def _on_character_select(self, character: str):
        self._character = character
        px_path = os.path.join(self._assets_dir, f"{character}-design.png")
        pix = QPixmap(px_path) if os.path.exists(px_path) else None
        self._portrait.update_pixmap(pix)

    def _confirm(self):
        name = self._name.text().strip() or "Hero"
        try:
            from core.game_logic import set_character_name

            set_character_name(name)
        except Exception:
            pass
        cfg = load_config()
        cfg.ai.roast_intensity = self._intensity
        cfg.sprite.character = self._character
        cfg.onboarding_done = True
        save_config(cfg)
        # Remove legacy flag file if it exists
        old_flag = os.path.join(
            os.path.expanduser("~/.config/chronicforge"), ".onboarding_done"
        )
        if os.path.exists(old_flag):
            try:
                os.unlink(old_flag)
            except OSError:
                pass
        self.accept()

    @staticmethod
    def is_done() -> bool:
        return is_onboarding_done()
