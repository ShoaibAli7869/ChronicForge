"""
ChronicForge — Analytics Engine
Queries SQLite for chart and heatmap data.
Pure Python — no Qt imports.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select

from core.database import Character, LogEntry, SessionFactory


def get_xp_by_day(days: int = 30) -> list[dict]:
    """
    Returns XP earned per day for the last N days.
    Fills gaps with zero so charts have continuous x-axis.
    [{'date': '2026-05-01', 'xp': 240}, ...]
    """
    start = (date.today() - timedelta(days=days - 1)).isoformat()

    with SessionFactory() as session:
        rows = session.execute(
            select(LogEntry.date, func.sum(LogEntry.xp_awarded).label("xp"))
            .where(LogEntry.character_id == 1, LogEntry.date >= start)
            .group_by(LogEntry.date)
            .order_by(LogEntry.date)
        ).all()

    # Build lookup
    xp_map = {r.date: int(r.xp) for r in rows}

    # Fill every day including zeros
    result = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        result.append({"date": d, "xp": xp_map.get(d, 0)})
    return result


def get_stat_history(days: int = 30) -> dict[str, list[dict]]:
    """
    Returns each stat's daily log count (proxy for growth) per day.
    {'strength': [{'date': '...', 'count': 2}, ...], ...}
    """
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    stats = [
        "strength",
        "intellect",
        "charisma",
        "vitality",
        "discipline",
        "creativity",
        "wealth",
    ]

    with SessionFactory() as session:
        rows = session.execute(
            select(
                LogEntry.date, LogEntry.category, func.count(LogEntry.id).label("cnt")
            )
            .where(LogEntry.character_id == 1, LogEntry.date >= start)
            .group_by(LogEntry.date, LogEntry.category)
            .order_by(LogEntry.date)
        ).all()

    # Build per-stat lookup
    lookup: dict[str, dict[str, int]] = defaultdict(dict)
    for r in rows:
        lookup[r.category][r.date] = int(r.cnt)

    result = {}
    all_days = [
        (date.today() - timedelta(days=days - 1 - i)).isoformat() for i in range(days)
    ]
    for stat in stats:
        result[stat] = [{"date": d, "count": lookup[stat].get(d, 0)} for d in all_days]
    return result


def get_heatmap_data(days: int = 365) -> list[dict]:
    """
    GitHub-style activity heatmap.
    Returns one entry per day with activity level 0-4.
    [{'date': '...', 'xp': 0, 'count': 0, 'level': 0}, ...]
    level: 0=none, 1=light, 2=moderate, 3=good, 4=excellent
    """
    start = (date.today() - timedelta(days=days - 1)).isoformat()

    with SessionFactory() as session:
        rows = session.execute(
            select(
                LogEntry.date,
                func.sum(LogEntry.xp_awarded).label("xp"),
                func.count(LogEntry.id).label("cnt"),
            )
            .where(LogEntry.character_id == 1, LogEntry.date >= start)
            .group_by(LogEntry.date)
        ).all()

    xp_map = {r.date: int(r.xp) for r in rows}
    cnt_map = {r.date: int(r.cnt) for r in rows}

    result = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        xp = xp_map.get(d, 0)
        cnt = cnt_map.get(d, 0)
        # Level based on XP thresholds
        if xp == 0:
            level = 0
        elif xp < 100:
            level = 1
        elif xp < 300:
            level = 2
        elif xp < 600:
            level = 3
        else:
            level = 4
        result.append({"date": d, "xp": xp, "count": cnt, "level": level})
    return result


def get_best_day_of_week() -> list[dict]:
    """
    Returns average XP per day of week.
    [{'day': 'Mon', 'avg_xp': 320}, ...]
    """
    with SessionFactory() as session:
        rows = session.scalars(select(LogEntry).where(LogEntry.character_id == 1)).all()

    from datetime import datetime

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_xp: dict[int, list[int]] = defaultdict(list)

    for r in rows:
        try:
            d = datetime.strptime(r.date, "%Y-%m-%d")
            dow = d.weekday()
            day_xp[dow].append(r.xp_awarded)
        except Exception:
            pass

    return [
        {
            "day": day_names[i],
            "avg_xp": round(sum(day_xp[i]) / len(day_xp[i])) if day_xp[i] else 0,
        }
        for i in range(7)
    ]


def get_today_summary() -> dict:
    """Quick summary for dashboard headers."""
    today = date.today().isoformat()
    with SessionFactory() as session:
        rows = session.scalars(
            select(LogEntry).where(LogEntry.character_id == 1, LogEntry.date == today)
        ).all()
    total_xp = sum(r.xp_awarded for r in rows)
    stats_done = list({r.category for r in rows})
    return {
        "count": len(rows),
        "total_xp": total_xp,
        "stats_done": stats_done,
        "date": today,
    }


def get_streak_calendar(weeks: int = 18) -> list[dict]:
    """
    Same as heatmap but limited to N weeks for the compact calendar view.
    """
    return get_heatmap_data(days=weeks * 7)
