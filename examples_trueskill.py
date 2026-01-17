"""
Example: Using NHL TrueSkill Ratings

This example demonstrates how to use the TrueSkill rating system
to calculate and query player ratings.
"""

from nhl_trueskill import NHLTrueSkillRatings


def example_calculate_ratings():
    """Example: Calculate ratings for a season"""
    print("="*70)
    print("EXAMPLE 1: Calculate Ratings for 2023-24 Season")
    print("="*70 + "\n")
    
    with NHLTrueSkillRatings() as ratings:
        # Process the 2023-24 regular season
        stats = ratings.process_season(season=2023, game_type=2)
        
        print(f"Processed {stats['games_processed']} games")
        print(f"Updated {stats['players_updated']} player ratings")


def example_query_top_players():
    """Example: Get top rated players"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Top 10 Players by TrueSkill Rating")
    print("="*70 + "\n")
    
    with NHLTrueSkillRatings() as ratings:
        top_players = ratings.get_top_players(limit=10, min_games=20)
        
        print(f"{'Rank':<6} {'Name':<25} {'Pos':<5} {'Skill':<8} {'Games':<6}")
        print("-"*60)
        
        for i, player in enumerate(top_players, 1):
            name = f"{player['first_name']} {player['last_name']}"
            skill = player['skill_estimate']
            games = player['games_played']
            pos = player['position'] or '??'
            
            print(f"{i:<6} {name:<25} {pos:<5} {skill:<8.2f} {games:<6}")


def example_team_rating():
    """Example: Calculate team rating for a lineup"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Calculate Team Rating from Player IDs")
    print("="*70 + "\n")
    
    with NHLTrueSkillRatings() as ratings:
        # Example: Edmonton Oilers top line
        # (Connor McDavid, Leon Draisaitl, Ryan Nugent-Hopkins)
        player_ids = [8478402, 8477934, 8479318]
        
        # Weight by time on ice (in seconds)
        toi_weights = [1200, 1150, 1100]  # ~20, 19, 18 minutes
        
        team_rating = ratings.calculate_team_rating(player_ids, toi_weights)
        
        print(f"Player IDs: {player_ids}")
        print(f"TOI Weights: {toi_weights}")
        print(f"Team Rating: {team_rating:.2f}")
        print("\nNote: This is a weighted average of player skill estimates")


def example_export_ratings():
    """Example: Export ratings to JSON"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Export Ratings to JSON")
    print("="*70 + "\n")
    
    with NHLTrueSkillRatings() as ratings:
        output_file = "data/nhl_trueskill_ratings.json"
        ratings.export_ratings(output_file)
        print(f"✓ Exported all player ratings to {output_file}")


def example_query_specific_player():
    """Example: Query a specific player's rating"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Query Specific Player Rating")
    print("="*70 + "\n")
    
    with NHLTrueSkillRatings() as ratings:
        # Connor McDavid's player ID
        player_id = 8478402
        
        # Get rating from database
        result = ratings.conn.execute("""
            SELECT 
                p.first_name,
                p.last_name,
                r.mu,
                r.sigma,
                r.skill_estimate,
                r.games_played
            FROM player_trueskill_ratings r
            JOIN players p ON r.player_id = p.player_id
            WHERE r.player_id = ?
        """, [player_id]).fetchone()
        
        if result:
            first, last, mu, sigma, skill, games = result
            print(f"Player: {first} {last}")
            print(f"Mean (μ): {mu:.2f}")
            print(f"Uncertainty (σ): {sigma:.2f}")
            print(f"Skill Estimate: {skill:.2f}")
            print(f"Games Played: {games}")
        else:
            print(f"No rating found for player {player_id}")
            print("You may need to run calculate_trueskill_ratings.py first")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("NHL TrueSkill Rating System - Usage Examples")
    print("="*70)
    
    # Note: These examples assume you have NHL data in your database
    # Run nhl_db_loader.py first to load game data
    
    print("\nNOTE: These examples require game data in the database.")
    print("If you haven't loaded any data yet, run:")
    print("  1. Download game data with nhl_game_events.py")
    print("  2. Load into database with nhl_db_loader.py")
    print("  3. Then run calculate_trueskill_ratings.py")
    print()
    
    # Uncomment examples as needed:
    
    # example_calculate_ratings()
    # example_query_top_players()
    # example_team_rating()
    # example_export_ratings()
    # example_query_specific_player()
    
    print("\nUncomment examples in this file to run them.")
    print("See README_TRUESKILL.md for full documentation.")
