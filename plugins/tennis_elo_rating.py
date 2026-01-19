import json
from pathlib import Path
from datetime import datetime
import math

class TennisEloRating:
    """
    Elo rating system for ATP/WTA Tennis.
    Maintains separate ratings for men (ATP) and women (WTA).
    """
    
    def __init__(self, k_factor=32, initial_rating=1500):
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        # Separate ratings for ATP and WTA
        self.atp_ratings = {}
        self.wta_ratings = {}
        self.atp_matches_played = {}
        self.wta_matches_played = {}
        
    def _get_tour_dicts(self, tour):
        """Get the appropriate ratings/matches dicts for a tour."""
        if tour.upper() == 'ATP':
            return self.atp_ratings, self.atp_matches_played
        else:  # WTA
            return self.wta_ratings, self.wta_matches_played
        
    def get_rating(self, player, tour='ATP'):
        """Get rating for a player in their tour."""
        ratings, matches = self._get_tour_dicts(tour)
        if player not in ratings:
            ratings[player] = self.initial_rating
            matches[player] = 0
        return ratings[player]
        
    def predict(self, player_a, player_b, tour='ATP'):
        """
        Predict probability of Player A defeating Player B.
        Both players must be from the same tour.
        """
        ra = self.get_rating(player_a, tour)
        rb = self.get_rating(player_b, tour)
        
        return 1 / (1 + 10 ** ((rb - ra) / 400))
        
    def update(self, winner, loser, tour='ATP'):
        """
        Update ratings after a match.
        Tennis is binary (Win/Loss).
        """
        ratings, matches = self._get_tour_dicts(tour)
        
        rw = self.get_rating(winner, tour)
        rl = self.get_rating(loser, tour)
        
        expected_win = 1 / (1 + 10 ** ((rl - rw) / 400))
        
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

    def get_rankings(self, tour='ATP', top_n=10):
        """Get top N players for a specific tour."""
        ratings, _ = self._get_tour_dicts(tour)
        return sorted(ratings.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    def get_all_players(self, tour='ATP'):
        """Get all players for a tour."""
        ratings, _ = self._get_tour_dicts(tour)
        return list(ratings.keys())
