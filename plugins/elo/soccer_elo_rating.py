"""
SoccerEloRating - Base class for soccer-specific Elo rating systems.
Handles 3-way outcomes (Home, Draw, Away).
"""

import math
from typing import Dict, Union, Tuple, Optional
from plugins.elo.base_elo_rating import BaseEloRating, Matchup, GameResult


class SoccerEloRating(BaseEloRating):
    """
    Base class for soccer Elo rating systems with 3-way outcome support.
    """

    def __init__(
        self,
        k_factor: float = 20.0,
        home_advantage: float = 60.0,
        initial_rating: float = 1500.0,
        draw_coefficient: float = 0.25,
        draw_width: float = 200.0,
    ):
        """
        Initialize Soccer Elo rating system.

        Args:
            k_factor: How quickly ratings change
            home_advantage: Elo points added for home field
            initial_rating: Starting rating for new teams
            draw_coefficient: Peak draw probability (at 0 rating difference)
            draw_width: Controls how quickly draw probability drops as rating gap grows
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
        )
        self.draw_coefficient = draw_coefficient
        self.draw_width = draw_width

    def _apply_home_advantage(self, home_rating: float, is_neutral: bool) -> float:
        """
        Apply home advantage to rating if not neutral.

        Args:
            home_rating: Home team's base rating
            is_neutral: Whether the game is at a neutral site

        Returns:
            Home team's rating with home advantage applied
        """
        if is_neutral:
            return home_rating
        return home_rating + self.config.home_advantage

    def update(
        self,
        home_team: Optional[Union[Matchup, str]] = None,
        away_team: Optional[Union[GameResult, str, bool, float]] = None,
        home_won: Optional[Union[bool, float]] = None,
        **kwargs,
    ) -> Optional[float]:
        """
        Update Elo ratings after a game result.

        This method implements the abstract update method from BaseEloRating
        while providing soccer-specific logic for 3-way outcomes.

        Args:
            home_team: Name of home team or Matchup object
            away_team: Name of away team, GameResult, or result value
            home_won: True/1.0 if home team won, False/0.0 if away team won,
                      0.5 for draw, or score margin for margin-of-victory
            **kwargs: Additional arguments including is_neutral

        Returns:
            Rating change for home team (for backward compatibility)
        """
        # Parse arguments using the base class parser
        parsed = self.parser.parse_update_args(
            home_team=home_team, away_team=away_team, home_won=home_won, **kwargs
        )
        
        # Extract soccer-specific parameters
        is_neutral = kwargs.get('is_neutral', False)
        
        # Get current ratings
        if parsed.matchup.home_team is None or parsed.matchup.away_team is None:
            raise ValueError("Matchup must have both home and away teams")
        
        rh = self.get_rating(parsed.matchup.home_team)
        ra = self.get_rating(parsed.matchup.away_team)

        # Apply home advantage if not neutral
        try:
            home_rating_with_adv = self._apply_home_advantage(rh, is_neutral)
        except AttributeError:
            # Fallback for compatibility
            if is_neutral:
                home_rating_with_adv = rh
            else:
                home_rating_with_adv = rh + self.config.home_advantage

        # Calculate expected score for home team
        expected_home = self.expected_score(home_rating_with_adv, ra)

        # Determine actual score based on result
        if parsed.result.home_won is True:
            actual_home = 1.0
        elif parsed.result.home_won is False:
            actual_home = 0.0
        elif parsed.result.home_won == 0.5:
            actual_home = 0.5
        else:
            # For score margin, use logistic transformation
            # Max margin effect capped at 2.0 (equivalent to ~0.88 probability)
            margin = min(max(float(parsed.result.home_won), -2.0), 2.0)
            actual_home = 1.0 / (1.0 + math.exp(-margin))

        # Calculate rating changes
        home_change = self.calculator.calculate_rating_change(expected_home, actual_home)

        # Update ratings (Zero-sum)
        self.ratings[parsed.matchup.home_team] = rh + home_change
        self.ratings[parsed.matchup.away_team] = ra - home_change
        
        return home_change

    def predict_probs(
        self,
        home_team: Union[str, Matchup],
        away_team: Optional[str] = None,
        is_neutral: bool = False,
    ) -> Tuple[float, float, float]:
        """
        Predict probabilities for Home Win, Draw, Away Win.

        Args:
            home_team: Name of home team or Matchup object
            away_team: Name of away team (if home_team is a string)
            is_neutral: Whether the game is at a neutral site (if home_team is a string)

        Returns: (p_home, p_draw, p_away)
        """
        if isinstance(home_team, Matchup):
            matchup = home_team
            rh = self.get_rating(matchup.home_team)
            ra = self.get_rating(matchup.away_team)
            is_neutral = matchup.is_neutral
        else:
            rh = self.get_rating(home_team)
            ra = self.get_rating(away_team)

        # Apply home advantage
        try:
            rh_adv = self._apply_home_advantage(rh, is_neutral)
        except AttributeError:
            # Fallback for compatibility
            if is_neutral:
                rh_adv = rh
            else:
                rh_adv = rh + self.config.home_advantage
        dr = rh_adv - ra

        # 1. Calculate Expected Points (standard Elo win prob)
        # Expected points = P(Home) + 0.5 * P(Draw)
        expected_points = self.expected_score(rh_adv, ra)

        # 2. Estimate Draw Probability
        # Draw is most likely when teams are equal strength.
        p_draw = self.draw_coefficient * math.exp(-((dr / self.draw_width) ** 2))

        # Clamp draw probability to reasonable bounds for soccer
        p_draw = max(0.05, min(0.35, p_draw))

        # 3. Derive Win/Loss probs
        # P(Home) = ExpPoints - 0.5 * P(Draw)
        p_home = max(0.01, expected_points - 0.5 * p_draw)
        p_away = max(0.01, 1.0 - p_home - p_draw)

        # Normalize to sum to 1.0
        total = p_home + p_draw + p_away
        return (p_home / total, p_draw / total, p_away / total)

    def predict_3way(
        self,
        home_team: Union[str, Matchup],
        away_team: Optional[str] = None,
        is_neutral: bool = False,
    ) -> Dict[str, float]:
        """
        Predict 3-way outcome as dict.

        Args:
            home_team: Name of home team or Matchup object
            away_team: Name of away team (if home_team is a string)
            is_neutral: Whether the game is at a neutral site (if home_team is a string)

        Returns: {'home': p_home, 'draw': p_draw, 'away': p_away}
        """
        p_home, p_draw, p_away = self.predict_probs(home_team, away_team, is_neutral)
        return {"home": p_home, "draw": p_draw, "away": p_away}
