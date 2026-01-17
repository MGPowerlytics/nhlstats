#!/usr/bin/env python3
"""
Calculate TrueSkill ratings for NHL players

This script processes historical game data and calculates TrueSkill ratings
for all players based on game outcomes.

Usage:
    python calculate_trueskill_ratings.py [--season SEASON] [--all-seasons]
    
Examples:
    python calculate_trueskill_ratings.py --season 2023
    python calculate_trueskill_ratings.py --all-seasons
"""

import argparse
import sys
from pathlib import Path
from nhl_trueskill import NHLTrueSkillRatings


def calculate_ratings(season: int = None, all_seasons: bool = False):
    """
    Calculate TrueSkill ratings for specified season(s)
    
    Args:
        season: Specific season to process (e.g., 2023)
        all_seasons: Process all available seasons
    """
    
    with NHLTrueSkillRatings() as ratings:
        
        if all_seasons:
            # Get all available seasons from database
            seasons = ratings.conn.execute("""
                SELECT DISTINCT season 
                FROM games 
                WHERE game_state = 'OFF'
                ORDER BY season
            """).fetchall()
            
            print(f"Found {len(seasons)} seasons in database")
            
            for (season_year,) in seasons:
                print(f"\n{'='*80}")
                print(f"Processing Season {season_year}")
                print('='*80)
                
                # Process regular season
                stats = ratings.process_season(season=season_year, game_type=2)
                
                # Process playoffs if available
                playoff_count = ratings.conn.execute("""
                    SELECT COUNT(*) FROM games 
                    WHERE season = ? AND game_type = 3 AND game_state = 'OFF'
                """, [season_year]).fetchone()[0]
                
                if playoff_count > 0:
                    print(f"\nProcessing {playoff_count} playoff games...")
                    playoff_stats = ratings.process_season(season=season_year, game_type=3)
                    
        elif season:
            print(f"Processing Season {season}")
            
            # Process regular season
            stats = ratings.process_season(season=season, game_type=2)
            
            # Process playoffs
            playoff_count = ratings.conn.execute("""
                SELECT COUNT(*) FROM games 
                WHERE season = ? AND game_type = 3 AND game_state = 'OFF'
            """, [season]).fetchone()[0]
            
            if playoff_count > 0:
                print(f"\nProcessing {playoff_count} playoff games...")
                playoff_stats = ratings.process_season(season=season, game_type=3)
        else:
            print("Error: Must specify --season or --all-seasons")
            return False
        
        # Display top players
        print("\n" + "="*80)
        print("TOP 50 NHL PLAYERS BY TRUESKILL RATING")
        print("="*80)
        print(f"{'Rank':<6} {'Name':<25} {'Pos':<5} {'Skill':<8} {'μ':<8} {'σ':<8} {'Games':<6}")
        print("-"*80)
        
        top_players = ratings.get_top_players(limit=50, min_games=20)
        
        for i, player in enumerate(top_players, 1):
            name = f"{player['first_name']} {player['last_name']}"
            pos = player['position'] or '??'
            skill = player['skill_estimate']
            mu = player['mu']
            sigma = player['sigma']
            games = player['games_played']
            
            print(f"{i:<6} {name:<25} {pos:<5} {skill:<8.2f} {mu:<8.2f} {sigma:<8.2f} {games:<6}")
        
        # Export all ratings to JSON
        output_file = "data/nhl_trueskill_ratings.json"
        ratings.export_ratings(output_file)
        print(f"\n✓ Exported all ratings to {output_file}")
        
        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Calculate TrueSkill ratings for NHL players',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--season',
        type=int,
        help='Process specific season (e.g., 2023 for 2023-24 season)'
    )
    
    parser.add_argument(
        '--all-seasons',
        action='store_true',
        help='Process all available seasons in chronological order'
    )
    
    args = parser.parse_args()
    
    if not args.season and not args.all_seasons:
        parser.print_help()
        sys.exit(1)
    
    success = calculate_ratings(season=args.season, all_seasons=args.all_seasons)
    
    if success:
        print("\n✓ TrueSkill rating calculation complete!")
        sys.exit(0)
    else:
        print("\n✗ Failed to calculate ratings")
        sys.exit(1)


if __name__ == "__main__":
    main()
