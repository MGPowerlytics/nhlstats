import json
from pathlib import Path
from datetime import datetime
import math
from typing import Union
from .base_elo_rating import BaseEloRating


class TennisEloRating(BaseEloRating):
    """
    Elo rating system for ATP/WTA Tennis.
    Maintains separate ratings for men (ATP) and women (WTA).

    Note: Tennis doesn't have home/away teams, so we adapt the BaseEloRating interface.
    For predict/update methods, we treat player_a as "home" and player_b as "away".
    """

    def __init__(self, k_factor=32, home_advantage=0, initial_rating=1500):
        """
        Initialize Tennis Elo rating system.

        Args:
            k_factor: K-factor for rating updates (default 32)
            home_advantage: Not used in tennis (default 0)
            initial_rating: Initial rating for new players (default 1500)
        """
        super().__init__(k_factor=k_factor, home_advantage=home_advantage, initial_rating=initial_rating)
        # Separate ratings for ATP and WTA
        self.atp_ratings = {}
        self.wta_ratings = {}
        self.atp_matches_played = {}
        self.wta_matches_played = {}

    def _normalize_name(self, name):
        """Normalize player name to 'Lastname I.' format."""
        if not name:
            return "Unknown"

        name = str(name).strip().title()

        # If already formatted as "Djokovic N." (ends with dot), keep it
        if name.endswith('.'):
            return name

        # If "Novak Djokovic", convert to "Djokovic N."
        parts = name.split()
        if len(parts) >= 2:
            first = parts[0]
            last = " ".join(parts[1:])
            return f"{last} {first[0]}."

        return name

    def _get_tour_dicts(self, tour):
        """Get the appropriate ratings/matches dicts for a tour."""
        if str(tour).upper() == 'ATP':
            return self.atp_ratings, self.atp_matches_played
        else:  # WTA
            return self.wta_ratings, self.wta_matches_played

    def get_rating(self, player, tour='ATP'):
        """Get rating for a player in their tour."""
        ratings, matches = self._get_tour_dicts(tour)
        player = self._normalize_name(player)

        if player not in ratings:
            ratings[player] = self.initial_rating
        if player not in matches:
            matches[player] = 0
        return ratings[player]

    def get_match_count(self, player, tour='ATP'):
        """Get number of matches played by a player."""
        _, matches = self._get_tour_dicts(tour)
        player = self._normalize_name(player)
        return matches.get(player, 0)

    def predict(self, player_a, player_b, tour='ATP', is_neutral=True):
        """
        Predict probability of Player A defeating Player B.
        Both players must be from the same tour.

        Note: Tennis is always neutral (no home advantage).
        The is_neutral parameter is ignored (always True for tennis).
        """
        ra = self.get_rating(player_a, tour)
        rb = self.get_rating(player_b, tour)

        return self.expected_score(ra, rb)

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score (probability of team A winning).
        """
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def update(
        self,
        home_team: str,
        away_team: str,
        home_won: Union[bool, float] = None,
        is_neutral: bool = True,
        tour: str = 'ATP',
        **kwargs
    ):
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
            tour: 'ATP' or 'WTA'
        """
        ratings, matches = self._get_tour_dicts(tour)

        p1 = self._normalize_name(home_team)
        p2 = self._normalize_name(away_team)

        # Determine actual winner/loser
        if home_won is None:
            # Legacy mode: first arg is winner, second is loser
            winner = p1
            loser = p2
        else:
            # Standard mode
            if home_won:
                winner = p1
                loser = p2
            else:
                winner = p2
                loser = p1

        # Initialize if new
        if winner not in ratings:
            ratings[winner] = self.initial_rating
        if winner not in matches:
            matches[winner] = 0
        if loser not in ratings:
            ratings[loser] = self.initial_rating
        if loser not in matches:
            matches[loser] = 0

        rw = ratings[winner]
        rl = ratings[loser]

        expected_win = 1.0 / (1.0 + 10.0 ** ((rl - rw) / 400.0))

        # Calculate K-Factor
        # Higher K for newer players to converge faster
        k = self.k_factor

        # Simple dynamic K:
        if matches[winner] < 20: k *= 1.5
        if matches[loser] < 20: k *= 1.5

        change = k * (1.0 - expected_win)

        ratings[winner] = rw + change
        ratings[loser] = rl - change

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

    def legacy_update(self, winner, loser, tour='ATP'):
        """
        Legacy update method for backward compatibility.
        Same as update() for tennis.
        """
        return self.update(winner, loser, tour=tour, is_neutral=True)

    # Tennis-specific methods (preserved for backward compatibility)

    def get_rankings(self, tour='ATP', top_n=10):
        """Get top N players for a specific tour."""
        ratings, _ = self._get_tour_dicts(tour)
        return sorted(ratings.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def get_all_players(self, tour='ATP'):
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
        return self.predict(home_team, away_team, tour='ATP', is_neutral=True)

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
            return self.update(home_team, away_team, tour='ATP', is_neutral=True)
        else:
            return self.update(away_team, home_team, tour='ATP', is_neutral=True)
