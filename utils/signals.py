"""
ChronicForge — Central Event Bus
Single source of truth for all PySide6 signals.
Import event_bus from here everywhere.
"""

from PySide6.QtCore import QObject, Signal


class _EventBus(QObject):
    # Sprite reactions
    xp_gained = Signal(int)
    level_up = Signal(int)
    stat_bonus_awarded = Signal(dict)  # {stat_name: delta_float} emitted when level-up grants stat bonuses
    roast_ready = Signal(str)
    quest_complete = Signal(str)
    take_damage = Signal()
    victory = Signal()
    # Proactive sprite remarks (time-aware, unprompted)
    sprite_remark = Signal(str)
    # UI refresh
    stats_updated = Signal()
    quests_updated = Signal()
    # KDE notification
    notify = Signal(str, str)  # title, body
    # Settings changed
    config_saved = Signal()


event_bus = _EventBus()
