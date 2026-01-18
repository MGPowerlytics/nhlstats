import json
from pathlib import Path
from datetime import datetime
import math

class TennisEloRating:
    """
    Elo rating system for ATP/WTA Tennis.
    Tracks ratings for individual players.
    """
    
    def __init__(self, k_factor=32, initial_rating=1500):
        self.k_factor = k_factor
        self.initial_rating = initial_rating
        self.ratings = {}
        self.matches_played = {}
        
    def get_rating(self, player):
        if player not in self.ratings:
            self.ratings[player] = self.initial_rating
            self.matches_played[player] = 0
        return self.ratings[player]
        
    def predict(self, player_a, player_b):
        """
        Predict probability of Player A defeating Player B.
        """
        ra = self.get_rating(player_a)
        rb = self.get_rating(player_b)
        
        return 1 / (1 + 10 ** ((rb - ra) / 400))
        
    def update(self, winner, loser):
        """
        Update ratings after a match.
        Tennis is binary (Win/Loss).
        """
        rw = self.get_rating(winner)
        rl = self.get_rating(loser)
        
        expected_win = 1 / (1 + 10 ** ((rl - rw) / 400))
        
        # Calculate K-Factor
        # Higher K for newer players to converge faster
        # Lower K for established veterans
        k = self.k_factor
        
        # Simple dynamic K:
        if self.matches_played[winner] < 20: k *= 1.5
        if self.matches_played[loser] < 20: k *= 1.5
        
        change = k * (1.0 - expected_win)
        
        self.ratings[winner] = rw + change
        self.ratings[loser] = rl - change
        
        self.matches_played[winner] += 1
        self.matches_played[loser] += 1
        
        return change

    def get_rankings(self, top_n=10):
        return sorted(self.ratings.items(), key=lambda x: x[1], reverse=True)[:top_n]
