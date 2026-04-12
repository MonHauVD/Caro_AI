"""Application run mode (set from CLI in app.main)."""

from enum import Enum, auto


class GameMode(Enum):
    """NORMAL: human vs AI; DEVELOPER: AI vs AI; BENCHMARK: automated matchups."""
    NORMAL = auto()
    DEVELOPER = auto()
    BENCHMARK = auto()
