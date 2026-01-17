#!/usr/bin/env python3
"""
Query NHL TrueSkill Ratings

Utility script to query and display player TrueSkill ratings.

Usage:
    python query_trueskill_ratings.py [options]
    
Examples:
    # Top 50 players
    python query_trueskill_ratings.py --top 50
    
    # Search for specific player
    python query_trueskill_ratings.py --player "McDavid"
    
    # Get specific player by ID
    python query_trueskill_ratings.py --player-id 8478402
    
    # Top goalies
    python query_trueskill_ratings.py --top 20 --position G
    
    # Rating history for a player
    python query_trueskill_ratings.py --player-id 8478402 --history
"""

import argparse
import sys
from nhl_trueskill import NHLTrueSkillRatings


def display_top_players(ratings: NHLTrueSkillRatings, limit: int, position: str = None, min_games: int = 20):
    """Display top rated players"""
    
    # Build query
    query = """
        SELECT 
            r.player_id,
            p.first_name,
            p.last_name,
            p.position_code,
            r.mu,
            r.sigma,
            r.skill_estimate,
            r.games_played,
            r.last_updated
        FROM player_trueskill_ratings r
        JOIN players p ON r.player_id = p.player_id
        WHERE r.games_played >= ?
    """
    
    params = [min_games]
    
    if position:
        query += " AND p.position_code = ?"
        params.append(position)
    
    query += " ORDER BY r.skill_estimate DESC LIMIT ?"
    params.append(limit)
    
    results = ratings.conn.execute(query, params).fetchall()
    
    if not results:
        print("No players found matching criteria")
        return
    
    # Display header
    title = f"TOP {limit} NHL PLAYERS BY TRUESKILL RATING"
    if position:
        title += f" (Position: {position})"
    
    print("\n" + "="*85)
    print(title)
    print("="*85)
    print(f"{'Rank':<6} {'Name':<25} {'Pos':<5} {'Skill':<8} {'μ':<8} {'σ':<8} {'Games':<6}")
    print("-"*85)
    
    for i, row in enumerate(results, 1):
        player_id, first, last, pos, mu, sigma, skill, games, updated = row
        name = f"{first} {last}"
        pos_str = pos or '??'
        
        print(f"{i:<6} {name:<25} {pos_str:<5} {skill:<8.2f} {mu:<8.2f} {sigma:<8.2f} {games:<6}")


def search_player(ratings: NHLTrueSkillRatings, search_term: str):
    """Search for player by name"""
    
    results = ratings.conn.execute("""
        SELECT 
            r.player_id,
            p.first_name,
            p.last_name,
            p.position_code,
            r.mu,
            r.sigma,
            r.skill_estimate,
            r.games_played,
            r.last_updated
        FROM player_trueskill_ratings r
        JOIN players p ON r.player_id = p.player_id
        WHERE LOWER(p.first_name || ' ' || p.last_name) LIKE ?
        ORDER BY r.skill_estimate DESC
    """, [f"%{search_term.lower()}%"]).fetchall()
    
    if not results:
        print(f"No players found matching '{search_term}'")
        return
    
    print(f"\nFound {len(results)} player(s) matching '{search_term}':\n")
    print(f"{'ID':<10} {'Name':<25} {'Pos':<5} {'Skill':<8} {'μ':<8} {'σ':<8} {'Games':<6}")
    print("-"*80)
    
    for row in results:
        player_id, first, last, pos, mu, sigma, skill, games, updated = row
        name = f"{first} {last}"
        pos_str = pos or '??'
        
        print(f"{player_id:<10} {name:<25} {pos_str:<5} {skill:<8.2f} {mu:<8.2f} {sigma:<8.2f} {games:<6}")


def display_player_rating(ratings: NHLTrueSkillRatings, player_id: int, show_history: bool = False):
    """Display rating for specific player"""
    
    # Get current rating
    result = ratings.conn.execute("""
        SELECT 
            p.first_name,
            p.last_name,
            p.position_code,
            p.sweater_number,
            r.mu,
            r.sigma,
            r.skill_estimate,
            r.games_played,
            r.last_updated
        FROM player_trueskill_ratings r
        JOIN players p ON r.player_id = p.player_id
        WHERE r.player_id = ?
    """, [player_id]).fetchone()
    
    if not result:
        print(f"No rating found for player ID {player_id}")
        return
    
    first, last, pos, number, mu, sigma, skill, games, updated = result
    name = f"{first} {last}"
    
    print("\n" + "="*70)
    print(f"TRUESKILL RATING: {name}")
    print("="*70)
    print(f"Player ID:        {player_id}")
    print(f"Position:         {pos or 'Unknown'}")
    if number:
        print(f"Number:           #{number}")
    print()
    print(f"Skill Estimate:   {skill:.2f} (μ - 3σ)")
    print(f"Mean (μ):         {mu:.2f}")
    print(f"Uncertainty (σ):  {sigma:.2f}")
    print(f"Games Played:     {games}")
    print(f"Last Updated:     {updated}")
    
    # Show rating history if requested
    if show_history:
        history = ratings.conn.execute("""
            SELECT 
                h.game_id,
                h.game_date,
                h.mu_before,
                h.sigma_before,
                h.mu_after,
                h.sigma_after,
                h.team_won,
                h.toi_seconds
            FROM player_trueskill_history h
            WHERE h.player_id = ?
            ORDER BY h.game_date DESC
            LIMIT 20
        """, [player_id]).fetchall()
        
        if history:
            print("\n" + "="*70)
            print("RECENT RATING HISTORY (Last 20 games)")
            print("="*70)
            print(f"{'Date':<12} {'Game ID':<12} {'Result':<6} {'TOI':<6} {'μ Before':<10} {'μ After':<10} {'Change':<8}")
            print("-"*70)
            
            for row in history:
                game_id, date, mu_before, sigma_before, mu_after, sigma_after, won, toi = row
                result = "WIN" if won else "LOSS"
                toi_min = toi // 60 if toi else 0
                mu_change = mu_after - mu_before
                change_str = f"{mu_change:+.2f}"
                
                print(f"{date:<12} {game_id:<12} {result:<6} {toi_min:<6} {mu_before:<10.2f} {mu_after:<10.2f} {change_str:<8}")


def display_position_rankings(ratings: NHLTrueSkillRatings, min_games: int = 20):
    """Display top players by position"""
    
    positions = ['C', 'L', 'R', 'D', 'G']
    position_names = {
        'C': 'Centers',
        'L': 'Left Wings',
        'R': 'Right Wings',
        'D': 'Defensemen',
        'G': 'Goalies'
    }
    
    for pos in positions:
        results = ratings.conn.execute("""
            SELECT 
                r.player_id,
                p.first_name,
                p.last_name,
                r.skill_estimate,
                r.games_played
            FROM player_trueskill_ratings r
            JOIN players p ON r.player_id = p.player_id
            WHERE p.position_code = ?
            AND r.games_played >= ?
            ORDER BY r.skill_estimate DESC
            LIMIT 10
        """, [pos, min_games]).fetchall()
        
        if results:
            print(f"\n{position_names[pos]} (Top 10):")
            print("-" * 50)
            
            for i, (player_id, first, last, skill, games) in enumerate(results, 1):
                name = f"{first} {last}"
                print(f"{i:2d}. {name:<25} {skill:6.2f} ({games} games)")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Query NHL TrueSkill ratings',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--top', type=int, metavar='N', help='Show top N players')
    parser.add_argument('--position', choices=['C', 'L', 'R', 'D', 'G'], help='Filter by position')
    parser.add_argument('--player', type=str, help='Search for player by name')
    parser.add_argument('--player-id', type=int, help='Get rating for specific player ID')
    parser.add_argument('--history', action='store_true', help='Show rating history (use with --player-id)')
    parser.add_argument('--min-games', type=int, default=20, help='Minimum games played (default: 20)')
    parser.add_argument('--by-position', action='store_true', help='Show top 10 for each position')
    
    args = parser.parse_args()
    
    # Need at least one action
    if not any([args.top, args.player, args.player_id, args.by_position]):
        parser.print_help()
        sys.exit(1)
    
    with NHLTrueSkillRatings() as ratings:
        
        if args.top:
            display_top_players(ratings, args.top, args.position, args.min_games)
            
        if args.player:
            search_player(ratings, args.player)
            
        if args.player_id:
            display_player_rating(ratings, args.player_id, args.history)
            
        if args.by_position:
            display_position_rankings(ratings, args.min_games)


if __name__ == "__main__":
    main()
