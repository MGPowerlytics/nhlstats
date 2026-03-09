#!/usr/bin/env python3
"""
Verify Elo system data quality.
Checks for team data completeness, Elo probability variance, and recommendation pipeline.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))
from db_manager import default_db
import pandas as pd


def verify_team_data():
    """Verify team data exists in placed_bets."""
    print("1. VERIFYING TEAM DATA IN placed_bets...")

    query = """
        SELECT
            sport,
            COUNT(*) as total_bets,
            SUM(CASE WHEN home_team IS NULL OR home_team = 'None' THEN 1 ELSE 0 END) as missing_home,
            SUM(CASE WHEN away_team IS NULL OR away_team = 'None' THEN 1 ELSE 0 END) as missing_away,
            ROUND((SUM(CASE WHEN home_team IS NULL OR home_team = 'None' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))::numeric, 1) as missing_pct
        FROM placed_bets
        WHERE status IN ('won', 'lost')
        GROUP BY sport
        ORDER BY total_bets DESC
    """

    result = default_db.fetch_df(query)

    if result.empty:
        print("   ⚠️  No settled bets found")
        return False

    all_ok = True
    total_missing = 0
    total_bets = 0

    for _, row in result.iterrows():
        sport = row["sport"]
        missing_home = row["missing_home"]
        missing_away = row["missing_away"]
        missing_pct = row["missing_pct"]
        total_bets_sport = row["total_bets"]

        total_missing += max(missing_home, missing_away)  # Count worst case
        total_bets += total_bets_sport

        if missing_pct > 5:
            print(
                f"   ❌ {sport}: {missing_pct:.1f}% missing team data ({missing_home}/{total_bets_sport} bets)"
            )
            all_ok = False
        else:
            print(f"   ✅ {sport}: {missing_pct:.1f}% missing team data")

    overall_missing_pct = (total_missing / total_bets * 100) if total_bets > 0 else 100

    print(f"\n   Overall: {overall_missing_pct:.1f}% of bets missing team data")

    if overall_missing_pct > 5:
        print("   ❌ FAIL: Too many bets missing team data")
        return False
    else:
        print("   ✅ PASS: Team data completeness acceptable")
        return all_ok


def verify_elo_variance():
    """Verify Elo probabilities have reasonable variance."""
    print("\n2. VERIFYING ELO PROBABILITY VARIANCE...")

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

    if results.empty:
        print("   ⚠️  No Elo probabilities found")
        return False

    all_ok = True

    for _, row in results.iterrows():
        sport = row["sport"]
        uniqueness = row["uniqueness_pct"] / 100
        std_dev = row["std_dev"]
        prob_range = row["prob_range"]
        unique_probs = row["unique_probs"]
        total_bets = row["total_bets"]

        # Different thresholds for different sports
        if sport == "TENNIS":
            # Tennis can have more variance
            min_uniqueness = 0.5
            min_std_dev = 0.05
        else:
            # Team sports should have reasonable variance
            min_uniqueness = 0.3
            min_std_dev = 0.02

        issues = []

        if uniqueness < min_uniqueness:
            issues.append(f"low uniqueness ({uniqueness:.1%})")

        if std_dev < min_std_dev:
            issues.append(f"low std dev ({std_dev:.4f})")

        if prob_range < 0.1 and sport != "TENNIS":
            issues.append(f"small range ({prob_range:.4f})")

        if issues:
            print(f"   ❌ {sport}: {', '.join(issues)}")
            print(f"      Details: {unique_probs} unique probs / {total_bets} bets")
            all_ok = False
        else:
            print(
                f"   ✅ {sport}: Good variance (uniqueness={uniqueness:.1%}, std={std_dev:.4f}, range={prob_range:.4f})"
            )

    return all_ok


def verify_recommendations():
    """Verify bet_recommendations has data."""
    print("\n3. VERIFYING bet_recommendations PIPELINE...")

    # Check if table exists
    table_check = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'bet_recommendations'
        ) as table_exists
    """

    table_exists = default_db.fetch_df(table_check)

    if not table_exists.iloc[0]["table_exists"]:
        print("   ❌ FAIL: bet_recommendations table does not exist")
        return False

    # Check for recent data
    query = """
        SELECT
            COUNT(*) as total_recommendations,
            COUNT(DISTINCT recommendation_date) as unique_dates,
            MIN(recommendation_date) as earliest_date,
            MAX(recommendation_date) as latest_date
        FROM bet_recommendations
        WHERE recommendation_date >= CURRENT_DATE - 30
    """

    result = default_db.fetch_df(query)

    total = result.iloc[0]["total_recommendations"]
    unique_dates = result.iloc[0]["unique_dates"]
    earliest = result.iloc[0]["earliest_date"]
    latest = result.iloc[0]["latest_date"]

    if total == 0:
        print("   ❌ FAIL: No bet recommendations in last 30 days")
        print("      Table exists but is empty")
        return False
    elif total < 10:
        print(f"   ⚠️  WARNING: Only {total} recommendations in last 30 days")
        print(f"      Dates: {earliest} to {latest} ({unique_dates} days)")
        return True  # Warning but not failure
    else:
        print(f"   ✅ PASS: {total} recommendations across {unique_dates} days")
        print(f"      Date range: {earliest} to {latest}")
        return True


def verify_elo_calibration():
    """Check basic Elo calibration."""
    print("\n4. VERIFYING ELO CALIBRATION...")

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

    if results.empty:
        print("   ⚠️  Not enough data for calibration check")
        return True

    all_ok = True

    for _, row in results.iterrows():
        sport = row["sport"]
        bets = row["bets"]
        avg_elo = row["avg_elo_prob"]
        win_rate = row["actual_win_rate"]
        error = row["calibration_error"]

        # Acceptable calibration error: ±0.05
        if abs(error) > 0.05:
            print(f"   ❌ {sport}: Poor calibration (error={error:.4f})")
            print(f"      Elo: {avg_elo:.3f}, Actual: {win_rate:.3f}, Bets: {bets}")
            all_ok = False
        else:
            print(f"   ✅ {sport}: Reasonable calibration (error={error:.4f})")

    return all_ok


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("ELO SYSTEM DATA QUALITY VERIFICATION")
    print("=" * 60)

    # Set POSTGRES_HOST if not set
    if "POSTGRES_HOST" not in os.environ:
        os.environ["POSTGRES_HOST"] = "localhost"

    try:
        # Test database connection
        test_query = "SELECT COUNT(*) as bet_count FROM placed_bets WHERE status IN ('won', 'lost')"
        test_result = default_db.fetch_df(test_query)
        settled_bets = test_result.iloc[0]["bet_count"]
        print(f"Connected to database. Found {settled_bets} settled bets.\n")

        # Run all checks
        checks = [
            ("Team Data", verify_team_data),
            ("Elo Variance", verify_elo_variance),
            ("Recommendations", verify_recommendations),
            ("Elo Calibration", verify_elo_calibration),
        ]

        results = []

        for check_name, check_func in checks:
            try:
                result = check_func()
                results.append((check_name, result))
            except Exception as e:
                print(f"   ❌ ERROR in {check_name}: {e}")
                results.append((check_name, False))

        # Summary
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)

        passed = 0
        failed = 0

        for check_name, result in results:
            if result:
                print(f"✅ {check_name}: PASS")
                passed += 1
            else:
                print(f"❌ {check_name}: FAIL")
                failed += 1

        print(f"\nTotal: {passed} passed, {failed} failed")

        if failed == 0:
            print("\n🎉 ALL CHECKS PASSED - Elo system data quality is good")
            return 0
        else:
            print("\n⚠️  SOME CHECKS FAILED - Review issues above")
            return 1

    except Exception as e:
        print(f"\n❌ DATABASE CONNECTION ERROR: {e}")
        print("Make sure PostgreSQL is running and POSTGRES_HOST is set correctly.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
