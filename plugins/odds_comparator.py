"""
Compares Elo probabilities against unified market odds to find betting opportunities.
"""

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

from db_manager import DBManager, default_db
from naming_resolver import NamingResolver


class OddsComparator:
    """
    Compares internal Elo probabilities with best available market odds.
    """

    def __init__(self, db_manager: DBManager = default_db):
        self.db = db_manager

    def get_best_odds(self, game_id: str) -> Dict[str, Dict]:
        """
        Retrieves the best available odds for a game from PostgreSQL.
        Returns a dictionary with 'home', 'away', and 'draw' best odds.
        """
        try:
            result = {}
            for side in ['home', 'away', 'draw']:
                df = self.db.fetch_df("""
                    SELECT bookmaker, price, last_update
                    FROM game_odds
                    WHERE game_id = :game_id AND outcome_name = :side
                    ORDER BY price DESC
                    LIMIT 1
                """, {'game_id': game_id, 'side': side})

                if not df.empty:
                    row = df.iloc[0]
                    result[side] = {
                        'bookmaker': row['bookmaker'],
                        'decimal_odds': float(row['price']),
                        'last_update': row['last_update']
                    }
            return result
        except Exception as e:
            print(f"Error fetching best odds for {game_id}: {e}")
            return {}

    def get_all_odds(self, game_id: str) -> List[Dict]:
        """
        Retrieves all available odds for a game.
        """
        return self.db.fetch_df("""
            SELECT bookmaker, outcome_name, price, last_update, external_id
            FROM game_odds
            WHERE game_id = :game_id
        """, {'game_id': game_id}).to_dict('records')

    def find_opportunities(self, sport: str, elo_ratings: Dict,
                          elo_system, threshold: float = 0.65,
                          min_edge: float = 0.05,
                          use_sharp_confirmation: bool = False) -> List[Dict]:
        """
        Identifies betting opportunities by comparing Elo with market odds.

        Bet Types:
        - Elo-only: use_sharp_confirmation=False (pure Elo vs Kalshi)
        - Sharp: use_sharp_confirmation=True (confirmed by sharp books)
        """
        opportunities = []

        try:
            today = datetime.now().strftime('%Y-%m-%d')
            query = """
                SELECT game_id, game_date, home_team_name, away_team_name, status
                FROM unified_games
                WHERE sport = :sport
                  AND game_date >= :today
                  AND status NOT IN ('Final', 'Finalized', 'OFF', 'Closed')
                ORDER BY game_date
            """
            games_df = self.db.fetch_df(query, {'sport': sport.upper(), 'today': today})

            print(f"🔍 Analyzing {len(games_df)} {sport.upper()} games for value bets...")

            for _, row in games_df.iterrows():
                game_id = row['game_id']

                # 1. Resolve source
                source = 'kalshi' # Unified games default
                if 'odds_api' in game_id.lower(): source = 'the_odds_api'

                # 2. Resolve Canonical Names
                canon_home = NamingResolver.resolve(sport, source, row['home_team_name']) or row['home_team_name']
                canon_away = NamingResolver.resolve(sport, source, row['away_team_name']) or row['away_team_name']

                # 3. Resolve Elo Names
                elo_home = NamingResolver.resolve(sport, 'elo', canon_home) or canon_home
                elo_away = NamingResolver.resolve(sport, 'elo', canon_away) or canon_away

                # 4. Get Odds
                all_odds = self.get_all_odds(game_id)
                if not all_odds: continue

                odds_by_bm = {}
                tickers_by_bm = {}
                for o in all_odds:
                    bm = o['bookmaker']
                    outcome = o['outcome_name']

                    # If outcome is a name, resolve it to 'home' or 'away'
                    if outcome not in ['home', 'away', 'draw']:
                        canon_outcome = NamingResolver.resolve(sport, 'the_odds_api', outcome) or outcome
                        if canon_outcome == canon_home: outcome = 'home'
                        elif canon_outcome == canon_away: outcome = 'away'
                        elif 'draw' in outcome.lower(): outcome = 'draw'

                    if bm not in odds_by_bm: odds_by_bm[bm] = {}
                    odds_by_bm[bm][outcome] = float(o['price'])

                    if bm not in tickers_by_bm: tickers_by_bm[bm] = {}
                    tickers_by_bm[bm][outcome] = o.get('external_id')

                kalshi_odds = odds_by_bm.get('Kalshi')
                if not kalshi_odds: continue

                sharp_bms = ['pinnacle', 'betmgm', 'draftkings', 'fanduel', 'williamhill']
                sharp_odds = None
                for sbm in sharp_bms:
                    if sbm in odds_by_bm:
                        sharp_odds = odds_by_bm[sbm]
                        break

                # 5. Predict
                try:
                    if sport.lower() == 'tennis':
                        tour = 'atp' if 'KXATPMATCH' in game_id or 'ATP' in game_id else 'wta'
                        home_win_prob = elo_system.predict(elo_home, elo_away, tour=tour)
                    elif hasattr(elo_system, 'predict_3way') and sport.lower() in ['epl', 'ligue1']:
                        probs = elo_system.predict_3way(elo_home, elo_away)
                        home_win_prob, draw_prob, away_win_prob = probs['home'], probs['draw'], probs['away']
                    else:
                        home_win_prob = elo_system.predict(elo_home, elo_away)
                except:
                    continue

                # 6. Evaluate Outcomes
                if sport.lower() in ['epl', 'ligue1']:
                    outcomes = [('home', row['home_team_name'], home_win_prob),
                                ('draw', 'Draw', draw_prob),
                                ('away', row['away_team_name'], away_win_prob)]
                else:
                    outcomes = [('home', row['home_team_name'], home_win_prob),
                                ('away', row['away_team_name'], 1 - home_win_prob)]

                for side, team_name, elo_prob in outcomes:
                    if side in kalshi_odds:
                        market_odds = kalshi_odds[side]
                        if market_odds <= 1.0: continue # Invalid odds

                        market_prob = 1 / market_odds
                        if market_prob > 0.99: continue # Skip if effectively a 100% lock

                        edge = elo_prob - market_prob

                        # Volume-focused: Relax threshold if we have high edge OR meet confidence
                        is_confident = (elo_prob > threshold) or (edge > 0.10)

                        if is_confident and edge > min_edge:
                            confirmed = True
                            if use_sharp_confirmation and sharp_odds and side in sharp_odds:
                                sharp_prob = 1 / sharp_odds[side]
                                # confirmed = market_prob < sharp_prob (within 2% tolerance)
                                if market_prob >= sharp_prob - 0.02:
                                    confirmed = False

                            if confirmed:
                                opportunities.append({
                                    'sport': sport,
                                    'game_id': game_id,
                                    'home_team': row['home_team_name'],
                                    'away_team': row['away_team_name'],
                                    'bet_on': team_name,
                                    'side': side,
                                    'elo_prob': elo_prob,
                                    'market_prob': market_prob,
                                    'market_odds': market_odds,
                                    'bookmaker': 'Kalshi',
                                    'ticker': tickers_by_bm.get('Kalshi', {}).get(side),
                                    'edge': edge,
                                    'sharp_confirmed': sharp_odds is not None and confirmed,
                                    'confidence': 'HIGH' if elo_prob > (threshold + 0.1) else 'MEDIUM'
                                })

            return opportunities

        except Exception as e:
            print(f"Error finding opportunities: {e}")
            import traceback; traceback.print_exc()
            return []
