"""
ChronicForge — Journal Engine
Long-form reflective journaling with prompts, mood tracking,
word-count goals, and XP rewards.
"""

import json
import random
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, select

from core.database import Character, JournalEntry, SessionFactory

# ── Journal XP constants ──────────────────────────────────────────────────────
XP_BASE_ENTRY = 50  # Base XP for any journal entry
XP_WORD_GOAL = 25  # Bonus for hitting word goal (default 100 words)
XP_PROMPT_BONUS = 15  # Bonus for using a daily prompt
XP_STREAK_MILESTONE = 100  # Bonus at 7/30/100 day journal streaks

WORD_GOAL_DEFAULT = 100

# ── Daily prompts ─────────────────────────────────────────────────────────────
_PROMPTS = [
    "What was the best moment of your day?",
    "What challenged you today, and how did you respond?",
    "What are you grateful for right now?",
    "What did you learn today — about yourself or the world?",
    "What would you do differently if you could replay today?",
    "Describe a small win that nobody else noticed.",
    "What's one thing you're avoiding? Why?",
    "If today had a title, what would it be?",
    "What conversation or interaction stayed with you today?",
    "What progress did you make toward a long-term goal?",
    "What drained your energy today? What replenished it?",
    "Write a letter to your future self — 30 days from now.",
    "What habit are you most proud of maintaining?",
    "Describe your current mood in three words. Then explain why.",
    "What's something you wish you had more time for?",
    "Who inspired you today, and why?",
    "What fear held you back today?",
    "What are you looking forward to tomorrow?",
    "What boundary did you set (or wish you had set) today?",
    "Describe a moment of unexpected kindness.",
    "What story are you telling yourself that might not be true?",
    "What does your ideal day look like? How close was today?",
    "What's one thing you can let go of?",
    "What made you laugh today?",
    "How did you take care of yourself today — body, mind, or spirit?",
    "What's a belief you held that you've changed your mind about?",
    "Describe a challenge you overcame recently.",
    "What does success look like to you right now?",
]


def get_daily_prompt() -> str:
    """Return a random journaling prompt. Deterministic per day."""
    today = date.today()
    seed = today.toordinal()
    rng = random.Random(seed)
    return rng.choice(_PROMPTS)


def get_all_prompts() -> list[str]:
    """Return all available prompts."""
    return list(_PROMPTS)


# ── Journal CRUD ──────────────────────────────────────────────────────────────


def create_journal_entry(
    title: str,
    body: str,
    mood: Optional[str] = None,
    tags: Optional[list[str]] = None,
    prompt_used: Optional[str] = None,
    entry_date: Optional[str] = None,
) -> dict:
    """
    Create a new journal entry. Awards XP based on:
    - Base XP for writing (only first entry per day)
    - Bonus for hitting word goal (class perks may reduce goal)
    - Bonus for using a prompt
    - Journal streak milestones

    Returns a dict with entry data and XP awarded.
    """
    today = date.today().isoformat()
    if entry_date is None:
        entry_date = today

    # --- Block future dates ---
    if entry_date > today:
        return {"error": "Cannot write journal entries for future dates."}

    # --- Block very old past dates (>30 days) ---
    from datetime import timedelta as _td
    cutoff = (date.today() - _td(days=30)).isoformat()
    if entry_date < cutoff:
        return {"error": "Cannot write journal entries older than 30 days."}

    # Normalize mood
    valid_moods = {"terrible", "bad", "okay", "good", "amazing"}
    if mood and mood.lower() not in valid_moods:
        mood = None
    elif mood:
        mood = mood.lower()

    word_count = len(body.split())
    tags_json = json.dumps(tags) if tags else None

    # --- XP: only first entry each day awards XP ---
    xp_awarded = 0
    already_today = False
    with SessionFactory() as _s:
        from sqlalchemy import func as _fn, select as _sel
        cnt = _s.scalar(
            _sel(_fn.count(JournalEntry.id)).where(
                JournalEntry.character_id == 1,
                JournalEntry.date == entry_date,
                JournalEntry.xp_awarded > 0,
            )
        )
        already_today = (cnt or 0) > 0

    if not already_today:
        # Minimum word requirement
        if word_count < 20:
            xp_awarded = 0  # Too short for XP
        else:
            xp_awarded = XP_BASE_ENTRY

            # Apply class perk: journal goal reduction
            effective_goal = WORD_GOAL_DEFAULT
            _char = None
            _perks: dict = {}
            try:
                from core.database import Character as _Ch
                with SessionFactory() as _s2:
                    _char = _s2.get(_Ch, 1)
                    if _char:
                        from core.game_logic import get_class_perks
                        _perks = get_class_perks(_char)
                        reduction = _perks.get("journal_goal_reduction", 0)
                        effective_goal = max(20, WORD_GOAL_DEFAULT - reduction)
            except Exception:
                pass

            if word_count >= effective_goal:
                xp_awarded += XP_WORD_GOAL
            if prompt_used:
                xp_awarded += XP_PROMPT_BONUS

            # Class perk: Monk/Overlord journal bonus
            try:
                if _char:
                    bonus = _perks.get("journal_bonus", 0)
                    if _perks.get("extra_journal_xp"):
                        bonus += 25
                    xp_awarded += bonus
            except Exception:
                pass

            # Journal streak bonus
            journal_streak = _compute_journal_streak(entry_date)
            if journal_streak > 0 and journal_streak % 7 == 0:
                xp_awarded += XP_STREAK_MILESTONE

    journal_streak = _compute_journal_streak(entry_date)

    with SessionFactory() as session:
        char = session.get(Character, 1)
        if not char:
            return {"error": "No character found."}

        entry = JournalEntry(
            character_id=char.id,
            date=entry_date,
            title=title,
            body=body,
            mood=mood,
            tags=tags_json,
            word_count=word_count,
            prompt_used=prompt_used,
            xp_awarded=xp_awarded,
        )
        session.add(entry)

        # Award XP to character
        char.xp += xp_awarded

        # Check level-up
        from core.game_logic import apply_level_up_stat_bonus, get_class, get_title, xp_for_level, xp_to_next_level

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

        entry_id = entry.id

    result = {
        "id": entry_id,
        "date": entry_date,
        "title": title,
        "body": body,
        "mood": mood,
        "tags": tags or [],
        "word_count": word_count,
        "prompt_used": prompt_used,
        "xp_awarded": xp_awarded,
        "journal_streak": journal_streak,
        "levelled_up": levelled_up,
        "new_level": char.level if levelled_up else None,
        "new_class": char.char_class if levelled_up else None,
        "stat_bonuses": stat_bonuses,
    }

    # Fire event for quest completion etc.
    try:
        from utils.signals import event_bus

        event_bus.xp_gained.emit(xp_awarded)
        if levelled_up:
            event_bus.level_up.emit(char.level)
        event_bus.journal_entry_created.emit(entry_id)
        event_bus.stats_updated.emit()
    except Exception:
        pass

    return result


def get_journal_entries(
    entry_date: Optional[str] = None,
    mood: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
) -> list[dict]:
    """Get journal entries with optional filters."""
    with SessionFactory() as session:
        q = (
            select(JournalEntry)
            .where(JournalEntry.character_id == 1)
            .order_by(JournalEntry.date.desc(), JournalEntry.created_at.desc())
        )

        if entry_date:
            q = q.where(JournalEntry.date == entry_date)
        if mood:
            q = q.where(JournalEntry.mood == mood.lower())
        if tag:
            # SQLite — rough JSON contains check
            q = q.where(JournalEntry.tags.contains(tag))

        q = q.offset(offset).limit(limit)
        entries = session.scalars(q).all()
        return [_entry_to_dict(e) for e in entries]


def get_journal_entry(entry_id: int) -> Optional[dict]:
    """Get a single journal entry by ID."""
    with SessionFactory() as session:
        entry = session.get(JournalEntry, entry_id)
        if not entry or entry.character_id != 1:
            return None
        return _entry_to_dict(entry)


def update_journal_entry(
    entry_id: int,
    title: Optional[str] = None,
    body: Optional[str] = None,
    mood: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> Optional[dict]:
    """Update an existing journal entry."""
    with SessionFactory() as session:
        entry = session.get(JournalEntry, entry_id)
        if not entry or entry.character_id != 1:
            return None

        if title is not None:
            entry.title = title
        if body is not None:
            entry.body = body
            entry.word_count = len(body.split())
        if mood is not None:
            valid_moods = {"terrible", "bad", "okay", "good", "amazing"}
            entry.mood = mood.lower() if mood.lower() in valid_moods else None
        if tags is not None:
            entry.tags = json.dumps(tags)

        session.commit()
        return _entry_to_dict(entry)


def delete_journal_entry(entry_id: int) -> bool:
    """Delete a journal entry. Returns True on success."""
    with SessionFactory() as session:
        entry = session.get(JournalEntry, entry_id)
        if not entry or entry.character_id != 1:
            return False
        session.delete(entry)
        session.commit()
        return True


# ── Journal stats ─────────────────────────────────────────────────────────────


def get_journal_stats() -> dict:
    """Get aggregate journal statistics."""
    with SessionFactory() as session:
        total = (
            session.scalar(select(func.count()).where(JournalEntry.character_id == 1))
            or 0
        )

        total_words = (
            session.scalar(
                select(func.sum(JournalEntry.word_count)).where(
                    JournalEntry.character_id == 1
                )
            )
            or 0
        )

        # Mood distribution
        mood_rows = session.execute(
            select(JournalEntry.mood, func.count())
            .where(JournalEntry.character_id == 1, JournalEntry.mood.isnot(None))
            .group_by(JournalEntry.mood)
        ).all()
        mood_dist = {row[0]: row[1] for row in mood_rows if row[0]}

        # Entry count by day (last 30 days)
        thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
        recent_dates = session.scalars(
            select(JournalEntry.date)
            .where(
                JournalEntry.character_id == 1,
                JournalEntry.date >= thirty_days_ago,
            )
            .distinct()
        ).all()

        streak = _compute_journal_streak()
        longest = _compute_longest_journal_streak()

        # Average words
        avg_words = round(total_words / total, 1) if total > 0 else 0

    return {
        "total_entries": total,
        "total_words": total_words,
        "avg_words_per_entry": avg_words,
        "mood_distribution": mood_dist,
        "current_streak": streak,
        "longest_streak": longest,
        "days_with_entries_30d": len(recent_dates),
        "dominant_mood": _dominant_mood(mood_dist),
    }


def get_calendar_data(year: int, month: int) -> list[dict]:
    """Get journal entries for a specific month (for calendar view)."""
    import calendar

    first_day = f"{year}-{month:02d}-01"
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = f"{year}-{month:02d}-{last_day_num:02d}"

    with SessionFactory() as session:
        entries = session.scalars(
            select(JournalEntry).where(
                JournalEntry.character_id == 1,
                JournalEntry.date >= first_day,
                JournalEntry.date <= last_day,
            )
        ).all()

        by_date: dict[str, list[dict]] = {}
        for e in entries:
            by_date.setdefault(e.date, []).append(
                {
                    "id": e.id,
                    "title": e.title,
                    "mood": e.mood,
                    "word_count": e.word_count,
                }
            )

    return [{"date": d, "entries": by_date.get(d, [])} for d in sorted(by_date.keys())]


# ── Streak helpers ────────────────────────────────────────────────────────────


def _compute_journal_streak(today_iso: Optional[str] = None) -> int:
    """Compute current journal streak (consecutive days with entries)."""
    if today_iso is None:
        today_iso = date.today().isoformat()

    with SessionFactory() as session:
        dates = session.scalars(
            select(JournalEntry.date)
            .where(JournalEntry.character_id == 1)
            .distinct()
            .order_by(JournalEntry.date.desc())
        ).all()

    if not dates:
        return 0

    streak = 0
    current = date.fromisoformat(today_iso)

    # Check if today has an entry
    if dates[0] == today_iso:
        streak = 1
        current = current - timedelta(days=1)
    elif dates[0] == (date.today() - timedelta(days=1)).isoformat():
        # Yesterday counts if today hasn't ended yet
        streak = 1
        current = date.today() - timedelta(days=2)
    else:
        return 0

    # Count backwards
    for d_str in dates[1:]:
        d = date.fromisoformat(d_str)
        if d == current:
            streak += 1
            current = current - timedelta(days=1)
        else:
            break

    return streak


def _compute_longest_journal_streak() -> int:
    """Compute the longest journal streak ever."""
    with SessionFactory() as session:
        dates = session.scalars(
            select(JournalEntry.date)
            .where(JournalEntry.character_id == 1)
            .distinct()
            .order_by(JournalEntry.date)
        ).all()

    if not dates:
        return 0

    longest = 1
    current_streak = 1
    parsed = [date.fromisoformat(d) for d in dates]

    for i in range(1, len(parsed)):
        if (parsed[i] - parsed[i - 1]).days == 1:
            current_streak += 1
            longest = max(longest, current_streak)
        else:
            current_streak = 1

    return max(longest, current_streak)


def _dominant_mood(mood_dist: dict) -> Optional[str]:
    """Return the most common mood."""
    if not mood_dist:
        return None
    return max(mood_dist, key=mood_dist.get)  # type: ignore[arg-type]


# ── Entry dict helper ─────────────────────────────────────────────────────────


def _entry_to_dict(e: JournalEntry) -> dict:
    tags = []
    if e.tags:
        try:
            tags = json.loads(e.tags)
        except (json.JSONDecodeError, TypeError):
            tags = []

    return {
        "id": e.id,
        "date": e.date,
        "title": e.title,
        "body": e.body,
        "mood": e.mood,
        "tags": tags,
        "word_count": e.word_count,
        "prompt_used": e.prompt_used,
        "xp_awarded": e.xp_awarded,
        "created_at": e.created_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
    }


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from core.database import init_db

    init_db()
    print("=== Journal Engine Test ===\n")

    # Prompt
    prompt = get_daily_prompt()
    print(f"Today's prompt: {prompt}\n")

    # Create
    result = create_journal_entry(
        title="Test Entry",
        body="This is a test journal entry. I'm testing the journal engine to make sure everything works correctly. Words words words words words words words words words words words words words words words words words words words words words words words words words words words.",
        mood="good",
        tags=["test", "journal"],
        prompt_used=prompt,
    )
    print(f"Created: {result}\n")

    # Stats
    stats = get_journal_stats()
    print(f"Stats: {stats}\n")

    # Get entries
    entries = get_journal_entries(limit=5)
    print(f"Recent entries: {len(entries)}")
    for e in entries:
        print(
            f"  [{e['date']}] {e['title']} — {e['word_count']} words — mood: {e['mood']}"
        )
