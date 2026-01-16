#!/usr/bin/env python3
"""
Complete NHL Betting Workflow:
1. Fetch current Kalshi markets
2. Get team stats from DuckDB
3. Generate model predictions
4. Compare with Kalshi odds
5. Identify value bets
"""

import json
import duckdb
import pandas as pd
import xgboost as xgb
from pathlib import Path
from datetime import datetime
from kalshi_python import Configuration, ApiClient, MarketsApi


class NHLBettingWorkflow:
    def __init__(self, db_path="data/nhlstats.duckdb", model_path="data/nhl_xgboost_hyperopt_model.json"):
        self.db_path = Path(db_path)
        self.model_path = Path(model_path)
        self.conn = None
        self.model = None
        self.kalshi_client = None
        
    def connect_db(self):
        """Connect to DuckDB"""
        self.conn = duckdb.connect(str(self.db_path), read_only=True)
        print("✓ Connected to DuckDB")
    
    def load_model(self):
        """Load trained XGBoost model"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        self.model = xgb.Booster()
        self.model.load_model(str(self.model_path))
        print("✓ Loaded XGBoost model")
    
    def setup_kalshi(self, api_key_id, private_key):
        """Setup Kalshi API client"""
        config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
        config.api_key['api_key_id'] = api_key_id
        config.api_key['private_key'] = private_key
        
        api_client = ApiClient(configuration=config)
        self.kalshi_client = MarketsApi(api_client)
        print("✓ Connected to Kalshi API")
    
    def fetch_kalshi_markets(self):
        """Fetch current NHL markets from Kalshi"""
        response = self.kalshi_client.get_markets(
            series_ticker='KXNHLGAME',
            limit=200,
            status='open'
        )
        
        markets = response.to_dict().get('markets', [])
        
        # Parse markets into games
        games = {}
        for market in markets:
            title = market.get('title', '')
            ticker = market.get('ticker', '')
            
            # Parse "Team A at Team B Winner?" 
            if 'Winner?' in title and ' at ' in title:
                parts = title.replace(' Winner?', '').split(' at ')
                if len(parts) == 2:
                    away_team = parts[0].strip()
                    home_team = parts[1].strip()
                    
                    # Extract team abbreviation from ticker
                    team_abbrev = ticker.split('-')[-1]
                    
                    game_key = f"{away_team} @ {home_team}"
                    
                    if game_key not in games:
                        games[game_key] = {
                            'away_team': away_team,
                            'home_team': home_team,
                            'date': ticker.split('-')[1][:7],  # Extract date from ticker
                        }
                    
                    # Add market odds
                    yes_bid = market.get('yes_bid', 0) / 100
                    yes_ask = market.get('yes_ask', 0) / 100
                    
                    if team_abbrev in ticker:
                        if home_team.upper().startswith(team_abbrev[:3]) or home_team.split()[-1].upper().startswith(team_abbrev[:3]):
                            games[game_key]['home_yes_bid'] = yes_bid
                            games[game_key]['home_yes_ask'] = yes_ask
                            games[game_key]['home_ticker'] = ticker
                        else:
                            games[game_key]['away_yes_bid'] = yes_bid
                            games[game_key]['away_yes_ask'] = yes_ask
                            games[game_key]['away_ticker'] = ticker
        
        print(f"✓ Found {len(games)} NHL games on Kalshi")
        return games
    
    def map_team_names(self, kalshi_name):
        """Map Kalshi team names to database team names"""
        # Common mappings
        mapping = {
            'New York R': 'New York Rangers',
            'New York I': 'New York Islanders',
            'Los Angeles': 'Los Angeles Kings',
            'St. Louis': 'St. Louis Blues',
            'Tampa Bay': 'Tampa Bay Lightning',
            'San Jose': 'San Jose Sharks',
            'Vegas': 'Vegas Golden Knights',
            'Utah': 'Utah Hockey Club',
        }
        
        if kalshi_name in mapping:
            return mapping[kalshi_name]
        
        # Try to find in database
        result = self.conn.execute("""
            SELECT DISTINCT team_name 
            FROM teams 
            WHERE team_name LIKE ? OR team_name LIKE ?
        """, (f"%{kalshi_name}%", f"{kalshi_name}%")).fetchone()
        
        if result:
            return result[0]
        
        return kalshi_name
    
    def get_team_stats(self, team_name, as_of_date=None):
        """Get rolling stats for a team from DuckDB"""
        
        # If no date specified, use latest available
        if as_of_date is None:
            date_query = "ORDER BY game_date DESC LIMIT 1"
        else:
            date_query = f"WHERE game_date <= '{as_of_date}' ORDER BY game_date DESC LIMIT 1"
        
        query = f"""
        WITH team_games AS (
            -- Flatten to one row per team per game
            SELECT game_id, game_date, home_team_id as team_id,
                   home_corsi_for as corsi_for,
                   home_corsi_against as corsi_against,
                   home_fenwick_for as fenwick_for,
                   home_fenwick_against as fenwick_against,
                   home_shots_for as shots_for,
                   home_goals_for as goals_for,
                   home_hd_chances_for as hd_chances_for,
                   home_save_pct as save_pct,
                   home_shots_against as shots_against
            FROM game_team_advanced_stats
            
            UNION ALL
            
            SELECT game_id, game_date, away_team_id as team_id,
                   away_corsi_for as corsi_for,
                   away_corsi_against as corsi_against,
                   away_fenwick_for as fenwick_for,
                   away_fenwick_against as fenwick_against,
                   away_shots_for as shots_for,
                   away_goals_for as goals_for,
                   away_hd_chances_for as hd_chances_for,
                   away_save_pct as save_pct,
                   away_shots_against as shots_against
            FROM game_team_advanced_stats
        ),
        rolling_stats AS (
            SELECT 
                game_id,
                game_date,
                team_id,
                
                -- Last 3 games
                AVG(corsi_for) OVER w3 as corsi_for_l3,
                AVG(corsi_against) OVER w3 as corsi_against_l3,
                AVG(fenwick_for) OVER w3 as fenwick_for_l3,
                AVG(fenwick_against) OVER w3 as fenwick_against_l3,
                AVG(shots_for) OVER w3 as shots_l3,
                AVG(goals_for) OVER w3 as goals_l3,
                AVG(hd_chances_for) OVER w3 as hd_chances_l3,
                AVG(save_pct) OVER w3 as save_pct_l3,
                
                -- Last 10 games
                AVG(corsi_for) OVER w10 as corsi_for_l10,
                AVG(corsi_against) OVER w10 as corsi_against_l10,
                AVG(fenwick_for) OVER w10 as fenwick_for_l10,
                AVG(fenwick_against) OVER w10 as fenwick_against_l10,
                AVG(shots_for) OVER w10 as shots_l10,
                AVG(goals_for) OVER w10 as goals_l10,
                AVG(hd_chances_for) OVER w10 as hd_chances_l10,
                AVG(save_pct) OVER w10 as save_pct_l10
                
            FROM team_games
            WINDOW 
                w3 AS (PARTITION BY team_id ORDER BY game_date, game_id ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING),
                w10 AS (PARTITION BY team_id ORDER BY game_date, game_id ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING)
        )
        SELECT 
            rs.*,
            t.team_name
        FROM rolling_stats rs
        JOIN teams t ON rs.team_id = t.team_id
        WHERE t.team_name = ?
        {date_query}
        """
        
        result = self.conn.execute(query, (team_name,)).fetchone()
        
        if result:
            cols = [desc[0] for desc in self.conn.description]
            return dict(zip(cols, result))
        
        return None
    
    def build_prediction_features(self, home_team, away_team):
        """Build feature vector for prediction"""
        
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        
        if not home_stats or not away_stats:
            return None, None
        
        # Build feature vector matching training data
        features = {
            'home_corsi_for_l3': home_stats['corsi_for_l3'],
            'home_corsi_against_l3': home_stats['corsi_against_l3'],
            'home_fenwick_for_l3': home_stats['fenwick_for_l3'],
            'home_fenwick_against_l3': home_stats['fenwick_against_l3'],
            'home_shots_l3': home_stats['shots_l3'],
            'home_goals_l3': home_stats['goals_l3'],
            'home_hd_chances_l3': home_stats['hd_chances_l3'],
            'home_save_pct_l3': home_stats['save_pct_l3'],
            'home_corsi_for_l10': home_stats['corsi_for_l10'],
            'home_corsi_against_l10': home_stats['corsi_against_l10'],
            'home_fenwick_for_l10': home_stats['fenwick_for_l10'],
            'home_fenwick_against_l10': home_stats['fenwick_against_l10'],
            'home_shots_l10': home_stats['shots_l10'],
            'home_goals_l10': home_stats['goals_l10'],
            'home_hd_chances_l10': home_stats['hd_chances_l10'],
            'home_save_pct_l10': home_stats['save_pct_l10'],
            
            'away_corsi_for_l3': away_stats['corsi_for_l3'],
            'away_corsi_against_l3': away_stats['corsi_against_l3'],
            'away_fenwick_for_l3': away_stats['fenwick_for_l3'],
            'away_fenwick_against_l3': away_stats['fenwick_against_l3'],
            'away_shots_l3': away_stats['shots_l3'],
            'away_goals_l3': away_stats['goals_l3'],
            'away_hd_chances_l3': away_stats['hd_chances_l3'],
            'away_save_pct_l3': away_stats['save_pct_l3'],
            'away_corsi_for_l10': away_stats['corsi_for_l10'],
            'away_corsi_against_l10': away_stats['corsi_against_l10'],
            'away_fenwick_for_l10': away_stats['fenwick_for_l10'],
            'away_fenwick_against_l10': away_stats['fenwick_against_l10'],
            'away_shots_l10': away_stats['shots_l10'],
            'away_goals_l10': away_stats['goals_l10'],
            'away_hd_chances_l10': away_stats['hd_chances_l10'],
            'away_save_pct_l10': away_stats['save_pct_l10'],
        }
        
        return features, (home_stats, away_stats)
    
    def predict_game(self, home_team, away_team):
        """Generate prediction for a game"""
        
        features, stats = self.build_prediction_features(home_team, away_team)
        
        if features is None:
            return None
        
        # Convert to DataFrame for XGBoost
        df = pd.DataFrame([features])
        dmatrix = xgb.DMatrix(df)
        
        # Predict probability of home team winning
        prob_home_win = self.model.predict(dmatrix)[0]
        
        return {
            'prob_home_win': float(prob_home_win),
            'prob_away_win': float(1 - prob_home_win),
            'features': features,
            'stats': stats
        }
    
    def calculate_expected_value(self, model_prob, market_price):
        """
        Calculate expected value of a bet
        
        EV = (probability of winning * payout) - cost
        
        For a binary market at price P:
        - Cost = P (what you pay)
        - Payout = $1 (if win)
        - EV = (model_prob * 1) - P
        """
        return (model_prob * 1.0) - market_price
    
    def analyze_opportunities(self, min_edge=0.05, min_ev=0.10):
        """
        Find betting opportunities
        
        Args:
            min_edge: Minimum edge (model prob - market prob) to consider
            min_ev: Minimum expected value to recommend
        """
        
        print("\n" + "=" * 80)
        print("🎲 NHL BETTING ANALYSIS")
        print("=" * 80)
        
        # Fetch Kalshi markets
        games = self.fetch_kalshi_markets()
        
        if not games:
            print("⚠️ No games found on Kalshi")
            return []
        
        opportunities = []
        
        print(f"\n📊 Analyzing {len(games)} games...\n")
        
        for i, (game_key, game_info) in enumerate(games.items(), 1):
            print(f"{i}. {game_key}")
            
            # Map team names
            home_team = self.map_team_names(game_info['home_team'])
            away_team = self.map_team_names(game_info['away_team'])
            
            print(f"   Mapped: {away_team} @ {home_team}")
            
            # Generate prediction
            prediction = self.predict_game(home_team, away_team)
            
            if prediction is None:
                print("   ⚠️ Insufficient data for prediction\n")
                continue
            
            model_home_prob = prediction['prob_home_win']
            model_away_prob = prediction['prob_away_win']
            
            print(f"   Model: Home {model_home_prob:.1%} | Away {model_away_prob:.1%}")
            
            # Get Kalshi prices (use bid for buying)
            home_bid = game_info.get('home_yes_bid', 0)
            away_bid = game_info.get('away_yes_bid', 0)
            
            if home_bid == 0 or away_bid == 0:
                print("   ⚠️ Missing market prices\n")
                continue
            
            print(f"   Kalshi: Home ${home_bid:.2f} | Away ${away_bid:.2f}")
            
            # Calculate edges and EV
            home_edge = model_home_prob - home_bid
            away_edge = model_away_prob - away_bid
            
            home_ev = self.calculate_expected_value(model_home_prob, home_bid)
            away_ev = self.calculate_expected_value(model_away_prob, away_bid)
            
            print(f"   Edge: Home {home_edge:+.1%} | Away {away_edge:+.1%}")
            print(f"   EV: Home ${home_ev:+.2f} | Away ${away_ev:+.2f}")
            
            # Check for opportunities
            home_opportunity = home_edge >= min_edge and home_ev >= min_ev
            away_opportunity = away_edge >= min_edge and away_ev >= min_ev
            
            if home_opportunity:
                opportunities.append({
                    'game': game_key,
                    'bet': 'HOME',
                    'team': home_team,
                    'model_prob': model_home_prob,
                    'market_price': home_bid,
                    'edge': home_edge,
                    'ev': home_ev,
                    'ticker': game_info.get('home_ticker', 'N/A'),
                    'date': game_info.get('date', 'N/A')
                })
                print(f"   ✅ BET HOME: Edge {home_edge:.1%}, EV ${home_ev:.2f}")
            
            if away_opportunity:
                opportunities.append({
                    'game': game_key,
                    'bet': 'AWAY',
                    'team': away_team,
                    'model_prob': model_away_prob,
                    'market_price': away_bid,
                    'edge': away_edge,
                    'ev': away_ev,
                    'ticker': game_info.get('away_ticker', 'N/A'),
                    'date': game_info.get('date', 'N/A')
                })
                print(f"   ✅ BET AWAY: Edge {away_edge:.1%}, EV ${away_ev:.2f}")
            
            print()
        
        return opportunities
    
    def print_recommendations(self, opportunities):
        """Print betting recommendations"""
        
        if not opportunities:
            print("\n⚠️ No betting opportunities found with current criteria")
            print("   Try lowering min_edge or min_ev thresholds")
            return
        
        print("\n" + "=" * 80)
        print(f"💰 BETTING RECOMMENDATIONS ({len(opportunities)} opportunities)")
        print("=" * 80)
        
        # Sort by EV
        opportunities.sort(key=lambda x: x['ev'], reverse=True)
        
        for i, opp in enumerate(opportunities, 1):
            print(f"\n{i}. {opp['game']}")
            print(f"   BET: {opp['team']} ({opp['bet']})")
            print(f"   Model Probability: {opp['model_prob']:.1%}")
            print(f"   Market Price: ${opp['market_price']:.2f}")
            print(f"   Edge: {opp['edge']:+.1%}")
            print(f"   Expected Value: ${opp['ev']:+.2f}")
            print(f"   Ticker: {opp['ticker']}")
            print(f"   Date: {opp['date']}")
        
        # Calculate total EV
        total_ev = sum(opp['ev'] for opp in opportunities)
        print(f"\n📈 Total Expected Value: ${total_ev:+.2f}")
        print(f"   (if betting $1 on each opportunity)")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def load_kalshi_credentials():
    """Load Kalshi API credentials from kalshkey file"""
    key_file = Path("kalshkey")
    
    if not key_file.exists():
        raise FileNotFoundError("kalshkey file not found")
    
    content = key_file.read_text()
    
    # Extract API key ID
    api_key_id = None
    for line in content.split('\n'):
        if 'API key id:' in line:
            api_key_id = line.split(':', 1)[1].strip()
            break
    
    # Extract private key
    private_key_lines = []
    in_key = False
    for line in content.split('\n'):
        if '-----BEGIN RSA PRIVATE KEY-----' in line:
            in_key = True
        if in_key:
            private_key_lines.append(line)
        if '-----END RSA PRIVATE KEY-----' in line:
            break
    
    private_key = '\n'.join(private_key_lines)
    
    return api_key_id, private_key


def main():
    """Run the complete betting workflow"""
    
    # Load credentials
    api_key_id, private_key = load_kalshi_credentials()
    
    # Create workflow
    workflow = NHLBettingWorkflow()
    
    try:
        # Setup
        workflow.connect_db()
        workflow.load_model()
        workflow.setup_kalshi(api_key_id, private_key)
        
        # Analyze opportunities
        # min_edge: model prob - market prob (5% = model thinks 60% when market is 55%)
        # min_ev: expected value per $1 bet (10¢ = $0.10 profit per $1)
        opportunities = workflow.analyze_opportunities(
            min_edge=0.05,  # 5% edge
            min_ev=0.05     # 5¢ expected value (lowered threshold)
        )
        
        # Print recommendations
        workflow.print_recommendations(opportunities)
        
        # Save to file
        output_file = Path("data/betting_recommendations.json")
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'opportunities': opportunities
            }, f, indent=2)
        print(f"\n💾 Saved recommendations to {output_file}")
        
    finally:
        workflow.close()


if __name__ == "__main__":
    main()
