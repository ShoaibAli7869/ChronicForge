"""
ChronicForge — Game Logic Core
Pure Python. Zero UI imports. Fully unit-testable.
Handles: XP, levelling, stat growth, class evolution,
         streak tracking, achievement detection.
"""

import math
from datetime import date, datetime
from typing import Optional

from core.database import Achievement, Character, LogEntry, Roast, SessionFactory
from core.streak_mechanics import (
    award_freeze_if_earned,
    check_and_apply_freeze,
    get_effective_date,
)

# ── XP curve ─────────────────────────────────────────────────────────────────


def xp_for_level(level: int) -> int:
    """Total XP required to reach `level` from scratch."""
    return level**2 * 100


def xp_to_next_level(level: int) -> int:
    """XP needed to go from `level` to `level+1`."""
    return xp_for_level(level + 1) - xp_for_level(level)


# ── Stat → XP mapping ─────────────────────────────────────────────────────────

STAT_KEYWORDS: dict[str, list[str]] = {
    "strength": [
        "gym",
        "workout",
        "exercise",
        "lift",
        "run",
        "sport",
        "swim",
        "hike",
        "push",
        "pull",
        "squat",
        "cardio",
        "walk",
    ],
    "intellect": [
        "read",
        "study",
        "learn",
        "course",
        "book",
        "research",
        "lecture",
        "paper",
        "tutorial",
        "practice",
        "code",
        "solve",
    ],
    "charisma": [
        "social",
        "network",
        "meet",
        "call",
        "friend",
        "date",
        "talk",
        "present",
        "interview",
        "mentor",
        "party",
        "chat",
    ],
    "vitality": [
        "sleep",
        "diet",
        "eat",
        "water",
        "hydrate",
        "nofap",
        "rest",
        "meditat",
        "breath",
        "health",
        "fast",
        "nutrition",
    ],
    "discipline": [
        "wake",
        "early",
        "routine",
        "habit",
        "consistent",
        "task",
        "plan",
        "organiz",
        "schedule",
        "focus",
        "deep work",
        "no phone",
    ],
    "creativity": [
        "write",
        "art",
        "design",
        "draw",
        "music",
        "creat",
        "build",
        "project",
        "blog",
        "compose",
        "sketch",
        "invent",
    ],
    "wealth": [
        "earn",
        "save",
        "invest",
        "income",
        "budget",
        "finance",
        "freelance",
        "sell",
        "profit",
        "crypto",
        "stock",
        "business",
    ],
}

# XP per intensity level per activity
XP_TABLE = {1: 30, 2: 75, 3: 150}

# Stat point gain per intensity
STAT_TABLE = {1: 0.3, 2: 0.7, 3: 1.4}

# Streak milestone stat bonuses
STREAK_STAT_BONUSES: dict[int, dict] = {
    7:   {"discipline": 1.0, "vitality": 0.5},
    14:  {"discipline": 1.5, "vitality": 0.5},
    30:  {"discipline": 2.0, "vitality": 1.0, "_all_other": 0.5},
    60:  {"discipline": 3.0, "vitality": 1.5, "_all_other": 1.0},
    100: {"discipline": 5.0, "vitality": 2.0, "_all_other": 2.0},
}
_ALL_STAT_NAMES: list[str] = list(STAT_KEYWORDS.keys())


def detect_stat(activity: str) -> str:
    """Guess which stat an activity text maps to. Returns 'discipline' as fallback."""
    text = activity.lower()
    scores = {stat: 0 for stat in STAT_KEYWORDS}
    for stat, keywords in STAT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[stat] += 1
    best = max(scores, key=lambda s: scores[s])
    return best if scores[best] > 0 else "discipline"


# ── Class evolution ───────────────────────────────────────────────────────────

CLASS_TREE = [
    # (level_required, dominant_stat, class_name)
    # Starter
    (1, None, "Wanderer"),
    (3, None, "Novice"),
    # Tier 1 (lv 5)
    (5, "strength", "Warrior"),
    (5, "intellect", "Scholar"),
    (5, "charisma", "Bard"),
    (5, "vitality", "Monk"),
    (5, "discipline", "Sentinel"),
    (5, "creativity", "Artificer"),
    (5, "wealth", "Merchant"),
    # Tier 2 (lv 15)
    (15, "strength", "Berserker"),
    (15, "intellect", "Archmage"),
    (15, "charisma", "Enchanter"),
    (15, "vitality", "Paladin"),
    (15, "discipline", "Warlord"),
    (15, "creativity", "Runesmith"),
    (15, "wealth", "Magnate"),
    # Secret classes
    (20, None, "Phantom"),  # balanced all stats
    (30, None, "Overlord"),  # total power > 400
]

SECRET_CLASSES = {
    "Night Owl": lambda c: c.current_streak >= 30 and c.vitality < 20,
    "Degenerate Scholar": lambda c: c.intellect > 80 and c.charisma < 20,
    "Gym Ghost": lambda c: c.strength > 60 and c.discipline < 25,
    "Discipline Demon": lambda c: c.discipline > 80,
    "Renaissance Man": lambda c: all(getattr(c, s) > 40 for s in STAT_KEYWORDS),
}

TITLES = {
    # Streak titles
    "3_day_streak": "Oath-Keeper",
    "7_day_streak": "Knight of Habit",
    "30_day_streak": "Iron Vow",
    "100_day_streak": "Legendary Resolve",
    # Stat titles
    "str_50": "Iron-Fisted",
    "int_50": "Loremaster",
    "cha_50": "Silver-Tongued",
    "vit_50": "Undying",
    "dis_50": "Unbreakable",
    "cre_50": "Visionary",
    "wea_50": "Golden Hand",
    # Level titles
    "level_10": "Veteran",
    "level_25": "Champion",
    "level_50": "Legend",
    "level_99": "Mythic",
}


def get_class(char: Character) -> str:
    """Determine character class from level + dominant stat."""
    if char.level < 3:
        return "Wanderer"
    if char.level < 5:
        return "Novice"

    stats = char.stats_dict
    dominant = max(stats, key=lambda s: stats[s])

    # Check secret classes first
    for secret_name, condition in SECRET_CLASSES.items():
        if condition(char):
            return secret_name

    # Tier 2
    if char.level >= 15:
        for req_lvl, req_stat, cls in CLASS_TREE:
            if req_lvl == 15 and req_stat == dominant:
                return cls

    # Tier 1
    if char.level >= 5:
        for req_lvl, req_stat, cls in CLASS_TREE:
            if req_lvl == 5 and req_stat == dominant:
                return cls

    return "Novice"


def get_title(char: Character) -> str:
    """Pick the most impressive earned title."""
    # Level titles take priority
    for threshold, title in [
        (99, "Mythic"),
        (50, "Legend"),
        (25, "Champion"),
        (10, "Veteran"),
    ]:
        if char.level >= threshold:
            return title
    # Streak
    if char.longest_streak >= 100:
        return "Iron Vow"
    if char.longest_streak >= 30:
        return "Knight of Habit"
    if char.longest_streak >= 7:
        return "Oath-Keeper"
    # Stat
    stats = char.stats_dict
    best_stat = max(stats, key=lambda s: stats[s])
    best_val = stats[best_stat]
    if best_val >= 50:
        mapping = {
            "strength": "Iron-Fisted",
            "intellect": "Loremaster",
            "charisma": "Silver-Tongued",
            "vitality": "Undying",
            "discipline": "Unbreakable",
            "creativity": "Visionary",
            "wealth": "Golden Hand",
        }
        return mapping.get(best_stat, "The Wanderer")
    return "The Wanderer"


# ── Achievement detection ─────────────────────────────────────────────────────

ACHIEVEMENT_DEFS = [
    ("first_log", "First Blood", "Logged thy first activity."),
    ("streak_3", "Oath-Keeper", "3-day activity streak."),
    ("streak_7", "Knight of Habit", "7 days straight. The realm notices."),
    ("streak_30", "Iron Vow", "30-day streak. Thou art unstoppable."),
    ("streak_100", "Legendary Resolve", "100 days. The gods bow."),
    ("level_5", "Blooded", "Reached Level 5."),
    ("level_10", "Veteran", "Reached Level 10."),
    ("level_25", "Champion", "Reached Level 25. Few walk this path."),
    ("level_50", "Legend", "Level 50. Thy name echoes."),
    ("stat_50", "Half-Century", "One stat reached 50."),
    ("all_stats_20", "Well-Rounded", "All stats above 20."),
    ("all_stats_50", "Renaissance Man", "All stats above 50."),
    ("quest_10", "Quest Hoarder", "Completed 10 quests."),
    ("quest_50", "Questmaster", "Completed 50 quests."),
    ("night_owl", "Night Owl", "Logged at 2am. Dark times."),
    ("early_bird", "Dawn Sentinel", "Logged before 6am."),
    ("gym_10", "Regular", "10 gym sessions logged."),
    ("read_10", "Bookworm", "10 reading sessions."),
    ("secret_class", "The Unexpected", "Unlocked a secret class."),
]


def check_achievements(char: Character, session) -> list[tuple[str, str]]:
    """Returns list of (key, title) for newly unlocked achievements."""
    unlocked_keys = {a.key for a in char.achievements}
    new_unlocks = []

    def unlock(key: str):
        if key not in unlocked_keys:
            defn = next((d for d in ACHIEVEMENT_DEFS if d[0] == key), None)
            if defn:
                ach = Achievement(
                    character_id=char.id,
                    key=defn[0],
                    title=defn[1],
                    description=defn[2],
                )
                session.add(ach)
                new_unlocks.append((defn[0], defn[1]))

    # Level checks
    if char.level >= 5:
        unlock("level_5")
    if char.level >= 10:
        unlock("level_10")
    if char.level >= 25:
        unlock("level_25")
    if char.level >= 50:
        unlock("level_50")

    # Streak checks
    if char.current_streak >= 3:
        unlock("streak_3")
    if char.current_streak >= 7:
        unlock("streak_7")
    if char.current_streak >= 30:
        unlock("streak_30")
    if char.current_streak >= 100:
        unlock("streak_100")

    # Stat checks
    stats = char.stats_dict
    if any(v >= 50 for v in stats.values()):
        unlock("stat_50")
    if all(v >= 20 for v in stats.values()):
        unlock("all_stats_20")
    if all(v >= 50 for v in stats.values()):
        unlock("all_stats_50")

    # Entry count checks
    entry_count = len(char.log_entries)
    if entry_count >= 1:
        unlock("first_log")

    # Quest checks
    completed_quests = sum(1 for q in char.quests if q.completed)
    if completed_quests >= 10:
        unlock("quest_10")
    if completed_quests >= 50:
        unlock("quest_50")

    # Secret class
    if get_class(char) in SECRET_CLASSES:
        unlock("secret_class")

    # Time-of-day checks (check current hour)
    hour = datetime.now().hour
    if hour == 2 or hour == 3:
        unlock("night_owl")
    if hour < 6:
        unlock("early_bird")

    # Category-specific counts
    gym_entries = sum(1 for e in char.log_entries if e.category == "strength")
    read_entries = sum(1 for e in char.log_entries if e.category == "intellect")
    if gym_entries >= 10:
        unlock("gym_10")
    if read_entries >= 10:
        unlock("read_10")

    return new_unlocks


# ── Streak milestone bonuses ──────────────────────────────────────────────────


def apply_streak_milestone_bonus(char) -> dict:
    """Award stat bonuses at streak milestones. Returns {stat: delta} or {} if no milestone."""
    streak = getattr(char, "current_streak", 0) or 0
    if streak not in STREAK_STAT_BONUSES:
        return {}
    bonuses = STREAK_STAT_BONUSES[streak]
    result = {}
    all_other_delta = bonuses.get("_all_other", 0.0)
    named_stats = {k: v for k, v in bonuses.items() if not k.startswith("_")}
    for stat in _ALL_STAT_NAMES:
        delta = named_stats.get(stat, all_other_delta)
        if delta > 0:
            old_val = getattr(char, stat, 10.0)
            new_val = round(min(200.0, old_val + delta), 2)
            setattr(char, stat, new_val)
            result[stat] = round(new_val - old_val, 2)
    return result


# ── Stat neglect detection ────────────────────────────────────────────────────


def check_neglected_stats(days: int = 7) -> list[str]:
    """Return list of stat names not logged in the last N days."""
    from datetime import date, timedelta

    from sqlalchemy import select

    cutoff = (date.today() - timedelta(days=days)).isoformat()

    with SessionFactory() as session:
        recent_stats = set(
            session.scalars(
                select(LogEntry.category)
                .where(LogEntry.character_id == 1)
                .where(LogEntry.date >= cutoff)
                .distinct()
            ).all()
        )

    return [s for s in _ALL_STAT_NAMES if s not in recent_stats]


# ── Core game actions ─────────────────────────────────────────────────────────


def log_activity(
    activity: str,
    intensity: int = 2,
    notes: Optional[str] = None,
    stat_override: Optional[str] = None,
) -> dict:
    """
    Log an activity, award XP and stat points, check level-up.
    Returns a result dict with everything that happened.
    """
    with SessionFactory() as session:
        char = session.get(Character, 1)
        if char is None:
            return {"error": "No character found. Run init_db() first."}

        # Clamp intensity
        intensity = max(1, min(3, intensity))

        # Detect stat
        stat = stat_override or detect_stat(activity)
        if stat not in STAT_KEYWORDS:
            stat = "discipline"

        # Calculate XP (with streak bonus)
        base_xp = XP_TABLE[intensity]
        streak_mult = 1.0 + min(char.current_streak * 0.05, 0.5)  # up to +50%
        xp_awarded = int(base_xp * streak_mult)
        stat_delta = STAT_TABLE[intensity]

        # Apply to character
        char.xp += xp_awarded
        current_val = getattr(char, stat)
        setattr(char, stat, round(min(200.0, current_val + stat_delta), 2))

        # Update streak using grace period logic
        effective_today = get_effective_date()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if char.last_active_date == effective_today:
            pass  # already logged today
        elif char.last_active_date and char.last_active_date >= yesterday:
            char.current_streak += 1
        else:
            char.current_streak = 1  # reset
        char.last_active_date = effective_today
        char.longest_streak = max(char.longest_streak, char.current_streak)
        # Award streak freeze at milestones
        award_freeze_if_earned(char)
        milestone_bonuses = apply_streak_milestone_bonus(char)

        # Log entry
        entry = LogEntry(
            character_id=char.id,
            date=today,
            category=stat,
            activity=activity,
            notes=notes,
            xp_awarded=xp_awarded,
            stat_delta=stat_delta,
            intensity=intensity,
        )
        session.add(entry)

        # Level up check
        levelled_up = False
        levels_gained = 0
        while char.xp >= xp_for_level(char.level + 1):
            char.level += 1
            levels_gained += 1
            levelled_up = True

        char.xp_to_next = xp_to_next_level(char.level)
        char.char_class = get_class(char)
        char.title = get_title(char)

        # Achievements
        new_achievements = check_achievements(char, session)

        session.commit()

        return {
            "activity": activity,
            "stat": stat,
            "xp_awarded": xp_awarded,
            "stat_delta": stat_delta,
            "intensity": intensity,
            "streak_bonus": round((streak_mult - 1.0) * 100),
            "current_streak": char.current_streak,
            "levelled_up": levelled_up,
            "new_level": char.level if levelled_up else None,
            "new_class": char.char_class if levelled_up else None,
            "achievements": new_achievements,
            "total_xp": char.xp,
            "xp_to_next": char.xp_to_next,
            "milestone_bonuses": milestone_bonuses,
        }


def get_character() -> dict:
    """Fetch full character snapshot."""
    with SessionFactory() as session:
        char = session.get(Character, 1)
        if not char:
            return {}
        return {
            "name": char.name,
            "title": char.title,
            "class": char.char_class,
            "level": char.level,
            "xp": char.xp,
            "xp_to_next": char.xp_to_next,
            "xp_percent": round(
                (char.xp - xp_for_level(char.level))
                / max(1, xp_to_next_level(char.level))
                * 100,
                1,
            ),
            "stats": char.stats_dict,
            "total_power": round(char.total_power, 1),
            "streak": char.current_streak,
            "longest_streak": char.longest_streak,
            "achievements": len(char.achievements),
            "streak_freezes": getattr(char, "streak_freezes", 0) or 0,
        }


def get_recent_logs(days: int = 7) -> list[dict]:
    """Get log entries from the past N days."""
    from sqlalchemy import select

    with SessionFactory() as session:
        stmt = (
            select(LogEntry)
            .where(LogEntry.character_id == 1)
            .order_by(LogEntry.created_at.desc())
            .limit(days * 10)
        )
        entries = session.scalars(stmt).all()
        return [
            {
                "id": e.id,
                "date": e.date,
                "activity": e.activity,
                "stat": e.category,
                "xp": e.xp_awarded,
                "intensity": e.intensity,
            }
            for e in entries
        ]


def set_character_name(name: str, hero_name: Optional[str] = None):
    """Set character name."""
    with SessionFactory() as session:
        char = session.get(Character, 1)
        if char:
            char.name = name
            session.commit()
