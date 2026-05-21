"""
ChronicForge — Sprite Engine  (v3)
- 24 animations, auto-detected frame counts
- 60fps physics: gravity, jump, floor snap, bounce
- Animation-matched walk/run speeds
- Proactive time-aware remarks (morning/evening/nudge)
- Production right-click menu (no test buttons)
- Double-click → opens dashboard log tab
"""

import math
import os
import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Callable, Optional

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from utils.signals import event_bus

# ── Constants ─────────────────────────────────────────────────────────────────
FRAME_SIZE = 128
SPRITE_SCALE = 3  # default; overridden per-instance from config
BOTTOM_PADDING = 28  # Transparent pixels at the bottom of the 128x128 frame
DT = 1 / 60.0
WALK_SPEED = 84.0
RUN_SPEED = 279.0
GRAVITY = 2200.0
JUMP_V0 = -660.0
BOUNCE_DAMP = 0.25


# ── States ────────────────────────────────────────────────────────────────────
class SpriteState(Enum):
    IDLE = auto()
    IDLE_TURN = auto()
    WALK = auto()
    WALK_TURN = auto()
    RUN = auto()
    RUN_TURN = auto()
    RUN_TO_IDLE = auto()
    JUMP = auto()
    FALL = auto()
    FALL_LOOP = auto()
    DASH = auto()
    SLIDE = auto()
    WALL_SLIDE = auto()
    WALL_JUMP = auto()
    LEDGE_HANG = auto()
    LEDGE_CLIMB = auto()
    HURT = auto()
    DEATH = auto()
    COMBO_1 = auto()
    COMBO_1_END = auto()
    COMBO_2 = auto()
    COMBO_2_END = auto()
    COMBO_3 = auto()
    COMBO_3_END = auto()


AIRBORNE = {
    SpriteState.JUMP,
    SpriteState.FALL,
    SpriteState.FALL_LOOP,
    SpriteState.WALL_JUMP,
    SpriteState.WALL_SLIDE,
}
LOCKED = {
    SpriteState.HURT,
    SpriteState.DEATH,
    SpriteState.DASH,
    SpriteState.COMBO_1,
    SpriteState.COMBO_2,
    SpriteState.COMBO_3,
    SpriteState.LEDGE_CLIMB,
}


@dataclass
class AnimConfig:
    file: str
    frames: int
    fps: int
    loop: bool
    pingpong: bool = False


def build_anim_map(prefix: str) -> dict:
    def a(name, fps, loop, pingpong=False):
        return AnimConfig(f"{prefix}-{name}.png", 0, fps, loop, pingpong)
    return {
        SpriteState.IDLE:         a("idle",         8,  True),
        SpriteState.IDLE_TURN:    a("idle_turn",     8,  False),
        SpriteState.WALK:         a("walk",          10, True),
        SpriteState.WALK_TURN:    a("walk_turn",     10, False),
        SpriteState.RUN:          a("run",           14, True),
        SpriteState.RUN_TURN:     a("run_turn",      12, False),
        SpriteState.RUN_TO_IDLE:  a("run_to_idle",   10, False),
        SpriteState.JUMP:         a("jump",          10, False),
        SpriteState.FALL:         a("fall",          10, False),
        SpriteState.FALL_LOOP:    a("fall_loop",     8,  True),
        SpriteState.DASH:         a("dash",          16, False),
        SpriteState.SLIDE:        a("slide",         10, False),
        SpriteState.WALL_SLIDE:   a("wall_slide",    8,  True),
        SpriteState.WALL_JUMP:    a("wall_jump",     10, False),
        SpriteState.LEDGE_HANG:   a("ledge_hang",    6,  True),
        SpriteState.LEDGE_CLIMB:  a("ledge_climb",   10, False),
        SpriteState.HURT:         a("hurt",          10, False),
        SpriteState.DEATH:        a("death",         8,  False),
        SpriteState.COMBO_1:      a("combo_1",       13, False),
        SpriteState.COMBO_1_END:  a("combo_1_end",   11, False),
        SpriteState.COMBO_2:      a("combo_2",       13, False),
        SpriteState.COMBO_2_END:  a("combo_2_end",   11, False),
        SpriteState.COMBO_3:      a("combo_3",       13, False),
        SpriteState.COMBO_3_END:  a("combo_3_end",   11, False),
    }


# ── Speech bubble ─────────────────────────────────────────────────────────────
class SpeechBubble(QWidget):
    def __init__(self, text: str, anchor: QWidget):
        super().__init__(None)
        self._anchor = anchor
        self._alpha = 0
        self._phase = "in"

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._font = QFont("monospace", 10, QFont.Weight.Bold)
        fm = QFontMetrics(self._font)
        lines = self._wrap(text, fm, 250)
        self._lines = lines
        bw = min(max(fm.horizontalAdvance(l) for l in lines) + 28, 278)
        bh = len(lines) * (fm.height() + 3) + 22
        self._bw, self._bh = bw, bh
        self.setFixedSize(bw + 16, bh + 18)

        self._reposition()
        self.show()

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(lambda: setattr(self, "_phase", "out"))
        self._hold.start(4200)

    def _wrap(self, text, fm, max_w):
        words, lines, cur = text.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if fm.horizontalAdvance(t) <= max_w:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or [text]

    def _reposition(self):
        geo = self._anchor.geometry()
        screen = QApplication.primaryScreen().availableGeometry()
        x = geo.center().x() - self.width() // 2
        y = geo.top() - self.height() - 6
        if y < screen.top() + 4:
            y = geo.bottom() + 6
        x = max(4, min(x, screen.right() - self.width() - 4))
        self.move(x, y)

    def _tick(self):
        if self._phase == "in":
            self._alpha = min(255, self._alpha + 22)
            if self._alpha >= 255:
                self._phase = "hold"
        elif self._phase == "out":
            self._alpha = max(0, self._alpha - 18)
            if self._alpha == 0:
                self._timer.stop()
                self.close()
                self.deleteLater()
                return
        self._reposition()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._alpha / 255)
        bw, bh = self._bw, self._bh
        mid = bw // 2

        # Outer glow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(200, 150, 40, 30)))
        p.drawRoundedRect(-3, -3, bw + 6, bh + 6, 12, 12)

        # Body
        p.setBrush(QBrush(QColor(10, 6, 2, 248)))
        p.setPen(QPen(QColor(180, 130, 40), 1.5))
        p.drawRoundedRect(0, 0, bw, bh, 10, 10)

        # Highlight
        p.setPen(QPen(QColor(255, 200, 80, 50), 1))
        p.drawLine(12, 2, bw - 12, 2)

        # Tail
        tail = QPainterPath()
        tail.moveTo(mid - 10, bh)
        tail.lineTo(mid + 10, bh)
        tail.lineTo(mid, bh + 15)
        tail.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(10, 6, 2, 248)))
        p.drawPath(tail)
        p.setPen(QPen(QColor(180, 130, 40), 1.5))
        p.drawLine(mid - 10, bh, mid, bh + 15)
        p.drawLine(mid + 10, bh, mid, bh + 15)

        # Text
        p.setFont(self._font)
        fm = QFontMetrics(self._font)
        lh = fm.height() + 3
        for i, line in enumerate(self._lines):
            y = 15 + i * lh
            p.setPen(QColor(0, 0, 0, 110))
            p.drawText(14, y + 1, line)
            p.setPen(QColor(245, 215, 140))
            p.drawText(13, y, line)
        p.end()


# ── Sprite widget ─────────────────────────────────────────────────────────────
class SpriteWidget(QWidget):
    def __init__(
        self,
        assets_dir: str,
        open_dashboard_fn: Callable = None,
        open_log_fn: Callable = None,
    ):
        super().__init__(None)
        self.assets_dir = assets_dir
        self._open_dashboard_fn = open_dashboard_fn
        self._open_log_fn = open_log_fn
        self._sheets: dict[SpriteState, QPixmap] = {}
        from config.settings import load_config as _lc
        _cfg = _lc()
        self._anim_map = build_anim_map(_cfg.sprite.character)

        self._state = SpriteState.IDLE
        self._frame = 0
        self._facing_right = True
        self._pending: Optional[SpriteState] = None

        # Physics
        self._px: float = 0.0
        self._py: float = 0.0
        self._vx: float = 0.0
        self._vy: float = 0.0
        self._on_floor = True
        self._floor_y: float = 0.0

        # Movement
        self._target_x: Optional[float] = None
        self._move_mode = "walk"

        # Interaction
        self._dragging = False
        self._drag_offset = QPoint()
        self._bubble: Optional[SpeechBubble] = None
        self._glow_alpha = 0
        self._glow_color = QColor(255, 200, 50)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # Read scale from config (can be overridden without restart)
        try:
            from config.settings import load_config

            self._scale = load_config().sprite.scale
        except Exception:
            self._scale = SPRITE_SCALE
        self.setFixedSize(FRAME_SIZE * self._scale, FRAME_SIZE * self._scale)

        self._load_sheets()

        # 60fps master loop
        self._loop = QTimer(self)
        self._loop.setInterval(16)
        self._loop.timeout.connect(self._tick)
        self._loop.start()

        # Animation frame timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._advance_frame)

        # Wander
        self._wander_timer = QTimer(self)
        self._wander_timer.timeout.connect(self._pick_dest)
        self._wander_timer.start(random.randint(10000, 22000))

        # Idle variety
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._idle_variety)
        self._idle_timer.start(random.randint(7000, 16000))

        # Proactive remark scheduler (checks every 5 min)
        self._remark_timer = QTimer(self)
        self._remark_timer.setInterval(5 * 60 * 1000)
        self._remark_timer.timeout.connect(self._proactive_check)
        self._remark_timer.start()

        # Event bus
        event_bus.xp_gained.connect(self._on_xp)
        event_bus.level_up.connect(self._on_level_up)
        event_bus.roast_ready.connect(self._show_bubble)
        event_bus.sprite_remark.connect(self._on_remark)
        event_bus.quest_complete.connect(self._on_quest)
        event_bus.take_damage.connect(self._on_damage)
        event_bus.victory.connect(self._on_victory)
        event_bus.config_saved.connect(self._on_config_saved)

        # Start position: bottom-right on the floor
        screen = QApplication.primaryScreen().availableGeometry()
        self._floor_y = float(
            screen.bottom() - self.height() + (BOTTOM_PADDING * self._scale)
        )
        self._px = float(screen.right() - self.width() - 50)
        self._py = self._floor_y
        self.move(int(self._px), int(self._py))

        self._apply(SpriteState.IDLE)
        self.show()

    # ── Sheet loading ─────────────────────────────────────────────────────────

    def _load_sheets(self):
        ok, missing = 0, []
        for state, cfg in self._anim_map.items():
            path = os.path.join(self.assets_dir, cfg.file)
            if not os.path.exists(path):
                missing.append(cfg.file)
                continue
            px = QPixmap(path)
            self._sheets[state] = px
            if cfg.frames == 0:
                cfg.frames = max(1, px.width() // FRAME_SIZE)
            ok += 1
        print(f"[ChronicForge] Loaded {ok}/{len(self._anim_map)} sprite sheets.")
        if missing:
            print(f"[ChronicForge] Missing sheets: {len(missing)}")

    # ── State machine ─────────────────────────────────────────────────────────

    def _apply(self, state: SpriteState, then: Optional[SpriteState] = None):
        if state not in self._sheets:
            state = SpriteState.IDLE
        self._state = state
        self._frame = 0
        self._pending = then
        cfg = self._anim_map[state]
        self._anim_timer.start(max(16, 1000 // cfg.fps))
        self.update()

    def _advance_frame(self):
        cfg = self._anim_map[self._state]
        last = cfg.frames - 1
        self._frame += 1
        if self._frame > last:
            if cfg.loop:
                self._frame = 0
            else:
                self._frame = last
                self._anim_timer.stop()
                self._on_anim_done()

    def _on_anim_done(self):
        chains = {
            SpriteState.COMBO_1: SpriteState.COMBO_1_END,
            SpriteState.COMBO_2: SpriteState.COMBO_2_END,
            SpriteState.COMBO_3: SpriteState.COMBO_3_END,
        }
        nxt = self._pending or chains.get(self._state)
        self._pending = None
        self._apply(nxt if nxt else SpriteState.IDLE)

    # ── 60fps physics tick ────────────────────────────────────────────────────

    def _tick(self):
        if self._dragging:
            self.update()
            return

        screen = QApplication.primaryScreen().availableGeometry()
        self._floor_y = float(
            screen.bottom() - self.height() + (BOTTOM_PADDING * self._scale)
        )

        # Horizontal movement
        if self._target_x is not None and self._state not in LOCKED:
            diff = self._target_x - self._px
            speed = (RUN_SPEED if self._move_mode == "run" else WALK_SPEED) * DT

            if abs(diff) <= speed + 1:
                self._px = self._target_x
                self._target_x = None
                self._vx = 0.0
                if self._state in (SpriteState.WALK, SpriteState.RUN):
                    self._apply(SpriteState.RUN_TO_IDLE, then=SpriteState.IDLE)
            else:
                new_facing = diff > 0
                move_st = (
                    SpriteState.RUN if self._move_mode == "run" else SpriteState.WALK
                )
                turn_st = (
                    SpriteState.RUN_TURN
                    if self._move_mode == "run"
                    else SpriteState.WALK_TURN
                )

                if self._state == SpriteState.IDLE:
                    if new_facing != self._facing_right:
                        self._facing_right = new_facing
                        self._apply(SpriteState.IDLE_TURN, then=move_st)
                    else:
                        self._apply(move_st)
                elif self._state in (SpriteState.WALK, SpriteState.RUN):
                    if new_facing != self._facing_right:
                        self._facing_right = new_facing
                        self._apply(turn_st, then=move_st)
                    else:
                        step = speed if diff > 0 else -speed
                        self._px += step

        # Gravity
        if not self._on_floor or self._vy < 0:
            self._vy += GRAVITY * DT
            self._py += self._vy * DT
            if self._py >= self._floor_y:
                self._py = self._floor_y
                self._vy = -self._vy * BOUNCE_DAMP if abs(self._vy) > 80 else 0.0
                self._on_floor = True
                if self._state in (
                    SpriteState.JUMP,
                    SpriteState.FALL,
                    SpriteState.FALL_LOOP,
                    SpriteState.WALL_JUMP,
                ):
                    self._apply(self._pending or SpriteState.IDLE)
            if self._vy > 60 and self._state == SpriteState.JUMP:
                self._apply(SpriteState.FALL_LOOP)
        else:
            self._py = self._floor_y
            self._vy = 0.0

        # Screen clamp
        self._px = max(
            float(screen.left()), min(self._px, float(screen.right() - self.width()))
        )

        # Glow decay
        if self._glow_alpha > 0:
            self._glow_alpha = max(0, self._glow_alpha - 5)

        self.move(int(self._px), int(self._py))
        self.update()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _get_frame(self) -> Optional[QPixmap]:
        sheet = self._sheets.get(self._state)
        if not sheet:
            return None
        cfg = self._anim_map[self._state]
        fi = max(0, min(self._frame, cfg.frames - 1))
        frame = sheet.copy(QRect(fi * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE))
        frame = frame.scaled(
            FRAME_SIZE * self._scale,
            FRAME_SIZE * self._scale,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        if not self._facing_right:
            frame = frame.transformed(QTransform().scale(-1, 1))
        return frame

    def paintEvent(self, _):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        cx, cy = self.width() // 2, self.height() // 2

        # Drop shadow
        if self._on_floor:
            sw = int(FRAME_SIZE * self._scale * 0.28)
            sh = max(4, sw // 4)
            floor_y_in_widget = self.height() - int(BOTTOM_PADDING * self._scale)
            grad = QRadialGradient(cx, floor_y_in_widget - sh // 2, sw // 2)
            grad.setColorAt(0.0, QColor(0, 0, 0, 80))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx - sw // 2, floor_y_in_widget - sh - 2, sw, sh)

        # Reaction glow
        if self._glow_alpha > 0:
            grad = QRadialGradient(cx, cy, FRAME_SIZE * self._scale * 0.45)
            c = QColor(self._glow_color)
            c.setAlpha(self._glow_alpha)
            c2 = QColor(self._glow_color)
            c2.setAlpha(0)
            grad.setColorAt(0.3, c)
            grad.setColorAt(1.0, c2)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(0, 0, self.width(), self.height())

        frame = self._get_frame()
        if frame:
            p.drawPixmap(0, 0, frame)
        p.end()

    # ── Behaviour ─────────────────────────────────────────────────────────────

    def _pick_dest(self):
        if self._state in LOCKED:
            return
        screen = QApplication.primaryScreen().availableGeometry()
        margin = self.width() // 2
        self._target_x = float(
            random.randint(margin, screen.width() - self.width() - margin)
        )
        self._move_mode = random.choice(["walk", "walk", "run"])
        self._wander_timer.setInterval(random.randint(10000, 24000))

    def _idle_variety(self):
        if self._state == SpriteState.IDLE and self._on_floor:
            self._apply(
                random.choice(
                    [
                        SpriteState.IDLE_TURN,
                        SpriteState.IDLE_TURN,
                        SpriteState.DASH,
                        SpriteState.SLIDE,
                    ]
                ),
                then=SpriteState.IDLE,
            )
        self._idle_timer.setInterval(random.randint(7000, 16000))

    def _do_jump(self, then: Optional[SpriteState] = None):
        if self._on_floor:
            self._vy = JUMP_V0
            self._on_floor = False
            self._apply(SpriteState.JUMP, then=then)
            self._glow_alpha = 180
            self._glow_color = QColor(255, 220, 80)

    # ── Proactive remarks ─────────────────────────────────────────────────────

    def _proactive_check(self):
        """
        Called every 5 minutes. Fires contextual Soldier Boy remarks based on
        time of day and whether the user has logged anything today.
        """
        try:
            from datetime import date

            from core.game_logic import get_character, get_recent_logs
            from core.roast_engine import proactive_remark

            hour = datetime.now().hour
            today = date.today().isoformat()
            today_logs = [l for l in get_recent_logs(1) if l["date"] == today]
            char = get_character()
            streak = char.get("streak", 0)

            # Determine context
            if hour < 9:
                context = "morning"
            elif hour < 14:
                context = "afternoon"
            elif hour < 20:
                # Evening: check if streak is in danger
                if not today_logs and streak > 0:
                    context = "streak_danger"
                elif not today_logs:
                    context = "no_log_nudge"
                else:
                    context = "afternoon"
            elif hour < 23:
                context = "evening"
            else:
                context = "night_owl"

            # Only fire remark 40% of the time to avoid being annoying
            if random.random() < 0.40:
                proactive_remark(context, speak=True)

        except Exception as e:
            print(f"[ChronicForge] Proactive check error: {e}")

    # ── Event reactions ───────────────────────────────────────────────────────

    def _on_xp(self, amount: int):
        self._do_jump()
        self._show_bubble(f"+{amount} XP")

    def _on_level_up(self, level: int):
        self._do_jump(then=SpriteState.COMBO_1)
        self._glow_color = QColor(100, 200, 255)
        self._glow_alpha = 255
        self._show_bubble(f"LEVEL {level}!")

    def _on_remark(self, text: str):
        """Proactive remark — sprite walks to a semi-centered position first."""
        screen = QApplication.primaryScreen().availableGeometry()
        # Pick a position roughly in the bottom-center of the screen
        target = float(random.randint(screen.width() // 3, 2 * screen.width() // 3))
        self._target_x = target
        self._move_mode = "walk"
        # Show bubble after a short delay (let sprite walk first)
        QTimer.singleShot(1800, lambda: self._show_bubble(text))

    def _on_quest(self, name: str):
        self._do_jump()

    def _on_damage(self):
        self._apply(SpriteState.HURT, then=SpriteState.IDLE)
        self._glow_alpha = 200
        self._glow_color = QColor(255, 50, 50)

    def _on_victory(self):
        self._do_jump(then=SpriteState.COMBO_3)
        self._glow_color = QColor(80, 255, 160)
        self._glow_alpha = 255

    def _show_bubble(self, text: str):
        if self._bubble:
            try:
                self._bubble.close()
            except:
                pass
        self._bubble = SpeechBubble(text, self)

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = e.pos()
            self._target_x = None

    def mouseMoveEvent(self, e):
        if self._dragging:
            screen = QApplication.primaryScreen().availableGeometry()
            new_pos = self.mapToGlobal(e.pos()) - self._drag_offset
            nx = max(screen.left(), min(new_pos.x(), screen.right() - self.width()))
            ny = max(screen.top(), min(new_pos.y(), screen.bottom() - self.height()))
            self._px, self._py = float(nx), float(ny)
            self.move(nx, ny)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            if self._py < self._floor_y - 10:
                self._on_floor = False
                self._vy = 0.0
                self._apply(SpriteState.FALL_LOOP)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            # Double-click → open log tab directly
            if self._open_log_fn:
                self._open_log_fn()
            else:
                self._do_jump()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#0e0702; color:#e8d5a3;
                border:1px solid #3a2208; font-family:monospace;
                font-size:11px; padding:4px; }
            QMenu::item { padding:7px 20px; }
            QMenu::item:selected { background:#2a1a06; color:#f5c842; }
            QMenu::separator { height:1px; background:#2a1808; margin:3px 8px; }
        """)
        menu.addAction("⚔  Open Chronicle").triggered.connect(
            lambda: self._open_dashboard_fn() if self._open_dashboard_fn else None
        )
        menu.addAction("📜  Log Activity").triggered.connect(
            lambda: self._open_log_fn() if self._open_log_fn else None
        )
        menu.addSeparator()
        menu.addAction("📌  Snap to floor").triggered.connect(self._snap_floor)
        menu.addAction("🎬  Test Animations").triggered.connect(self._test_animations)
        menu.addAction("⚡  Switch Character [DEV]").triggered.connect(self._dev_toggle_character)
        menu.addSeparator()
        menu.addAction("✕  Quit ChronicForge").triggered.connect(QApplication.quit)
        menu.exec(e.globalPos())

    def _on_config_saved(self):
        """Hot-reload sprite scale from config without restart."""
        try:
            from config.settings import load_config

            new_scale = load_config().sprite.scale
            if new_scale != self._scale:
                self._scale = new_scale
                self.setFixedSize(FRAME_SIZE * self._scale, FRAME_SIZE * self._scale)
                # Re-snap to floor since widget size changed
                screen = QApplication.primaryScreen().availableGeometry()
                self._floor_y = float(
                    screen.bottom() - self.height() + (BOTTOM_PADDING * self._scale)
                )
                self._py = self._floor_y
                self.move(int(self._px), int(self._py))
        except Exception as e:
            print(f"[ChronicForge] Scale reload failed: {e}")

    def _snap_floor(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self._floor_y = float(
            screen.bottom() - self.height() + (BOTTOM_PADDING * self._scale)
        )
        self._py = self._floor_y
        self._vy = 0.0
        self._on_floor = True
        self.move(int(self._px), int(self._py))

    def _dev_toggle_character(self):
        from config.settings import load_config, save_config
        cfg = load_config()
        cfg.sprite.character = (
            "female_hero" if cfg.sprite.character == "male_hero" else "male_hero"
        )
        save_config(cfg)
        self._anim_map = build_anim_map(cfg.sprite.character)
        self._sheets.clear()
        self._load_sheets()
        self._apply(SpriteState.IDLE)

    def _test_animations(self):
        """
        Open a submenu to trigger any animation from the sprite's animation list.
        """
        from PySide6.QtWidgets import QMenu

        anim_menu = QMenu("Select Animation", self)
        anim_menu.setStyleSheet("""
            QMenu { background:#0e0702; color:#e8d5a3;
                border:1px solid #3a2208; font-family:monospace;
                font-size:10px; padding:4px; }
            QMenu::item { padding:6px 16px; }
            QMenu::item:selected { background:#2a1a06; color:#f5c842; }
            QMenu::separator { height:1px; background:#2a1808; margin:2px 8px; }
        """)

        # Add all animations from self._anim_map
        for state in sorted(SpriteState, key=lambda s: s.name):
            anim_menu.addAction(state.name).triggered.connect(
                lambda checked=False, s=state: self._trigger_anim(s)
            )

        # Show the submenu
        cursor_pos = self.mapToGlobal(self.rect().center())
        anim_menu.exec(cursor_pos)

    def _trigger_anim(self, state: SpriteState):
        """
        Trigger a specific animation state and play it to completion.
        """
        print(f"[Sprite Test] Triggering animation: {state.name}")
        self._apply(state)

        # Snap to floor to ensure animations play properly
        self._py = self._floor_y
        self._vy = 0.0
        self._on_floor = True

    def _play_next_test_anim(self):
        """
        Play the next animation in the test queue.
        Called when current animation finishes.
        """
        if not hasattr(self, "_test_anim_queue") or self._test_anim_index >= len(
            self._test_anim_queue
        ):
            print("[Sprite Test] Animation test complete.")
            return

        state = self._test_anim_queue[self._test_anim_index]
        self._test_anim_index += 1
        print(f"[Sprite Test] Playing {state.name}...")
        self._set_state(state)

        # Schedule next animation based on current animation length
        anim = self._anim_config.get(state)
        if anim:
            duration = (anim.frames / anim.fps) * 1000  # Convert to milliseconds
            # Add 100ms delay between animations
            QTimer.singleShot(int(duration + 100), self._play_next_test_anim)
