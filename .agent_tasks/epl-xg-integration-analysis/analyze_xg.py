#!/usr/bin/env python3
"""Analyze xg/xga data in soccer_team_game_stats_ext."""
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

# 1. Full schema
schema = db.fetch_df("""
SELECT column_name, data_type, is_nullable, character_maximum_length,
       column_default
FROM information_schema.columns
WHERE table_name = 'soccer_team_game_stats_ext'
ORDER BY ordinal_position
""")
print("=== SCHEMA ===")
print(schema.to_string(index=False))
print()

# 2. Row counts
total = db.fetch_scalar("SELECT COUNT(*) FROM soccer_team_game_stats_ext")
epl_total = db.fetch_scalar("SELECT COUNT(*) FROM soccer_team_game_stats_ext WHERE game_id LIKE 'EPL_%'")
xg_null = db.fetch_scalar("SELECT COUNT(*) FROM soccer_team_game_stats_ext WHERE game_id LIKE 'EPL_%' AND xg IS NULL")
xg_not_null = db.fetch_scalar("SELECT COUNT(*) FROM soccer_team_game_stats_ext WHERE game_id LIKE 'EPL_%' AND xg IS NOT NULL")
xga_null = db.fetch_scalar("SELECT COUNT(*) FROM soccer_team_game_stats_ext WHERE game_id LIKE 'EPL_%' AND xga IS NULL")
xga_not_null = db.fetch_scalar("SELECT COUNT(*) FROM soccer_team_game_stats_ext WHERE game_id LIKE 'EPL_%' AND xga IS NOT NULL")

print("=== ROW COUNTS ===")
print(f"Total rows (all sports): {total}")
print(f"EPL rows: {epl_total}")
print(f"EPL xg NULL: {xg_null} ({xg_null/epl_total*100:.1f}%)" if epl_total else "EPL xg NULL: N/A")
print(f"EPL xg NOT NULL: {xg_not_null} ({xg_not_null/epl_total*100:.1f}%)" if epl_total else "EPL xg NOT NULL: N/A")
print(f"EPL xga NULL: {xga_null} ({xga_null/epl_total*100:.1f}%)" if epl_total else "EPL xga NULL: N/A")
print(f"EPL xga NOT NULL: {xga_not_null} ({xga_not_null/epl_total*100:.1f}%)" if epl_total else "EPL xga NOT NULL: N/A")
print()

# 3. xg/xga descriptive stats
xg_stats = db.fetch_df("""
SELECT
    MIN(xg) as xg_min,
    MAX(xg) as xg_max,
    AVG(xg) as xg_mean,
    STDDEV(xg) as xg_std,
    MIN(xga) as xga_min,
    MAX(xga) as xga_max,
    AVG(xga) as xga_mean,
    STDDEV(xga) as xga_std
FROM soccer_team_game_stats_ext
WHERE game_id LIKE 'EPL_%' AND xg IS NOT NULL
""")
print("=== XG/XGA DESCRIPTIVE STATS (EPL, non-NULL) ===")
print(xg_stats.to_string(index=False))
print()

# 4. Season breakdown
season_stats = db.fetch_df("""
SELECT
    SUBSTRING(game_id FROM 5 FOR 4) as season,
    COUNT(*) as total_rows,
    SUM(CASE WHEN xg IS NOT NULL THEN 1 ELSE 0 END) as xg_filled,
    SUM(CASE WHEN xg IS NULL THEN 1 ELSE 0 END) as xg_missing,
    ROUND(AVG(xg)::numeric, 3) as avg_xg,
    ROUND(AVG(xga)::numeric, 3) as avg_xga
FROM soccer_team_game_stats_ext
WHERE game_id LIKE 'EPL_%'
GROUP BY SUBSTRING(game_id FROM 5 FOR 4)
ORDER BY season
""")
print("=== SEASON BREAKDOWN ===")
print(season_stats.to_string(index=False))
print()

# 5. Check for NULL-xg rows that could be enriched - are there any left?
null_xg_rows = db.fetch_df("""
SELECT s.game_id, s.team, s.xg, s.xga,
    u.game_date, u.home_team_name, u.away_team_name
FROM soccer_team_game_stats_ext s
JOIN unified_games u ON s.game_id = u.game_id AND u.sport = 'EPL'
WHERE s.game_id LIKE 'EPL_%' AND s.xg IS NULL
ORDER BY u.game_date
""")
print(f"=== ROWS WITH NULL xg (possible enrichment targets): {len(null_xg_rows)} ===")
if len(null_xg_rows) > 0:
    print(null_xg_rows.head(50).to_string(index=False))
else:
    print("  (none - all rows enriched)")
print()

# 6. Correlation analysis: xg/xga vs actual goals
# Check what tables have goals data
tables = db.fetch_df("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
print("=== ALL TABLES ===")
for t in tables['table_name']:
    print(f"  {t}")
print()

# Check team_game_stats for goals info
tgs_cols = db.fetch_df("""
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'team_game_stats'
ORDER BY ordinal_position
""")
print("=== team_game_stats COLUMNS ===")
print(tgs_cols.to_string(index=False))
print()

# Check unified_games for goals
ug_cols = db.fetch_df("""
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'unified_games'
ORDER BY ordinal_position
""")
print("=== unified_games COLUMNS ===")
print(ug_cols.to_string(index=False))
print()

# 7. Do the correlation: join soccer_team_game_stats_ext with unified_games
# For each game, sum home/away xg and compare to actual score
corr_data = db.fetch_df("""
WITH game_xg AS (
    SELECT
        s.game_id,
        MAX(CASE WHEN s.is_home THEN s.xg END) as home_xg,
        MAX(CASE WHEN s.is_home THEN s.xga END) as home_xga,
        MAX(CASE WHEN NOT s.is_home THEN s.xg END) as away_xg,
        MAX(CASE WHEN NOT s.is_home THEN s.xga END) as away_xga,
        MAX(CASE WHEN s.is_home THEN s.goals END) as home_goals,
        MAX(CASE WHEN NOT s.is_home THEN s.goals END) as away_goals
    FROM soccer_team_game_stats_ext s
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
    ROUND(AVG(home_goals + away_goals)::numeric, 3) as avg_total_goals
FROM game_xg
""")
print("=== XG vs ACTUAL GOALS CORRELATION ===")
print(corr_data.to_string(index=False))
print()

# 8. Per-season correlations
per_season_corr = db.fetch_df("""
WITH game_xg AS (
    SELECT
        s.game_id,
        SUBSTRING(s.game_id FROM 5 FOR 4) as season,
        MAX(CASE WHEN s.is_home THEN s.xg END) as home_xg,
        MAX(CASE WHEN s.is_home THEN s.goals END) as home_goals,
        MAX(CASE WHEN NOT s.is_home THEN s.xg END) as away_xg,
        MAX(CASE WHEN NOT s.is_home THEN s.goals END) as away_goals
    FROM soccer_team_game_stats_ext s
    WHERE s.game_id LIKE 'EPL_%' AND s.xg IS NOT NULL
    GROUP BY s.game_id
)
SELECT
    season,
    COUNT(*) as n_games,
    ROUND(CORR(home_xg, home_goals)::numeric, 4) as corr_home_xg,
    ROUND(CORR(away_xg, away_goals)::numeric, 4) as corr_away_xg,
    ROUND(CORR(home_xg + away_xg, home_goals + away_goals)::numeric, 4) as corr_total
FROM game_xg
GROUP BY season
ORDER BY season
""")
print("=== PER-SEASON CORRELATIONS ===")
print(per_season_corr.to_string(index=False))
print()

# 9. Distribution buckets for xg
distrib = db.fetch_df("""
SELECT
    CASE
        WHEN xg < 0.5 THEN '< 0.5'
        WHEN xg < 1.0 THEN '0.5-1.0'
        WHEN xg < 1.5 THEN '1.0-1.5'
        WHEN xg < 2.0 THEN '1.5-2.0'
        WHEN xg < 2.5 THEN '2.0-2.5'
        WHEN xg < 3.0 THEN '2.5-3.0'
        ELSE '3.0+'
    END as xg_bucket,
    COUNT(*) as n_rows,
    ROUND(AVG(goals)::numeric, 3) as avg_actual_goals
FROM soccer_team_game_stats_ext
WHERE game_id LIKE 'EPL_%' AND xg IS NOT NULL
GROUP BY xg_bucket
ORDER BY MIN(xg)
""")
print("=== XG DISTRIBUTION BUCKETS ===")
print(distrib.to_string(index=False))
