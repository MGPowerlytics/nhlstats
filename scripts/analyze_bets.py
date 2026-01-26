"""
Analyze bet recommendations and track performance.
"""

import duckdb


def analyze_bets(start_date=None, end_date=None):
    """Analyze bet recommendations and performance."""

    conn = duckdb.connect("data/nhlstats.duckdb", read_only=True)

    print("=" * 80)
    print("BET RECOMMENDATIONS ANALYSIS")
    print("=" * 80)

    # Overall summary
    print("\n📊 OVERALL SUMMARY")
    print("-" * 80)

    result = conn.execute("""
        SELECT
            COUNT(*) as total_bets,
            COUNT(DISTINCT recommendation_date) as total_days,
            COUNT(DISTINCT sport) as sports_covered,
            AVG(edge) as avg_edge,
            AVG(elo_prob) as avg_elo_prob,
            MIN(recommendation_date) as first_date,
            MAX(recommendation_date) as last_date
        FROM bet_recommendations
    """).fetchone()

    print(f"Total Recommendations: {result[0]}")
    print(f"Days with Bets: {result[1]}")
    print(f"Sports Covered: {result[2]}")
    print(f"Average Edge: {result[3]:.1%}")
    print(f"Average Elo Probability: {result[4]:.1%}")
    print(f"Date Range: {result[5]} to {result[6]}")

    # By sport
    print("\n🏀 BY SPORT")
    print("-" * 80)
    print(
        f"{'Sport':<10} {'Total':<8} {'Avg Edge':<12} {'Avg Prob':<12} {'High Conf':<10}"
    )
    print("-" * 80)

    result = conn.execute("""
        SELECT
            sport,
            COUNT(*) as num_bets,
            AVG(edge) as avg_edge,
            AVG(elo_prob) as avg_elo_prob,
            SUM(CASE WHEN confidence = 'HIGH' THEN 1 ELSE 0 END) as high_conf
        FROM bet_recommendations
        GROUP BY sport
        ORDER BY num_bets DESC
    """).fetchall()

    for row in result:
        print(f"{row[0]:<10} {row[1]:<8} {row[2]:<12.1%} {row[3]:<12.1%} {row[4]:<10}")

    # By confidence
    print("\n💪 BY CONFIDENCE LEVEL")
    print("-" * 80)
    print(f"{'Confidence':<12} {'Count':<10} {'Avg Edge':<12} {'Avg Prob':<12}")
    print("-" * 80)

    result = conn.execute("""
        SELECT
            confidence,
            COUNT(*) as num_bets,
            AVG(edge) as avg_edge,
            AVG(elo_prob) as avg_elo_prob
        FROM bet_recommendations
        GROUP BY confidence
        ORDER BY avg_edge DESC
    """).fetchall()

    for row in result:
        print(f"{row[0]:<12} {row[1]:<10} {row[2]:<12.1%} {row[3]:<12.1%}")

    # Top opportunities by edge
    print("\n🎯 TOP 20 OPPORTUNITIES BY EDGE")
    print("-" * 80)
    print(f"{'Date':<12} {'Sport':<8} {'Matchup':<40} {'Edge':<10} {'Conf':<8}")
    print("-" * 80)

    result = conn.execute("""
        SELECT
            recommendation_date,
            sport,
            away_team || ' @ ' || home_team as matchup,
            edge,
            confidence
        FROM bet_recommendations
        ORDER BY edge DESC
        LIMIT 20
    """).fetchall()

    for row in result:
        matchup = row[2][:38] + ".." if len(row[2]) > 40 else row[2]
        print(
            f"{str(row[0]):<12} {row[1]:<8} {matchup:<40} {row[3]:<10.1%} {row[4]:<8}"
        )

    # Recent activity
    print("\n📅 LAST 7 DAYS ACTIVITY")
    print("-" * 80)
    print(f"{'Date':<12} {'Sport':<8} {'Count':<8} {'Avg Edge':<12} {'High Conf':<10}")
    print("-" * 80)

    result = conn.execute("""
        SELECT
            recommendation_date,
            sport,
            COUNT(*) as num_bets,
            AVG(edge) as avg_edge,
            SUM(CASE WHEN confidence = 'HIGH' THEN 1 ELSE 0 END) as high_conf
        FROM bet_recommendations
        WHERE recommendation_date >= CURRENT_DATE - INTERVAL 7 DAYS
        GROUP BY recommendation_date, sport
        ORDER BY recommendation_date DESC, sport
    """).fetchall()

    for row in result:
        print(f"{str(row[0]):<12} {row[1]:<8} {row[2]:<8} {row[3]:<12.1%} {row[4]:<10}")

    # Edge distribution
    print("\n📈 EDGE DISTRIBUTION")
    print("-" * 80)
    print(f"{'Edge Range':<15} {'Count':<10} {'Percentage':<12}")
    print("-" * 80)

    result = conn.execute("""
        SELECT
            CASE
                WHEN edge < 0.05 THEN '< 5%'
                WHEN edge < 0.10 THEN '5-10%'
                WHEN edge < 0.15 THEN '10-15%'
                WHEN edge < 0.20 THEN '15-20%'
                WHEN edge < 0.30 THEN '20-30%'
                ELSE '> 30%'
            END as edge_bucket,
            COUNT(*) as num_bets
        FROM bet_recommendations
        GROUP BY edge_bucket
        ORDER BY
            CASE edge_bucket
                WHEN '< 5%' THEN 1
                WHEN '5-10%' THEN 2
                WHEN '10-15%' THEN 3
                WHEN '15-20%' THEN 4
                WHEN '20-30%' THEN 5
                ELSE 6
            END
    """).fetchall()

    total = sum(row[1] for row in result)
    for row in result:
        pct = row[1] / total if total > 0 else 0
        print(f"{row[0]:<15} {row[1]:<10} {pct:<12.1%}")

    conn.close()

    print("\n" + "=" * 80)


if __name__ == "__main__":
    analyze_bets()
