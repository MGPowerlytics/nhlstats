"""
Shared types for betting system.

Contains data classes and types used across multiple betting modules.
"""

from dataclasses import dataclass


@dataclass
class GameIdentity:
    """Identity of a game for verification."""

    home_team: str
    away_team: str
    sport: str
