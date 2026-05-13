#!/usr/bin/env python3
"""Part 2: Correlation analysis - soccer_team_game_stats_ext joined with team_game_stats."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from plugins.db_manager import DBManager

db = DBManager(
    connection_string="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
)

# Check some sample rows of soccer_team_game_stats_ext with game_id pattern
sample = db.fetch_df("""
SELECT game_id, team, xg, xga
FROM soccer_team_game_stats_ext
WHERE game_id LIKE 'EPL_2024_%' AND xg IS NOT NULL
LIMIT 10
""")
print("=== SAMPLE soccer_team_game_stats_ext rows ===")
print(sample.to_string(index=False))
print()

# Check how team_game_stats relates (same game_id pattern)
tgs_sample = db.fetch_df("""
SELECT game_id, team, is_home, points_for, points_against
FROM team_game_stats
WHERE game_id LIKE 'EPL_2024_%'
LIMIT 10
""")
print("=== SAMPLE team_game_stats rows ===")
print(tgs_sample.to_string(index=False))
print()

# Verify game_id format compatibility between the two tables
compat_check = db.fetch_df("""
SELECT s.game_id, t.game_id as tgs_game_id, s.team, t.team as tgs_team
FROM soccer_team_game_stats_ext s
JOIN team_game_stats t ON s.game_id = t.game_id AND s.team = t.team
WHERE s.game_id LIKE 'EPL_2024_%'
LIMIT 10
""")
print("=== GAME_ID compatibility check ===")
print(compat_check.to_string(index=False))
print()

# Now do the correlation properly via team_game_stats
corr_data = db.fetch_df("""
WITH game_xg AS (
    SELECT
        s.game_id,
        MAX(CASE WHEN t.is_home THEN s.xg END) as home_xg,
        MAX(CASE WHEN t.is_home THEN s.xga END) as home_xga,
        MAX(CASE WHEN NOT t.is_home THEN s.xg END) as away_xg,
        MAX(CASE WHEN NOT t.is_home THEN s.xga END) as away_xga,
        MAX(CASE WHEN t.is_home THEN t.points_for END) as home_goals,
        MAX(CASE WHEN NOT t.is_home THEN t.points_for END) as away_goals
    FROM soccer_team_game_stats_ext s
    JOIN team_game_stats t ON s.game_id = t.game_id AND s.team = t.team
    WHERE s.game_id LIKE 'EPL_%' AND s.xg IS NOT NULL
    GROUP BY s.game_id
)
SELECT
    COUNT(*) as n_games,
    ROUND(CORR(home_xg, home_goals)::numeric, 4) as corr_home_xg_goals,
    ROUND(CORR(away_xg, away_goals)::numeric, 4) as corr_away_xg_goals,
    ROUND(CORR(home_xg + away_xg, home_goals + away_goals)::numeric, 4) as corr_total_xg_total_goals,
    ROUND(AVG(home_xg)::numeric, 3) as avg_home_xg,
    ROUND(AVG(home_goals)::numeric, 3) as avg_home_goals,
    ROUND(AVG(away_xg)::numeric, 3) as avg_away_xg,
    ROUND(AVG(away_goals)::numeric, 3) as avg_away_goals,
    ROUND(AVG(home_xg + away_xg)::numeric, 3) as avg_total_xg,
    ROUND(AVG(home_goals + away_goals)::numeric, 3) as avg_total_goals,
    ROUND(AVG(home_xg - home_goals)::numeric, 3) as mean_home_xg_error,
    ROUND(AVG(away_xg - away_goals)::numeric, 3) as mean_away_xg_error
FROM game_xg
""")
print("=== XG vs ACTUAL GOALS CORRELATION ===")
print(corr_data.to_string(index=False))
print()

# Per-season correlations
per_season = db.fetch_df("""
WITH game_xg AS (
    SELECT
        s.game_id,
        SUBSTRING(s.game_id FROM 5 FOR 4) as season,
        MAX(CASE WHEN t.is_home THEN s.xg END) as home_xg,
        MAX(CASE WHEN t.is_home THEN t.points_for END) as home_goals,
        MAX(CASE WHEN NOT t.is_home THEN s.xg END) as away_xg,
        MAX(CASE WHEN NOT t.is_home THEN t.points_for END) as away_goals
    FROM soccer_team_game_stats_ext s
    JOIN team_game_stats t ON s.game_id = t.game_id AND s.team = t.team
    WHERE s.game_id LIKE 'EPL_%' AND s.xg IS NOT NULL
    GROUP BY s.game_id
)
SELECT
    season,
    COUNT(*) as n_games,
    ROUND(CORR(home_xg, home_goals)::numeric, 4) as corr_home_xg,
    ROUND(CORR(away_xg, away_goals)::numeric, 4) as corr_away_xg,
    ROUND(CORR(home_xg + away_xg, home_goals + away_goals)::numeric, 4) as corr_total,
    ROUND(AVG(home_xg)::numeric, 3) as avg_home_xg,
    ROUND(AVG(home_goals)::numeric, 3) as avg_home_goals,
    ROUND(AVG(away_xg)::numeric, 3) as avg_away_xg,
    ROUND(AVG(away_goals)::numeric, 3) as avg_away_goals
FROM game_xg
GROUP BY season
ORDER BY season
""")
print("=== PER-SEASON CORRELATIONS ===")
print(per_season.to_string(index=False))
print()

# Distribution buckets
distrib = db.fetch_df("""
SELECT
    CASE
        WHEN s.xg < 0.5 THEN '< 0.5'
        WHEN s.xg < 1.0 THEN '0.5-1.0'
        WHEN s.xg < 1.5 THEN '1.0-1.5'
        WHEN s.xg < 2.0 THEN '1.5-2.0'
        WHEN s.xg < 2.5 THEN '2.0-2.5'
        WHEN s.xg < 3.0 THEN '2.5-3.0'
        ELSE '3.0+'
    END as xg_bucket,
    COUNT(*) as n_rows,
    ROUND(AVG(t.points_for)::numeric, 3) as avg_actual_goals,
    MIN(s.xg) as min_xg,
    MAX(s.xg) as max_xg
FROM soccer_team_game_stats_ext s
JOIN team_game_stats t ON s.game_id = t.game_id AND s.team = t.team
WHERE s.game_id LIKE 'EPL_%' AND s.xg IS NOT NULL
GROUP BY xg_bucket
ORDER BY MIN(s.xg)
""")
print("=== XG DISTRIBUTION BUCKETS ===")
print(distrib.to_string(index=False))
print()

# Check if there are any EPL rows where xg is NULL but game date is >= 2021 (Understat era)
recent_null = db.fetch_df("""
SELECT s.game_id, s.team, u.game_date, u.home_team_name, u.away_team_name
FROM soccer_team_game_stats_ext s
JOIN unified_games u ON s.game_id = u.game_id AND u.sport = 'EPL'
WHERE s.game_id LIKE 'EPL_%' AND s.xg IS NULL AND u.game_date >= '2021-08-01'
ORDER BY u.game_date
""")
print(f"=== RECENT (>=2021) ROWS WITH NULL xg: {len(recent_null)} ===")
if len(recent_null) > 0:
    print(recent_null.head(30).to_string(index=False))
else:
    print("  (none - all 2021+ rows have xg)")
print()

# Check 2021 specifically - the season has partial xg coverage
recent_null_2021 = db.fetch_df("""
SELECT s.game_id, s.team, u.game_date, u.home_team_name, u.away_team_name
FROM soccer_team_game_stats_ext s
JOIN unified_games u ON s.game_id = u.game_id AND u.sport = 'EPL'
WHERE s.game_id LIKE 'EPL_%' AND s.xg IS NULL AND u.game_date >= '2021-08-01' AND u.game_date < '2022-08-01'
ORDER BY u.game_date
""")
print(f"=== 2021-22 season NULL xg: {len(recent_null_2021)} ===")
if len(recent_null_2021) > 0:
    # Check which of these have Understat data - look at the enriched ones for reference
    enriched_2021 = db.fetch_df("""
    SELECT DISTINCT SUBSTRING(game_id FROM 5 FOR 4) as season, COUNT(*) as cnt
    FROM soccer_team_game_stats_ext
    WHERE game_id LIKE 'EPL_2021_%' AND xg IS NOT NULL
    GROUP BY season
    """)
    print("  Enriched 2021 rows:")
    print(enriched_2021.to_string(index=False))

    print("\n  Sample NULL xg in 2021-22 season:")
    print(recent_null_2021.head(20).to_string(index=False))
