import json
from pathlib import Path
from datetime import datetime
from typing import Union
from .base_elo_rating import BaseEloRating
class WNCAABEloRating(BaseEloRating):
    """Women's NCAA Basketball Elo Rating System."""
    def __init__(self, k_factor=20, home_advantage=100, initial_rating=1500):
        super().__init__(k_factor=k_factor, home_advantage=home_advantage, initial_rating=initial_rating)
        self.ratings = {}
    def get_rating(self, team):
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]
    def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float:
        """Predict home team win probability."""
        rh = self.get_rating(home_team)
        ra = self.get_rating(away_team)

        if not is_neutral:
            rh += self.home_advantage

        return self.expected_score(rh, ra)

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
        is_neutral: bool = False,
        home_win: Union[bool, float] = None,
        **kwargs
    ) -> None:
        # Handle aliasing
        if home_won is None and home_win is not None:
            home_won = home_win
        elif home_won is None and 'home_win' in kwargs:
            home_won = kwargs['home_win']
        elif home_won is None:
             raise ValueError("Must provide home_won")

        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        if not is_neutral:
            home_rating += self.home_advantage

        expected_home = self.expected_score(home_rating, away_rating)
        actual_home = 1.0 if home_won else 0.0
        change = self._calculate_rating_change(expected_home, actual_home)

        if not is_neutral:
            home_rating -= self.home_advantage

        self.ratings[home_team] = home_rating + change
        self.ratings[away_team] = away_rating - change

        return change
    def get_all_ratings(self):
        """Return dictionary of all team ratings."""
        return self.ratings.copy()
    def legacy_update(self, home_team: str, away_team: str, home_won: bool = None, is_neutral: bool = False, **kwargs):
        """
        Legacy update method for backward compatibility.
        Same as update() for WNCAAB.
        """
        return self.update(home_team, away_team, home_won, is_neutral=is_neutral, **kwargs)
def calculate_current_elo_ratings():
    from wncaab_games import WNCAABGames
    wncaab = WNCAABGames()
    df = wncaab.load_games()
    elo = WNCAABEloRating()
    # Sort by date
    df = df.sort_values("date")
    last_season = None
    for _, game in df.iterrows():
        # Season reversion for college rosters
        current_season = game.get("season")
        if current_season and current_season != last_season:
            if last_season is not None:
                # Revert towards mean
                for t in elo.ratings:
                    elo.ratings[t] = 0.65 * elo.ratings[t] + 0.35 * 1500
            last_season = current_season
        # Win = 1 if home score > away score
        h_score = game["home_score"]
        a_score = game["away_score"]
        neutral = game["neutral"]
        if h_score > a_score:
            res = 1.0
        else:
            res = 0.0
        elo.update(game["home_team"], game["away_team"], res, is_neutral=neutral)
    return elo
if __name__ == "__main__":
    elo = calculate_current_elo_ratings()
    print("Top 10 WNCAAB Teams:")
    ranked = sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (t, r) in enumerate(ranked, 1):
        print(f"{i}. {t}: {r:.1f}")
