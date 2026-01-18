"""
Regenerate betting predictions from saved Kalshi markets
Useful for testing different models or thresholds without hitting the API again
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
import duckdb
import xgboost as xgb
import pandas as pd


def map_team_names(kalshi_name, conn):
    """Map Kalshi team name to database team name"""
    
    # Common mappings
    mapping = {
        'New York R': 'New York Rangers',
        'New York I': 'New York Islanders',
        'Tampa Bay': 'Tampa Bay Lightning',
        'Vegas': 'Vegas Golden Knights',
        'Utah': 'Utah Hockey Club',
        'Los Angeles': 'Los Angeles Kings',
        'St. Louis': 'St. Louis Blues',
    }
    
    if kalshi_name in mapping:
        return mapping[kalshi_name]
    
    # Try exact match
    result = conn.execute(
        "SELECT team_name FROM teams WHERE team_name = ?",
        (kalshi_name,)
    ).fetchone()
    
    if result:
        return result[0]
    
    # Try LIKE match
    result = conn.execute(
        "SELECT team_name FROM teams WHERE team_name LIKE ?",
        (f"%{kalshi_name}%",)
    ).fetchone()
    
    if result:
        return result[0]
    
    return None


def get_team_stats(team_name, conn):
    """Get team statistics from DuckDB"""
    
    query = """
    WITH recent_games AS (
        SELECT 
            g.game_id,
            g.game_date,
            CASE 
                WHEN g.home_team_id = t.team_id THEN 'home'
                ELSE 'away'
            END as venue,
            gs.*
        FROM games g
        JOIN teams t ON (g.home_team_id = t.team_id OR g.away_team_id = t.team_id)
        JOIN game_stats gs ON g.game_id = gs.game_id AND t.team_id = gs.team_id
        WHERE t.team_name = ?
          AND g.game_date >= (CURRENT_DATE - INTERVAL '30 days')
        ORDER BY g.game_date DESC
        LIMIT 10
    )
    SELECT * FROM recent_games
    """
    
    df = conn.execute(query, (team_name,)).df()
    return df


def predict_game(away_team, home_team, model, conn):
    """Generate prediction for a game"""
    
    # Get stats for both teams
    away_stats = get_team_stats(away_team, conn)
    home_stats = get_team_stats(home_team, conn)
    
    if len(away_stats) < 3 or len(home_stats) < 3:
        return None
    
    # Calculate rolling features (L3 and L10)
    def calc_features(df, prefix):
        features = {}
        
        for window, suffix in [(3, 'l3'), (min(10, len(df)), 'l10')]:
            recent = df.head(window)
            
            features[f'{prefix}_corsi_for_{suffix}'] = recent['corsi_for'].mean()
            features[f'{prefix}_corsi_against_{suffix}'] = recent['corsi_against'].mean()
            features[f'{prefix}_fenwick_for_{suffix}'] = recent['fenwick_for'].mean()
            features[f'{prefix}_fenwick_against_{suffix}'] = recent['fenwick_against'].mean()
            features[f'{prefix}_shots_{suffix}'] = recent['shots'].mean()
            features[f'{prefix}_goals_{suffix}'] = recent['goals'].mean()
            features[f'{prefix}_hd_chances_{suffix}'] = recent['high_danger_chances'].mean() if 'high_danger_chances' in recent.columns else 0
            features[f'{prefix}_save_pct_{suffix}'] = recent['save_percentage'].mean()
        
        return features
    
    away_features = calc_features(away_stats, 'away')
    home_features = calc_features(home_stats, 'home')
    
    # Combine features
    features = {**away_features, **home_features}
    
    # Create DataFrame for prediction
    feature_df = pd.DataFrame([features])
    
    # Predict
    prediction = model.predict_proba(feature_df)[0][1]  # Probability of home win
    
    return prediction


def regenerate_predictions(date_str, model_path=None, min_edge=0.05, min_ev=0.05):
    """Regenerate predictions from saved markets"""
    
    print("=" * 80)
    print(f"🔄 REGENERATING PREDICTIONS FOR {date_str}")
    print("=" * 80)
    
    # Load markets
    markets_file = Path(f"data/betting/{date_str}/markets.json")
    
    if not markets_file.exists():
        print(f"❌ Markets file not found: {markets_file}")
        return
    
    with open(markets_file, 'r') as f:
        markets_data = json.load(f)
    
    markets = markets_data.get('markets', [])
    print(f"\n✓ Loaded {len(markets)} markets")
    
    # Load model
    if model_path is None:
        model_path = "data/nhl_xgboost_hyperopt_model.json"
    
    print(f"✓ Loading model: {model_path}")
    model = xgb.XGBClassifier()
    model.load_model(model_path)
    
    # Connect to database
    conn = duckdb.connect("data/nhlstats.duckdb", read_only=True)
    print("✓ Connected to DuckDB")
    
    # Group markets by game
    games = {}
    for market in markets:
        subtitle = market.get('subtitle', '')
        if not subtitle or ' vs ' not in subtitle:
            continue
        
        parts = subtitle.split(' vs ')
        if len(parts) != 2:
            continue
        
        away_team = parts[0].strip()
        home_team = parts[1].strip()
        game_key = f"{away_team} @ {home_team}"
        
        if game_key not in games:
            games[game_key] = {
                'away_team': away_team,
                'home_team': home_team,
                'markets': []
            }
        
        games[game_key]['markets'].append(market)
    
    print(f"✓ Grouped into {len(games)} games")
    print(f"\nSettings: min_edge={min_edge:.1%}, min_ev=${min_ev:.2f}")
    print("\n" + "=" * 80)
    
    # Analyze each game
    opportunities = []
    
    for i, (game_str, game_data) in enumerate(games.items(), 1):
        away_team_kalshi = game_data['away_team']
        home_team_kalshi = game_data['home_team']
        
        print(f"\n{i}. {game_str}")
        
        # Map to DB names
        away_team = map_team_names(away_team_kalshi, conn)
        home_team = map_team_names(home_team_kalshi, conn)
        
        if not away_team or not home_team:
            print(f"   ⚠️ Could not map teams")
            continue
        
        print(f"   Mapped: {away_team} @ {home_team}")
        
        # Get prediction
        home_prob = predict_game(away_team, home_team, model, conn)
        
        if home_prob is None:
            print(f"   ⚠️ Insufficient data")
            continue
        
        away_prob = 1 - home_prob
        print(f"   Model: Home {home_prob:.1%} | Away {away_prob:.1%}")
        
        # Find market prices
        home_market = None
        away_market = None
        
        for market in game_data['markets']:
            ticker = market.get('ticker', '')
            if home_team_kalshi.upper() in ticker.upper():
                home_market = market
            elif away_team_kalshi.upper() in ticker.upper():
                away_market = market
        
        if not home_market or not away_market:
            print(f"   ⚠️ Missing markets")
            continue
        
        # Calculate prices
        def get_price(market):
            if market.get('last_price'):
                return market['last_price'] / 100.0
            yes_bid = market.get('yes_bid', 0)
            yes_ask = market.get('yes_ask', 0)
            if yes_bid and yes_ask:
                return (yes_bid + yes_ask) / 200.0
            return None
        
        home_price = get_price(home_market)
        away_price = get_price(away_market)
        
        if not home_price or not away_price:
            print(f"   ⚠️ Could not calculate prices")
            continue
        
        print(f"   Kalshi: Home ${home_price:.2f} | Away ${away_price:.2f}")
        
        # Calculate edges and EVs
        home_edge = home_prob - home_price
        away_edge = away_prob - away_price
        home_ev = (home_prob * 1.0) - home_price
        away_ev = (away_prob * 1.0) - away_price
        
        print(f"   Edge: Home {home_edge:+.1%} | Away {away_edge:+.1%}")
        print(f"   EV: Home ${home_ev:+.2f} | Away ${away_ev:+.2f}")
        
        # Check for opportunities
        if home_edge >= min_edge and home_ev >= min_ev:
            print(f"   ✅ BET HOME: Edge {home_edge:.1%}, EV ${home_ev:.2f}")
            opportunities.append({
                'game': game_str,
                'bet': 'HOME',
                'team': home_team_kalshi,
                'model_prob': home_prob,
                'market_price': home_price,
                'edge': home_edge,
                'ev': home_ev,
                'ticker': home_market.get('ticker'),
                'date': date_str
            })
        
        if away_edge >= min_edge and away_ev >= min_ev:
            print(f"   ✅ BET AWAY: Edge {away_edge:.1%}, EV ${away_ev:.2f}")
            opportunities.append({
                'game': game_str,
                'bet': 'AWAY',
                'team': away_team_kalshi,
                'model_prob': away_prob,
                'market_price': away_price,
                'edge': away_edge,
                'ev': away_ev,
                'ticker': away_market.get('ticker'),
                'date': date_str
            })
    
    conn.close()
    
    # Save recommendations
    output_file = Path(f"data/betting/{date_str}/recommendations.json")
    
    with open(output_file, 'w') as f:
        json.dump({
            'date': date_str,
            'timestamp': datetime.now().isoformat(),
            'model': model_path,
            'min_edge': min_edge,
            'min_ev': min_ev,
            'count': len(opportunities),
            'opportunities': opportunities,
            'total_ev': sum(opp['ev'] for opp in opportunities)
        }, f, indent=2)
    
    print("\n" + "=" * 80)
    print(f"✅ Generated {len(opportunities)} recommendations")
    print(f"   Total EV: ${sum(opp['ev'] for opp in opportunities):+.2f}")
    print(f"   Saved to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Regenerate betting predictions from saved Kalshi markets"
    )
    parser.add_argument(
        '--date',
        required=True,
        help='Date in YYYY-MM-DD format'
    )
    parser.add_argument(
        '--model',
        help='Path to XGBoost model (default: data/nhl_xgboost_hyperopt_model.json)'
    )
    parser.add_argument(
        '--min-edge',
        type=float,
        default=0.05,
        help='Minimum edge threshold (default: 0.05 = 5%%)'
    )
    parser.add_argument(
        '--min-ev',
        type=float,
        default=0.05,
        help='Minimum expected value in dollars (default: 0.05 = $0.05)'
    )
    
    args = parser.parse_args()
    
    regenerate_predictions(
        date_str=args.date,
        model_path=args.model,
        min_edge=args.min_edge,
        min_ev=args.min_ev
    )
