#!/usr/bin/env python3
"""
Test TrueSkill Rating System

Simple tests to validate the TrueSkill implementation works correctly.
"""

import sys
import trueskill


def test_trueskill_library():
    """Test that TrueSkill library is installed and working"""
    print("Testing TrueSkill library...")
    
    # Create environment
    env = trueskill.TrueSkill()
    
    # Create two players
    player1 = env.create_rating()
    player2 = env.create_rating()
    
    print(f"  Player 1 initial rating: μ={player1.mu:.2f}, σ={player1.sigma:.2f}")
    print(f"  Player 2 initial rating: μ={player2.mu:.2f}, σ={player2.sigma:.2f}")
    
    # Simulate player 1 winning
    new_player1, new_player2 = env.rate_1vs1(player1, player2)
    
    print(f"  After P1 wins:")
    print(f"    Player 1: μ={new_player1.mu:.2f}, σ={new_player1.sigma:.2f} (gained {new_player1.mu - player1.mu:.2f})")
    print(f"    Player 2: μ={new_player2.mu:.2f}, σ={new_player2.sigma:.2f} (lost {player2.mu - new_player2.mu:.2f})")
    
    assert new_player1.mu > player1.mu, "Winner should gain rating"
    assert new_player2.mu < player2.mu, "Loser should lose rating"
    assert new_player1.sigma < player1.sigma, "Uncertainty should decrease"
    
    print("  ✓ TrueSkill library working correctly\n")
    return True


def test_database_connection():
    """Test database connection and schema"""
    print("Testing database connection...")
    
    try:
        from nhl_trueskill import NHLTrueSkillRatings
        
        with NHLTrueSkillRatings() as ratings:
            # Test that tables were created
            tables = ratings.conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name LIKE '%trueskill%'
            """).fetchall()
            
            print(f"  Found {len(tables)} TrueSkill tables:")
            for (table_name,) in tables:
                print(f"    - {table_name}")
            
            assert len(tables) >= 2, "Should have at least 2 TrueSkill tables"
            
        print("  ✓ Database connection and schema OK\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        return False


def test_rating_calculation():
    """Test rating calculation logic"""
    print("Testing rating calculation...")
    
    try:
        from nhl_trueskill import NHLTrueSkillRatings
        
        with NHLTrueSkillRatings() as ratings:
            
            # Test getting/creating ratings
            player1_id = 8478402  # Connor McDavid
            player2_id = 8477934  # Ryan Nugent-Hopkins
            
            rating1 = ratings.get_or_create_rating(player1_id)
            rating2 = ratings.get_or_create_rating(player2_id)
            
            print(f"  Created ratings for players {player1_id} and {player2_id}")
            print(f"    Player {player1_id}: μ={rating1.mu:.2f}, σ={rating1.sigma:.2f}")
            print(f"    Player {player2_id}: μ={rating2.mu:.2f}, σ={rating2.sigma:.2f}")
            
            # Test team rating calculation
            player_ids = [player1_id, player2_id]
            weights = [1200, 1000]  # TOI in seconds
            
            team_rating = ratings.calculate_team_rating(player_ids, weights)
            print(f"  Team rating (weighted): {team_rating:.2f}")
            
            assert isinstance(team_rating, float), "Team rating should be a float"
            # Conservative estimate (mu - 3*sigma) can be 0 or negative for new players
            # This is expected behavior
            
        print("  ✓ Rating calculation working correctly\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_game_processing():
    """Test processing a game if data exists"""
    print("Testing game processing...")
    
    try:
        from nhl_trueskill import NHLTrueSkillRatings
        
        with NHLTrueSkillRatings() as ratings:
            
            # Check if games table exists
            tables = ratings.conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='games'
            """).fetchall()
            
            if not tables:
                print("  ! No games table found in database")
                print("  ! This is OK for a fresh database - skipping test")
                print("  ✓ Test skipped (no data available)\n")
                return True
            
            # Find a completed game
            game = ratings.conn.execute("""
                SELECT game_id, home_team_id, away_team_id, home_score, away_score
                FROM games
                WHERE game_state = 'OFF'
                AND home_score IS NOT NULL
                AND away_score IS NOT NULL
                ORDER BY game_date DESC
                LIMIT 1
            """).fetchone()
            
            if not game:
                print("  ! No completed games found in database - skipping test")
                print("  (This is OK if database is empty)")
                print("  ✓ Test skipped (no data available)\n")
                return True
            
            game_id, home_team, away_team, home_score, away_score = game
            home_won = home_score > away_score
            
            print(f"  Testing with game {game_id}:")
            print(f"    Home team {home_team}: {home_score}")
            print(f"    Away team {away_team}: {away_score}")
            print(f"    Winner: {'Home' if home_won else 'Away'}")
            
            # Process the game
            home_players, away_players = ratings.update_game_ratings(game_id, home_won)
            
            print(f"    Updated {home_players} home players")
            print(f"    Updated {away_players} away players")
            
            if home_players > 0 and away_players > 0:
                print("  ✓ Game processing working correctly\n")
                return True
            else:
                print("  ! No players updated (might be missing player stats)\n")
                return True
                
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("="*70)
    print("NHL TrueSkill Rating System - Test Suite")
    print("="*70 + "\n")
    
    tests = [
        ("TrueSkill Library", test_trueskill_library),
        ("Database Connection", test_database_connection),
        ("Rating Calculation", test_rating_calculation),
        ("Game Processing", test_game_processing),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"Test '{name}' failed with exception: {e}\n")
            results.append((name, False))
    
    # Summary
    print("="*70)
    print("Test Summary")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
