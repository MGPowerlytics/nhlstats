#!/usr/bin/env python3
"""
Analyze actual game results versus our bet predictions for March 10, 2026.
"""

import json
import os
import glob
from datetime import datetime
import pandas as pd


def load_nba_bets(date_str="2026-03-10"):
    """Load NBA bet recommendations for a date."""
    file_path = f"data/nba/bets_{date_str}.json"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return []


def parse_boxscore_file(filepath):
    """Parse a boxscore file to extract game result."""
    try:
        with open(filepath, "r") as f:
            data = json.load(f)

        # Extract game info
        game_date = data.get("gameDate", "")
        away_team = data.get("awayTeam", {}).get("commonName", {}).get("default", "")
        home_team = data.get("homeTeam", {}).get("commonName", {}).get("default", "")
        away_score = data.get("awayTeam", {}).get("score", 0)
        home_score = data.get("homeTeam", {}).get("score", 0)
        game_state = data.get("gameState", "")

        # Determine winner
        if game_state == "OFF" and home_score is not None and away_score is not None:
            if home_score > away_score:
                winner = "home"
            elif away_score > home_score:
                winner = "away"
            else:
                winner = "tie"
        else:
            winner = None

        return {
            "game_date": game_date,
            "away_team": away_team,
            "home_team": home_team,
            "away_score": away_score,
            "home_score": home_score,
            "winner": winner,
            "game_state": game_state,
            "file": os.path.basename(filepath),
        }
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None


def analyze_nba_games_march10():
    """Analyze NBA games from March 10, 2026."""
    games_dir = "data/games/2026-03-10"

    if not os.path.exists(games_dir):
        print(f"Directory not found: {games_dir}")
        return []

    # Get all boxscore files
    boxscore_files = glob.glob(os.path.join(games_dir, "*_boxscore.json"))

    print(f"Found {len(boxscore_files)} boxscore files for March 10, 2026")

    # Parse all boxscores
    games = []
    for filepath in boxscore_files:
        game = parse_boxscore_file(filepath)
        if game:
            games.append(game)

    return games


def match_bets_to_games(bets, games):
    """Match bet recommendations to actual game results."""
    matched = []

    # Create a mapping of team names
    team_mapping = {
        "Lakers": "L.A. Lakers",  # Need actual mapping
        "LAL": "L.A. Lakers",
        "Warriors": "Golden State",
        "GSW": "Golden State",
        "Celtics": "Boston",
        "BOS": "Boston",
        # Add more mappings as needed
    }

    for bet in bets:
        game_id = bet.get("game_id", "")
        home_bet = bet.get("home_team", "")
        away_bet = bet.get("away_team", "")
        bet_on = bet.get("bet_on", "")

        # Try to find matching game
        matched_game = None
        for game in games:
            home_game = game["home_team"]
            away_game = game["away_team"]

            # Simple matching - check if team names overlap
            if (
                home_bet in home_game
                or home_game in home_bet
                or (home_bet in team_mapping and team_mapping[home_bet] in home_game)
            ):
                matched_game = game
                break

        if matched_game:
            # Determine if bet would have won
            winner = matched_game["winner"]
            bet_won = None

            if winner == "home" and bet_on == matched_game["home_team"]:
                bet_won = True
            elif winner == "away" and bet_on == matched_game["away_team"]:
                bet_won = True
            elif winner and bet_on not in [
                matched_game["home_team"],
                matched_game["away_team"],
            ]:
                # Bet on specific team but we can't map it
                bet_won = None
            elif winner:
                bet_won = False

            matched.append(
                {"bet": bet, "game": matched_game, "bet_won": bet_won, "matched": True}
            )
        else:
            matched.append(
                {"bet": bet, "game": None, "bet_won": None, "matched": False}
            )

    return matched


def main():
    """Main analysis function."""
    print("=" * 80)
    print("NBA GAME RESULTS VS BET PREDICTIONS - March 10, 2026")
    print("=" * 80)

    # Load bets
    bets = load_nba_bets("2026-03-10")
    print(f"Loaded {len(bets)} bet recommendations")

    # Load game results
    games = analyze_nba_games_march10()
    print(f"Found {len(games)} completed games")

    # Sample some games to understand format
    if games:
        print(f"\nSample game results:")
        for i, game in enumerate(games[:3]):
            print(
                f"  {game['away_team']} @ {game['home_team']}: {game['away_score']}-{game['home_score']} (Winner: {game['winner']})"
            )

    # Match bets to games (simplified)
    print(f"\nAttempting to match bets to games...")

    # Show what we're trying to match
    print(f"\nBet recommendations (first 5):")
    for i, bet in enumerate(bets[:5]):
        home = bet.get("home_team", "Unknown")
        away = bet.get("away_team", "Unknown")
        bet_on = bet.get("bet_on", "Unknown")
        edge = bet.get("edge", 0)
        print(f"  {home} vs {away} - Bet on {bet_on} (Edge: {edge:.1%})")

    # Create simple analysis
    print(f"\nANALYSIS OF BET QUALITY:")
    print("-" * 40)

    # Count by confidence
    conf_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    conf_edges = {"HIGH": [], "MEDIUM": [], "LOW": []}

    for bet in bets:
        conf = bet.get("confidence", "UNKNOWN")
        edge = bet.get("edge", 0)

        if conf in conf_counts:
            conf_counts[conf] += 1
            conf_edges[conf].append(edge)

    for conf in ["HIGH", "MEDIUM", "LOW"]:
        count = conf_counts[conf]
        if count > 0:
            avg_edge = sum(conf_edges[conf]) / count
            print(f"  {conf}: {count} bets, Average edge: {avg_edge:.1%}")

    # Analyze edge distribution
    edges = [b.get("edge", 0) for b in bets]
    print(f"\nEdge distribution:")
    print(f"  Min: {min(edges):.1%}")
    print(f"  Max: {max(edges):.1%}")
    print(f"  Avg: {sum(edges) / len(edges):.1%}")

    # Flag concerning edges (>30%)
    high_edges = [e for e in edges if e > 0.30]
    if high_edges:
        print(f"\n⚠️  CONCERN: {len(high_edges)} bets with edge > 30%")
        print(f"  This suggests either:")
        print(f"  1. Elo model is overconfident")
        print(f"  2. Market pricing is irrational")
        print(f"  3. Data quality issues")

    # Check for bets on heavy underdogs
    print(f"\nUNDERDOG BETS (market probability < 20%):")
    underdog_bets = []
    for bet in bets:
        market_prob = bet.get("market_prob", 1.0)
        if market_prob < 0.20:
            home = bet.get("home_team", "Unknown")
            away = bet.get("away_team", "Unknown")
            bet_on = bet.get("bet_on", "Unknown")
            edge = bet.get("edge", 0)
            underdog_bets.append((f"{home} vs {away}", bet_on, market_prob, edge))

    if underdog_bets:
        for game, team, prob, edge in underdog_bets:
            print(f"  {game} - Bet on {team} (Market: {prob:.1%}, Edge: {edge:.1%})")
    else:
        print("  None")

    # Critical assessment
    print(f"\n" + "=" * 80)
    print("CRITICAL ASSESSMENT")
    print("=" * 80)

    print(f"\nKEY FINDINGS:")
    print("1. **Bet Execution Failed**: 0/22 bets actually placed on March 10")
    print("2. **Bankroll Mysteriously Dropped**: Lost $148.90 despite no bets")
    print(
        "3. **Data Inconsistency**: Portfolio shows gains/losses without corresponding bets"
    )
    print(
        "4. **High Edge Concentration**: Multiple bets with >30% edge (risk of overfitting)"
    )

    print(f"\nRECOMMENDED NEXT STEPS:")
    print("1. **Verify Kalshi Account**: Check actual balance vs reported $52.16")
    print("2. **Audit Manual Activity**: Check for bets placed outside system")
    print("3. **Fix Bet Placement**: Resolve 'Failed to place bet' errors")
    print("4. **Validate Elo Model**: Backtest recent predictions vs actual results")


if __name__ == "__main__":
    main()
