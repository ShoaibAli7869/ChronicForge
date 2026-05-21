"""
ChronicForge — Game Logic Core
Pure Python. Zero UI imports. Fully unit-testable.
Handles: XP, levelling, stat growth, class evolution,
         streak tracking, achievement detection.
"""

import math
from datetime import date, datetime, timedelta
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

# ── Level-up stat bonus constants ─────────────────────────────────────────────

LEVEL_UP_BASE_BONUS = 1.5        # awarded to all stats per level gained
LEVEL_UP_DOMINANT_EXTRA = 0.5   # extra bonus for class-dominant stat per level gained
ALL_STATS = list(STAT_KEYWORDS)


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

# ---------------------------------------------------------------------------
#  CLASS PERKS — each class grants gameplay bonuses
# ---------------------------------------------------------------------------

CLASS_PERKS: dict[str, dict] = {
    # Tier 1 (Level 5)
    "Warrior":     {"stat_bonus": "strength", "xp_multiplier": 0.10, "desc": "Iron Resolve: +10% XP from strength"},
    "Scholar":     {"extra_quest_slots": 1,   "desc": "Deep Study: +1 custom quest slot"},
    "Bard":        {"extra_freeze": True,     "desc": "Silver Tongue: +1 streak freeze at milestones"},
    "Monk":        {"journal_bonus": 15,      "desc": "Vital Essence: +15 XP on first journal entry"},
    "Sentinel":    {"daily_quest_bonus": 5,   "desc": "Daily Drill: +5 XP per daily quest completed"},
    "Artificer":   {"journal_goal_reduction": 25, "desc": "Spark of Genius: journal word goal -25"},
    "Merchant":    {"stat_bonus": "wealth", "xp_multiplier": 0.10, "desc": "Golden Touch: +10% XP from wealth"},
    # Tier 2 (Level 15)
    "Berserker":   {"stat_bonus": "strength", "xp_multiplier": 0.25, "desc": "Battle Fury: +25% XP from strength"},
    "Archmage":    {"extra_quest_slots": 2,   "desc": "Arcane Knowledge: +2 custom quest slots"},
    "Enchanter":   {"freeze_recharge_days": 5, "desc": "Mass Appeal: freezes recharge every 5 days"},
    "Paladin":     {"streak_protection": 0.50, "desc": "Divine Shield: lose only 50% of streak on break"},
    "Warlord":     {"daily_quest_bonus": 10,  "desc": "Iron March: +10 XP per daily quest"},
    "Runesmith":   {"journal_goal_reduction": 50, "desc": "Runic Inscription: journal word goal -50"},
    "Magnate":     {"compound_interest": 0.02, "desc": "Compound Interest: +2% XP per 10 streak days (max +20%)"},
    # Secret classes
    "Phantom":     {"stat_bonus": "all", "xp_multiplier": 0.10, "extra_quest_slots": 1, "desc": "Ghost Walk: +10% XP all"},
    "Overlord":    {"extra_quest_slots": 3, "extra_journal_xp": True, "desc": "Absolute Rule: +3 quest slots, bonus journal XP"},
    "Night Owl":   {"journal_bonus": 10, "desc": "Nocturnal: +10 bonus journal XP"},
    "Degenerate Scholar": {"stat_bonus": "intellect", "xp_multiplier": 0.15, "desc": "Obsessive Study: +15% intellect XP"},
    "Gym Ghost":   {"stat_bonus": "strength", "xp_multiplier": 0.15, "desc": "Eternal Pump: +15% strength XP"},
    "Discipline Demon": {"extra_quest_slots": 1, "daily_quest_bonus": 8, "desc": "Iron Will: +1 quest, +8 XP/daily"},
    "Renaissance Man": {"stat_bonus": "all", "xp_multiplier": 0.08, "desc": "Polymath: +8% XP all"},
}


def get_class_perks(char) -> dict:
    """Return the active perk dict for the character's current class."""
    return CLASS_PERKS.get(char.char_class, {})


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


# ── Level-up stat bonus ───────────────────────────────────────────────────────


def apply_level_up_stat_bonus(char, levels_gained: int) -> dict:
    """
    Award stat bonuses for each level gained.

    All stats receive LEVEL_UP_BASE_BONUS * levels_gained.
    The class-dominant stat also receives LEVEL_UP_DOMINANT_EXTRA * levels_gained.
    Stats are capped at 200.0.

    Returns a dict {stat: actual_delta} for all 7 stats.
    Changes are applied directly to `char` — caller is responsible for committing.
    """
    perks = get_class_perks(char)
    dominant = perks.get("stat_bonus")
    if not dominant or dominant == "all":
        stats = char.stats_dict
        dominant = max(stats, key=lambda s: stats[s])

    bonuses = {}
    for stat in ALL_STATS:
        old_val = getattr(char, stat)
        delta = levels_gained * LEVEL_UP_BASE_BONUS
        if stat == dominant:
            delta += levels_gained * LEVEL_UP_DOMINANT_EXTRA
        new_val = min(200.0, old_val + delta)
        setattr(char, stat, round(new_val, 2))
        bonuses[stat] = round(new_val - old_val, 2)

    return bonuses


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

# Maps each achievement key to XP and stat rewards granted on first unlock.
# "stat": None  → no stat reward
# "stat": "all" → apply stat_delta to all 7 stats
# "stat": "dominant" → apply stat_delta to the character's highest stat
ACHIEVEMENT_REWARDS: dict[str, dict] = {
    "first_log":    {"xp": 50,   "stat": "discipline",  "stat_delta": 0.5},
    "streak_3":     {"xp": 75,   "stat": "discipline",  "stat_delta": 0.5},
    "streak_7":     {"xp": 150,  "stat": "discipline",  "stat_delta": 1.0},
    "streak_30":    {"xp": 500,  "stat": "vitality",    "stat_delta": 2.0},
    "streak_100":   {"xp": 2000, "stat": "discipline",  "stat_delta": 5.0},
    "level_5":      {"xp": 100,  "stat": None,          "stat_delta": 0.0},
    "level_10":     {"xp": 250,  "stat": None,          "stat_delta": 0.0},
    "level_25":     {"xp": 750,  "stat": None,          "stat_delta": 0.0},
    "level_50":     {"xp": 2000, "stat": None,          "stat_delta": 0.0},
    "stat_50":      {"xp": 200,  "stat": "dominant",    "stat_delta": 1.0},
    "all_stats_20": {"xp": 300,  "stat": "all",         "stat_delta": 0.5},
    "all_stats_50": {"xp": 1000, "stat": "all",         "stat_delta": 2.0},
    "quest_10":     {"xp": 200,  "stat": "discipline",  "stat_delta": 0.5},
    "quest_50":     {"xp": 500,  "stat": "discipline",  "stat_delta": 1.0},
    "gym_10":       {"xp": 150,  "stat": "strength",    "stat_delta": 1.0},
    "read_10":      {"xp": 150,  "stat": "intellect",   "stat_delta": 1.0},
    "night_owl":    {"xp": 50,   "stat": "vitality",    "stat_delta": 0.3},
    "early_bird":   {"xp": 50,   "stat": "discipline",  "stat_delta": 0.5},
    "secret_class": {"xp": 500,  "stat": "all",         "stat_delta": 1.0},
}


_ACHIEVEMENT_DEF_MAP: dict[str, tuple] = {d[0]: d for d in ACHIEVEMENT_DEFS}


def check_achievements(char: Character, session) -> tuple[list[tuple[str, str]], int]:
    """
    Returns (new_unlocks, achievement_xp_total) where new_unlocks is a list of
    (key, title) for newly unlocked achievements and achievement_xp_total is
    the total XP awarded by those achievements.
    """
    unlocked_keys = {a.key for a in char.achievements}
    new_unlocks: list[tuple[str, str]] = []
    achievement_xp_total = 0

    def unlock(key: str):
        nonlocal achievement_xp_total
        if key in unlocked_keys:
            return
        defn = _ACHIEVEMENT_DEF_MAP.get(key)
        if not defn:
            return
        session.add(Achievement(
            character_id=char.id,
            key=defn[0],
            title=defn[1],
            description=defn[2],
        ))
        new_unlocks.append((defn[0], defn[1]))

        reward = ACHIEVEMENT_REWARDS.get(key, {"xp": 50, "stat": None, "stat_delta": 0.0})
        xp_bonus = reward.get("xp", 0)
        achievement_xp_total += xp_bonus
        char.xp += xp_bonus
        delta = reward.get("stat_delta", 0.0)
        stat_target = reward.get("stat")
        if delta > 0 and stat_target:
            if stat_target == "all":
                for s in STAT_KEYWORDS:
                    setattr(char, s, round(min(200.0, getattr(char, s) + delta), 2))
            elif stat_target == "dominant":
                stats = char.stats_dict
                dominant = max(stats, key=lambda s: stats[s])
                setattr(char, dominant, round(min(200.0, getattr(char, dominant) + delta), 2))
            elif hasattr(char, stat_target):
                setattr(char, stat_target, round(min(200.0, getattr(char, stat_target) + delta), 2))

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

    return new_unlocks, achievement_xp_total


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

        # Level up check (initial pass, before achievement XP)
        levelled_up = False
        while char.xp >= xp_for_level(char.level + 1):
            char.level += 1
            levelled_up = True

        # Achievements — also awards XP/stat bonuses, may trigger further level-ups
        new_achievements, achievement_xp = check_achievements(char, session)

        while char.xp >= xp_for_level(char.level + 1):
            char.level += 1
            levelled_up = True

        stat_bonuses = {}
        if levelled_up:
            stat_bonuses = apply_level_up_stat_bonus(char, levels_gained)

        char.xp_to_next = xp_to_next_level(char.level)
        char.char_class = get_class(char)
        char.title = get_title(char)

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
            "achievement_xp": achievement_xp,
            "total_xp": char.xp,
            "xp_to_next": char.xp_to_next,
            "stat_bonuses": stat_bonuses,
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


def check_daily_login_bonus() -> dict:
    """Award +25 XP and +0.2 to weakest stat on first app open each day."""
    today = date.today().isoformat()

    with SessionFactory() as session:
        char = session.get(Character, 1)
        if char is None:
            return {"awarded": False}
        if char.last_login_date == today:
            return {"awarded": False}

        # Find weakest stat
        stats = char.stats_dict
        weakest_stat = min(stats, key=lambda s: stats[s])

        # Award bonus
        char.xp += 25
        old_val = getattr(char, weakest_stat)
        new_val = round(min(200.0, old_val + 0.2), 2)
        setattr(char, weakest_stat, new_val)
        char.last_login_date = today

        session.commit()
        return {
            "awarded": True,
            "xp": 25,
            "stat": weakest_stat,
            "stat_delta": round(new_val - old_val, 2),
        }
