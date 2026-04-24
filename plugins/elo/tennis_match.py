"""Tennis match data structures to address Primitive Obsession in tennis_elo_rating.py."""

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class TennisMatchContext:
    """Context for a tennis match between two players.

    This dataclass addresses the Primitive Obsession smell by grouping
    related primitive parameters that appear repeatedly in tennis_elo_rating.py.
    """

    player_a: str
    player_b: str
    tour: str = "ATP"
    is_neutral: bool = True

    def __post_init__(self):
        """Validate tour value."""
        if self.tour not in ("ATP", "WTA"):
            raise ValueError(f"Tour must be 'ATP' or 'WTA', got: {self.tour}")

    @property
    def home_team(self) -> str:
        """Alias for player_a for BaseEloRating interface compatibility."""
        return self.player_a

    @property
    def away_team(self) -> str:
        """Alias for player_b for BaseEloRating interface compatibility."""
        return self.player_b

    @classmethod
    def from_team_interface(
        cls, home_team: str, away_team: str, is_neutral: bool = False
    ) -> "TennisMatchContext":
        """Create from team-based interface (BaseEloRating compatibility)."""
        return cls(
            player_a=home_team,
            player_b=away_team,
            tour="ATP",  # Default for team interface
            is_neutral=True,  # Tennis is always neutral
        )


@dataclass
class TennisMatchResult:
    """Result of a tennis match.

    This dataclass groups the result-related parameters that appear
    repeatedly in update methods.
    """

    context: TennisMatchContext
    home_won: Optional[Union[bool, float]] = None
    winner: Optional[str] = None
    loser: Optional[str] = None

    def __post_init__(self):
        """Validate that we have either home_won or winner/loser."""
        if self.home_won is None and (self.winner is None or self.loser is None):
            raise ValueError("Must provide either home_won or winner/loser")

    @classmethod
    def from_team_result(
        cls,
        home_team: str,
        away_team: str,
        home_win: Union[bool, float],
        is_neutral: bool = False,
    ) -> "TennisMatchResult":
        """Create from team-based result interface."""
        context = TennisMatchContext.from_team_interface(
            home_team, away_team, is_neutral
        )
        return cls(context=context, home_won=home_win)

    @classmethod
    def from_legacy_result(
        cls, winner: str, loser: str, tour: str = "ATP"
    ) -> "TennisMatchResult":
        """Create from legacy tennis result interface."""
        context = TennisMatchContext(player_a=winner, player_b=loser, tour=tour)
        return cls(context=context, winner=winner, loser=loser)


@dataclass
class TennisEloUpdateParams:
    """Parameters for Elo rating update calculation.

    This dataclass groups the related primitive parameters used in
    _calculate_update_change method to address Primitive Obsession.
    """

    rating_winner: float
    rating_loser: float
    matches_winner: int
    matches_loser: int

    @property
    def rw(self) -> float:
        """Alias for rating_winner for backward compatibility."""
        return self.rating_winner

    @property
    def rl(self) -> float:
        """Alias for rating_loser for backward compatibility."""
        return self.rating_loser

    @property
    def mw(self) -> int:
        """Alias for matches_winner for backward compatibility."""
        return self.matches_winner

    @property
    def ml(self) -> int:
        """Alias for matches_loser for backward compatibility."""
        return self.matches_loser
