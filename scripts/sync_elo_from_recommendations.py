#!/usr/bin/env python3
"""
Sync Elo probabilities from bet_recommendations to placed_bets.
bet_recommendations has correct Elo probabilities calculated with team data.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'plugins'))
from db_manager import default_db


def sync_elo_probabilities():
    """Sync Elo probabilities from bet_recommendations to placed_bets."""
    print("Syncing Elo probabilities from bet_recommendations...")

    # First, check how many bets need updating
    check_query = """
        SELECT
            COUNT(*) as total_bets,
            SUM(CASE WHEN pb.elo_prob IS NOT NULL THEN 1 ELSE 0 END) as has_elo,
            SUM(CASE WHEN br.elo_prob IS NOT NULL THEN 1 ELSE 0 END) as has_recommendation_elo
        FROM placed_bets pb
        LEFT JOIN bet_recommendations br ON pb.ticker = br.ticker
        WHERE pb.status IN ('won', 'lost')
    """

    check_result = default_db.fetch_df(check_query)
    total_bets = check_result.iloc[0]['total_bets']
    has_elo = check_result.iloc[0]['has_elo']
    has_recommendation_elo = check_result.iloc[0]['has_recommendation_elo']

    print(f"Total settled bets: {total_bets}")
    print(f"Bets with Elo probabilities: {has_elo}")
    print(f"Bets with matching recommendations: {has_recommendation_elo}")

    # Update Elo probabilities from recommendations
    # Use the latest recommendation for each ticker
    update_query = """
        WITH latest_recommendations AS (
            SELECT
                ticker,
                elo_prob,
                market_prob,
                edge,
                confidence,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY created_at DESC) as rn
            FROM bet_recommendations
            WHERE elo_prob IS NOT NULL
        )
        UPDATE placed_bets pb
        SET
            elo_prob = lr.elo_prob,
            market_prob = lr.market_prob,
            edge = lr.edge,
            confidence = lr.confidence
        FROM latest_recommendations lr
        WHERE pb.ticker = lr.ticker
          AND lr.rn = 1
          AND pb.status IN ('won', 'lost')
          AND pb.elo_prob IS NOT NULL  -- Only update existing Elo probabilities
    """

    try:
        result = default_db.execute(update_query)
        print(f"✅ Updated Elo probabilities for bets with matching recommendations")

        # Check how many were updated
        after_query = """
            SELECT
                COUNT(*) as updated_count
            FROM placed_bets pb
            INNER JOIN bet_recommendations br ON pb.ticker = br.ticker
            WHERE pb.status IN ('won', 'lost')
              AND pb.elo_prob IS NOT NULL
        """

        after_result = default_db.fetch_df(after_query)
        updated_count = after_result.iloc[0]['updated_count']
        print(f"   Total bets with synced Elo probabilities: {updated_count}")

        return True

    except Exception as e:
        print(f"❌ Error syncing Elo probabilities: {e}")
        return False


def analyze_elo_variance_after_sync():
    """Analyze Elo probability variance after sync."""
    print("\nAnalyzing Elo probability variance after sync...")

    query = """
        SELECT
            sport,
            COUNT(DISTINCT elo_prob) as unique_probs,
            COUNT(*) as total_bets,
            ROUND((COUNT(DISTINCT elo_prob) * 100.0 / COUNT(*))::numeric, 1) as uniqueness_pct,
            ROUND(STDDEV(elo_prob)::numeric, 4) as std_dev,
            ROUND(MIN(elo_prob)::numeric, 4) as min_prob,
            ROUND(MAX(elo_prob)::numeric, 4) as max_prob,
            ROUND((MAX(elo_prob) - MIN(elo_prob))::numeric, 4) as prob_range
        FROM placed_bets
        WHERE status IN ('won', 'lost')
          AND elo_prob IS NOT NULL
        GROUP BY sport
        ORDER BY total_bets DESC
    """

    results = default_db.fetch_df(query)

    print("Elo probability distribution by sport:")
    for _, row in results.iterrows():
        sport = row['sport']
        unique_probs = row['unique_probs']
        total_bets = row['total_bets']
        uniqueness = row['uniqueness_pct']
        std_dev = row['std_dev']
        prob_range = row['prob_range']

        print(f"  {sport}:")
        print(f"    Bets: {total_bets}, Unique probabilities: {unique_probs} ({uniqueness}%)")
        print(f"    Std dev: {std_dev:.4f}, Range: {prob_range:.4f}")

        # Check if variance is reasonable
        if sport != 'TENNIS':  # Tennis has different characteristics
            if uniqueness < 30 or std_dev < 0.02:
                print(f"    ⚠️  WARNING: Low variance")
            else:
                print(f"    ✅ Good variance")

    return results


def analyze_calibration_after_sync():
    """Analyze Elo calibration after sync."""
    print("\nAnalyzing Elo calibration after sync...")

    query = """
        SELECT
            sport,
            COUNT(*) as bets,
            ROUND(AVG(elo_prob)::numeric, 4) as avg_elo_prob,
            ROUND(AVG(CASE WHEN status = 'won' THEN 1.0 ELSE 0.0 END)::numeric, 4) as actual_win_rate,
            ROUND((AVG(CASE WHEN status = 'won' THEN 1.0 ELSE 0.0 END) - AVG(elo_prob))::numeric, 4) as calibration_error
        FROM placed_bets
        WHERE status IN ('won', 'lost')
          AND elo_prob IS NOT NULL
        GROUP BY sport
        HAVING COUNT(*) >= 10
        ORDER BY COUNT(*) DESC
    """

    results = default_db.fetch_df(query)

    print("Elo calibration by sport:")
    for _, row in results.iterrows():
        sport = row['sport']
        bets = row['bets']
        avg_elo = row['avg_elo_prob']
        win_rate = row['actual_win_rate']
        error = row['calibration_error']

        print(f"  {sport}:")
        print(f"    Bets: {bets}, Avg Elo: {avg_elo:.3f}, Win rate: {win_rate:.3f}")
        print(f"    Calibration error: {error:.4f}")

        if abs(error) > 0.05:
            print(f"    ⚠️  WARNING: Poor calibration (error > 0.05)")
        else:
            print(f"    ✅ Good calibration")

    return results


def main():
    """Main function."""
    # Set POSTGRES_HOST if not set
    if 'POSTGRES_HOST' not in os.environ:
        os.environ['POSTGRES_HOST'] = 'localhost'

    try:
        # Test connection
        test_query = "SELECT COUNT(*) as count FROM placed_bets WHERE status IN ('won', 'lost')"
        test_result = default_db.fetch_df(test_query)
        settled_bets = test_result.iloc[0]['count']
        print(f"Connected to database. Found {settled_bets} settled bets.\n")

        # Sync Elo probabilities
        success = sync_elo_probabilities()

        if not success:
            print("\n❌ Failed to sync Elo probabilities")
            return 1

        # Analyze results
        variance_results = analyze_elo_variance_after_sync()
        calibration_results = analyze_calibration_after_sync()

        # Summary
        print("\n" + "="*60)
        print("SYNC SUMMARY")
        print("="*60)

        # Check if variance improved
        poor_variance_sports = []
        for _, row in variance_results.iterrows():
            sport = row['sport']
            uniqueness = row['uniqueness_pct']
            std_dev = row['std_dev']

            if sport != 'TENNIS' and (uniqueness < 30 or std_dev < 0.02):
                poor_variance_sports.append(sport)

        # Check calibration
        poor_calibration_sports = []
        for _, row in calibration_results.iterrows():
            sport = row['sport']
            error = abs(row['calibration_error'])

            if error > 0.05:
                poor_calibration_sports.append(sport)

        if not poor_variance_sports and not poor_calibration_sports:
            print("🎉 SUCCESS: Elo probabilities synced successfully!")
            print("   All sports show good variance and calibration")
            return 0
        else:
            print("⚠️  PARTIAL SUCCESS: Elo probabilities synced but issues remain:")
            if poor_variance_sports:
                print(f"   Poor variance: {', '.join(poor_variance_sports)}")
            if poor_calibration_sports:
                print(f"   Poor calibration: {', '.join(poor_calibration_sports)}")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
