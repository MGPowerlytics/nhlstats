"""
Elo factory/registry for sport-specific Elo rating classes.

Provides a unified way to instantiate the appropriate Elo class for a given sport.
"""

from typing import Dict, Type
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

# Registry mapping sport names to Elo classes
ELO_CLASS_REGISTRY: Dict[str, Type[BaseEloRating]] = {
    "nba": NBAEloRating,
    "nhl": NHLEloRating,
    "mlb": MLBEloRating,
    "nfl": NFLEloRating,
    "epl": EPLEloRating,
    "ligue1": Ligue1EloRating,
    "ncaab": NCAABEloRating,
    "wncaab": WNCAABEloRating,
    "tennis": TennisEloRating,
}


def get_elo_class(sport: str) -> Type[BaseEloRating]:
    """
    Get the Elo rating class for a given sport.

    Args:
        sport: Sport name (e.g., "nba", "nhl", "mlb", "nfl", "epl", "ligue1",
               "ncaab", "wncaab", "tennis")

    Returns:
        The Elo rating class for the sport.

    Raises:
        ValueError: If the sport is not supported.
    """
    sport_lower = sport.lower()
    if sport_lower not in ELO_CLASS_REGISTRY:
        raise ValueError(
            f"Unsupported sport: {sport}. "
            f"Supported sports: {list(ELO_CLASS_REGISTRY.keys())}"
        )
    return ELO_CLASS_REGISTRY[sport_lower]


def create_elo_instance(sport: str, **kwargs) -> BaseEloRating:
    """
    Create an instance of the Elo rating class for a given sport.

    Args:
        sport: Sport name.
        **kwargs: Additional keyword arguments to pass to the class constructor.

    Returns:
        An instance of the appropriate Elo rating class.
    """
    elo_class = get_elo_class(sport)
    return elo_class(**kwargs)


# Convenience function for backward compatibility
def get_elo_for_sport(sport: str, **kwargs) -> BaseEloRating:
    """Alias for create_elo_instance."""
    return create_elo_instance(sport, **kwargs)
