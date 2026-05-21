"""
ChronicForge — Database Layer
SQLAlchemy 2.0 ORM models + session factory.
Single SQLite file at ~/.local/share/chronicforge/save.db
"""

import os
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

# ── DB path ───────────────────────────────────────────────────────────────────
DB_DIR = os.path.expanduser("~/.local/share/chronicforge")
DB_PATH = os.path.join(DB_DIR, "save.db")


class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────────


class Character(Base):
    """The player's RPG character — single row, id=1 always."""

    __tablename__ = "character"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(64), default="Hero")
    title: Mapped[str] = mapped_column(String(128), default="The Wanderer")
    char_class: Mapped[str] = mapped_column(String(64), default="Wanderer")
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    xp_to_next: Mapped[int] = mapped_column(Integer, default=100)

    # Core stats (0–200 scale, base 10)
    strength: Mapped[float] = mapped_column(Float, default=10.0)
    intellect: Mapped[float] = mapped_column(Float, default=10.0)
    charisma: Mapped[float] = mapped_column(Float, default=10.0)
    vitality: Mapped[float] = mapped_column(Float, default=10.0)
    discipline: Mapped[float] = mapped_column(Float, default=10.0)
    creativity: Mapped[float] = mapped_column(Float, default=10.0)
    wealth: Mapped[float] = mapped_column(Float, default=10.0)

    # Streak tracking
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    streak_freezes: Mapped[int] = mapped_column(Integer, default=0)
    last_login_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    log_entries: Mapped[List["LogEntry"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    quests: Mapped[List["Quest"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    achievements: Mapped[List["Achievement"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    roasts: Mapped[List["Roast"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    journal_entries: Mapped[List["JournalEntry"]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )

    @property
    def stats_dict(self) -> dict:
        return {
            "strength": self.strength,
            "intellect": self.intellect,
            "charisma": self.charisma,
            "vitality": self.vitality,
            "discipline": self.discipline,
            "creativity": self.creativity,
            "wealth": self.wealth,
        }

    @property
    def total_power(self) -> float:
        return sum(self.stats_dict.values())

    def __repr__(self):
        return f"<Character {self.name} Lv{self.level} [{self.char_class}]>"


class LogEntry(Base):
    """One logged activity/habit entry."""

    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character.id"))
    character: Mapped["Character"] = relationship(back_populates="log_entries")

    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    category: Mapped[str] = mapped_column(String(32))  # stat name
    activity: Mapped[str] = mapped_column(String(256))  # free text
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)
    stat_delta: Mapped[float] = mapped_column(Float, default=0.0)
    intensity: Mapped[int] = mapped_column(Integer, default=2)  # 1-3
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Quest(Base):
    """Daily / weekly / life quests."""

    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character.id"))
    character: Mapped["Character"] = relationship(back_populates="quests")

    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    quest_type: Mapped[str] = mapped_column(String(16))  # daily/weekly/life
    stat_target: Mapped[str] = mapped_column(String(32))  # which stat it targets
    xp_reward: Mapped[int] = mapped_column(Integer, default=100)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    failed: Mapped[bool] = mapped_column(Boolean, default=False)
    due_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Achievement(Base):
    """Unlocked achievements / titles."""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character.id"))
    character: Mapped["Character"] = relationship(back_populates="achievements")

    key: Mapped[str] = mapped_column(String(64), unique=False)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Roast(Base):
    """Journal of all roasts/praise the sprite has delivered."""

    __tablename__ = "roasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character.id"))
    character: Mapped["Character"] = relationship(back_populates="roasts")

    text: Mapped[str] = mapped_column(Text)
    roast_type: Mapped[str] = mapped_column(String(16))  # roast/praise/neutral
    trigger: Mapped[str] = mapped_column(String(64))  # what triggered it
    source: Mapped[str] = mapped_column(String(16), default="template")  # template/groq
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JournalEntry(Base):
    """Long-form reflective journal entry — separate from quick activity logs."""

    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character.id"))
    character: Mapped["Character"] = relationship(back_populates="journal_entries")

    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    mood: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    # moods: terrible / bad / okay / good / amazing
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON-encoded list of tag strings, e.g. '["gym","reading"]'
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    prompt_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The prompt text that inspired this entry (if any)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ── Engine & session factory ──────────────────────────────────────────────────


def get_engine():
    os.makedirs(DB_DIR, exist_ok=True)
    return create_engine(
        f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False}
    )


def init_db():
    """Create all tables and seed a default character if none exists."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    with SessionFactory() as session:
        char = session.get(Character, 1)
        if char is None:
            char = Character(id=1)
            session.add(char)
            session.commit()
            print("[ChronicForge] New character created.")
        else:
            print(f"[ChronicForge] Loaded: {char}")
    return SessionFactory


# Singleton session factory — import from anywhere
_engine = get_engine()
Base.metadata.create_all(_engine)
SessionFactory = sessionmaker(bind=_engine)


def _migrate_add_last_login(engine) -> None:
    """Safe migration: adds last_login_date column if it doesn't exist."""
    from sqlalchemy import text

    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE character ADD COLUMN last_login_date VARCHAR(10)"))
            conn.commit()
        except Exception:
            pass  # Column already exists, that's fine


_migrate_add_last_login(_engine)
