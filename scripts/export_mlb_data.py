#!/usr/bin/env python3
"""
Extract MLB Data to CSV for Backtesting - FIXED v3

This script connects to the PostgreSQL database and exports MLB game data
to CSV files that can be used for backtesting in any environment.

This version correctly handles the schema where bet_recommendations
doesn't have a game_id or generated_at column.
"""

import sys
from datetime import datetime
import pandas as pd
from pathlib import Path
from db_manager import default_db

def export_mlb_data(start_date: str, end_date: str, output_dir: str = "mlb_backtest_data"):
    """Export MLB data to CSV files."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    params = {
        "start_date": start_date,
        "end_date": end_date
    }

    try:
        # 1. Export game results
        print("📥 Exporting game results...")
        game_query = """
            SELECT
                game_id,
                game_date,
                sport,
                home_team_name as home_team,
                away_team_name as away_team,
                home_score,
                away_score,
                status,
                commence_time,
                venue
            FROM unified_games
            WHERE sport = 'MLB'
                AND game_date >= :start_date
                AND game_date <= :end_date
                AND status IN ('Final', 'Completed')
            ORDER BY game_date
        """
        print(f"Executing query: {game_query}")
        print(f"Params: {params}")
        games_df = default_db.fetch_df(game_query, params)
        print(f"   ✓ Fetched {len(games_df)} games")
        games_df.to_csv(output_path / "mlb_games.csv", index=False)
        print(f"✓ Exported {len(games_df)} games")

        # 2. Export Elo probabilities with proper join
        print("\n📥 Exporting Elo probabilities...")
        elo_query = """
            SELECT
                r.*,
                g.game_id
            FROM bet_recommendations r
            JOIN unified_games g
                ON r.home_team = g.home_team_name
                AND r.away_team = g.away_team_name
                AND r.recommendation_date = g.game_date
            WHERE g.sport = 'MLB'
                AND g.game_date >= :start_date
                AND g.game_date <= :end_date
                AND g.status IN ('Final', 'Completed')
            ORDER BY r.created_at
        """
        print(f"Executing query: {elo_query}")
        print(f"Params: {params}")
        elo_df = default_db.fetch_df(elo_query, params)
        print(f"   ✓ Fetched {len(elo_df)} Elo probabilities")
        elo_df.to_csv(output_path / "mlb_elo_probabilities.csv", index=False)
        print(f"✓ Exported {len(elo_df)} Elo probabilities")

        # 3. Export market odds (Kalshi, BetMGM, etc.)
        print("\n📥 Exporting market odds...")
        odds_query = """
            SELECT
                o.*,
                g.game_id
            FROM game_odds o
            JOIN unified_games g
                ON o.game_id = g.game_id
            WHERE g.sport = 'MLB'
                AND g.game_date >= :start_date
                AND g.game_date <= :end_date
                AND g.status IN ('Final', 'Completed')
            ORDER BY g.game_date, o.bookmaker, o.market_name
        """
        print(f"Executing query: {odds_query}")
        print(f"Params: {params}")
        odds_df = default_db.fetch_df(odds_query, params)
        print(f"   ✓ Fetched {len(odds_df)} odds records")
        odds_df.to_csv(output_path / "mlb_market_odds.csv", index=False)
        print(f"✓ Exported {len(odds_df)} odds records")

        # 4. Export betting recommendations
        print("\n📥 Exporting betting recommendations...")
        bet_query = """
            SELECT
                r.*,
                g.home_team_name,
                g.away_team_name,
                g.home_score,
                g.away_score
            FROM bet_recommendations r
            JOIN unified_games g
                ON r.home_team = g.home_team_name
                AND r.away_team = g.away_team_name
                AND r.recommendation_date = g.game_date
            WHERE g.sport = 'MLB'
                AND g.game_date >= :start_date
                AND g.game_date <= :end_date
                AND g.status IN ('Final', 'Completed')
            ORDER BY r.created_at
        """
        print(f"Executing query: {bet_query}")
        print(f"Params: {params}")
        bet_df = default_db.fetch_df(bet_query, params)
        print(f"   ✓ Fetched {len(bet_df)} betting recommendations")
        bet_df.to_csv(output_path / "mlb_betting_recommendations.csv", index=False)
        print(f"✓ Exported {len(bet_df)} betting recommendations")

        print("\n✅ All data exported successfully!")
        print(f"📁 Data saved to: {output_path.absolute()}")

    except Exception as e:
        print(f"\n✗ Error during export: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export MLB data to CSV for backtesting")
    parser.add_argument("--start_date", default="2021-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end_date", default="2024-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--output_dir", default="mlb_backtest_data", help="Output directory")

    args = parser.parse_args()

    try:
        export_mlb_data(args.start_date, args.end_date, args.output_dir)
        sys.exit(0)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
