from typing import Union, Optional
from plugins.elo.base_elo_rating import BaseEloRating, Matchup, GameResult, EloConfig
from plugins.elo.tennis_match import (
    TennisMatchContext,
    TennisMatchResult,
    TennisEloUpdateParams,
)


class TennisEloRating(BaseEloRating):
    """
    Elo rating system for ATP/WTA Tennis.
    Maintains separate ratings for men (ATP) and women (WTA).

    Note: Tennis doesn't have home/away teams, so we adapt the BaseEloRating interface.
    For predict/update methods, we treat player_a as "home" and player_b as "away".
    """

    def __init__(
        self,
        k_factor: float = 32.0,
        home_advantage: float = 0.0,
        initial_rating: float = 1500.0,
        config: Optional[EloConfig] = None,
    ) -> None:
        """
        Initialize Tennis Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 32)
            home_advantage: Not used in tennis (default 0)
            initial_rating: Initial rating for new players (default 1500)
            config: Optional EloConfig object
        """
        super().__init__(
            k_factor=k_factor,
            home_advantage=home_advantage,
            initial_rating=initial_rating,
            config=config,
        )
        # Separate ratings for ATP and WTA
        self.atp_ratings: dict[str, float] = {}
        self.wta_ratings: dict[str, float] = {}
        self.atp_matches_played: dict[str, int] = {}
        self.wta_matches_played: dict[str, int] = {}

    def _normalize_name(self, name: str, tour: str = "ATP") -> str:
        """Normalize player name to 'Lastname I.' format.

        Also attempts fuzzy matching for single-word last names.

        Args:
            name: Player name to normalize
            tour: Tournament type ("ATP" or "WTA")

        Returns:
            Normalized player name
        """
        if not name:
            return "Unknown"

        name = str(name).strip().title()

        # If already formatted as "Djokovic N." (ends with dot), keep it
        if name.endswith("."):
            return name

        # If "Novak Djokovic", convert to "Djokovic N."
        parts = name.split()
        if len(parts) >= 2:
            first = parts[0]
            last = parts[-1]  # Use last part as last name
            return f"{last} {first[0]}."

        # Single word name (e.g., "Korda") - try to find matching player
        # Look for players whose name starts with this last name
        ratings = self.atp_ratings if str(tour).upper() == "ATP" else self.wta_ratings
        for player_name in ratings:
            # Check if the player's last name matches (before the initial)
            if player_name.startswith(name + " "):
                return player_name

        return name

    def _get_tour_dicts(self, tour: str) -> tuple[dict[str, float], dict[str, int]]:
        """Get the appropriate ratings/matches dicts for a tour.

        Args:
            tour: Tournament type ("ATP" or "WTA")

        Returns:
            Tuple of (ratings_dict, matches_played_dict)
        """
        if str(tour).upper() == "ATP":
            return self.atp_ratings, self.atp_matches_played
        else:  # WTA
            return self.wta_ratings, self.wta_matches_played

    def get_rating(self, player: str, tour: str = "ATP") -> float:
        """Get rating for a player in their tour.

        Args:
            player: Player name
            tour: Tournament type ("ATP" or "WTA")

        Returns:
            Player's Elo rating
        """
        ratings, matches = self._get_tour_dicts(tour)
        player = self._normalize_name(player, tour)

        if player not in ratings:
            ratings[player] = self.config.initial_rating
        if player not in matches:
            matches[player] = 0
        return ratings[player]

    def get_match_count(self, player: str, tour: str = "ATP") -> int:
        """Get number of matches played by a player.

        Args:
            player: Player name
            tour: Tournament type ("ATP" or "WTA")

        Returns:
            Number of matches played
        """
        _, matches = self._get_tour_dicts(tour)
        player = self._normalize_name(player, tour)
        return matches.get(player, 0)

    # Helper methods to address Primitive Obsession smell
    def _create_match_context(
        self, player_a: str, player_b: str, tour: str = "ATP", is_neutral: bool = True
    ) -> TennisMatchContext:
        """
        Create TennisMatchContext from primitive parameters.
        Centralizes creation logic to reduce duplication.

        Args:
            player_a: First player name
            player_b: Second player name
            tour: Tournament type ("ATP" or "WTA")
            is_neutral: Whether match is at neutral site

        Returns:
            TennisMatchContext object
        """
        return TennisMatchContext(
            player_a=player_a, player_b=player_b, tour=tour, is_neutral=is_neutral
        )

    def _create_match_result(
        self,
        player_a: str,
        player_b: str,
        home_won: Union[bool, float],
        tour: str = "ATP",
        is_neutral: bool = True,
    ) -> TennisMatchResult:
        """
        Create TennisMatchResult from primitive parameters.
        Centralizes creation logic to reduce duplication.

        Args:
            player_a: First player name (treated as "home")
            player_b: Second player name (treated as "away")
            home_won: 1.0 if player_a wins, 0.0 if player_b wins
            tour: Tournament type ("ATP" or "WTA")
            is_neutral: Whether match is at neutral site

        Returns:
            TennisMatchResult object
        """
        context = self._create_match_context(player_a, player_b, tour, is_neutral)
        return TennisMatchResult(context=context, home_won=home_won)

    def _create_legacy_match_result(
        self, winner: str, loser: str, tour: str = "ATP", is_neutral: bool = True
    ) -> TennisMatchResult:
        """
        Create TennisMatchResult for legacy calling convention.
        In legacy mode, first argument is winner, second is loser.

        Args:
            winner: Winning player name
            loser: Losing player name
            tour: Tournament type ("ATP" or "WTA")
            is_neutral: Whether match is at neutral site

        Returns:
            TennisMatchResult object with winner/loser set
        """
        context = self._create_match_context(winner, loser, tour, is_neutral)
        return TennisMatchResult(
            context=context,
            home_won=None,  # Legacy mode indicator
            winner=winner,
            loser=loser,
        )

    def _create_team_match_context(
        self, home_team: str, away_team: str, is_neutral: bool = False
    ) -> TennisMatchContext:
        """
        Create TennisMatchContext from team interface parameters.
        Centralizes creation logic for BaseEloRating interface compatibility.

        Args:
            home_team: Player A (treated as "home" for interface compatibility)
            away_team: Player B (treated as "away" for interface compatibility)
            is_neutral: Ignored for tennis (always neutral)

        Returns:
            TennisMatchContext object
        """
        return TennisMatchContext.from_team_interface(home_team, away_team, is_neutral)

    def _create_team_match_result(
        self,
        home_team: str,
        away_team: str,
        home_win: Union[bool, float],
        is_neutral: bool = False,
    ) -> TennisMatchResult:
        """
        Create TennisMatchResult from team interface parameters.
        Centralizes creation logic for BaseEloRating interface compatibility.

        Args:
            home_team: Player A (treated as "home" for interface compatibility)
            away_team: Player B (treated as "away" for interface compatibility)
            home_win: 1.0 if home_team wins, 0.0 if away_team wins
            is_neutral: Ignored for tennis (always neutral)

        Returns:
            TennisMatchResult object
        """
        context = self._create_team_match_context(home_team, away_team, is_neutral)
        return TennisMatchResult(context=context, home_won=home_win)

    def predict(
        self,
        home_team: str,
        away_team: str,
        is_neutral: bool = False,
        *,
        tour: str = "ATP",
    ) -> float:
        """
        Predict probability of home team (player_a) defeating away team (player_b).
        Both players must be from the same tour.

        Note: Tennis is always neutral (no home advantage).
        The is_neutral parameter is ignored (always True for tennis).

        Args:
            home_team: First player name (treated as "home" for interface compatibility)
            away_team: Second player name (treated as "away" for interface compatibility)
            is_neutral: Whether the match is at a neutral site (ignored for tennis, always True)
            tour: Tournament type ("ATP" or "WTA") - keyword-only argument

        Returns:
            Probability (0.0 to 1.0) of home_team winning
        """
        # For BaseEloRating interface compatibility, map home_team/away_team to player_a/player_b
        # Note: is_neutral is ignored for tennis (always neutral)
        context = self._create_match_context(
            home_team, away_team, tour, is_neutral=True
        )
        return self.predict_with_context(context)

    def predict_with_context(self, context: "TennisMatchContext") -> float:
        """
        Predict probability using TennisMatchContext dataclass.

        Args:
            context: Tennis match context

        Returns:
            Probability (0.0 to 1.0) of player_a winning
        """
        ra = self.get_rating(context.player_a, context.tour)
        rb = self.get_rating(context.player_b, context.tour)

        return self.expected_score(ra, rb)

    def _determine_winner_loser(
        self,
        p1: str,
        p2: str,
        home_won: Optional[Union[bool, float]],
    ) -> tuple[str, str]:
        """Determine actual winner and loser names based on calling convention."""
        if home_won is None:
            # Legacy mode: first arg is winner, second is loser
            return p1, p2

        # Standard mode
        if home_won:
            return p1, p2
        return p2, p1

    def _init_player_if_new(
        self,
        player: str,
        ratings: dict[str, float],
        matches: dict[str, int],
    ) -> None:
        """Initialize player ratings and match counts if they are not present."""
        if player not in ratings:
            ratings[player] = self.config.initial_rating
        if player not in matches:
            matches[player] = 0

    def _calculate_update_change(
        self,
        rw: float,
        rl: float,
        mw: int,
        ml: int,
    ) -> float:
        """Calculate Elo rating change based on current ratings and match counts.

        Args:
            rw: Rating of winner
            rl: Rating of loser
            mw: Matches played by winner
            ml: Matches played by loser

        Returns:
            Elo rating change for winner (negative for loser)
        """
        # For backward compatibility, support both primitive parameters and dataclass
        params = TennisEloUpdateParams(
            rating_winner=rw, rating_loser=rl, matches_winner=mw, matches_loser=ml
        )
        return self._calculate_update_change_with_params(params)

    def _calculate_update_change_with_params(
        self,
        params: TennisEloUpdateParams,
    ) -> float:
        """Calculate Elo rating change using TennisEloUpdateParams dataclass.

        Args:
            params: TennisEloUpdateParams dataclass with rating and match data

        Returns:
            Elo rating change for winner (negative for loser)
        """
        expected_win = 1.0 / (1.0 + 10.0 ** ((params.rl - params.rw) / 400.0))

        # Calculate K-Factor
        # Higher K for newer players to converge faster
        k = self.config.k_factor

        # Simple dynamic K:
        if params.mw < 20:
            k *= 1.5
        if params.ml < 20:
            k *= 1.5

        return k * (1.0 - expected_win)

    def update(
        self,
        home_team: Optional[Union[Matchup, str]] = None,
        away_team: Optional[Union[GameResult, str, bool, float]] = None,
        home_won: Optional[Union[bool, float]] = None,
        **kwargs,
    ) -> Optional[float]:
        """
        Update ratings after a match.

        Supports two calling conventions:
        1. Standard BaseEloRating: update(p1, p2, home_won=True) -> p1 won
        2. Legacy Tennis: update(winner, loser) -> winner won (home_won=None)

        Args:
            home_team: Player A (or Winner in legacy mode)
            away_team: Player B (or Loser in legacy mode)
            home_won: True if home_team won, False if away_team won. None for legacy mode.
            is_neutral: Always True for tennis.
            matchup: Optional Matchup object
            result: Optional GameResult object
            tour: 'ATP' or 'WTA'
        """
        # Extract tennis-specific parameters from kwargs
        tour = kwargs.get("tour", "ATP")
        is_neutral = kwargs.get("is_neutral", True)

        # Extract from Matchup if provided
        if isinstance(home_team, Matchup):
            matchup = home_team
            home_team = matchup.home_team
            away_team = matchup.away_team
            # Extract home_won from matchup if not provided
            if home_won is None and hasattr(matchup, "home_won"):
                home_won = matchup.home_won

        # Extract from GameResult if provided
        if isinstance(away_team, GameResult):
            result = away_team
            away_team = None  # Will be determined from result
            home_won = result.home_won

        # Create context and result objects
        # Note: For legacy mode (home_won=None), we need special handling
        if home_won is None:
            # Legacy mode: home_team is winner, away_team is loser
            match_result = self._create_legacy_match_result(
                home_team, away_team, tour, is_neutral
            )
        else:
            # Standard mode: use helper
            match_result = self._create_match_result(
                home_team, away_team, home_won, tour, is_neutral
            )

        return self.update_with_result(match_result)

    def update_with_result(self, match_result: "TennisMatchResult") -> float:
        """
        Update ratings using TennisMatchResult dataclass.

        Args:
            match_result: Tennis match result

        Returns:
            Rating change
        """
        context = match_result.context
        ratings, matches = self._get_tour_dicts(context.tour)

        p1 = self._normalize_name(context.player_a, context.tour)
        p2 = self._normalize_name(context.player_b, context.tour)

        # Determine winner and loser
        if match_result.winner and match_result.loser:
            # Legacy mode
            winner = self._normalize_name(match_result.winner, context.tour)
            loser = self._normalize_name(match_result.loser, context.tour)
        else:
            # Standard mode
            winner, loser = self._determine_winner_loser(p1, p2, match_result.home_won)

        self._init_player_if_new(winner, ratings, matches)
        self._init_player_if_new(loser, ratings, matches)

        params = TennisEloUpdateParams(
            rating_winner=ratings[winner],
            rating_loser=ratings[loser],
            matches_winner=matches[winner],
            matches_loser=matches[loser],
        )
        change = self._calculate_update_change_with_params(params)

        ratings[winner] += change
        ratings[loser] -= change

        matches[winner] += 1
        matches[loser] += 1

        return change

    def get_all_ratings(self):
        """
        Return dictionary of all player ratings.

        Returns a dictionary with ATP and WTA ratings combined.
        Keys are formatted as "ATP:PlayerName" or "WTA:PlayerName".
        """
        all_ratings = {}
        for player, rating in self.atp_ratings.items():
            all_ratings[f"ATP:{player}"] = rating
        for player, rating in self.wta_ratings.items():
            all_ratings[f"WTA:{player}"] = rating
        return all_ratings

    def legacy_update(self, winner: str, loser: str, tour: str = "ATP") -> float:
        """
        Legacy update method for backward compatibility.
        Same as update() for tennis.

        Args:
            winner: Winning player name
            loser: Losing player name
            tour: Tournament type ("ATP" or "WTA")

        Returns:
            Rating change applied to winner
        """
        match_result = TennisMatchResult.from_legacy_result(winner, loser, tour)
        return self.update_with_result(match_result)

    # Tennis-specific methods (preserved for backward compatibility)

    def get_rankings(
        self, tour: str = "ATP", top_n: int = 10
    ) -> list[tuple[str, float]]:
        """Get top N players for a specific tour.

        Args:
            tour: Tournament type ("ATP" or "WTA")
            top_n: Number of top players to return

        Returns:
            List of (player_name, rating) tuples sorted by rating descending
        """
        ratings, _ = self._get_tour_dicts(tour)
        return sorted(ratings.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def get_all_players(self, tour: str = "ATP") -> list[str]:
        """Get all players for a tour.

        Args:
            tour: Tournament type ("ATP" or "WTA")

        Returns:
            List of all player names
        """
        ratings, _ = self._get_tour_dicts(tour)
        return list(ratings.keys())

    # BaseEloRating interface adaptation methods

    def predict_team(
        self, home_team: str, away_team: str, is_neutral: bool = False
    ) -> float:
        """
        Adapt team-based predict to tennis player-based predict.
        This is for BaseEloRating interface compatibility.

        Args:
            home_team: Player A (treated as "home" for interface compatibility)
            away_team: Player B (treated as "away" for interface compatibility)
            is_neutral: Ignored for tennis (always neutral)

        Returns:
            Probability that home_team (player_a) defeats away_team (player_b)
        """
        context = self._create_team_match_context(home_team, away_team, is_neutral)
        return self.predict_with_context(context)

    def update_team(
        self,
        home_team: str,
        away_team: str,
        home_win: Union[bool, float],
        is_neutral: bool = False,
    ) -> float:
        """
        Adapt team-based update to tennis player-based update.
        This is for BaseEloRating interface compatibility.

        Args:
            home_team: Player A (treated as "home" for interface compatibility)
            away_team: Player B (treated as "away" for interface compatibility)
            home_win: 1.0 if home_team wins, 0.0 if away_team wins
            is_neutral: Ignored for tennis (always neutral)

        Returns:
            Rating change
        """
        match_result = self._create_team_match_result(
            home_team, away_team, home_win, is_neutral
        )
        return self.update_with_result(match_result)
