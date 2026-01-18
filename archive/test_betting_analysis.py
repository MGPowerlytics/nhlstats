#!/usr/bin/env python3
"""
Test betting opportunity detection with real data
"""

import sys
import pandas as pd
from kalshi_markets import fetch_nba_markets
from nba_elo_rating import NBAEloRating, load_nba_games_from_json

# Team name mapping (Kalshi full names to NBA abbreviations)
TEAM_MAP = {
    'Miami': 'Heat', 'Golden State': 'Warriors', 'Boston': 'Celtics', 
    'Detroit': 'Pistons', 'Los Angeles L': 'Lakers', 'Brooklyn': 'Nets',
    'Indiana': 'Pacers', 'Philadelphia': '76ers', 'Toronto': 'Raptors',
    'Charlotte': 'Hornets', 'Atlanta': 'Hawks', 'Chicago': 'Bulls',
    'New York': 'Knicks', 'Cleveland': 'Cavaliers', 'Milwaukee': 'Bucks',
    'Washington': 'Wizards', 'Orlando': 'Magic', 'Memphis': 'Grizzlies',
    'Minnesota': 'Timberwolves', 'Denver': 'Nuggets', 'Phoenix': 'Suns',
    'Los Angeles C': 'Clippers', 'Sacramento': 'Kings', 'Utah': 'Jazz',
    'Portland': 'Trail Blazers', 'Oklahoma City': 'Thunder',
    'Dallas': 'Mavericks', 'New Orleans': 'Pelicans', 'Houston': 'Rockets',
    'San Antonio': 'Spurs'
}

print("=" * 80)
print("🎲 NBA BETTING OPPORTUNITY ANALYSIS")
print("=" * 80)

# Load historical games and build Elo ratings
print("\n📊 Loading NBA games and building Elo ratings...")
games_df = load_nba_games_from_json()
print(f"Loaded {len(games_df)} games")

# Initialize and train Elo
elo = NBAEloRating(k_factor=20, home_advantage=100)
for _, game in games_df.iterrows():
    elo.update(game['home_team'], game['away_team'], game['home_win'])

print(f"✅ Elo ratings for {len(elo.ratings)} teams")

# Show top ratings
ratings_df = pd.DataFrame([(t, r) for t, r in elo.ratings.items()], 
                         columns=['team', 'rating']).sort_values('rating', ascending=False)
print(f"\n🏆 Top 10 Teams:")
for i, row in ratings_df.head(10).iterrows():
    print(f"  {row['team']:20s} {row['rating']:.0f}")

# Fetch markets
print(f"\n💰 Fetching Kalshi markets...")
markets = fetch_nba_markets()
print(f"Found {len(markets)} markets")

# Parse and analyze
print(f"\n🔍 Analyzing betting opportunities...\n")

analyzed = []
for market in markets:
    title = market.get('title', '')
    if ' at ' not in title or 'Winner?' not in title:
        continue
    
    # Parse teams
    parts = title.replace(' Winner?', '').split(' at ')
    if len(parts) != 2:
        continue
    
    away_full = parts[0].strip()
    home_full = parts[1].strip()
    
    # Map to team names
    away_team = TEAM_MAP.get(away_full)
    home_team = TEAM_MAP.get(home_full)
    
    if not away_team or not home_team:
        print(f"⚠️  Could not map: {away_full} / {home_full}")
        continue
    
    # Get market odds
    ticker = market.get('ticker', '')
    yes_ask = market.get('yes_ask', 0) / 100
    
    # Determine which team this market is for
    # Kalshi creates two markets: one for each team
    home_abbr = home_team[:3].upper() if len(home_team) > 3 else home_team.upper()
    away_abbr = away_team[:3].upper() if len(away_team) > 3 else away_team.upper()
    
    if ticker.endswith(f'-{home_abbr}') or ticker.endswith(f'-{home_team[:3].upper()}'):
        market_home_prob = yes_ask
    elif ticker.endswith(f'-{away_abbr}') or ticker.endswith(f'-{away_team[:3].upper()}'):
        market_home_prob = 1 - yes_ask
    else:
        # Try to infer from title if ticker doesn't match
        continue
    
    # Skip if we already analyzed this game
    game_key = f"{away_team} @ {home_team}"
    if any(a['game'] == game_key for a in analyzed):
        continue
    
    # Get Elo prediction
    elo_home_prob = elo.predict(home_team, away_team)
    
    edge = elo_home_prob - market_home_prob
    edge_pct = (edge / market_home_prob * 100) if market_home_prob > 0 else 0
    
    analyzed.append({
        'game': game_key,
        'home_team': home_team,
        'away_team': away_team,
        'elo_prob': elo_home_prob,
        'market_prob': market_home_prob,
        'edge': edge,
        'edge_pct': edge_pct,
        'elo_home_rating': elo.ratings.get(home_team, 1500),
        'elo_away_rating': elo.ratings.get(away_team, 1500)
    })

# Sort by absolute edge
analyzed.sort(key=lambda x: abs(x['edge']), reverse=True)

print(f"\n📈 ALL GAMES (sorted by edge):\n")
for i, bet in enumerate(analyzed, 1):
    edge_str = f"+{bet['edge']*100:.1f}%" if bet['edge'] > 0 else f"{bet['edge']*100:.1f}%"
    meets_criteria = bet['elo_prob'] > 0.64 and bet['edge'] > 0.05
    indicator = "✅" if meets_criteria else "  "
    
    print(f"{indicator} {i:2}. {bet['game']:40s}")
    print(f"     Elo: {bet['elo_prob']*100:5.1f}% (Home {bet['elo_home_rating']:.0f} vs Away {bet['elo_away_rating']:.0f})")
    print(f"     Market: {bet['market_prob']*100:5.1f}% | Edge: {edge_str:7s}")
    print()

# Count opportunities
high_confidence = [b for b in analyzed if b['elo_prob'] > 0.64 and b['edge'] > 0.05]
medium_confidence = [b for b in analyzed if b['elo_prob'] > 0.55 and b['edge'] > 0.03]

print("\n" + "=" * 80)
print(f"📊 SUMMARY")
print("=" * 80)
print(f"Total games analyzed: {len(analyzed)}")
print(f"HIGH confidence bets (Elo>64%, Edge>5%): {len(high_confidence)} ({len(high_confidence)/len(analyzed)*100:.0f}%)")
print(f"MEDIUM confidence bets (Elo>55%, Edge>3%): {len(medium_confidence)} ({len(medium_confidence)/len(analyzed)*100:.0f}%)")
print()

if high_confidence:
    print("🎯 HIGH CONFIDENCE BETTING OPPORTUNITIES:")
    for bet in high_confidence:
        edge_str = f"+{bet['edge']*100:.1f}%" if bet['edge'] > 0 else f"{bet['edge']*100:.1f}%"
        print(f"  • {bet['game']}: Elo {bet['elo_prob']*100:.0f}% vs Market {bet['market_prob']*100:.0f}% (Edge: {edge_str})")

print("\n" + "=" * 80)
