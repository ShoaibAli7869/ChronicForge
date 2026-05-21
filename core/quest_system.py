"""
ChronicForge — Quest System
Generates daily / weekly / life quests based on character stats.
Tracks completion and failure. Awards XP on completion.

Fixes in this version:
  - get_active_quests() now filters daily by today, weekly by current week
  - Old incomplete daily quests from past days auto-expired at midnight
  - _quest_to_dict includes intensity field derived from xp_reward
"""

import random
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select

from core.database import Character, Quest, SessionFactory
from core.game_logic import xp_to_next_level

QUEST_STAT_REWARDS = {"daily": 0.3, "weekly": 0.5, "life": 1.0}
_STAT_CAP = 200.0

# ── Quest templates ───────────────────────────────────────────────────────────

DAILY_TEMPLATES = {
    "strength": [
        ("Iron Will", "Complete a workout session today.", 2),
        ("Warrior's Call", "Do 50 push-ups before nightfall.", 2),
        ("Siege Training", "30 minutes of physical exercise.", 1),
        ("Knight's Regimen", "Hit the gym or run at least 2km.", 3),
        ("Body of Steel", "Full body workout — no skipping.", 3),
    ],
    "intellect": [
        ("Scholar's Duty", "Read at least 20 pages today.", 1),
        ("Arcane Study", "Complete one study session (45+ min).", 2),
        ("Lore Seeker", "Learn something new and write it down.", 1),
        ("Deep Work Rite", "2 hours of focused, distraction-free work.", 3),
        ("Tome of Progress", "Finish a chapter or module.", 2),
    ],
    "charisma": [
        ("Silver Tongue", "Have a meaningful conversation today.", 1),
        ("Social Oath", "Reach out to someone you haven't talked to.", 2),
        ("Herald's Task", "Make one new professional connection.", 3),
        ("Bard's Practice", "Practice public speaking or storytelling.", 2),
        ("Bonds of Steel", "Spend quality time with friends or family.", 1),
    ],
    "vitality": [
        ("Temple Maintenance", "Drink 2L of water today.", 1),
        ("Monk's Slumber", "Sleep 7–9 hours tonight.", 2),
        ("Clean Fuel", "Eat a clean, healthy meal.", 1),
        ("Mind Fortress", "Meditate for 10+ minutes.", 2),
        ("Streak Guardian", "Maintain thy daily streak.", 1),
    ],
    "discipline": [
        ("Dawn Protocol", "Wake up before 7am.", 2),
        ("No Scroll Oath", "No phone for the first hour after waking.", 2),
        ("Task Slayer", "Complete your 3 most important tasks.", 3),
        ("Routine Keeper", "Follow your morning routine without fail.", 2),
        ("Iron Schedule", "Plan tomorrow before midnight.", 1),
    ],
    "creativity": [
        ("Forge Something", "Create anything — write, draw, code, build.", 2),
        ("Artisan's Call", "Work on a personal project for 30+ min.", 2),
        ("Spark of Genius", "Write down 10 ideas (any topic).", 1),
        ("Builder's Oath", "Make measurable progress on a side project.", 3),
        ("Chronicle Entry", "Write in a journal or blog.", 1),
    ],
    "wealth": [
        ("Ledger Check", "Review your budget or expenses.", 1),
        ("Golden Discipline", "Avoid one unnecessary purchase today.", 2),
        ("Merchant's Eye", "Research one investment or income idea.", 2),
        ("Treasury Report", "Update your financial tracker.", 1),
        ("Wealth Ritual", "Set aside any amount into savings.", 1),
    ],
}

WEEKLY_TEMPLATES = [
    ("Weekly Warrior", "Hit the gym 4 times this week.", "strength", 3, 400),
    ("Scholar's Week", "Read every single day this week.", "intellect", 3, 350),
    ("Social Crusade", "Meet or call 3 different people.", "charisma", 2, 300),
    ("Vitality Week", "Sleep 7+ hrs and hydrate every day.", "vitality", 2, 350),
    ("The Iron Week", "Complete all daily quests 5 days.", "discipline", 3, 500),
    (
        "Creator's Sprint",
        "Work on your project 5 days this week.",
        "creativity",
        3,
        400,
    ),
    ("Coin Keeper", "Log expenses every day this week.", "wealth", 2, 250),
    ("The Full Plate", "Log at least 3 activities every day.", "discipline", 3, 600),
    ("Endurance Trial", "Exercise 5 days straight.", "strength", 3, 500),
    ("Deep Work Week", "4 deep-work sessions this week.", "intellect", 3, 450),
]

LIFE_QUESTS = [
    ("The Iron Body", "Log 100 workout sessions.", "strength", 10000),
    ("Loremaster", "Read 50 books (log each one).", "intellect", 15000),
    ("The Network", "Make 100 meaningful connections.", "charisma", 12000),
    ("Temple of Flesh", "Maintain a 90-day wellness streak.", "vitality", 20000),
    ("The Unbreakable", "Complete a 365-day streak.", "discipline", 50000),
    ("Grand Artificer", "Ship 10 personal projects.", "creativity", 18000),
    ("The Treasury", "Save thy first 10,000 in any currency.", "wealth", 25000),
]


# ── Quest engine ──────────────────────────────────────────────────────────────


def expire_old_daily_quests():
    """
    Mark incomplete daily quests from past days as failed.
    Called at startup and midnight tick.
    Prevents past-day quests from polluting the active quest list.
    """
    today = date.today().isoformat()
    with SessionFactory() as session:
        old = session.scalars(
            select(Quest).where(
                Quest.character_id == 1,
                Quest.quest_type == "daily",
                Quest.completed == False,
                Quest.failed == False,
                Quest.due_date < today,
            )
        ).all()
        count = len(old)
        for q in old:
            q.failed = True
        if count:
            session.commit()
            print(f"[ChronicForge] Expired {count} past daily quest(s).")


def generate_daily_quests(n: int = 3) -> list[dict]:
    """
    Generate N daily quests for today only.
    Guard: returns existing if already generated today.
    """
    today = date.today().isoformat()
    expire_old_daily_quests()

    with SessionFactory() as session:
        char = session.get(Character, 1)
        if not char:
            return []

        existing = session.scalars(
            select(Quest).where(
                Quest.character_id == 1,
                Quest.quest_type == "daily",
                Quest.due_date == today,
                Quest.failed == False,
            )
        ).all()
        if existing:
            return [_quest_to_dict(q) for q in existing]

        # Weight toward weakest stats
        stats = char.stats_dict
        min_val = min(stats.values())
        max_val = max(stats.values()) + 0.1
        weights = {s: (max_val - v + min_val + 1) for s, v in stats.items()}
        selected = random.choices(
            list(weights.keys()), weights=list(weights.values()), k=n
        )

        created = []
        for stat in selected:
            title, desc, intensity = random.choice(DAILY_TEMPLATES[stat])
            base_xp = {1: 60, 2: 120, 3: 200}[intensity]
            xp_reward = int(base_xp * (1 + char.level * 0.05))
            q = Quest(
                character_id=char.id,
                title=title,
                description=desc,
                quest_type="daily",
                stat_target=stat,
                xp_reward=xp_reward,
                due_date=today,
            )
            session.add(q)
            created.append(q)
        session.commit()
        return [_quest_to_dict(q) for q in created]


def generate_weekly_quest() -> Optional[dict]:
    """Generate one weekly quest if none exists for this week."""
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    week_end = (date.today() + timedelta(days=6 - date.today().weekday())).isoformat()

    with SessionFactory() as session:
        char = session.get(Character, 1)
        if not char:
            return None

        existing = session.scalars(
            select(Quest).where(
                Quest.character_id == 1,
                Quest.quest_type == "weekly",
                Quest.due_date >= week_start,
                Quest.due_date <= week_end,
                Quest.failed == False,
            )
        ).first()
        if existing:
            return _quest_to_dict(existing)

        title, desc, stat, intensity, xp_reward = random.choice(WEEKLY_TEMPLATES)
        xp_reward = int(xp_reward * (1 + char.level * 0.03))
        q = Quest(
            character_id=char.id,
            title=title,
            description=desc,
            quest_type="weekly",
            stat_target=stat,
            xp_reward=xp_reward,
            due_date=week_end,
        )
        session.add(q)
        session.commit()
        return _quest_to_dict(q)


def seed_life_quests():
    """Seed permanent life quests if not already present."""
    with SessionFactory() as session:
        char = session.get(Character, 1)
        if not char:
            return
        existing_titles = {q.title for q in char.quests if q.quest_type == "life"}
        for title, desc, stat, xp in LIFE_QUESTS:
            if title not in existing_titles:
                session.add(
                    Quest(
                        character_id=char.id,
                        title=title,
                        description=desc,
                        quest_type="life",
                        stat_target=stat,
                        xp_reward=xp,
                    )
                )
        session.commit()


def complete_quest(quest_id: int) -> dict:
    """Mark a quest complete and award XP."""
    with SessionFactory() as session:
        quest = session.get(Quest, quest_id)
        if not quest or quest.completed:
            return {"error": "Quest not found or already completed."}
        quest.completed = True
        quest.completed_at = datetime.utcnow()

        char = session.get(Character, 1)
        char.xp += quest.xp_reward

        stat_gain = {}
        stat_delta = QUEST_STAT_REWARDS.get(quest.quest_type, 0.3)
        stat_name = quest.stat_target
        if stat_name and hasattr(char, stat_name):
            old_val = getattr(char, stat_name)
            new_val = round(min(_STAT_CAP, old_val + stat_delta), 2)
            setattr(char, stat_name, new_val)
            stat_gain = {stat_name: round(new_val - old_val, 2)}

        from core.game_logic import apply_level_up_stat_bonus, get_class, get_title, xp_for_level

        levelled_up = False
        levels_gained = 0
        while char.xp >= xp_for_level(char.level + 1):
            char.level += 1
            levels_gained += 1
            levelled_up = True

        stat_bonuses = {}
        if levelled_up:
            stat_bonuses = apply_level_up_stat_bonus(char, levels_gained)

        char.xp_to_next = xp_to_next_level(char.level)
        char.char_class = get_class(char)
        char.title = get_title(char)
        session.commit()
        return {
            "quest": quest.title,
            "xp_awarded": quest.xp_reward,
            "levelled_up": levelled_up,
            "new_level": char.level if levelled_up else None,
            "stat_gain": stat_gain,
            "stat_bonuses": stat_bonuses,
        }


def auto_complete_matching_quests(activity_stat: str) -> list[dict]:
    """
    Auto-complete any incomplete daily quests whose stat_target matches
    activity_stat. Awards XP and stat reward (daily rate) for each.
    Returns a list of result dicts for all auto-completed quests.
    """
    today = date.today().isoformat()
    results = []

    with SessionFactory() as session:
        char = session.get(Character, 1)
        if not char:
            return results

        matching = session.scalars(
            select(Quest).where(
                Quest.character_id == 1,
                Quest.quest_type == "daily",
                Quest.stat_target == activity_stat,
                Quest.completed == False,
                Quest.failed == False,
                Quest.due_date == today,
            )
        ).all()

        from core.game_logic import get_class, get_title, xp_for_level

        for q in matching:
            q.completed = True
            q.completed_at = datetime.utcnow()
            char.xp += q.xp_reward

            stat_gain = {}
            stat_name = q.stat_target
            if stat_name and hasattr(char, stat_name):
                old_val = getattr(char, stat_name)
                new_val = round(min(_STAT_CAP, old_val + QUEST_STAT_REWARDS["daily"]), 2)
                setattr(char, stat_name, new_val)
                stat_gain = {stat_name: round(new_val - old_val, 2)}

            levelled_up = False
            while char.xp >= xp_for_level(char.level + 1):
                char.level += 1
                levelled_up = True

            results.append(
                {
                    "quest": q.title,
                    "xp_awarded": q.xp_reward,
                    "levelled_up": levelled_up,
                    "new_level": char.level if levelled_up else None,
                    "stat_gain": stat_gain,
                }
            )

        if matching:
            char.xp_to_next = xp_to_next_level(char.level)
            char.char_class = get_class(char)
            char.title = get_title(char)
            session.commit()

    return results


def get_active_quests() -> dict:
    """
    Return active quests grouped by type.
    Daily: only today's quests.
    Weekly: only this week's quests.
    Life: all incomplete life quests.
    """
    today = date.today().isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    week_end = (date.today() + timedelta(days=6 - date.today().weekday())).isoformat()

    with SessionFactory() as session:
        # Daily — today only
        daily = session.scalars(
            select(Quest)
            .where(
                Quest.character_id == 1,
                Quest.quest_type == "daily",
                Quest.due_date == today,
                Quest.failed == False,
            )
            .order_by(Quest.completed, Quest.id)
        ).all()

        # Weekly — this week only
        weekly = session.scalars(
            select(Quest)
            .where(
                Quest.character_id == 1,
                Quest.quest_type == "weekly",
                Quest.due_date >= week_start,
                Quest.due_date <= week_end,
                Quest.failed == False,
            )
            .order_by(Quest.completed, Quest.id)
        ).all()

        # Life — all, no date filter
        life = session.scalars(
            select(Quest)
            .where(
                Quest.character_id == 1,
                Quest.quest_type == "life",
                Quest.completed == False,
                Quest.failed == False,
            )
            .order_by(Quest.id)
        ).all()

        return {
            "daily": [_quest_to_dict(q) for q in daily],
            "weekly": [_quest_to_dict(q) for q in weekly],
            "life": [_quest_to_dict(q) for q in life],
        }


def get_quest_history(limit: int = 20) -> list[dict]:
    """Return recently completed quests."""
    with SessionFactory() as session:
        done = session.scalars(
            select(Quest)
            .where(
                Quest.character_id == 1,
                Quest.completed == True,
            )
            .order_by(Quest.completed_at.desc())
            .limit(limit)
        ).all()
        return [_quest_to_dict(q) for q in done]


def auto_complete_matching_quests(stat: str) -> list[dict]:
    """
    After logging an activity, auto-tick daily quests that target
    the same stat AND are not yet complete.
    Returns list of completed quest dicts so caller can fire events.
    """
    today = date.today().isoformat()
    completed = []
    with SessionFactory() as session:
        matching = session.scalars(
            select(Quest).where(
                Quest.character_id == 1,
                Quest.quest_type == "daily",
                Quest.due_date == today,
                Quest.completed == False,
                Quest.failed == False,
                Quest.stat_target == stat,
            )
        ).all()

        from core.game_logic import apply_level_up_stat_bonus, get_class, get_title, xp_for_level

        char = session.get(Character, 1)
        for q in matching:
            q.completed = True
            q.completed_at = datetime.utcnow()
            char.xp += q.xp_reward

            levelled_up = False
            levels_gained = 0
            while char.xp >= xp_for_level(char.level + 1):
                char.level += 1
                levels_gained += 1
                levelled_up = True

            stat_bonuses = {}
            if levelled_up:
                stat_bonuses = apply_level_up_stat_bonus(char, levels_gained)

            char.xp_to_next = xp_to_next_level(char.level)
            char.char_class = get_class(char)
            char.title = get_title(char)

            completed.append(
                {
                    "quest": q.title,
                    "xp_awarded": q.xp_reward,
                    "levelled_up": levelled_up,
                    "new_level": char.level if levelled_up else None,
                    "stat_bonuses": stat_bonuses,
                }
            )

        if completed:
            session.commit()
            print(
                f"[ChronicForge] Auto-completed {len(completed)} quest(s) for stat: {stat}"
            )

    return completed


def _quest_to_dict(q: Quest) -> dict:
    xp = q.xp_reward
    intensity = 1 if xp < 100 else (3 if xp > 300 else 2)
    return {
        "id": q.id,
        "title": q.title,
        "description": q.description,
        "type": q.quest_type,
        "stat": q.stat_target,
        "xp_reward": q.xp_reward,
        "intensity": intensity,
        "completed": q.completed,
        "failed": q.failed,
        "due": q.due_date,
    }
