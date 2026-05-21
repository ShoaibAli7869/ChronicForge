"""
ChronicForge — Journal Tab  (v7 — Illuminated Codex)

KEY ARCHITECTURE:
  Pages store RAW text (as the user typed it, no pre-wrapping).
  wrap_text() handles all visual wrapping at paint time and during
  overflow detection. It breaks oversized words character-by-character.
  Overflow detection counts wrapped lines vs page capacity, then splits
  the RAW text at the character position where the visual page ends.
  This eliminates the double-wrap bug and the invisible-text bug.
"""

import calendar as cal_mod
import math
from datetime import date, timedelta
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.journal_engine import (
    create_journal_entry,
    delete_journal_entry,
    get_calendar_data,
    get_daily_prompt,
    get_journal_entries,
    get_journal_entry,
    get_journal_stats,
    update_journal_entry,
)
from ui.theme import (
    C_CRIMSON,
    C_GOLD_BRIGHT,
    C_GOLD_DIM,
    C_GREEN,
    C_INK,
    C_INK_DIM,
    C_INK_FAINT,
    C_INK_MID,
    C_RULE,
    C_RULE_GOLD,
    font_cinzel,
    font_mono,
    font_serif,
)
from utils.signals import event_bus

# ═══════════════════════════════════════════════════════════════════════════════
#  PALETTE
# ═══════════════════════════════════════════════════════════════════════════════
C_PARCHMENT = "#ede0c8"
C_PARCHMENT_WARM = "#e5d6ba"
C_PARCHMENT_DK = "#d5c8a8"
C_PARCHMENT_EDGE = "#c8b890"
C_PARCHMENT_FOX = "#c2a87a"
C_LEATHER = "#1e1410"
C_LEATHER_MID = "#2a1c14"
C_LEATHER_LT = "#3e2a1c"
C_LEATHER_WARM = "#362218"
C_GOLD_LEAF = "#c8820a"
C_GOLD_DARK = "#8a6008"
C_GOLD_ACCENT = "#d4a020"
C_RED_WAX = "#8b1a1a"
C_RED_RUBRIC = "#982222"
C_GREEN_VERD = "#2a6a30"
C_SPINE_DARK = "#120a04"

MOODS = [
    ("terrible", "😤", "Terrible", C_RED_WAX),
    ("bad", "😟", "Bad", "#a06808"),
    ("okay", "😐", "Okay", C_INK_DIM),
    ("good", "🙂", "Good", C_GREEN_VERD),
    ("amazing", "🔥", "Amazing", C_GOLD_LEAF),
]
MOOD_MAP = {m[0]: m for m in MOODS}
DAY_ABBR = ["M", "T", "W", "T", "F", "S", "S"]

PAGE_MARGIN = 18
TEXT_INSET = 8
LINE_HEIGHT = 18
TITLE_BLOCK = 32
FOLIO_RESERVE = 16


# ═══════════════════════════════════════════════════════════════════════════════
#  TEXT WRAPPING — handles ALL cases including unbreakable long strings
# ═══════════════════════════════════════════════════════════════════════════════
def wrap_text(text: str, fm: QFontMetrics, width: int) -> list[str]:
    """Word-wrap text. Breaks oversized words char-by-char.
    Returns list of visual lines ready to paint."""
    if width <= 0:
        return [text] if text else [""]
    lines: list[str] = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        words = para.split(" ")
        cur = ""
        for word in words:
            if not word:
                # Multiple spaces produced empty string
                if cur:
                    cur += " "
                continue
            # If the word itself is wider than the line, break it char-by-char
            if fm.horizontalAdvance(word) > width:
                # Flush current line first
                if cur:
                    lines.append(cur)
                    cur = ""
                # Break the long word
                chunk = ""
                for ch in word:
                    test = chunk + ch
                    if fm.horizontalAdvance(test) > width:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                    else:
                        chunk = test
                # Remaining chunk becomes start of current line
                cur = chunk
                continue

            test = cur + (" " if cur else "") + word
            if fm.horizontalAdvance(test) <= width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines if lines else [""]


def compute_page_capacity(page_height: int, has_title: bool) -> int:
    """How many visual lines fit on one page."""
    inner_h = page_height - 2 * PAGE_MARGIN
    text_h = (
        inner_h - (TITLE_BLOCK if has_title else 0) - FOLIO_RESERVE - TEXT_INSET * 2
    )
    return max(1, text_h // LINE_HEIGHT)


def split_raw_text_to_pages(
    text: str,
    fm: QFontMetrics,
    text_width: int,
    page_height: int,
    has_title_on_first: bool,
) -> list[str]:
    """Split raw text into pages. Each page holds the raw substring
    that produces exactly `capacity` visual lines when wrapped.
    Pages store RAW text — no pre-wrapping."""
    if not text.strip():
        return [""]

    pages: list[str] = []
    remaining = text

    while remaining:
        is_first = len(pages) == 0
        capacity = compute_page_capacity(page_height, has_title_on_first and is_first)
        # Wrap the remaining text
        lines = wrap_text(remaining, fm, text_width)

        if len(lines) <= capacity:
            # Everything fits on this page
            pages.append(remaining)
            break

        # Find where in the raw text the capacity-th line ends.
        # We take the first `capacity` lines, figure out how many raw
        # characters that covers, and split there.
        page_lines = lines[:capacity]

        # Calculate raw char count consumed by these lines.
        # We must account for the fact that wrap_text splits on \n and spaces,
        # so we walk the raw text matching the produced lines.
        char_count = _count_raw_chars_for_lines(remaining, page_lines, fm, text_width)

        pages.append(remaining[:char_count])
        remaining = remaining[char_count:]
        # Strip a leading newline at page boundary to avoid blank first line
        if remaining.startswith("\n"):
            remaining = remaining[1:]

    return pages if pages else [""]


def _count_raw_chars_for_lines(
    raw: str, target_lines: list[str], fm: QFontMetrics, width: int
) -> int:
    """Count how many characters of `raw` produce `target_lines` when wrapped.
    Walks the raw text, wrapping as we go, counting lines until we've
    matched the target count."""
    target_count = len(target_lines)
    line_count = 0
    pos = 0
    raw_len = len(raw)

    while pos < raw_len and line_count < target_count:
        # Find end of current paragraph (next \n or end of string)
        nl = raw.find("\n", pos)
        if nl == -1:
            para = raw[pos:]
            para_end = raw_len
        else:
            para = raw[pos:nl]
            para_end = nl + 1  # Skip past the \n

        if not para:
            # Empty paragraph = one blank line
            line_count += 1
            if line_count >= target_count:
                pos = para_end
                break
            pos = para_end
            continue

        # Wrap this paragraph and count lines
        para_lines = wrap_text(para, fm, width)
        lines_from_para = len(para_lines)

        if line_count + lines_from_para <= target_count:
            # Whole paragraph fits within remaining capacity
            line_count += lines_from_para
            pos = para_end
        else:
            # Partial paragraph — need to find the char position within
            # the paragraph where we've consumed enough lines
            lines_needed = target_count - line_count
            # Reconstruct: consume `lines_needed` visual lines worth of text
            consumed = _chars_for_n_wrapped_lines(para, lines_needed, fm, width)
            pos = pos + consumed
            line_count = target_count
            break

    return pos


def _chars_for_n_wrapped_lines(
    text: str, n_lines: int, fm: QFontMetrics, width: int
) -> int:
    """How many characters of `text` (a single paragraph, no newlines)
    produce exactly `n_lines` wrapped lines."""
    if n_lines <= 0:
        return 0

    line_count = 0
    pos = 0
    words = text.split(" ")
    word_positions: list[tuple[int, int]] = []  # (start, end) in raw text
    i = 0
    for word in words:
        start = text.find(word, i)
        end = start + len(word)
        word_positions.append((start, end))
        i = end

    cur = ""
    cur_end = 0
    for wi, word in enumerate(words):
        if not word:
            continue
        wstart, wend = word_positions[wi]

        # Character-level break for oversized words
        if fm.horizontalAdvance(word) > width:
            if cur:
                line_count += 1
                if line_count >= n_lines:
                    return cur_end
                cur = ""
            chunk = ""
            for ci, ch in enumerate(word):
                test = chunk + ch
                if fm.horizontalAdvance(test) > width:
                    if chunk:
                        line_count += 1
                        if line_count >= n_lines:
                            return wstart + ci - len(chunk)
                    chunk = ch
                else:
                    chunk = test
            cur = chunk
            cur_end = wend
            continue

        test = cur + (" " if cur else "") + word
        if fm.horizontalAdvance(test) <= width:
            cur = test
            cur_end = wend
        else:
            if cur:
                line_count += 1
                if line_count >= n_lines:
                    return cur_end
            cur = word
            cur_end = wend

    # Final line
    if cur:
        line_count += 1
    return len(text)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAINT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _fill_parchment(p: QPainter, rect: QRect, color: str = C_PARCHMENT):
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRect(rect)
    rg = QRadialGradient(
        rect.center().x(), rect.center().y(), max(rect.width(), rect.height()) * 0.7
    )
    rg.setColorAt(0.0, QColor(0, 0, 0, 0))
    rg.setColorAt(0.85, QColor(0, 0, 0, 0))
    rg.setColorAt(1.0, QColor(0, 0, 0, 20))
    p.setBrush(QBrush(rg))
    p.drawRect(rect)
    p.setPen(Qt.PenStyle.NoPen)
    for fx, fy, rw, rh, a in [
        (0.22, 0.28, 18, 12, 7),
        (0.72, 0.62, 14, 16, 5),
        (0.48, 0.88, 12, 10, 8),
        (0.85, 0.15, 10, 14, 6),
    ]:
        p.setBrush(QBrush(QColor(C_PARCHMENT_FOX).lighter(110)))
        p.setOpacity(a / 255.0 * 4)
        p.drawEllipse(
            QPoint(
                rect.left() + int(rect.width() * fx),
                rect.top() + int(rect.height() * fy),
            ),
            rw,
            rh,
        )
    p.setOpacity(1.0)


def _draw_corner_flourish(p: QPainter, rect: QRect, sz: int = 10):
    p.setPen(QPen(QColor(C_GOLD_DARK), 1.0))
    for cx, cy, dx, dy in [
        (rect.left(), rect.top(), 1, 1),
        (rect.right(), rect.top(), -1, 1),
        (rect.left(), rect.bottom(), 1, -1),
        (rect.right(), rect.bottom(), -1, -1),
    ]:
        p.drawLine(cx, cy, cx + dx * sz, cy)
        p.drawLine(cx, cy, cx, cy + dy * sz)
        d = 4
        mx, my = cx + dx * d, cy + dy * d
        path = QPainterPath()
        path.moveTo(mx, my - 2)
        path.lineTo(mx + 2, my)
        path.lineTo(mx, my + 2)
        path.lineTo(mx - 2, my)
        path.closeSubpath()
        p.setBrush(QBrush(QColor(C_GOLD_LEAF)))
        p.drawPath(path)
        p.setBrush(Qt.BrushStyle.NoBrush)


def _draw_ruled_lines(p: QPainter, left: int, right: int, start_y: int, max_y: int):
    p.setPen(QPen(QColor(170, 158, 130, 45), 0.5))
    y = start_y
    while y < max_y:
        p.drawLine(left + 2, y, right - 2, y)
        y += LINE_HEIGHT


def _draw_drop_cap(p: QPainter, letter: str, x: int, y: int):
    cap = 26
    p.setBrush(QBrush(QColor(C_RED_WAX)))
    p.setPen(QPen(QColor(C_GOLD_DARK), 1))
    p.drawRoundedRect(x, y, cap, cap, 3, 3)
    p.setPen(QPen(QColor(C_GOLD_LEAF), 0.5))
    p.drawRoundedRect(x + 2, y + 2, cap - 4, cap - 4, 2, 2)
    p.setFont(font_cinzel(15, QFont.Weight.Bold))
    p.setPen(QPen(QColor(C_PARCHMENT)))
    p.drawText(QRect(x, y, cap, cap), Qt.AlignmentFlag.AlignCenter, letter.upper())


def _draw_wax_seal(p: QPainter, cx: int, cy: int, emoji: str):
    r = 14
    p.setBrush(QBrush(QColor(C_RED_WAX)))
    p.setPen(Qt.PenStyle.NoPen)
    for ang in range(0, 360, 45):
        ox = int(math.cos(math.radians(ang)) * 1.5)
        oy = int(math.sin(math.radians(ang)) * 1.5)
        ro = r + (1 if ang % 90 == 0 else -1)
        p.drawEllipse(QPoint(cx + ox, cy + oy), ro, ro)
    p.setPen(QPen(QColor(C_GOLD_DARK), 0.8))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPoint(cx, cy), r - 3, r - 3)
    p.setFont(font_serif(12))
    p.setPen(QPen(QColor(C_PARCHMENT)))
    p.drawText(QRect(cx - 8, cy - 8, 16, 16), Qt.AlignmentFlag.AlignCenter, emoji)


# ═══════════════════════════════════════════════════════════════════════════════
#  COMPACT CALENDAR
# ═══════════════════════════════════════════════════════════════════════════════
class CompactCalendar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(210)
        self._today = date.today()
        self._view_year = self._today.year
        self._view_month = self._today.month
        self._selected_day: int | None = self._today.day
        self._entry_dates: set[str] = set()
        self._hovered_day: int | None = None
        self._on_clicked: Optional[Callable[[], None]] = None
        self._cell_rects: dict[int, QRect] = {}
        self._nav_left_rect = QRect()
        self._nav_right_rect = QRect()
        self.setMouseTracking(True)

    def set_entry_dates(self, dates: set[str]):
        self._entry_dates = dates
        self.update()

    def set_click_callback(self, cb):
        self._on_clicked = cb

    def selected_date(self) -> str:
        d = self._selected_day or self._today.day
        return f"{self._view_year}-{self._view_month:02d}-{d:02d}"

    def navigate(self, delta: int):
        self._view_month += delta
        if self._view_month < 1:
            self._view_month = 12
            self._view_year -= 1
        elif self._view_month > 12:
            self._view_month = 1
            self._view_year += 1
        self._selected_day = None
        self.update()

    def go_today(self):
        self._view_year = self._today.year
        self._view_month = self._today.month
        self._selected_day = self._today.day
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        m = 4
        area = QRect(m, m, w - 2 * m, h - 2 * m)
        _fill_parchment(p, area, C_PARCHMENT_WARM)
        p.setPen(QPen(QColor(C_GOLD_DARK), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(area)
        p.setPen(QPen(QColor(C_GOLD_LEAF), 0.5))
        p.drawRect(area.adjusted(3, 3, -3, -3))

        hdr_y = area.top() + 6
        month_str = date(self._view_year, self._view_month, 1).strftime("%B %Y").upper()
        self._nav_left_rect = QRect(area.left() + 6, hdr_y, 22, 18)
        self._nav_right_rect = QRect(area.right() - 28, hdr_y, 22, 18)
        p.setFont(font_serif(10, QFont.Weight.Bold))
        p.setPen(QPen(QColor(C_GOLD_LEAF)))
        p.drawText(self._nav_left_rect, Qt.AlignmentFlag.AlignCenter, "◂")
        p.drawText(self._nav_right_rect, Qt.AlignmentFlag.AlignCenter, "▸")
        p.setFont(font_cinzel(9, QFont.Weight.Bold))
        p.setPen(QPen(QColor(C_RED_RUBRIC)))
        p.drawText(
            QRect(area.left(), hdr_y, area.width(), 18),
            Qt.AlignmentFlag.AlignHCenter,
            month_str,
        )

        rule_y = hdr_y + 22
        p.setPen(QPen(QColor(C_GOLD_DARK), 0.8))
        p.drawLine(area.left() + 8, rule_y, area.right() - 8, rule_y)
        for fx in [0.25, 0.5, 0.75]:
            p.setBrush(QBrush(QColor(C_GOLD_LEAF)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(area.left() + int(area.width() * fx), rule_y), 2, 2)

        dow_y = rule_y + 5
        cw = (area.width() - 14) // 7
        p.setFont(font_cinzel(6, QFont.Weight.Bold))
        p.setPen(QPen(QColor(C_RED_RUBRIC)))
        for i, name in enumerate(DAY_ABBR):
            p.drawText(
                QRect(area.left() + 7 + i * cw, dow_y, cw, 12),
                Qt.AlignmentFlag.AlignCenter,
                name,
            )

        grid_y = dow_y + 15
        ch = max(22, (area.bottom() - grid_y - 4) // 6)
        days = list(
            cal_mod.Calendar().itermonthdates(self._view_year, self._view_month)
        )
        self._cell_rects.clear()
        row, col = 0, 0
        for d in days:
            if col == 7:
                col = 0
                row += 1
            x = area.left() + 7 + col * cw
            y = grid_y + row * ch
            rect = QRect(x + 1, y + 1, cw - 2, ch - 2)
            in_month = d.month == self._view_month
            if in_month:
                self._cell_rects[d.day] = rect
                is_today = d == self._today
                is_sel = self._selected_day == d.day
                is_hover = self._hovered_day == d.day
                has_entry = d.isoformat() in self._entry_dates
                if is_sel:
                    p.setBrush(QBrush(QColor(C_RED_WAX)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRoundedRect(rect, 3, 3)
                    tc = QColor(C_PARCHMENT)
                elif is_hover:
                    p.setBrush(QBrush(QColor(C_GOLD_ACCENT).lighter(170)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawRoundedRect(rect, 3, 3)
                    tc = QColor(C_LEATHER)
                elif has_entry:
                    p.setBrush(QBrush(QColor(C_PARCHMENT_DK)))
                    p.setPen(QPen(QColor(C_GOLD_DARK), 0.5))
                    p.drawRoundedRect(rect, 2, 2)
                    tc = QColor(C_INK)
                else:
                    tc = QColor(C_RED_RUBRIC) if is_today else QColor(C_INK)
                p.setFont(
                    font_serif(
                        9, QFont.Weight.Bold if is_today else QFont.Weight.Normal
                    )
                )
                p.setPen(QPen(tc))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(d.day))
                if has_entry and not is_sel:
                    p.setBrush(QBrush(QColor(C_GOLD_LEAF)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPoint(rect.center().x(), rect.bottom() - 2), 2, 2)
            col += 1
        p.end()

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.pos()
        if self._nav_left_rect.contains(pos):
            self.navigate(-1)
            return
        if self._nav_right_rect.contains(pos):
            self.navigate(1)
            return
        for day_num, rect in self._cell_rects.items():
            if rect.contains(pos):
                self._selected_day = day_num
                self.update()
                if self._on_clicked:
                    self._on_clicked()
                return

    def mouseMoveEvent(self, e):
        old = self._hovered_day
        self._hovered_day = None
        for day_num, rect in self._cell_rects.items():
            if rect.contains(e.pos()):
                self._hovered_day = day_num
                break
        if old != self._hovered_day:
            self.update()


# ═══════════════════════════════════════════════════════════════════════════════
#  OPEN BOOK
# ═══════════════════════════════════════════════════════════════════════════════
class OpenBook(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entry_id: int | None = None
        self._entry_title = ""
        self._pages: list[str] = []
        self._raw_body = ""
        self._current_spread = 0
        self._mood: str | None = None
        self._word_count = 0
        self._entry_date = ""
        self._editing = False
        self._active_page_idx = 0
        self.setMinimumSize(460, 360)
        self.setMouseTracking(True)

        self._editor = QPlainTextEdit(self)
        self._editor.setFont(font_serif(11))
        self._editor.setTabChangesFocus(True)
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background: transparent;
                color: {C_INK};
                border: none;
                padding: 0px;
                selection-background-color: rgba(200, 130, 10, 50);
                selection-color: {C_INK};
            }}
        """)
        self._editor.hide()
        self._editor.textChanged.connect(self._on_text_changed)
        self._left_rect = QRect()
        self._right_rect = QRect()
        self._body_font = font_serif(11)
        self._body_fm = QFontMetrics(self._body_font)

    def _page_geom(self):
        w, h = self.width(), self.height()
        spine_w = 16
        page_w = (w - spine_w) // 2
        page_h = h - 12
        return page_w, page_h, spine_w

    def _text_width(self) -> int:
        pw, _, _ = self._page_geom()
        return pw - 2 * PAGE_MARGIN - 2 * TEXT_INSET - 6

    def _resplit(self):
        tw = self._text_width()
        _, ph, _ = self._page_geom()
        if tw <= 0 or ph <= 0:
            self._pages = [self._raw_body] if self._raw_body else [""]
            return
        self._pages = split_raw_text_to_pages(
            self._raw_body, self._body_fm, tw, ph, bool(self._entry_title)
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def load_entry(self, entry: dict):
        self._entry_id = entry["id"]
        self._entry_title = entry["title"]
        self._mood = entry.get("mood")
        self._word_count = entry["word_count"]
        self._entry_date = entry["date"]
        self._raw_body = entry["body"]
        self._current_spread = 0
        self._end_editing()
        self._resplit()
        self.update()

    def load_new(self, entry_date: str):
        self._entry_id = None
        self._entry_title = ""
        self._mood = None
        self._word_count = 0
        self._entry_date = entry_date
        self._raw_body = ""
        self._pages = [""]
        self._current_spread = 0
        self._end_editing()
        self.update()

    def clear(self):
        self._entry_id = None
        self._entry_title = ""
        self._raw_body = ""
        self._pages = []
        self._mood = None
        self._word_count = 0
        self._entry_date = ""
        self._current_spread = 0
        self._end_editing()
        self.update()

    def start_editing(self):
        self._editing = True
        self._active_page_idx = self._current_spread * 2
        if not self._pages:
            self._pages = [""]
        while len(self._pages) <= self._active_page_idx:
            self._pages.append("")
        self._position_editor()
        self._editor.blockSignals(True)
        self._editor.setPlainText(self._pages[self._active_page_idx])
        self._editor.blockSignals(False)
        self._editor.show()
        self._editor.setFocus()
        self._editor.raise_()
        self.update()

    def _end_editing(self):
        if self._editing:
            self._commit_editor()
            self._raw_body = "".join(self._pages)
        self._editing = False
        self._editor.hide()

    def _commit_editor(self):
        if 0 <= self._active_page_idx < len(self._pages):
            self._pages[self._active_page_idx] = self._editor.toPlainText()

    @property
    def total_pages(self) -> int:
        return max(1, len(self._pages))

    @property
    def body_text(self) -> str:
        if self._editing:
            self._commit_editor()
        return "".join(self._pages)

    def title(self) -> str:
        return self._entry_title

    def entry_date(self) -> str:
        return self._entry_date

    def mood(self) -> str | None:
        return self._mood

    def set_metadata(self, title: str = "", mood: str | None = None):
        if title:
            self._entry_title = title
        if mood is not None:
            self._mood = mood
        self.update()

    def _page_text(self, idx: int) -> str:
        return self._pages[idx] if 0 <= idx < len(self._pages) else ""

    # ── Editor positioning ────────────────────────────────────────────────────

    def _position_editor(self):
        pw, ph, sw = self._page_geom()
        has_title = self._active_page_idx == 0 and bool(self._entry_title)
        toff = TITLE_BLOCK if has_title else 0
        py = 6
        if self._active_page_idx % 2 == 0:
            px = 6
        else:
            px = 6 + pw + sw + 4
        ex = px + PAGE_MARGIN + TEXT_INSET
        ey = py + PAGE_MARGIN + toff + TEXT_INSET
        ew = pw - 2 * PAGE_MARGIN - 2 * TEXT_INSET - 6
        eh = ph - 2 * PAGE_MARGIN - toff - FOLIO_RESERVE - 2 * TEXT_INSET
        self._editor.setGeometry(max(0, ex), max(0, ey), max(10, ew), max(10, eh))

    def _on_text_changed(self):
        if not self._editing:
            return
        text = self._editor.toPlainText()
        while len(self._pages) <= self._active_page_idx:
            self._pages.append("")
        self._pages[self._active_page_idx] = text

        # Check visual overflow using same wrap logic as renderer
        tw = self._text_width()
        _, ph, _ = self._page_geom()
        has_title = self._active_page_idx == 0 and bool(self._entry_title)
        capacity = compute_page_capacity(ph, has_title)
        wrapped = wrap_text(text, self._body_fm, tw)

        if len(wrapped) > capacity:
            # Find the raw split point: how many raw chars produce `capacity` lines
            char_count = _count_raw_chars_for_lines(
                text, wrapped[:capacity], self._body_fm, tw
            )
            kept = text[:char_count]
            overflow = text[char_count:]
            # Strip leading newline from overflow
            if overflow.startswith("\n"):
                overflow = overflow[1:]

            self._pages[self._active_page_idx] = kept

            nxt = self._active_page_idx + 1
            while len(self._pages) <= nxt:
                self._pages.append("")
            # Prepend overflow to next page's raw text
            existing = self._pages[nxt]
            if existing.strip():
                self._pages[nxt] = overflow + existing
            else:
                self._pages[nxt] = overflow

            # Update editor to show only what fits
            self._editor.blockSignals(True)
            self._editor.setPlainText(kept)
            c = self._editor.textCursor()
            c.movePosition(QTextCursor.MoveOperation.End)
            self._editor.setTextCursor(c)
            self._editor.blockSignals(False)

            self._switch_to_page(nxt)

        self._word_count = sum(
            len(pg.split()) for pg in self._pages if pg and pg.strip()
        )
        self.update()

    def _switch_to_page(self, idx: int):
        self._commit_editor()
        self._active_page_idx = idx
        self._current_spread = idx // 2
        self._position_editor()
        self._editor.blockSignals(True)
        self._editor.setPlainText(self._page_text(idx))
        c = self._editor.textCursor()
        c.movePosition(QTextCursor.MoveOperation.Start)
        self._editor.setTextCursor(c)
        self._editor.blockSignals(False)
        self._editor.setFocus()
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pw, ph, sw = self._page_geom()
        py = 6

        desk = QLinearGradient(0, 0, 0, h)
        desk.setColorAt(0, QColor(C_LEATHER))
        desk.setColorAt(0.5, QColor(C_LEATHER_MID))
        desk.setColorAt(1, QColor(C_LEATHER))
        p.setBrush(QBrush(desk))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 4, 4)
        p.setPen(QPen(QColor(255, 255, 255, 4), 0.4))
        for gy in range(0, h, 5):
            p.drawLine(0, gy, w, gy)

        lr = QRect(6, py, pw - 2, ph)
        self._left_rect = lr
        self._draw_page(p, lr, self._current_spread * 2, True)

        sx = 6 + pw - 2
        sr = QRect(sx, py - 2, sw + 4, ph + 4)
        sg = QLinearGradient(sr.topLeft(), sr.topRight())
        sg.setColorAt(0.0, QColor(C_LEATHER_LT))
        sg.setColorAt(0.18, QColor(C_LEATHER_WARM))
        sg.setColorAt(0.42, QColor(C_SPINE_DARK))
        sg.setColorAt(0.58, QColor(C_SPINE_DARK))
        sg.setColorAt(0.82, QColor(C_LEATHER_WARM))
        sg.setColorAt(1.0, QColor(C_LEATHER_LT))
        p.setBrush(QBrush(sg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(sr)
        p.setPen(QPen(QColor(C_GOLD_DARK), 1.2))
        scx = sr.center().x()
        for frac in [0.18, 0.38, 0.5, 0.62, 0.82]:
            by = sr.top() + int(sr.height() * frac)
            p.drawLine(sr.left() + 2, by, sr.right() - 2, by)
        p.setBrush(QBrush(QColor(C_GOLD_LEAF)))
        p.setPen(QPen(QColor(C_GOLD_DARK), 0.6))
        p.drawEllipse(QPoint(scx, sr.center().y()), 4, 4)

        rr = QRect(sx + sw + 4, py, pw - 2, ph)
        self._right_rect = rr
        self._draw_page(p, rr, self._current_spread * 2 + 1, False)

        if self._current_spread > 0:
            p.setPen(QPen(QColor(C_GOLD_LEAF)))
            p.setFont(font_serif(12, QFont.Weight.Bold))
            p.drawText(
                QRect(10, h // 2 - 10, 20, 20), Qt.AlignmentFlag.AlignCenter, "◂"
            )
        max_sp = max(0, (self.total_pages - 1) // 2)
        if self._current_spread < max_sp:
            p.setPen(QPen(QColor(C_GOLD_LEAF)))
            p.setFont(font_serif(12, QFont.Weight.Bold))
            p.drawText(
                QRect(w - 30, h // 2 - 10, 20, 20), Qt.AlignmentFlag.AlignCenter, "▸"
            )
        p.end()

    def _draw_page(self, p: QPainter, rect: QRect, page_idx: int, is_left: bool):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 45)))
        p.drawRect(rect.adjusted(3, 3, 3, 3))
        _fill_parchment(p, rect)
        p.setPen(QPen(QColor(C_GOLD_DARK), 0.7))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rect)

        # Gutter shadow
        gw = 12
        if is_left:
            gg = QLinearGradient(rect.right() - gw, 0, rect.right(), 0)
        else:
            gg = QLinearGradient(rect.left() + gw, 0, rect.left(), 0)
        gg.setColorAt(0.0, QColor(0, 0, 0, 0))
        gg.setColorAt(1.0, QColor(0, 0, 0, 25))
        p.setBrush(QBrush(gg))
        p.setPen(Qt.PenStyle.NoPen)
        if is_left:
            p.drawRect(QRect(rect.right() - gw, rect.top(), gw, rect.height()))
        else:
            p.drawRect(QRect(rect.left(), rect.top(), gw, rect.height()))

        # Fore-edge
        p.setPen(QPen(QColor(C_PARCHMENT_EDGE), 0.4))
        edge_x = rect.left() if is_left else rect.right()
        sign = 1 if is_left else -1
        for i in range(3):
            p.drawLine(
                edge_x + sign * i, rect.top() + 3, edge_x + sign * i, rect.bottom() - 3
            )

        inner = rect.adjusted(PAGE_MARGIN, PAGE_MARGIN, -PAGE_MARGIN, -PAGE_MARGIN)
        p.setPen(QPen(QColor(C_RED_RUBRIC), 0.3))
        p.drawLine(inner.left() + 3, inner.top(), inner.left() + 3, inner.bottom())
        _draw_corner_flourish(p, inner, sz=9)

        has_title = page_idx == 0 and bool(self._entry_title)
        toff = TITLE_BLOCK if has_title else 0
        text_top = inner.top() + TEXT_INSET + toff
        text_bot = inner.bottom() - FOLIO_RESERVE
        text_left = inner.left() + TEXT_INSET
        text_w = inner.width() - 2 * TEXT_INSET

        _draw_ruled_lines(p, text_left, text_left + text_w, text_top, text_bot)

        # Folio
        p.setFont(font_serif(7, italic=True))
        p.setPen(QPen(QColor(C_INK_FAINT)))
        folio = page_idx + 1
        if folio <= self.total_pages:
            al = Qt.AlignmentFlag.AlignLeft if is_left else Qt.AlignmentFlag.AlignRight
            p.drawText(
                QRect(inner.left(), inner.bottom() - 12, inner.width(), 12),
                al,
                str(folio),
            )

        # Title
        if has_title:
            first_ch = self._entry_title[0] if self._entry_title else ""
            if first_ch:
                _draw_drop_cap(
                    p, first_ch, inner.left() + TEXT_INSET, inner.top() + TEXT_INSET
                )
                p.setFont(font_cinzel(10, QFont.Weight.Bold))
                p.setPen(QPen(QColor(C_RED_RUBRIC)))
                p.drawText(
                    QRect(
                        inner.left() + TEXT_INSET + 30,
                        inner.top() + TEXT_INSET + 2,
                        inner.width() - TEXT_INSET - 40,
                        24,
                    ),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    self._entry_title[1:50],
                )
            rule_y = inner.top() + TEXT_INSET + TITLE_BLOCK - 4
            p.setPen(QPen(QColor(C_GOLD_DARK), 0.7))
            p.drawLine(
                inner.left() + TEXT_INSET, rule_y, inner.right() - TEXT_INSET, rule_y
            )
            if self._mood and self._mood in MOOD_MAP:
                _draw_wax_seal(
                    p,
                    inner.right() - TEXT_INSET - 14,
                    inner.top() + TEXT_INSET + 12,
                    MOOD_MAP[self._mood][1],
                )

        # Text — skip if editor is overlaid
        if self._editing and page_idx == self._active_page_idx:
            return

        text = self._page_text(page_idx)
        if not text:
            if page_idx == 0 and self._entry_id is None and not self._editing:
                p.setFont(font_serif(10, italic=True))
                p.setPen(QPen(QColor(C_INK_FAINT)))
                p.drawText(
                    QRect(text_left, text_top + 8, text_w, text_bot - text_top),
                    Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                    "Select a date and press\n'New Entry' to begin\nwriting in thy codex…",
                )
            return

        # Render using SAME wrap_text — handles long words properly
        lines = wrap_text(text, self._body_fm, text_w)
        max_lines = (text_bot - text_top) // LINE_HEIGHT
        p.setFont(self._body_font)
        p.setPen(QPen(QColor(C_INK)))
        for i, line in enumerate(lines[:max_lines]):
            ly = text_top + i * LINE_HEIGHT
            p.drawText(
                QRect(text_left, ly, text_w, LINE_HEIGHT),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line,
            )

        if len(lines) > max_lines:
            p.setPen(QPen(QColor(C_RED_RUBRIC)))
            p.setFont(font_serif(8, italic=True))
            p.drawText(
                QRect(text_left, text_bot - 12, text_w, 12),
                Qt.AlignmentFlag.AlignRight,
                f"— page {folio + 1} →",
            )

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.pos()
        if self._editing:
            if self._right_rect.contains(pos) and self._active_page_idx % 2 == 0:
                nxt = self._active_page_idx + 1
                while len(self._pages) <= nxt:
                    self._pages.append("")
                self._switch_to_page(nxt)
                return
            if self._left_rect.contains(pos) and self._active_page_idx % 2 == 1:
                prev = self._active_page_idx - 1
                if prev >= 0:
                    self._switch_to_page(prev)
                return
        else:
            if self._left_rect.contains(pos) and self._current_spread > 0:
                self._current_spread -= 1
                self.update()
            elif self._right_rect.contains(pos):
                max_sp = max(0, (self.total_pages - 1) // 2)
                if self._current_spread < max_sp:
                    self._current_spread += 1
                    self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not self._editing and self._raw_body:
            self._resplit()
        if self._editing:
            self._position_editor()
        self.update()


# ═══════════════════════════════════════════════════════════════════════════════
#  JOURNAL TAB
# ═══════════════════════════════════════════════════════════════════════════════
class JournalTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_date: str = date.today().isoformat()
        self._editing = False
        self._mood: str | None = None
        self._build()
        self._load_entries()
        self._load_calendar_data()
        self._load_prompt()
        self._load_stats()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # LEFT SIDEBAR
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet(f"""
            QWidget {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 {C_LEATHER}, stop:0.5 {C_LEATHER_MID}, stop:1 {C_LEATHER}); }}
        """)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(10, 8, 10, 8)
        sl.setSpacing(5)

        self._calendar = CompactCalendar()
        self._calendar.set_click_callback(self._on_calendar_clicked)
        sl.addWidget(self._calendar)

        today_btn = QPushButton("⊕ Today")
        today_btn.setFont(font_mono(8))
        today_btn.setFixedHeight(22)
        today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        today_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{C_GOLD_DIM};
                border:1px solid {C_GOLD_DARK}; border-radius:2px; }}
            QPushButton:hover {{ color:{C_GOLD_BRIGHT}; border-color:{C_GOLD_LEAF}; }}
        """)
        today_btn.clicked.connect(self._go_today)
        sl.addWidget(today_btn)
        sl.addWidget(self._divider())

        self._entry_hdr = QLabel("TODAY'S ENTRIES")
        self._entry_hdr.setFont(font_cinzel(6, QFont.Weight.Bold))
        self._entry_hdr.setStyleSheet(
            f"color:{C_GOLD_DIM}; background:transparent; letter-spacing:2px;"
        )
        sl.addWidget(self._entry_hdr)

        entry_scroll = QScrollArea()
        entry_scroll.setWidgetResizable(True)
        entry_scroll.setFixedHeight(110)
        entry_scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollBar:vertical {{ width:4px; background:transparent; }}
            QScrollBar::handle:vertical {{ background:{C_GOLD_DARK}; border-radius:2px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        self._entry_container = QWidget()
        self._entry_container.setStyleSheet("background:transparent;")
        self._entry_list = QVBoxLayout(self._entry_container)
        self._entry_list.setContentsMargins(0, 0, 0, 0)
        self._entry_list.setSpacing(1)
        entry_scroll.setWidget(self._entry_container)
        sl.addWidget(entry_scroll)
        sl.addWidget(self._divider())

        sl.addWidget(self._sec_hdr("CODEX STATS"))
        self._stats_label = QLabel("—")
        self._stats_label.setFont(font_mono(7))
        self._stats_label.setStyleSheet(
            f"color:{C_PARCHMENT_DK}; background:transparent;"
        )
        self._stats_label.setWordWrap(True)
        sl.addWidget(self._stats_label)
        sl.addWidget(self._divider())

        sl.addWidget(self._sec_hdr("DAILY PROMPT"))
        self._prompt_label = QLabel("Loading…")
        self._prompt_label.setFont(font_serif(8, italic=True))
        self._prompt_label.setStyleSheet(
            f"color:{C_PARCHMENT_EDGE}; background:transparent;"
        )
        self._prompt_label.setWordWrap(True)
        sl.addWidget(self._prompt_label)

        use_btn = QPushButton("Use prompt")
        use_btn.setFont(font_mono(7))
        use_btn.setFixedHeight(20)
        use_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        use_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{C_GOLD_DIM};
                border:1px solid {C_GOLD_DARK}; border-radius:2px; }}
            QPushButton:hover {{ color:{C_GOLD_BRIGHT}; }}
        """)
        use_btn.clicked.connect(self._use_prompt)
        sl.addWidget(use_btn)
        sl.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._edit_btn = self._sidebar_btn("✎ Edit", C_GOLD_DIM, C_GOLD_DARK)
        self._edit_btn.clicked.connect(self._start_edit)
        self._edit_btn.setVisible(False)
        btn_row.addWidget(self._edit_btn)
        self._delete_btn = self._sidebar_btn("✕ Del", C_INK_FAINT, C_PARCHMENT_EDGE)
        self._delete_btn.clicked.connect(self._delete_entry)
        self._delete_btn.setVisible(False)
        btn_row.addWidget(self._delete_btn)
        btn_row.addStretch()
        sl.addLayout(btn_row)

        new_btn = QPushButton("✦  NEW  ENTRY")
        new_btn.setFont(font_cinzel(8, QFont.Weight.Bold))
        new_btn.setFixedHeight(32)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{ background:{C_LEATHER_LT}; color:{C_GOLD_LEAF};
                border:1px solid {C_GOLD_DARK}; letter-spacing:2px; }}
            QPushButton:hover {{ background:{C_LEATHER_WARM}; color:{C_GOLD_BRIGHT};
                border-color:{C_GOLD_LEAF}; }}
        """)
        new_btn.clicked.connect(self._new_entry)
        sl.addWidget(new_btn)
        root.addWidget(sidebar)

        # RIGHT — Book + Toolbar
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self._book = OpenBook()
        right.addWidget(self._book, stretch=1)

        self._editor_bar = QWidget()
        self._editor_bar.setFixedHeight(42)
        self._editor_bar.setStyleSheet(
            f"QWidget {{ background:{C_LEATHER}; border-top:1px solid {C_GOLD_DARK}; }}"
        )
        eb = QHBoxLayout(self._editor_bar)
        eb.setContentsMargins(8, 4, 8, 4)
        eb.setSpacing(5)

        self._title_edit = QTextEdit()
        self._title_edit.setPlaceholderText("Entry title…")
        self._title_edit.setFont(font_cinzel(9, QFont.Weight.Bold))
        self._title_edit.setFixedHeight(28)
        self._title_edit.setStyleSheet(f"""
            QTextEdit {{ background:{C_PARCHMENT_WARM}; color:{C_RED_RUBRIC};
                border:1px solid {C_GOLD_DARK}; padding:2px 6px; }}
        """)
        self._title_edit.textChanged.connect(self._on_title_changed)
        eb.addWidget(self._title_edit, stretch=1)

        self._mood_buttons: dict[str, QPushButton] = {}
        for mk, emoji, name, color in MOODS:
            btn = QPushButton(emoji)
            btn.setToolTip(name)
            btn.setCheckable(True)
            btn.setFixedSize(26, 26)
            btn.setFont(font_serif(12))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{ background:{C_PARCHMENT_WARM}; border:1px solid {C_PARCHMENT_EDGE}; border-radius:2px; }}
                QPushButton:hover {{ border-color:{color}; }}
                QPushButton:checked {{ border:2px solid {color}; background:{C_PARCHMENT_DK}; }}
            """)
            btn.clicked.connect(lambda _c, k=mk: self._set_mood(k))
            self._mood_buttons[mk] = btn
            eb.addWidget(btn)

        eb.addSpacing(6)
        self._save_btn = QPushButton("✦ SAVE")
        self._save_btn.setFont(font_cinzel(7, QFont.Weight.Bold))
        self._save_btn.setFixedSize(68, 26)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{ background:{C_PARCHMENT_WARM}; color:{C_RED_RUBRIC}; border:1px solid {C_RED_WAX}; }}
            QPushButton:hover {{ color:{C_GOLD_BRIGHT}; border-color:{C_GOLD_LEAF}; background:{C_PARCHMENT_DK}; }}
            QPushButton:disabled {{ color:{C_INK_FAINT}; border-color:{C_PARCHMENT_EDGE}; }}
        """)
        self._save_btn.clicked.connect(self._save_entry)
        eb.addWidget(self._save_btn)

        cancel_btn = QPushButton("✕")
        cancel_btn.setFont(font_mono(9))
        cancel_btn.setFixedSize(26, 26)
        cancel_btn.setToolTip("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{C_INK_FAINT};
                border:1px solid {C_PARCHMENT_EDGE}; border-radius:2px; }}
            QPushButton:hover {{ color:{C_RED_RUBRIC}; border-color:{C_RED_WAX}; }}
        """)
        cancel_btn.clicked.connect(self._cancel_edit)
        eb.addWidget(cancel_btn)

        self._word_lbl = QLabel("0w")
        self._word_lbl.setFont(font_mono(7))
        self._word_lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
        eb.addWidget(self._word_lbl)
        self._feedback = QLabel("")
        self._feedback.setFont(font_mono(7))
        self._feedback.setStyleSheet(f"color:{C_GREEN}; background:transparent;")
        eb.addWidget(self._feedback)

        self._editor_bar.setVisible(False)
        right.addWidget(self._editor_bar)
        root.addLayout(right, stretch=1)

    def _divider(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet(f"background:{C_GOLD_DARK}; border:none;")
        return f

    def _sec_hdr(self, text):
        lbl = QLabel(text)
        lbl.setFont(font_cinzel(6, QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color:{C_GOLD_DIM}; background:transparent; letter-spacing:2px;"
        )
        return lbl

    def _sidebar_btn(self, text, fg, border):
        btn = QPushButton(text)
        btn.setFont(font_mono(8))
        btn.setFixedHeight(24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{fg}; border:1px solid {border}; padding:0 8px; }}
            QPushButton:hover {{ color:{C_GOLD_BRIGHT}; }}
        """)
        return btn

    # ── Calendar ──────────────────────────────────────────────────────────────

    def _on_calendar_clicked(self):
        self._selected_date = self._calendar.selected_date()
        self._cancel_edit()
        self._load_entries()
        try:
            entries = get_journal_entries(entry_date=self._selected_date, limit=1)
            if entries:
                self._view_entry(entries[0]["id"])
            else:
                self._book.load_new(self._selected_date)
        except Exception:
            self._book.load_new(self._selected_date)

    def _go_today(self):
        self._selected_date = date.today().isoformat()
        self._calendar.go_today()
        self._cancel_edit()
        self._load_entries()
        self._book.load_new(self._selected_date)

    def _load_entries(self):
        while self._entry_list.count():
            item = self._entry_list.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        try:
            entries = get_journal_entries(entry_date=self._selected_date, limit=20)
        except Exception:
            entries = []
        try:
            d = date.fromisoformat(self._selected_date)
            today = date.today()
            if d == today:
                label = "TODAY'S ENTRIES"
            elif d == today - timedelta(days=1):
                label = "YESTERDAY"
            else:
                label = d.strftime("%d %b %Y").upper()
            self._entry_hdr.setText(label)
        except ValueError:
            pass
        if not entries:
            lbl = QLabel("  No entries")
            lbl.setFont(font_serif(8, italic=True))
            lbl.setStyleSheet(f"color:{C_INK_FAINT}; background:transparent;")
            self._entry_list.addWidget(lbl)
            self._entry_list.addStretch()
            return
        for e in entries:
            btn = QPushButton()
            me = MOOD_MAP.get(e.get("mood") or "", ("", "", "", ""))[1]
            btn.setText(f"{me + ' ' if me else ''}{e['title'][:26]}")
            btn.setFont(font_serif(8))
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{ text-align:left; padding:1px 6px; background:transparent;
                    color:{C_GOLD_DIM}; border:none; border-bottom:1px solid {C_LEATHER_LT}; }}
                QPushButton:hover {{ color:{C_GOLD_BRIGHT}; background:{C_LEATHER_LT}; }}
            """)
            btn.clicked.connect(lambda _c, eid=e["id"]: self._view_entry(eid))
            self._entry_list.addWidget(btn)
        self._entry_list.addStretch()

    def _view_entry(self, entry_id: int):
        self._cancel_edit()
        entry = get_journal_entry(entry_id)
        if not entry:
            return
        self._selected_date = entry["date"]
        self._book.load_entry(entry)
        self._edit_btn.setVisible(True)
        self._delete_btn.setVisible(True)

    def _new_entry(self):
        self._cancel_edit()
        self._book.load_new(self._selected_date)
        self._start_edit()

    def _start_edit(self):
        self._editing = True
        self._mood = self._book.mood()
        if self._book._entry_id:
            self._title_edit.setPlainText(self._book.title())
        else:
            self._title_edit.clear()
        for mk, btn in self._mood_buttons.items():
            btn.setChecked(mk == self._mood)
        self._editor_bar.setVisible(True)
        self._save_btn.setEnabled(False)
        self._edit_btn.setVisible(False)
        self._delete_btn.setVisible(False)
        self._feedback.setText("")
        self._book.start_editing()
        self._update_word_display()
        self._word_timer = QTimer(self)
        self._word_timer.timeout.connect(self._update_word_display)
        self._word_timer.start(400)

    def _cancel_edit(self):
        self._editing = False
        if hasattr(self, "_word_timer"):
            self._word_timer.stop()
        self._book._end_editing()
        self._editor_bar.setVisible(False)
        self._title_edit.clear()
        for btn in self._mood_buttons.values():
            btn.setChecked(False)
        self._feedback.setText("")
        self._book.update()

    def _on_title_changed(self):
        if self._editing:
            title = self._title_edit.toPlainText().strip()
            self._save_btn.setEnabled(bool(title))
            self._book.set_metadata(title=title, mood=self._mood)

    def _set_mood(self, mk):
        if self._mood == mk:
            self._mood = None
            for btn in self._mood_buttons.values():
                btn.setChecked(False)
        else:
            self._mood = mk
            for k, btn in self._mood_buttons.items():
                btn.setChecked(k == mk)
        self._book.set_metadata(mood=self._mood)

    def _update_word_display(self):
        wc = self._book._word_count
        self._word_lbl.setText(f"{wc}w")
        self._word_lbl.setStyleSheet(
            f"color:{C_GREEN if wc >= 100 else C_INK_FAINT}; background:transparent;"
        )

    def _save_entry(self):
        title = self._title_edit.toPlainText().strip()
        if not title:
            self._feedback.setText("Title required")
            self._feedback.setStyleSheet(
                f"color:{C_RED_RUBRIC}; background:transparent;"
            )
            return
        self._book._commit_editor()
        body = self._book.body_text
        if not body.strip() and not self._book._entry_id:
            self._feedback.setText("Write something first")
            self._feedback.setStyleSheet(
                f"color:{C_RED_RUBRIC}; background:transparent;"
            )
            return
        try:
            if self._book._entry_id:
                result = update_journal_entry(
                    self._book._entry_id, title=title, body=body, mood=self._mood
                )
                if result:
                    self._feedback.setText("Updated ✓")
                    self._feedback.setStyleSheet(
                        f"color:{C_GREEN}; background:transparent;"
                    )
                else:
                    self._feedback.setText("Failed")
                    return
            else:
                prompt_used = None
                pt = self._prompt_label.text()
                if pt and pt != "Loading…":
                    prompt_used = pt.strip('"')
                result = create_journal_entry(
                    title=title,
                    body=body,
                    mood=self._mood,
                    prompt_used=prompt_used,
                    entry_date=self._selected_date,
                )
                if "error" in result:
                    self._feedback.setText(result["error"])
                    return
                xp = result["xp_awarded"]
                streak = result.get("journal_streak", 0)
                self._feedback.setText(f"+{xp}XP · {streak}d streak")
                self._feedback.setStyleSheet(
                    f"color:{C_GREEN}; background:transparent;"
                )
                if result.get("levelled_up"):
                    event_bus.level_up.emit(result["new_level"])

            self._editing = False
            if hasattr(self, "_word_timer"):
                self._word_timer.stop()
            self._book._end_editing()
            self._editor_bar.setVisible(False)
            self._edit_btn.setVisible(True)
            self._delete_btn.setVisible(True)

            eid = self._book._entry_id
            if eid is None and isinstance(result, dict) and "id" in result:
                eid = result["id"]
            if eid is not None:
                saved = get_journal_entry(eid)
                if saved:
                    self._book.load_entry(saved)

            self._load_entries()
            self._load_calendar_data()
            self._load_stats()
            self._title_edit.clear()
            QTimer.singleShot(4000, lambda: self._feedback.setText(""))
        except Exception as exc:
            self._feedback.setText(f"Error: {exc}")
            self._feedback.setStyleSheet(
                f"color:{C_RED_RUBRIC}; background:transparent;"
            )

    def _delete_entry(self):
        if self._book._entry_id is None:
            return
        if self._delete_btn.text() == "✕ Del":
            self._delete_btn.setText("Sure?")
            self._delete_btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{C_RED_RUBRIC};
                    border:2px solid {C_RED_WAX}; padding:0 8px; }}""")
            QTimer.singleShot(3000, self._reset_del)
            return
        if delete_journal_entry(self._book._entry_id):
            self._book.clear()
            self._edit_btn.setVisible(False)
            self._delete_btn.setVisible(False)
            self._load_entries()
            self._load_calendar_data()
            self._load_stats()
        self._reset_del()

    def _reset_del(self):
        self._delete_btn.setText("✕ Del")
        self._delete_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{C_INK_FAINT};
                border:1px solid {C_PARCHMENT_EDGE}; padding:0 8px; }}
            QPushButton:hover {{ color:{C_RED_RUBRIC}; border-color:{C_RED_WAX}; }}""")

    def _load_prompt(self):
        try:
            self._prompt_label.setText(f'"{get_daily_prompt()}"')
        except Exception:
            self._prompt_label.setText('"Reflect upon thy day."')

    def _use_prompt(self):
        self._new_entry()
        pt = self._prompt_label.text().strip('"')
        self._title_edit.setPlainText(pt)
        self._book.set_metadata(title=pt)

    def _load_stats(self):
        try:
            s = get_journal_stats()
            dm_key = s.get("dominant_mood")
            dm = (
                f"{MOOD_MAP[dm_key][1]} {MOOD_MAP[dm_key][2]}"
                if dm_key and dm_key in MOOD_MAP
                else "—"
            )
            self._stats_label.setText(
                f"{s['total_entries']} entries · {s['total_words']:,}w\n"
                f"Streak: {s['current_streak']}d (best {s['longest_streak']}d)\n"
                f"Month: {s['days_with_entries_30d']}/30 · {dm}"
            )
        except Exception:
            self._stats_label.setText("—")

    def _load_calendar_data(self):
        try:
            today = date.today()
            data = get_calendar_data(today.year, today.month)
            self._calendar.set_entry_dates({d["date"] for d in data})
        except Exception:
            pass

    def refresh(self):
        self._load_entries()
        self._load_calendar_data()
        self._load_stats()
