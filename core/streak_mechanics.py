"""
core/streak_mechanics.py — streak freeze system and grace period.
"""

from datetime import date, datetime, timedelta
from typing import Optional


def get_effective_date() -> str:
    """
    Return the 'effective' date for streak purposes.
    If it's before grace_hour (default 2am), treat it as yesterday.
    """
    try:
        from config.settings import load_config

        grace_hour = load_config().streak_grace_hour
    except Exception:
        grace_hour = 2

    now = datetime.now()
    if now.hour < grace_hour:
        return (date.today() - timedelta(days=1)).isoformat()
    return date.today().isoformat()


def check_and_apply_freeze(char) -> bool:
    """
    Check if streak would be broken and apply a freeze if available.
    Call this when loading the app if last_active_date != today.
    Returns True if a freeze was consumed.
    """
    effective_today = get_effective_date()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    last = char.last_active_date
    if last is None:
        return False

    # If last active was yesterday or today → streak intact, no freeze needed
    if last >= yesterday:
        return False

    # Streak would break — check for available freezes
    freezes = getattr(char, "streak_freezes", 0) or 0
    if freezes > 0:
        char.streak_freezes = freezes - 1
        char.last_active_date = yesterday  # bridge the gap
        print(f"[ChronicForge] Streak freeze used! {char.streak_freezes} remaining.")
        return True

    return False


def award_freeze_if_earned(char) -> bool:
    """
    Award a streak freeze at certain milestones.
    Milestones: 3, 7, 14, 30, 60, 100 days.
    Returns True if a freeze was awarded.
    """
    milestones = {3, 7, 14, 30, 60, 100}
    streak = char.current_streak

    if streak in milestones:
        current = getattr(char, "streak_freezes", 0) or 0
        max_f = 3  # cap at 3 banked freezes
        if current < max_f:
            char.streak_freezes = current + 1
            print(
                f"[ChronicForge] Streak freeze earned at {streak} days! "
                f"Total: {char.streak_freezes}"
            )
            return True
    return False


def get_streak_status(char) -> dict:
    """
    Return a full streak status dict for display.
    """
    freezes = getattr(char, "streak_freezes", 0) or 0
    effective = get_effective_date()

    try:
        from config.settings import load_config

        grace = load_config().streak_grace_hour
    except Exception:
        grace = 2

    last = char.last_active_date or ""
    active_today = last >= effective if last else False

    return {
        "current_streak": char.current_streak,
        "longest_streak": char.longest_streak,
        "freezes": freezes,
        "active_today": active_today,
        "grace_hour": grace,
        "effective_date": effective,
        "at_risk": not active_today and char.current_streak > 0,
    }
