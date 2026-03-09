from typing import Union, Optional
from plugins.elo.base_elo_rating import BaseEloRating, Matchup, GameResult, EloConfig


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
        self.atp_ratings = {}
        self.wta_ratings = {}
        self.atp_matches_played = {}
        self.wta_matches_played = {}

    def _normalize_name(self, name, tour="ATP"):
        """Normalize player name to 'Lastname I.' format.

        Also attempts fuzzy matching for single-word last names.
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

    def _get_tour_dicts(self, tour):
        """Get the appropriate ratings/matches dicts for a tour."""
        if str(tour).upper() == "ATP":
            return self.atp_ratings, self.atp_matches_played
        else:  # WTA
            return self.wta_ratings, self.wta_matches_played

    def get_rating(self, player, tour="ATP"):
        """Get rating for a player in their tour."""
        ratings, matches = self._get_tour_dicts(tour)
        player = self._normalize_name(player, tour)

        if player not in ratings:
            ratings[player] = self.config.initial_rating
        if player not in matches:
            matches[player] = 0
        return ratings[player]

    def get_match_count(self, player, tour="ATP"):
        """Get number of matches played by a player."""
        _, matches = self._get_tour_dicts(tour)
        player = self._normalize_name(player, tour)
        return matches.get(player, 0)

    def predict(self, player_a, player_b, tour="ATP", is_neutral=True):
        """
        Predict probability of Player A defeating Player B.
        Both players must be from the same tour.

        Note: Tennis is always neutral (no home advantage).
        The is_neutral parameter is ignored (always True for tennis).
        """
        ra = self.get_rating(player_a, tour)
        rb = self.get_rating(player_b, tour)

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
        """Calculate Elo rating change based on current ratings and match counts."""
        expected_win = 1.0 / (1.0 + 10.0 ** ((rl - rw) / 400.0))

        # Calculate K-Factor
        # Higher K for newer players to converge faster
        k = self.config.k_factor

        # Simple dynamic K:
        if mw < 20:
            k *= 1.5
        if ml < 20:
            k *= 1.5

        return k * (1.0 - expected_win)

    def update(
        self,
        home_team: str = None,
        away_team: str = None,
        home_won: Union[bool, float] = None,
        is_neutral: bool = True,
        matchup: Optional[Matchup] = None,
        result: Optional[GameResult] = None,
        tour: str = "ATP",
        **kwargs,
    ) -> float:
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
        # Extract from Matchup if provided
        if matchup:
            home_team = matchup.home_team
            away_team = matchup.away_team
            is_neutral = matchup.is_neutral

        # Extract from GameResult if provided
        if result:
            home_won = result.home_won

        ratings, matches = self._get_tour_dicts(tour)

        p1 = self._normalize_name(home_team, tour)
        p2 = self._normalize_name(away_team, tour)

        winner, loser = self._determine_winner_loser(p1, p2, home_won)

        self._init_player_if_new(winner, ratings, matches)
        self._init_player_if_new(loser, ratings, matches)

        change = self._calculate_update_change(
            ratings[winner], ratings[loser], matches[winner], matches[loser]
        )

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

    def legacy_update(self, winner, loser, tour="ATP"):
        """
        Legacy update method for backward compatibility.
        Same as update() for tennis.
        """
        return self.update(winner, loser, tour=tour, is_neutral=True)

    # Tennis-specific methods (preserved for backward compatibility)

    def get_rankings(self, tour="ATP", top_n=10):
        """Get top N players for a specific tour."""
        ratings, _ = self._get_tour_dicts(tour)
        return sorted(ratings.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def get_all_players(self, tour="ATP"):
        """Get all players for a tour."""
        ratings, _ = self._get_tour_dicts(tour)
        return list(ratings.keys())

    # BaseEloRating interface adaptation methods

    def predict_team(self, home_team, away_team, is_neutral=False):
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
        return self.predict(home_team, away_team, tour="ATP", is_neutral=True)

    def update_team(self, home_team, away_team, home_win, is_neutral=False):
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
        if home_win == 1.0:
            return self.update(home_team, away_team, tour="ATP", is_neutral=True)
        else:
            return self.update(away_team, home_team, tour="ATP", is_neutral=True)
