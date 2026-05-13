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
from plugins.elo.tennis_features import (
    TennisFeatureBuilder,
    TennisFeatureConfig,
    TennisMatchupFeatures,
)
from plugins.elo.unrivaled_elo_rating import UnrivaledEloRating
from plugins.elo.cba_elo_rating import CBAEloRating
from plugins.elo.factory import (
    ELO_CLASS_REGISTRY,
    get_elo_class,
    create_elo_instance,
    get_elo_for_sport,
)

# Export dataclasses and components for advanced usage
from plugins.elo.elo_dataclasses import (
    Matchup,
    GameResult,
    EloConfig,
    UpdateArgs,
    DEFAULT_K_FACTOR,
    DEFAULT_HOME_ADVANTAGE,
    DEFAULT_INITIAL_RATING,
    ELO_RATING_SCALE,
    ELO_EXPONENT_BASE,
    MOV_MULTIPLIER_CONSTANT,
    MOV_ELO_SCALING_FACTOR,
    MOV_MINIMUM_VALUE,
    MOV_LOG_OFFSET,
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
    "TennisFeatureBuilder",
    "TennisFeatureConfig",
    "TennisMatchupFeatures",
    "UnrivaledEloRating",
    "CBAEloRating",
    "ELO_CLASS_REGISTRY",
    "get_elo_class",
    "create_elo_instance",
    "get_elo_for_sport",
    # Dataclasses and constants
    "Matchup",
    "GameResult",
    "EloConfig",
    "UpdateArgs",
    "DEFAULT_K_FACTOR",
    "DEFAULT_HOME_ADVANTAGE",
    "DEFAULT_INITIAL_RATING",
    "ELO_RATING_SCALE",
    "ELO_EXPONENT_BASE",
    "MOV_MULTIPLIER_CONSTANT",
    "MOV_ELO_SCALING_FACTOR",
    "MOV_MINIMUM_VALUE",
    "MOV_LOG_OFFSET",
]
