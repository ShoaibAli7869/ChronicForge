"""
ChronicForge — Quest Editor & Habit Template System
Pure Python. Zero UI imports.

Quest editor: full CRUD for custom quests (create, read, update, delete).
Habit templates: pre-built quest bundles the user can import in one click.

Custom quests use quest_type='custom' to distinguish from auto-generated ones.
"""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select

from core.database import Character, Quest, SessionFactory
from core.game_logic import xp_to_next_level

# ── CRUD ──────────────────────────────────────────────────────────────────────


def create_custom_quest(
    title: str,
    description: str,
    stat: str,
    xp_reward: int = 100,
    quest_type: str = "custom",
    due_days: Optional[int] = None,
) -> dict:
    """
    Create a new custom quest. Enforces:
    - quest_type forced to "custom" or "life" (not daily/weekly)
    - XP capped by character level
    - Slot limit by class
    """
    # Force quest_type to safe values
    if quest_type not in ("custom", "life"):
        quest_type = "custom"

    due_date = None
    if due_days is not None:
        due_date = (date.today() + timedelta(days=due_days)).isoformat()
    elif quest_type == "life":
        due_date = None  # life quests have no due date

    with SessionFactory() as session:
        char = session.get(Character, 1)
        if not char:
            return {"error": "No character found."}

        # --- Enforce slot limit ---
        try:
            from core.game_logic import get_max_custom_quests
            max_slots = get_max_custom_quests(char)
        except Exception:
            max_slots = 3

        existing_custom = len(
            [q for q in char.quests
             if q.quest_type in ("custom", "life")
             and not q.completed and not q.failed]
        )
        if existing_custom >= max_slots:
            return {
                "error": f"Quest slot limit reached ({max_slots} max). "
                         f"Complete or delete existing quests to create new ones."
            }

        # --- Enforce XP cap by level ---
        try:
            from core.game_logic import get_max_quest_xp
            max_xp = get_max_quest_xp(char)
        except Exception:
            max_xp = 300
        xp_reward = max(10, min(xp_reward, max_xp))

        q = Quest(
            character_id=char.id,
            title=title[:256],
            description=description,
            quest_type=quest_type,
            stat_target=stat,
            xp_reward=xp_reward,
            due_date=due_date,
        )
        session.add(q)
        session.commit()
        return _quest_to_dict(q)


def update_custom_quest(
    quest_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    stat: Optional[str] = None,
    xp_reward: Optional[int] = None,
) -> dict:
    """Update fields on an existing custom quest."""
    with SessionFactory() as session:
        q = session.get(Quest, quest_id)
        if not q:
            return {"error": f"Quest {quest_id} not found."}
        if title:
            q.title = title[:256]
        if description:
            q.description = description
        if stat:
            q.stat_target = stat
        if xp_reward:
            q.xp_reward = max(10, min(xp_reward, 10000))
        session.commit()
        return _quest_to_dict(q)


def delete_quest(quest_id: int) -> bool:
    """Delete any quest by ID. Returns True on success."""
    with SessionFactory() as session:
        q = session.get(Quest, quest_id)
        if not q:
            return False
        session.delete(q)
        session.commit()
        return True


def get_custom_quests() -> list[dict]:
    """Return all custom quests (not auto-generated ones)."""
    with SessionFactory() as session:
        quests = session.scalars(
            select(Quest)
            .where(
                Quest.character_id == 1,
                Quest.quest_type.in_(["custom", "daily", "weekly", "life"]),
                Quest.failed == False,
            )
            .order_by(Quest.completed, Quest.created_at.desc())
        ).all()
        return [_quest_to_dict(q) for q in quests]


def get_all_active_quests_for_editor() -> list[dict]:
    """Return all quests including auto-generated, for the editor view."""
    with SessionFactory() as session:
        today = date.today().isoformat()
        week_end = (
            date.today() + timedelta(days=6 - date.today().weekday())
        ).isoformat()
        week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()

        quests = session.scalars(
            select(Quest)
            .where(Quest.character_id == 1, Quest.failed == False)
            .order_by(Quest.quest_type, Quest.completed, Quest.created_at.desc())
        ).all()
        return [_quest_to_dict(q) for q in quests]


def _quest_to_dict(q: Quest) -> dict:
    from core.quest_system import _quest_to_dict as _base

    try:
        return _base(q)
    except Exception:
        xp = q.xp_reward
        return {
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "type": q.quest_type,
            "stat": q.stat_target,
            "xp_reward": xp,
            "intensity": 1 if xp < 100 else (3 if xp > 300 else 2),
            "completed": q.completed,
            "failed": q.failed,
            "due": q.due_date,
        }


# ── HABIT TEMPLATE BUNDLES ────────────────────────────────────────────────────

HABIT_BUNDLES: dict[str, dict] = {
    "gym_starter": {
        "name": "Gym Starter Pack",
        "description": "Daily and weekly quests for building a consistent training habit.",
        "icon": "⚔",
        "color": "#c84040",
        "quests": [
            # Daily
            {
                "title": "Morning Warrior",
                "description": "Complete a workout before noon.",
                "stat": "strength",
                "type": "daily",
                "xp": 120,
            },
            {
                "title": "Push-Up Protocol",
                "description": "50 push-ups at any point today.",
                "stat": "strength",
                "type": "daily",
                "xp": 80,
            },
            {
                "title": "Hydration Oath",
                "description": "Drink 2+ litres of water today.",
                "stat": "vitality",
                "type": "daily",
                "xp": 60,
            },
            {
                "title": "Post-Workout Log",
                "description": "Log your workout in the chronicle.",
                "stat": "discipline",
                "type": "daily",
                "xp": 50,
            },
            # Weekly
            {
                "title": "Iron Week",
                "description": "Train at least 4 times this week.",
                "stat": "strength",
                "type": "weekly",
                "xp": 500,
            },
            {
                "title": "Endurance Test",
                "description": "One session over 60 minutes this week.",
                "stat": "strength",
                "type": "weekly",
                "xp": 350,
            },
            # Life
            {
                "title": "100 Workouts",
                "description": "Log 100 total training sessions.",
                "stat": "strength",
                "type": "life",
                "xp": 5000,
            },
            {
                "title": "The Iron Body",
                "description": "Train consistently for 90 days straight.",
                "stat": "strength",
                "type": "life",
                "xp": 15000,
            },
        ],
    },
    "student_pack": {
        "name": "Student / Scholar Pack",
        "description": "Quests for deep work, reading, and consistent learning.",
        "icon": "📜",
        "color": "#4080d0",
        "quests": [
            {
                "title": "Daily Pages",
                "description": "Read at least 20 pages today.",
                "stat": "intellect",
                "type": "daily",
                "xp": 80,
            },
            {
                "title": "Deep Work Block",
                "description": "90 minutes of distraction-free study.",
                "stat": "intellect",
                "type": "daily",
                "xp": 150,
            },
            {
                "title": "No Phone Morning",
                "description": "No social media before noon.",
                "stat": "discipline",
                "type": "daily",
                "xp": 100,
            },
            {
                "title": "Knowledge Journal",
                "description": "Write down 3 things you learned today.",
                "stat": "intellect",
                "type": "daily",
                "xp": 60,
            },
            {
                "title": "Scholar's Week",
                "description": "Study every day this week.",
                "stat": "intellect",
                "type": "weekly",
                "xp": 400,
            },
            {
                "title": "Deep Work Week",
                "description": "4 sessions of 90+ min deep work.",
                "stat": "intellect",
                "type": "weekly",
                "xp": 500,
            },
            {
                "title": "50 Books",
                "description": "Read 50 books (log each one).",
                "stat": "intellect",
                "type": "life",
                "xp": 10000,
            },
            {
                "title": "Loremaster",
                "description": "Complete a course or certification.",
                "stat": "intellect",
                "type": "life",
                "xp": 8000,
            },
        ],
    },
    "creator_pack": {
        "name": "Creator / Builder Pack",
        "description": "For makers, coders, writers, artists. Ship things.",
        "icon": "✒",
        "color": "#a0a020",
        "quests": [
            {
                "title": "Daily Creation",
                "description": "Make something — write, code, draw, build.",
                "stat": "creativity",
                "type": "daily",
                "xp": 100,
            },
            {
                "title": "Project Sprint",
                "description": "2+ hours on a personal project.",
                "stat": "creativity",
                "type": "daily",
                "xp": 150,
            },
            {
                "title": "Idea Dump",
                "description": "Write down 10 ideas (any topic).",
                "stat": "creativity",
                "type": "daily",
                "xp": 60,
            },
            {
                "title": "Creator's Week",
                "description": "Create something every day this week.",
                "stat": "creativity",
                "type": "weekly",
                "xp": 450,
            },
            {
                "title": "Ship Something",
                "description": "Publish or share one finished project.",
                "stat": "creativity",
                "type": "weekly",
                "xp": 600,
            },
            {
                "title": "10 Projects Shipped",
                "description": "Complete and ship 10 personal projects.",
                "stat": "creativity",
                "type": "life",
                "xp": 12000,
            },
            {
                "title": "The Blog",
                "description": "Write and publish 52 posts (one/week).",
                "stat": "creativity",
                "type": "life",
                "xp": 15000,
            },
        ],
    },
    "monk_pack": {
        "name": "Monk / Wellness Pack",
        "description": "Sleep, meditation, diet, hydration. Temple maintenance.",
        "icon": "🌿",
        "color": "#30a060",
        "quests": [
            {
                "title": "Temple Maintenance",
                "description": "Drink 2L water + eat one clean meal.",
                "stat": "vitality",
                "type": "daily",
                "xp": 80,
            },
            {
                "title": "Morning Ritual",
                "description": "Meditate for 10+ minutes after waking.",
                "stat": "vitality",
                "type": "daily",
                "xp": 100,
            },
            {
                "title": "Lights Out",
                "description": "In bed before midnight. No screens.",
                "stat": "vitality",
                "type": "daily",
                "xp": 90,
            },
            {
                "title": "Vitality Week",
                "description": "Sleep 7+ hrs and hydrate every day.",
                "stat": "vitality",
                "type": "weekly",
                "xp": 400,
            },
            {
                "title": "30-Day Streak",
                "description": "Log wellness every day for 30 days.",
                "stat": "vitality",
                "type": "life",
                "xp": 8000,
            },
            {
                "title": "365 Days",
                "description": "Maintain the streak for a full year.",
                "stat": "vitality",
                "type": "life",
                "xp": 50000,
            },
        ],
    },
    "discipline_pack": {
        "name": "Discipline / Routine Pack",
        "description": "Wake early, plan the day, execute without excuses.",
        "icon": "🛡",
        "color": "#8050b0",
        "quests": [
            {
                "title": "Dawn Protocol",
                "description": "Wake up before 7am.",
                "stat": "discipline",
                "type": "daily",
                "xp": 120,
            },
            {
                "title": "Task Slayer",
                "description": "Complete your top 3 tasks today.",
                "stat": "discipline",
                "type": "daily",
                "xp": 150,
            },
            {
                "title": "No Scroll Morning",
                "description": "No phone in the first hour after waking.",
                "stat": "discipline",
                "type": "daily",
                "xp": 100,
            },
            {
                "title": "Plan Tomorrow",
                "description": "Write tomorrow's priorities tonight.",
                "stat": "discipline",
                "type": "daily",
                "xp": 60,
            },
            {
                "title": "Iron Week",
                "description": "Complete all daily quests 5 days.",
                "stat": "discipline",
                "type": "weekly",
                "xp": 600,
            },
            {
                "title": "The Unbreakable",
                "description": "Maintain a 365-day streak.",
                "stat": "discipline",
                "type": "life",
                "xp": 50000,
            },
        ],
    },
    "wealth_pack": {
        "name": "Wealth / Finance Pack",
        "description": "Budget, save, invest. Build financial discipline.",
        "icon": "⚖",
        "color": "#30a0a0",
        "quests": [
            {
                "title": "Ledger Check",
                "description": "Review expenses and budget today.",
                "stat": "wealth",
                "type": "daily",
                "xp": 80,
            },
            {
                "title": "Spend-Free Day",
                "description": "Zero unnecessary purchases today.",
                "stat": "wealth",
                "type": "daily",
                "xp": 120,
            },
            {
                "title": "Invest Something",
                "description": "Move any amount into savings/investment.",
                "stat": "wealth",
                "type": "daily",
                "xp": 100,
            },
            {
                "title": "Financial Week",
                "description": "Log finances every day this week.",
                "stat": "wealth",
                "type": "weekly",
                "xp": 350,
            },
            {
                "title": "Emergency Fund",
                "description": "Build a 3-month emergency fund.",
                "stat": "wealth",
                "type": "life",
                "xp": 20000,
            },
            {
                "title": "The Treasury",
                "description": "Save 10,000 in any currency.",
                "stat": "wealth",
                "type": "life",
                "xp": 30000,
            },
        ],
    },
    "social_pack": {
        "name": "Social / Charisma Pack",
        "description": "Network, connect, communicate. Build real relationships.",
        "icon": "🎭",
        "color": "#c07820",
        "quests": [
            {
                "title": "Daily Connection",
                "description": "Have one meaningful conversation today.",
                "stat": "charisma",
                "type": "daily",
                "xp": 80,
            },
            {
                "title": "Reach Out",
                "description": "Contact someone you haven't spoken to.",
                "stat": "charisma",
                "type": "daily",
                "xp": 100,
            },
            {
                "title": "Social Week",
                "description": "Meet or call 3 different people.",
                "stat": "charisma",
                "type": "weekly",
                "xp": 350,
            },
            {
                "title": "Public Speaking",
                "description": "Speak in front of a group this week.",
                "stat": "charisma",
                "type": "weekly",
                "xp": 500,
            },
            {
                "title": "100 Connections",
                "description": "Make 100 meaningful connections.",
                "stat": "charisma",
                "type": "life",
                "xp": 12000,
            },
        ],
    },
}


def get_bundle_names() -> list[dict]:
    """Return list of available bundles with metadata."""
    return [
        {
            "key": key,
            "name": bundle["name"],
            "description": bundle["description"],
            "icon": bundle["icon"],
            "color": bundle["color"],
            "count": len(bundle["quests"]),
        }
        for key, bundle in HABIT_BUNDLES.items()
    ]


def import_bundle(bundle_key: str, quest_types: Optional[list[str]] = None) -> dict:
    """
    Import all quests from a habit bundle into the character's quest list.
    quest_types: filter to only import certain types e.g. ['daily', 'weekly']
                 None = import all types.
    Returns summary of what was imported.
    """
    bundle = HABIT_BUNDLES.get(bundle_key)
    if not bundle:
        return {"error": f"Bundle '{bundle_key}' not found."}

    imported = {"daily": 0, "weekly": 0, "life": 0, "custom": 0}
    skipped = 0

    with SessionFactory() as session:
        char = session.get(Character, 1)
        if not char:
            return {"error": "No character found."}

        # Get existing quest titles to avoid exact duplicates
        existing_titles = {
            q.title for q in char.quests if not q.failed and not q.completed
        }

        today = date.today().isoformat()
        week_end = (
            date.today() + timedelta(days=6 - date.today().weekday())
        ).isoformat()

        for qdef in bundle["quests"]:
            qtype = qdef["type"]

            # Filter by requested types
            if quest_types and qtype not in quest_types:
                continue

            # Skip exact title duplicates
            if qdef["title"] in existing_titles:
                skipped += 1
                continue

            # Set due date
            if qtype == "daily":
                due = today
            elif qtype == "weekly":
                due = week_end
            else:
                due = None

            # Scale XP with level
            xp = int(qdef["xp"] * (1 + char.level * 0.03))

            q = Quest(
                character_id=char.id,
                title=qdef["title"],
                description=qdef["description"],
                quest_type=qtype,
                stat_target=qdef["stat"],
                xp_reward=xp,
                due_date=due,
            )
            session.add(q)
            imported[qtype] = imported.get(qtype, 0) + 1

        session.commit()

    total = sum(imported.values())
    return {
        "bundle": bundle["name"],
        "imported": imported,
        "total": total,
        "skipped": skipped,
    }
