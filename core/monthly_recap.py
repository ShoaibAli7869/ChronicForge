"""
ChronicForge — Monthly Recap Generator
Produces a PDF "Chronicle Scroll" at the end of each month.

Contents:
  Page 1 — Cover: hero name, class, month, Soldier Boy verdict (Groq)
  Page 2 — Stats: radar chart representation, stat bars, XP total
  Page 3 — Activity heatmap + best day of week + stat breakdown
  Page 4 — Quest summary + roast journal highlights
  Page 5 — Next month guidance (Soldier Boy advice via Groq)

Output: ~/ChronicForge_Recap_YYYY-MM.pdf
Auto-runs on 1st of each month via main.py midnight tick.
"""

import io
import math
import os
from datetime import date, datetime, timedelta
from typing import Optional

# ── Helpers ────────────────────────────────────────────────────────────────────


def _month_range(year: int, month: int) -> tuple[str, str]:
    """Return (start_date, end_date) ISO strings for the given month."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _prev_month() -> tuple[int, int]:
    """Return (year, month) of the previous month."""
    today = date.today()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def _gather_month_data(year: int, month: int) -> dict:
    """Pull all stats for the given month from SQLite."""
    from sqlalchemy import func as sqlfunc
    from sqlalchemy import select

    from core.analytics import get_best_day_of_week
    from core.database import LogEntry, Quest, Roast, SessionFactory
    from core.game_logic import get_character

    start, end = _month_range(year, month)

    with SessionFactory() as session:
        # Log entries
        entries = session.scalars(
            select(LogEntry)
            .where(
                LogEntry.character_id == 1, LogEntry.date >= start, LogEntry.date <= end
            )
            .order_by(LogEntry.date)
        ).all()

        # Quests completed this month
        quests = (
            session.scalars(
                select(Quest).where(
                    Quest.character_id == 1,
                    Quest.completed == True,
                    Quest.completed_at >= f"{start}T00:00:00",
                    Quest.completed_at <= f"{end}T23:59:59",
                )
            ).all()
            if entries
            else []
        )

        # Roasts from this month
        roasts = session.scalars(
            select(Roast)
            .where(
                Roast.character_id == 1,
                Roast.created_at >= f"{start}T00:00:00",
                Roast.created_at <= f"{end}T23:59:59",
            )
            .order_by(Roast.created_at.desc())
            .limit(8)
        ).all()

    # Aggregate stats
    from collections import defaultdict

    stat_totals = defaultdict(lambda: {"xp": 0, "count": 0, "delta": 0.0})
    xp_by_day = defaultdict(int)
    active_days = set()

    for e in entries:
        stat_totals[e.category]["xp"] += e.xp_awarded
        stat_totals[e.category]["count"] += 1
        stat_totals[e.category]["delta"] += e.stat_delta
        xp_by_day[e.date] += e.xp_awarded
        active_days.add(e.date)

    total_xp = sum(e.xp_awarded for e in entries)
    total_entries = len(entries)
    days_in_month = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    active_count = len(active_days)
    consistency = round(active_count / days_in_month * 100)

    # Best stat
    best_stat = (
        max(stat_totals, key=lambda s: stat_totals[s]["xp"])
        if stat_totals
        else "discipline"
    )
    worst_stat = min(
        (
            s
            for s in [
                "strength",
                "intellect",
                "charisma",
                "vitality",
                "discipline",
                "creativity",
                "wealth",
            ]
            if stat_totals[s]["count"] == 0 or stat_totals[s]["xp"] < 50
        ),
        default="wealth",
    )

    char = get_character()

    return {
        "year": year,
        "month": month,
        "month_name": date(year, month, 1).strftime("%B %Y"),
        "char": char,
        "total_xp": total_xp,
        "total_entries": total_entries,
        "active_days": active_count,
        "days_in_month": days_in_month,
        "consistency": consistency,
        "stat_totals": dict(stat_totals),
        "xp_by_day": dict(xp_by_day),
        "best_stat": best_stat,
        "worst_stat": worst_stat,
        "quests_done": len(quests),
        "quest_list": [q.title for q in quests[:6]],
        "roasts": [{"text": r.text, "type": r.roast_type} for r in roasts],
        "start": start,
        "end": end,
    }


def _get_verdict(data: dict, tone: str = "roast") -> str:
    """Groq-powered Soldier Boy monthly verdict. Falls back to template."""
    try:
        from core.roast_engine import _get_groq

        client = _get_groq()
        if client:
            char = data["char"]
            prompt = (
                "You are Soldier Boy from 'The Boys' — brutal, crude, 80s superhero. "
                "No filter, dark humour.\n\n"
                f"Hero: {char['name']}, Level {char['level']} {char['class']}\n"
                f"Month: {data['month_name']}\n"
                f"Total XP: {data['total_xp']}\n"
                f"Active days: {data['active_days']}/{data['days_in_month']} "
                f"({data['consistency']}% consistency)\n"
                f"Best stat: {data['best_stat']} | Neglected: {data['worst_stat']}\n"
                f"Quests completed: {data['quests_done']}\n\n"
                f"Write a 3-sentence Soldier Boy {tone} verdict on this month. "
                "Be specific, brutal, and funny. No markdown."
            )
            resp = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.95,
            )
            return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ChronicForge] Groq verdict failed: {e}")

    # Template fallback
    c = data["consistency"]
    xp = data["total_xp"]
    if c >= 80:
        return (
            f"Not bad. {c}% consistency is actually something. "
            f"{xp} XP logged — I've seen worse. "
            f"Don't get cocky though. You're still a work in progress."
        )
    elif c >= 50:
        return (
            f"{c}% consistency. Half-assing it as usual. "
            f"{xp} XP is something, but you and I both know you could've done more. "
            f"Next month: show up every damn day or don't bother."
        )
    else:
        return (
            f"{c}% consistency. {data['active_days']} days out of {data['days_in_month']}. "
            f"That's not a habit, that's a coincidence. "
            f"I survived 40 years in a Russian lab. You can't log an activity every day?"
        )


def _get_next_month_advice(data: dict) -> str:
    """Soldier Boy's advice for next month. Groq or template."""
    try:
        from core.roast_engine import _get_groq

        client = _get_groq()
        if client:
            prompt = (
                "You are Soldier Boy from 'The Boys'. Brutal, crude, no filter.\n\n"
                f"This hero neglected: {data['worst_stat']}\n"
                f"This hero excelled at: {data['best_stat']}\n"
                f"Consistency: {data['consistency']}%\n\n"
                "Give 2 sentences of brutal but specific advice for next month. "
                "Name the neglected stat. No markdown."
            )
            resp = _get_groq().chat.completions.create(
                model="llama3-70b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=80,
                temperature=0.9,
            )
            return resp.choices[0].message.content.strip()
    except Exception:
        pass
    return (
        f"You neglected {data['worst_stat']}. Fix that. "
        f"Next month: log {data['worst_stat']} at least every other day or "
        f"Soldier Boy will be very disappointed."
    )


# ── PDF generation ─────────────────────────────────────────────────────────────


def generate_monthly_recap(
    year: Optional[int] = None,
    month: Optional[int] = None,
    output_dir: Optional[str] = None,
) -> str:
    """
    Generate the monthly recap PDF.
    Defaults to previous month. Returns path to created PDF.
    """
    from reportlab.lib.colors import Color, HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    if year is None or month is None:
        year, month = _prev_month()

    if output_dir is None:
        output_dir = os.path.expanduser("~/ChronicForge_Recaps")
    os.makedirs(output_dir, exist_ok=True)

    out_path = os.path.join(output_dir, f"ChronicForge_Recap_{year}-{month:02d}.pdf")

    data = _gather_month_data(year, month)
    verdict = _get_verdict(data)
    advice = _get_next_month_advice(data)

    W, H = A4  # 595 x 842 pts

    # Colours
    C_BG = HexColor("#0d0802")
    C_GOLD = HexColor("#c8a020")
    C_GOLD_B = HexColor("#f5c842")
    C_INK = HexColor("#d4b870")
    C_DIM = HexColor("#7a5a30")
    C_FAINT = HexColor("#3a2810")
    C_GREEN = HexColor("#50a030")
    C_RED = HexColor("#b03020")
    C_WHITE = HexColor("#e8d5a3")

    STAT_COLORS = {
        "strength": HexColor("#c84040"),
        "intellect": HexColor("#4080d0"),
        "charisma": HexColor("#c07820"),
        "vitality": HexColor("#30a060"),
        "discipline": HexColor("#8050b0"),
        "creativity": HexColor("#a0a020"),
        "wealth": HexColor("#30a0a0"),
    }

    c = canvas.Canvas(out_path, pagesize=A4)

    def _draw_bg():
        c.setFillColor(C_BG)
        c.rect(0, 0, W, H, fill=1, stroke=0)

    def _rule(y, color=C_FAINT, width=W - 80):
        c.setStrokeColor(color)
        c.setLineWidth(0.5)
        c.line(40, y, 40 + width, y)

    def _title(text, y, size=22, color=None):
        c.setFillColor(color or C_GOLD_B)
        c.setFont("Helvetica-Bold", size)
        c.drawString(40, y, text)

    def _body(text, y, size=10, color=None, x=40, max_width=515):
        """Draw wrapped body text."""
        from reportlab.lib.utils import simpleSplit

        c.setFillColor(color or C_INK)
        c.setFont("Helvetica", size)
        lines = simpleSplit(text, "Helvetica", size, max_width)
        for line in lines:
            c.drawString(x, y, line)
            y -= size * 1.5
        return y

    def _label(text, y, size=7, color=None, x=40):
        c.setFillColor(color or C_FAINT)
        c.setFont("Helvetica-Bold", size)
        c.drawString(x, y, text.upper())

    def _stat_bar(stat, value, max_val, y, x=40, bar_w=300, bar_h=8):
        col = STAT_COLORS.get(stat, C_GOLD)
        fill_w = max(2, bar_w * min(value, max_val) / max(max_val, 1))
        # Track
        c.setFillColor(HexColor("#1a1005"))
        c.rect(x, y, bar_w, bar_h, fill=1, stroke=0)
        # Fill
        c.setFillColor(col)
        c.rect(x, y, fill_w, bar_h, fill=1, stroke=0)
        # Label
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + bar_w + 6, y + 1, f"{stat[:3].upper()}  {value:.1f}")

    def _mini_radar(cx, cy, radius, stats_dict, max_val=100):
        """Draw a mini radar chart in PDF."""
        stat_keys = [
            "strength",
            "intellect",
            "charisma",
            "vitality",
            "discipline",
            "creativity",
            "wealth",
        ]
        n = len(stat_keys)
        # Grid rings
        for ring in [0.25, 0.5, 0.75, 1.0]:
            pts = []
            for i in range(n):
                angle = math.radians(-90 + i * 360 / n)
                r = radius * ring
                pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
            c.setStrokeColor(HexColor("#2a1a08"))
            c.setLineWidth(0.5)
            path = c.beginPath()
            path.moveTo(*pts[0])
            for pt in pts[1:]:
                path.lineTo(*pt)
            path.close()
            c.drawPath(path)
        # Spokes
        for i in range(n):
            angle = math.radians(-90 + i * 360 / n)
            c.setStrokeColor(HexColor("#2a1a08"))
            c.line(cx, cy, cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        # Stat polygon
        pts = []
        for i, stat in enumerate(stat_keys):
            val = stats_dict.get(stat, 10.0)
            mag = radius * min(val, max_val) / max_val
            angle = math.radians(-90 + i * 360 / n)
            pts.append((cx + mag * math.cos(angle), cy + mag * math.sin(angle)))
        c.setFillColor(HexColor("#c8a02033"))
        c.setStrokeColor(C_GOLD)
        c.setLineWidth(1.5)
        path = c.beginPath()
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)
        path.close()
        c.drawPath(path, fill=1)
        # Dots
        for i, (px, py) in enumerate(pts):
            col = STAT_COLORS.get(stat_keys[i], C_GOLD)
            c.setFillColor(col)
            c.circle(px, py, 3, fill=1, stroke=0)

    # ═══════════════════════════════════════════════════════════════
    # PAGE 1 — COVER
    # ═══════════════════════════════════════════════════════════════
    _draw_bg()

    # Top ornament line
    c.setStrokeColor(C_GOLD)
    c.setLineWidth(1.5)
    c.line(40, H - 40, W - 40, H - 40)
    c.setStrokeColor(C_FAINT)
    c.setLineWidth(0.5)
    c.line(40, H - 44, W - 40, H - 44)

    # Chronicle header
    _label("Chronicle of Progress", H - 65, size=8, color=C_FAINT)

    # Month title
    c.setFillColor(C_GOLD_B)
    c.setFont("Helvetica-Bold", 36)
    c.drawString(40, H - 110, data["month_name"].upper())

    # Character info
    char = data["char"]
    c.setFillColor(C_GOLD)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(
        40, H - 140, f"{char['name']}  ·  Level {char['level']} {char['class']}"
    )
    c.setFillColor(C_DIM)
    c.setFont("Helvetica", 10)
    c.drawString(40, H - 158, f"{char['title']}  ·  Power {char['total_power']:.0f}")

    _rule(H - 170, C_GOLD)

    # Key metrics row
    metrics = [
        ("TOTAL XP", str(data["total_xp"]), C_GOLD_B),
        ("ACTIVE DAYS", f"{data['active_days']}/{data['days_in_month']}", C_GREEN),
        (
            "CONSISTENCY",
            f"{data['consistency']}%",
            C_GREEN if data["consistency"] >= 60 else C_RED,
        ),
        ("QUESTS DONE", str(data["quests_done"]), C_GOLD),
        ("ENTRIES", str(data["total_entries"]), C_DIM),
    ]
    mx = 40
    for label_txt, val_txt, col in metrics:
        _label(label_txt, H - 195, x=mx)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(mx, H - 215, val_txt)
        mx += (W - 80) // len(metrics)

    _rule(H - 230, C_FAINT)

    # Soldier Boy verdict
    c.setFillColor(C_GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, H - 258, "⚡  SOLDIER BOY'S VERDICT")
    _rule(H - 264, C_RULE_PDF := HexColor("#2a1a08"))

    # Verdict box background
    verdict_y = H - 270
    c.setFillColor(HexColor("#110a03"))
    c.rect(40, verdict_y - 80, W - 80, 80, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#4a3010"))
    c.setLineWidth(1)
    c.rect(40, verdict_y - 80, W - 80, 80, fill=0, stroke=1)

    c.setFillColor(C_WHITE)
    c.setFont("Helvetica", 11)
    from reportlab.lib.utils import simpleSplit

    lines = simpleSplit(f'"{verdict}"', "Helvetica", 11, W - 120)
    ty = verdict_y - 20
    for line in lines[:4]:
        c.drawString(56, ty, line)
        ty -= 17

    # Bottom ornament
    _rule(60, C_FAINT)
    _rule(56, C_GOLD)
    c.setFillColor(C_FAINT)
    c.setFont("Helvetica", 7)
    c.drawCentredString(
        W / 2, 42, f"ChronicForge  ·  Generated {date.today().isoformat()}"
    )

    c.showPage()

    # ═══════════════════════════════════════════════════════════════
    # PAGE 2 — STATS
    # ═══════════════════════════════════════════════════════════════
    _draw_bg()
    _rule(H - 40, C_GOLD)
    _label("Stats & Growth", H - 55, size=9, color=C_GOLD)
    _rule(H - 62, C_FAINT)

    # Radar chart (left)
    _mini_radar(
        160, H - 220, 110, char["stats"], max_val=max(max(char["stats"].values()), 20)
    )
    # Radar labels
    stat_keys = [
        "strength",
        "intellect",
        "charisma",
        "vitality",
        "discipline",
        "creativity",
        "wealth",
    ]
    for i, stat in enumerate(stat_keys):
        angle = math.radians(-90 + i * 360 / 7)
        lx = 160 + 130 * math.cos(angle)
        ly = (H - 220) + 130 * math.sin(angle)
        col = STAT_COLORS.get(stat, C_GOLD)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(lx, ly, stat[:3].upper())

    # Stat bars (right)
    bx, by = 340, H - 100
    _label("Current Attributes", by + 10, x=bx, color=C_FAINT)
    max_stat = max(char["stats"].values()) or 1
    for stat, val in char["stats"].items():
        _stat_bar(stat, val, max(max_stat, 50), by, x=bx, bar_w=200)
        by -= 20

    # XP per day timeline bar chart
    chart_y = by - 20
    _label(f"Daily XP Timeline  ·  Total: {data['total_xp']}", chart_y + 5, x=40)
    _rule(chart_y, C_RULE_PDF)
    chart_y -= 6

    xp_map = data["xp_by_day"]
    start_d = date.fromisoformat(data["start"])
    days_n = data["days_in_month"]
    max_xp_d = max(xp_map.values(), default=1) or 1
    chart_h = 60
    bar_area = 480
    bar_w = max(3, int(bar_area / days_n) - 1)
    gap = max(1, bar_w // 3)

    for day_i in range(days_n):
        d_obj = start_d + timedelta(days=day_i)
        xp_v = xp_map.get(d_obj.isoformat(), 0)
        bh = int(xp_v / max_xp_d * chart_h)
        bx_ = 40 + day_i * (bar_w + gap)
        if bh > 0:
            level = 1 if xp_v < 100 else 2 if xp_v < 300 else 3 if xp_v < 600 else 4
            bar_cols = [
                HexColor("#1a1005"),
                HexColor("#7a5010"),
                HexColor("#b08020"),
                HexColor("#d4a030"),
                HexColor("#f5c842"),
            ]
            c.setFillColor(bar_cols[level])
            c.rect(bx_, chart_y - chart_h, bar_w, bh, fill=1, stroke=0)
        else:
            c.setFillColor(HexColor("#1a1005"))
            c.rect(bx_, chart_y - chart_h, bar_w, 2, fill=1, stroke=0)

        # Week separator
        if day_i > 0 and d_obj.weekday() == 0:
            c.setStrokeColor(HexColor("#2a1a08"))
            c.setLineWidth(0.3)
            c.line(bx_ - gap // 2, chart_y - chart_h - 4, bx_ - gap // 2, chart_y + 4)

    # X-axis month start label
    c.setFillColor(C_FAINT)
    c.setFont("Helvetica", 6)
    c.drawString(40, chart_y - chart_h - 12, data["start"])
    c.drawRightString(40 + days_n * (bar_w + gap), chart_y - chart_h - 12, data["end"])

    by = chart_y - chart_h - 24

    # XP gained per stat bars
    _label(f"XP by Stat  ·  {data['total_entries']} total entries", by + 5, x=40)
    _rule(by, C_RULE_PDF)
    by -= 18
    st = data["stat_totals"]
    max_xp = max((v["xp"] for v in st.values()), default=1) or 1
    for stat in stat_keys:
        info = st.get(stat, {"xp": 0, "count": 0})
        xp_v = info["xp"]
        cnt = info["count"]
        col = STAT_COLORS.get(stat, C_GOLD)
        fill_w = max(0, 280 * xp_v / max_xp) if max_xp else 0
        c.setFillColor(HexColor("#1a1005"))
        c.rect(40, by, 280, 8, fill=1, stroke=0)
        if fill_w > 0:
            c.setFillColor(col)
            c.rect(40, by, fill_w, 8, fill=1, stroke=0)
        c.setFillColor(col if cnt > 0 else C_FAINT)
        c.setFont("Helvetica-Bold", 7)
        entry_str = f"{cnt} entr{'y' if cnt == 1 else 'ies'}"
        c.drawString(328, by + 1, f"{stat[:3].upper()}  +{xp_v} XP  ({entry_str})")
        by -= 15

    _rule(50, C_FAINT)
    _rule(46, C_GOLD)
    c.setFillColor(C_FAINT)
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 32, f"ChronicForge  ·  {data['month_name']}")
    c.showPage()

    # ═══════════════════════════════════════════════════════════════
    # PAGE 3 — ACTIVITY CALENDAR + BEST DAY
    # ═══════════════════════════════════════════════════════════════
    _draw_bg()
    _rule(H - 40, C_GOLD)
    _label("Activity Calendar", H - 55, size=9, color=C_GOLD)
    _rule(H - 62, C_FAINT)

    # Mini heatmap for the month
    cal_y = H - 90
    cal_x = 40
    cell = 14
    gap = 3
    days_in = data["days_in_month"]
    xp_map = data["xp_by_day"]

    LEVEL_COLORS_PDF = [
        HexColor("#1a1005"),
        HexColor("#3a2808"),
        HexColor("#7a5010"),
        HexColor("#b08020"),
        HexColor("#f5c842"),
    ]

    _label(data["month_name"], cal_y + 12, x=cal_x, color=C_GOLD, size=9)
    cal_y -= 4

    start_date = date.fromisoformat(data["start"])
    dow_offset = start_date.weekday()

    day_labels = ["M", "T", "W", "T", "F", "S", "S"]
    for di, dl in enumerate(day_labels):
        c.setFillColor(C_FAINT)
        c.setFont("Helvetica", 6)
        c.drawCentredString(cal_x + di * (cell + gap) + cell // 2, cal_y, dl)
    cal_y -= 12

    for day_num in range(days_in):
        d_obj = start_date + timedelta(days=day_num)
        ds = d_obj.isoformat()
        xp_v = xp_map.get(ds, 0)
        level = (
            0
            if xp_v == 0
            else 1
            if xp_v < 100
            else 2
            if xp_v < 300
            else 3
            if xp_v < 600
            else 4
        )
        col = LEVEL_COLORS_PDF[level]
        dow = (day_num + dow_offset) % 7
        week = (day_num + dow_offset) // 7
        cx_ = cal_x + dow * (cell + gap)
        cy_ = cal_y - week * (cell + gap)
        c.setFillColor(col)
        c.rect(cx_, cy_, cell, cell, fill=1, stroke=0)
        if xp_v > 0:
            c.setFillColor(HexColor("#0d0802"))
            c.setFont("Helvetica-Bold", 5)
            c.drawCentredString(cx_ + cell // 2, cy_ + 3, str(d_obj.day))

    # Legend
    lx = cal_x
    ly = cal_y - (days_in // 7 + 2) * (cell + gap) - 10
    c.setFillColor(C_FAINT)
    c.setFont("Helvetica", 6)
    c.drawString(lx, ly, "Less")
    lx += 26
    for lvl in range(5):
        c.setFillColor(LEVEL_COLORS_PDF[lvl])
        c.rect(
            lx + lvl * (cell - 4 + gap), ly - 2, cell - 4, cell - 4, fill=1, stroke=0
        )
    lx += 5 * (cell - 4 + gap) + 4
    c.setFillColor(C_FAINT)
    c.drawString(lx, ly, "More")

    # Best day of week bars
    from core.analytics import get_best_day_of_week

    dow_data = get_best_day_of_week()
    bar_x = 360
    bar_y = H - 90
    bar_w = 22
    bar_gap = 6
    max_dow = max(d["avg_xp"] for d in dow_data) or 1
    bar_area_h = 160

    _label("Best Day of Week  (Avg XP)", bar_y + 12, x=bar_x, color=C_FAINT, size=8)
    bar_y -= 4

    for i, d_item in enumerate(dow_data):
        bh = int(d_item["avg_xp"] / max_dow * bar_area_h)
        bx_ = bar_x + i * (bar_w + bar_gap)
        is_best = d_item["avg_xp"] == max_dow
        col = C_GOLD if is_best else HexColor("#4a3010")
        if bh > 0:
            c.setFillColor(col)
            c.rect(bx_, bar_y - bar_area_h, bar_w, bh, fill=1, stroke=0)
        c.setFillColor(C_FAINT if not is_best else C_GOLD)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(bx_ + bar_w // 2, bar_y - bar_area_h - 12, d_item["day"])
        if d_item["avg_xp"] > 0:
            c.setFillColor(col)
            c.setFont("Helvetica", 6)
            c.drawCentredString(
                bx_ + bar_w // 2, bar_y - bar_area_h + bh + 2, str(d_item["avg_xp"])
            )

    _rule(50, C_FAINT)
    _rule(46, C_GOLD)
    c.setFillColor(C_FAINT)
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 32, f"ChronicForge  ·  {data['month_name']}")
    c.showPage()

    # ═══════════════════════════════════════════════════════════════
    # PAGE 4 — QUESTS + ROAST JOURNAL
    # ═══════════════════════════════════════════════════════════════
    _draw_bg()
    _rule(H - 40, C_GOLD)
    _label("Quests & Chronicle", H - 55, size=9, color=C_GOLD)
    _rule(H - 62, C_FAINT)

    cy = H - 85
    _label(
        f"Quests Completed This Month  ·  {data['quests_done']} total", cy, color=C_GOLD
    )
    cy -= 14
    _rule(cy, C_RULE_PDF)
    cy -= 16

    if data["quest_list"]:
        for qt in data["quest_list"]:
            c.setFillColor(C_GOLD)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(40, cy, "✦")
            c.setFillColor(C_INK)
            c.setFont("Helvetica", 9)
            c.drawString(56, cy, qt)
            cy -= 16
    else:
        c.setFillColor(C_FAINT)
        c.setFont("Helvetica", 9)
        c.drawString(40, cy, "No quests completed this month.")
        cy -= 16

    cy -= 10
    _label("Chronicle of Shame & Glory  ·  Selected Entries", cy, color=C_GOLD)
    cy -= 14
    _rule(cy, C_RULE_PDF)
    cy -= 16

    type_colors = {"roast": C_RED, "praise": C_GREEN, "neutral": C_FAINT}
    for entry in data["roasts"][:6]:
        col = type_colors.get(entry["type"], C_FAINT)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(40, cy, "·")
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica", 9)
        lines = simpleSplit(f'"{entry["text"]}"', "Helvetica", 9, W - 100)
        for i, line in enumerate(lines[:2]):
            c.drawString(54, cy - i * 12, line)
        cy -= 12 * min(len(lines), 2) + 8

    _rule(50, C_FAINT)
    _rule(46, C_GOLD)
    c.setFillColor(C_FAINT)
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 32, f"ChronicForge  ·  {data['month_name']}")
    c.showPage()

    # ═══════════════════════════════════════════════════════════════
    # PAGE 5 — NEXT MONTH ORDERS
    # ═══════════════════════════════════════════════════════════════
    _draw_bg()
    _rule(H - 40, C_GOLD)
    _label("Orders for Next Month", H - 55, size=9, color=C_GOLD)
    _rule(H - 62, C_FAINT)

    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    next_name = date(next_year, next_month, 1).strftime("%B %Y")

    c.setFillColor(C_GOLD_B)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(40, H - 110, next_name.upper())

    c.setFillColor(C_GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, H - 140, "⚡  SOLDIER BOY'S ORDERS")

    # Advice box
    c.setFillColor(HexColor("#110a03"))
    c.rect(40, H - 230, W - 80, 80, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#4a3010"))
    c.rect(40, H - 230, W - 80, 80, fill=0, stroke=1)
    c.setFillColor(C_WHITE)
    c.setFont("Helvetica", 11)
    lines = simpleSplit(advice, "Helvetica", 11, W - 120)
    ty = H - 162
    for line in lines[:4]:
        c.drawString(56, ty, line)
        ty -= 17

    # Focus areas
    c.setFillColor(C_GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, H - 258, "FOCUS AREAS")
    _rule(H - 264, C_RULE_PDF)

    areas = [
        (f"Neglected stat: {data['worst_stat'].upper()}", C_RED),
        (f"Keep building: {data['best_stat'].upper()}", C_GREEN),
        (f"Target consistency: {min(data['consistency'] + 20, 100)}%+", C_GOLD),
    ]
    ay = H - 285
    for text, col in areas:
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, ay, "▸")
        c.setFillColor(C_INK)
        c.setFont("Helvetica", 10)
        c.drawString(56, ay, text)
        ay -= 22

    # Closing ornament
    c.setStrokeColor(C_GOLD)
    c.setLineWidth(1.5)
    c.line(40, 70, W - 40, 70)
    c.setFillColor(C_GOLD)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, 52, "FORGE THY LEGEND.  ONE DAY AT A TIME.")
    c.setFillColor(C_FAINT)
    c.setFont("Helvetica", 7)
    c.drawCentredString(
        W / 2,
        38,
        "ChronicForge  ·  Generated by Soldier Boy's Department of Disappointment",
    )

    c.save()
    print(f"[ChronicForge] Recap PDF: {out_path}")
    return out_path


# ── Auto-run check ─────────────────────────────────────────────────────────────


def should_generate_recap() -> bool:
    """True on the 1st of the month if this month's recap doesn't exist yet."""
    today = date.today()
    if today.day != 1:
        return False
    year, month = _prev_month()
    out_dir = os.path.expanduser("~/ChronicForge_Recaps")
    out_path = os.path.join(out_dir, f"ChronicForge_Recap_{year}-{month:02d}.pdf")
    return not os.path.exists(out_path)


def maybe_generate_recap() -> Optional[str]:
    """Called from midnight tick — generates recap if needed."""
    if should_generate_recap():
        try:
            return generate_monthly_recap()
        except Exception as e:
            print(f"[ChronicForge] Recap generation failed: {e}")
    return None
