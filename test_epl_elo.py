
import pandas as pd
from plugins.elo.epl_elo_rating import EPLEloRating, calculate_current_elo_ratings
from plugins.epl_games import EPLGames

def test_elo_consistency():
    print("Testing EPL Elo Consistency...")

    # 1. Load games
    epl_games = EPLGames()
    df = epl_games.load_games()
    df = df.sort_values("date")
    print(f"Loaded {len(df)} games.")

    # 2. Calculate ratings
    elo = calculate_current_elo_ratings()

    # 3. Check some top teams
    ranked = sorted(elo.ratings.items(), key=lambda x: x[1], reverse=True)
    print("\nCurrent Top 10 Teams:")
    for i, (team, r) in enumerate(ranked[:10]):
        print(f"{i+1}. {team:20}: {r:.1f}")

    # 4. Check a specific game prediction
    # Find a recent game
    recent_game = df.iloc[-1]
    print(f"\nLast Game: {recent_game['date'].date()} - {recent_game['home_team']} vs {recent_game['away_team']} ({recent_game['home_score']}-{recent_game['away_score']}, {recent_game['result']})")

    h, a = recent_game['home_team'], recent_game['away_team']
    ph, pd, pa = elo.predict_probs(h, a)
    print(f"Prediction for {h} vs {a}:")
    print(f"  Home: {ph:.1%}, Draw: {pd:.1%}, Away: {pa:.1%}")

    # 5. Check sum of probabilities
    print(f"Sum of probs: {ph + pd + pa:.4f}")

    # 6. Verify draw probability logic
    # Teams with same rating should have highest draw prob
    elo_neutral = EPLEloRating()
    elo_neutral.ratings["Team A"] = 1500
    elo_neutral.ratings["Team B"] = 1500
    p_h, p_d, p_a = elo_neutral.predict_probs("Team A", "Team B", is_neutral=True)
    print(f"\nNeutral 1500 vs 1500:")
    print(f"  Home: {p_h:.1%}, Draw: {p_d:.1%}, Away: {p_a:.1%}")

    # Team A much stronger
    elo_neutral.ratings["Team A"] = 1800
    p_h, p_d, p_a = elo_neutral.predict_probs("Team A", "Team B", is_neutral=True)
    print(f"\nNeutral 1800 vs 1500:")
    print(f"  Home: {p_h:.1%}, Draw: {p_d:.1%}, Away: {p_a:.1%}")

if __name__ == "__main__":
    test_elo_consistency()
