"""
core/backup.py — auto-backup to ~/.local/share/chronicforge/backups/
JSON export and CSV export.
"""

import csv
import glob
import json
import os
import shutil
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import Achievement, Character, LogEntry, Quest, Roast, SessionFactory

BACKUP_DIR = os.path.expanduser("~/.local/share/chronicforge/backups")
DB_PATH = os.path.expanduser("~/.local/share/chronicforge/save.db")
MAX_BACKUPS = 30


def create_backup(label: str = "") -> Optional[str]:
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
        _prune_old_backups()
        return dst
    except Exception as e:
        print(f"[ChronicForge] Backup failed: {e}")
        return None


def _prune_old_backups():
    try:
        files = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")], reverse=True
        )
        for old in files[MAX_BACKUPS:]:
            os.unlink(os.path.join(BACKUP_DIR, old))
    except Exception:
        pass


def list_backups() -> list[dict]:
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
    if not os.path.exists(backup_path):
        return False
    try:
        create_backup("pre_restore")
        shutil.copy2(backup_path, DB_PATH)
        return True
    except Exception as e:
        print(f"[ChronicForge] Restore failed: {e}")
        return False


def export_json(output_dir: Optional[str] = None) -> str:
    if output_dir is None:
        output_dir = os.path.expanduser(
            f"~/ChronicForge_export_{date.today().isoformat()}"
        )
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "chronicforge_data.json")

    data = {}
    with SessionFactory() as session:
        char = session.get(Character, 1)
        if char:
            data["character"] = {
                c.name: getattr(char, c.name)
                for c in char.__table__.columns
                if c.name not in ["created_at", "updated_at"]
            }

        data["log_entries"] = [
            {
                c.name: getattr(entry, c.name)
                for c in entry.__table__.columns
                if c.name not in ["created_at", "updated_at"]
            }
            for entry in session.query(LogEntry).all()
        ]
        data["quests"] = [
            {
                c.name: getattr(quest, c.name)
                for c in quest.__table__.columns
                if c.name not in ["created_at", "updated_at", "completed_at"]
            }
            for quest in session.query(Quest).all()
        ]
        data["achievements"] = [
            {
                c.name: getattr(ach, c.name)
                for c in ach.__table__.columns
                if c.name not in ["unlocked_at"]
            }
            for ach in session.query(Achievement).all()
        ]
        data["roasts"] = [
            {
                c.name: getattr(roast, c.name)
                for c in roast.__table__.columns
                if c.name not in ["created_at"]
            }
            for roast in session.query(Roast).all()
        ]

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filepath


def export_csv(output_dir: Optional[str] = None) -> str:
    if output_dir is None:
        output_dir = os.path.expanduser(
            f"~/ChronicForge_export_{date.today().isoformat()}"
        )
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "chronicforge_log.csv")

    with SessionFactory() as session:
        entries = session.query(LogEntry).all()

        with open(filepath, "w", newline="") as f:
            if not entries:
                f.write("No log entries.")
                return filepath

            writer = csv.writer(f)
            cols = [c.name for c in LogEntry.__table__.columns]
            writer.writerow(cols)

            for entry in entries:
                writer.writerow([getattr(entry, c) for c in cols])

    return filepath
