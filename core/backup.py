"""
ChronicForge — Backup & Export System
Auto-backups SQLite DB daily. Exports to JSON/CSV.
Restores from backup.

Backup location: ~/.local/share/chronicforge/backups/
  Keeps last 30 daily backups. Auto-runs at midnight tick.

Export location: ~/ChronicForge_export_YYYY-MM-DD/
"""

import csv
import json
import os
import shutil
from datetime import date, datetime
from typing import Optional

DB_PATH = os.path.expanduser("~/.local/share/chronicforge/save.db")
BACKUP_DIR = os.path.expanduser("~/.local/share/chronicforge/backups")
MAX_BACKUPS = 30


# ── Backup ────────────────────────────────────────────────────────────────────


def create_backup(label: str = "") -> Optional[str]:
    """
    Copy save.db to backups/ with today's date stamp.
    Returns path to backup file, or None on failure.
    Silently skips if a backup for today already exists.
    """
    if not os.path.exists(DB_PATH):
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)
    today = date.today().isoformat()
    suffix = f"_{label}" if label else ""
    filename = f"chronicforge_{today}{suffix}.db"
    dst = os.path.join(BACKUP_DIR, filename)

    if os.path.exists(dst) and not label:
        return dst  # already backed up today

    try:
        shutil.copy2(DB_PATH, dst)

        # FIX 1: Also back up config.toml alongside the DB
        config_src = os.path.expanduser("~/.config/chronicforge/config.toml")
        if os.path.exists(config_src):
            config_dst = dst.replace(".db", "_config.toml")
            shutil.copy2(config_src, config_dst)

        _prune_old_backups()
        print(f"[ChronicForge] Backup created: {filename}")
        return dst
    except Exception as e:
        print(f"[ChronicForge] Backup failed: {e}")
        return None


def _prune_old_backups():
    """Keep only the last MAX_BACKUPS backup files."""
    try:
        files = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")], reverse=True
        )
        for old in files[MAX_BACKUPS:]:
            os.unlink(os.path.join(BACKUP_DIR, old))
    except Exception:
        pass


def list_backups() -> list[dict]:
    """Return list of available backups with metadata."""
    if not os.path.isdir(BACKUP_DIR):
        return []
    result = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if not f.endswith(".db"):
            continue
        path = os.path.join(BACKUP_DIR, f)
        size = os.path.getsize(path)
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        result.append(
            {
                "filename": f,
                "path": path,
                "size_kb": round(size / 1024, 1),
                "date": mtime.strftime("%Y-%m-%d %H:%M"),
            }
        )
    return result


def restore_backup(backup_path: str) -> bool:
    """
    Restore a backup. Creates a safety backup of current DB first.
    Returns True on success.
    """
    if not os.path.exists(backup_path):
        return False
    try:
        # Safety backup of current state
        create_backup("pre_restore")
        shutil.copy2(backup_path, DB_PATH)
        print(f"[ChronicForge] Restored from: {backup_path}")
        return True
    except Exception as e:
        print(f"[ChronicForge] Restore failed: {e}")
        return False


# ── Export ────────────────────────────────────────────────────────────────────


def export_json(output_dir: Optional[str] = None) -> str:
    """
    Export all data to JSON.
    Returns path to the created file.
    """
    from sqlalchemy import select

    from core.database import (
        Achievement,
        Character,
        LogEntry,
        Quest,
        Roast,
        SessionFactory,
    )

    if output_dir is None:
        output_dir = os.path.expanduser(
            f"~/ChronicForge_export_{date.today().isoformat()}"
        )
    os.makedirs(output_dir, exist_ok=True)

    data: dict = {}

    with SessionFactory() as session:
        char = session.get(Character, 1)
        if char:
            data["character"] = {
                "name": char.name,
                "title": char.title,
                "class": char.char_class,
                "level": char.level,
                "xp": char.xp,
                "stats": char.stats_dict,
                "streak": char.current_streak,
                "longest_streak": char.longest_streak,
                "created_at": char.created_at.isoformat(),
            }

        entries = session.scalars(
            select(LogEntry)
            .where(LogEntry.character_id == 1)
            .order_by(LogEntry.created_at)
        ).all()
        data["log_entries"] = [
            {
                "id": e.id,
                "date": e.date,
                "activity": e.activity,
                "stat": e.category,
                "xp": e.xp_awarded,
                "intensity": e.intensity,
                "notes": e.notes,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]

        quests = session.scalars(select(Quest).where(Quest.character_id == 1)).all()
        data["quests"] = [
            {
                "id": q.id,
                "title": q.title,
                "type": q.quest_type,
                "stat": q.stat_target,
                "xp_reward": q.xp_reward,
                "completed": q.completed,
                "failed": q.failed,
                "due_date": q.due_date,
            }
            for q in quests
        ]

        roasts = session.scalars(
            select(Roast).where(Roast.character_id == 1).order_by(Roast.created_at)
        ).all()
        data["roast_journal"] = [
            {
                "text": r.text,
                "type": r.roast_type,
                "trigger": r.trigger,
                "source": r.source,
                "date": r.created_at.isoformat(),
            }
            for r in roasts
        ]

        achievements = session.scalars(
            select(Achievement).where(Achievement.character_id == 1)
        ).all()
        data["achievements"] = [
            {"key": a.key, "title": a.title, "unlocked_at": a.unlocked_at.isoformat()}
            for a in achievements
        ]

    data["exported_at"] = datetime.utcnow().isoformat()
    data["version"] = "chronicforge_v2"

    out_path = os.path.join(output_dir, "chronicforge_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[ChronicForge] JSON export: {out_path}")
    return out_path


def export_csv(output_dir: Optional[str] = None) -> str:
    """
    Export log entries to CSV for spreadsheet use.
    Returns path to created file.
    """
    from sqlalchemy import select

    from core.database import LogEntry, SessionFactory

    if output_dir is None:
        output_dir = os.path.expanduser(
            f"~/ChronicForge_export_{date.today().isoformat()}"
        )
    os.makedirs(output_dir, exist_ok=True)

    out_path = os.path.join(output_dir, "chronicforge_log.csv")

    with SessionFactory() as session:
        entries = session.scalars(
            select(LogEntry)
            .where(LogEntry.character_id == 1)
            .order_by(LogEntry.date, LogEntry.created_at)
        ).all()

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "date",
                "activity",
                "stat",
                "xp_awarded",
                "intensity",
                "notes",
                "created_at",
            ]
        )
        for e in entries:
            writer.writerow(
                [
                    e.date,
                    e.activity,
                    e.category,
                    e.xp_awarded,
                    e.intensity,
                    e.notes or "",
                    e.created_at.isoformat(),
                ]
            )

    print(f"[ChronicForge] CSV export: {out_path}")
    return out_path


def export_all(output_dir: Optional[str] = None) -> dict[str, str]:
    """Export both JSON and CSV. Returns {'json': path, 'csv': path}."""
    if output_dir is None:
        output_dir = os.path.expanduser(
            f"~/ChronicForge_export_{date.today().isoformat()}"
        )
    return {
        "json": export_json(output_dir),
        "csv": export_csv(output_dir),
        "dir": output_dir,
    }
