"""
Elo rating system package.

Exports all sport-specific Elo rating classes and the base class.
"""

from plugins.elo.base_elo_rating import BaseEloRating
from plugins.elo.nba_elo_rating import NBAEloRating
from plugins.elo.nhl_elo_rating import NHLEloRating
from plugins.elo.mlb_elo_rating import MLBEloRating
from plugins.elo.nfl_elo_rating import NFLEloRating
from plugins.elo.epl_elo_rating import EPLEloRating
from plugins.elo.ligue1_elo_rating import Ligue1EloRating
from plugins.elo.ncaab_elo_rating import NCAABEloRating
from plugins.elo.wncaab_elo_rating import WNCAABEloRating
from plugins.elo.tennis_elo_rating import TennisEloRating
from plugins.elo.factory import (
    ELO_CLASS_REGISTRY,
    get_elo_class,
    create_elo_instance,
    get_elo_for_sport,
)

__all__ = [
    "BaseEloRating",
    "NHLEloRating",
    "NBAEloRating",
    "MLBEloRating",
    "NFLEloRating",
    "EPLEloRating",
    "Ligue1EloRating",
    "NCAABEloRating",
    "WNCAABEloRating",
    "TennisEloRating",
    "ELO_CLASS_REGISTRY",
    "get_elo_class",
    "create_elo_instance",
    "get_elo_for_sport",
]
