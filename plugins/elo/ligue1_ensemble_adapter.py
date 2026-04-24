
"""
Ligue 1 Ensemble Adapter.
Wraps Ligue1EnsembleModel to provide a standard Elo-like interface.
"""

import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Tuple, Any, List
from dataclasses import dataclass, field

from plugins.elo.ligue1_elo_rating import Ligue1EloRating
from plugins.elo.ligue1_ensemble import Ligue1EnsembleModel
from plugins.naming_resolver import NamingResolver, NamingContext

@dataclass
class _Ligue1TeamStats:
    """Rolling per-team season aggregates for Ligue 1."""
    games_played: int = 0
    goals_for: float = 0.0
    goals_against: float = 0.0
    wins: float = 0.0  # 1.0 for win, 0.5 for draw
    last_game_date: Optional[date] = None
    recent_results: List[float] = field(default_factory=list) # List of 1.0, 0.5, 0.0

@dataclass
class Ligue1EnsembleAdapter:
    """
    Adapter for Ligue 1 Ensemble Model.
    Matches the interface expected by the betting pipeline.
    """

    elo: Ligue1EloRating = field(default_factory=Ligue1EloRating)
    ensemble: Ligue1EnsembleModel = field(default_factory=Ligue1EnsembleModel)
    team_stats: Dict[str, _Ligue1TeamStats] = field(default_factory=dict)
    bookmaker_probs: Dict[Tuple[str, str], Dict[str, float]] = field(default_factory=dict)
    reference_date: Optional[date] = None

    def __post_init__(self):
        # Try to load existing model
        self.ensemble.load()

    @property
    def ratings(self) -> Dict[str, float]:
        return self.elo.ratings

    @ratings.setter
    def ratings(self, new_ratings: Dict[str, float]) -> None:
        self.elo.ratings = dict(new_ratings or {})

    def get_rating(self, team: str) -> float:
        return self.elo.get_rating(team)

    def get_all_ratings(self) -> Dict[str, float]:
        return self.elo.get_all_ratings()

    def predict_probs(self, home_team: str, away_team: str) -> Tuple[float, float, float]:
        """
        Predict Home/Draw/Away probabilities.
        """
        # 1. Get Elo probabilities (base)
        p_home_elo, p_draw_elo, p_away_elo = self.elo.predict_probs(home_team, away_team)

        # 2. Build feature set for ML
        h_stats = self.team_stats.get(home_team, _Ligue1TeamStats())
        a_stats = self.team_stats.get(away_team, _Ligue1TeamStats())

        bm = self.bookmaker_probs.get((home_team, away_team),
                                     {"home": 0.4, "draw": 0.25, "away": 0.35})

        features = {
            'home_elo': self.elo.get_rating(home_team),
            'away_elo': self.elo.get_rating(away_team),
            'elo_diff': self.elo.get_rating(home_team) - self.elo.get_rating(away_team),
            'home_form': np.mean(h_stats.recent_results) if h_stats.recent_results else 0.5,
            'away_form': np.mean(a_stats.recent_results) if a_stats.recent_results else 0.5,
            'home_avg_gf': h_stats.goals_for / h_stats.games_played if h_stats.games_played > 0 else 1.2,
            'home_avg_ga': h_stats.goals_against / h_stats.games_played if h_stats.games_played > 0 else 1.2,
            'away_avg_gf': a_stats.goals_for / a_stats.games_played if a_stats.games_played > 0 else 1.1,
            'away_avg_ga': a_stats.goals_against / a_stats.games_played if a_stats.games_played > 0 else 1.3,
            'bookmaker_prob_home': bm['home'],
            'bookmaker_prob_draw': bm['draw'],
            'bookmaker_prob_away': bm['away'],
            'elo_prob_home': p_home_elo,
            'elo_prob_draw': p_draw_elo,
            'elo_prob_away': p_away_elo
        }

        # 3. Get Ensemble prediction
        probs = self.ensemble.predict_probs(features)
        return (probs['home'], probs['draw'], probs['away'])

    def predict(self, home_team: str, away_team: str) -> float:
        """Standard Elo predict returns Home Win probability."""
        p_h, p_d, p_a = self.predict_probs(home_team, away_team)
        return p_h

    def update(self, home_team: str, away_team: str, home_won: Any, **kwargs) -> None:
        """Update the underlying Elo system."""
        self.elo.update(home_team, away_team, home_won, **kwargs)

    def populate_from_db(self, db, season_year: Optional[int] = None, reference_date: Optional[date] = None) -> None:
        """Populate team stats and bookmaker odds from DB."""
        ref = reference_date or date.today()
        self.reference_date = ref
        year = season_year or (ref.year if ref.month > 7 else ref.year - 1)

        self._load_team_stats(db, year, ref)
        self._load_bookmaker_odds(db, ref)

    def _load_team_stats(self, db, year: int, ref: date) -> None:
        """Aggregate Ligue 1 season stats."""
        query = """
            SELECT game_date, home_team, away_team, home_score, away_score, result
            FROM ligue1_games
            WHERE game_date < :ref
              AND (EXTRACT(YEAR FROM game_date) = :year OR EXTRACT(YEAR FROM game_date) = :year + 1)
              AND home_score IS NOT NULL
            ORDER BY game_date
        """
        df = db.fetch_df(query, {"year": int(year), "ref": ref})
        if df is None or df.empty:
            return

        stats: Dict[str, _Ligue1TeamStats] = {}
        for row in df.itertuples(index=False):
            h, a = row.home_team, row.away_team
            hs, as_ = float(row.home_score), float(row.away_score)
            res = row.result

            h_s = stats.setdefault(h, _Ligue1TeamStats())
            a_s = stats.setdefault(a, _Ligue1TeamStats())

            h_s.games_played += 1
            h_s.goals_for += hs
            h_s.goals_against += as_

            a_s.games_played += 1
            a_s.goals_for += as_
            a_s.goals_against += hs

            if res == 'H':
                h_s.wins += 1.0
                h_s.recent_results.append(1.0)
                a_s.recent_results.append(0.0)
            elif res == 'A':
                a_s.wins += 1.0
                h_s.recent_results.append(0.0)
                a_s.recent_results.append(1.0)
            else:
                h_s.wins += 0.5
                a_s.wins += 0.5
                h_s.recent_results.append(0.5)
                a_s.recent_results.append(0.5)

            # Keep only last 5 for form
            if len(h_s.recent_results) > 5: h_s.recent_results.pop(0)
            if len(a_s.recent_results) > 5: a_s.recent_results.pop(0)

        self.team_stats = stats

    def _load_bookmaker_odds(self, db, ref: date) -> None:
        """Load recent bookmaker odds to estimate consensus probabilities for upcoming games."""
        query = """
            SELECT
                u.home_team_name,
                u.away_team_name,
                o.outcome_name,
                o.price
            FROM unified_games u
            JOIN game_odds o ON u.game_id = o.game_id
            WHERE u.sport = 'LIGUE1'
              AND u.game_date >= :ref
              AND u.game_date < :ref + interval '7 days'
              AND o.market_name = '3-way'
            ORDER BY o.last_update DESC
        """
        df = db.fetch_df(query, {"ref": ref})
        if df is None or df.empty:
            return

        # Simple consensus: average prices per matchup and outcome
        # price is likely in decimal odds (e.g. 2.5) or American (-150)
        # But for probabilities we need to handle both.
        # Standard in this project: price is DECIMAL(10,4), likely decimal odds.

        # Group by home/away/outcome
        matchups = df.groupby(['home_team_name', 'away_team_name'])

        bm_probs = {}
        for (h, a), group in matchups:
            # Get latest odds for each outcome (Home/Draw/Away)
            # outcome_name is likely 'Home', 'Draw', 'Away' or 'H', 'D', 'A'
            probs = {}
            for outcome in ['Home', 'Draw', 'Away', 'H', 'D', 'A']:
                sub = group[group['outcome_name'].str.lower() == outcome.lower()]
                if not sub.empty:
                    # Use avg price of latest updates
                    avg_price = sub['price'].iloc[0] # Just take the most recent one for now
                    if avg_price > 0:
                        probs[outcome[0].upper()] = 1.0 / float(avg_price)

            # Normalize to 1.0 (remove overround)
            h_p = probs.get('H', probs.get('H', 0.4)) # Fallback if missing
            d_p = probs.get('D', probs.get('D', 0.25))
            a_p = probs.get('A', probs.get('A', 0.35))

            # Use specific ones if found
            h_p = probs.get('H', 0.4)
            d_p = probs.get('D', 0.25)
            a_p = probs.get('A', 0.35)

            total = h_p + d_p + a_p
            if total > 0:
                bm_probs[(h, a)] = {
                    "home": h_p / total,
                    "draw": d_p / total,
                    "away": a_p / total
                }

        self.bookmaker_probs = bm_probs
