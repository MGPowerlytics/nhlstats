"""
NCAAB Elo Rating System

Production-ready Elo rating system for NCAA Basketball predictions.
Inherits from StandardEloRating for default implementation.
"""

from plugins.elo.base_elo_rating import StandardEloRating


class NCAABEloRating(StandardEloRating):
    """NCAAB-specific Elo rating system."""

    # Inherits default __init__ and update from StandardEloRating
