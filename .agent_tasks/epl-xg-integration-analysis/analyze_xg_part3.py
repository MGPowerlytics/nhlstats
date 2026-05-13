#!/usr/bin/env python3
"""Part 3: Additional checks on enrichment coverage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from plugins.db_manager import DBManager

db = DBManager(
    connection_string="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
)

# Check distribution more carefully - game_id format
seasons = db.fetch_df("""
SELECT
    SUBSTRING(game_id FROM 5 FOR 4) as season,
    COUNT(*) as total,
    SUM(CASE WHEN xg IS NOT NULL THEN 1 ELSE 0 END) as enriched,
    SUM(CASE WHEN xg IS NULL THEN 1 ELSE 0 END) as missing,
    ROUND(AVG(xg)::numeric, 3) as avg_xg,
    ROUND(AVG(xga)::numeric, 3) as avg_xga
FROM soccer_team_game_stats_ext
WHERE game_id LIKE 'EPL_%'
GROUP BY SUBSTRING(game_id FROM 5 FOR 4)
ORDER BY season
""")
print("=== SEASON DISTRIBUTION ===")
print(seasons.to_string(index=False))
print()

# Count distinct games
games = db.fetch_df("""
SELECT
    COUNT(DISTINCT game_id) as total_epl_games,
    COUNT(DISTINCT CASE WHEN xg IS NOT NULL THEN game_id END) as games_with_xg,
    COUNT(DISTINCT CASE WHEN xg IS NULL THEN game_id END) as games_without_xg
FROM soccer_team_game_stats_ext
WHERE game_id LIKE 'EPL_%'
""")
print("=== DISTINCT GAMES ===")
print(games.to_string(index=False))
print()

# Progress file
progress_path = Path("data/understat_enrichment_progress.json")
if progress_path.exists():
    progress = json.loads(progress_path.read_text())
    print("=== UNDERSTAT ENRICHMENT PROGRESS ===")
    for k, v in sorted(progress.items()):
        print(f"  Season {k}: {v}")
print()

# Show season-by-season with game_id patterns to understand coverage
# The 2021 season has 183 enriched games but 816 total rows
# (408 games since 2 rows per game). So only 183/408 = 45% enriched?
# But 2022=361/361 (100%). What's going on with 2021?
pattern_2021 = db.fetch_df("""
SELECT DISTINCT
    SUBSTRING(game_id FROM 5 FOR 9) as game_prefix,
    u.game_date
FROM soccer_team_game_stats_ext s
JOIN unified_games u ON s.game_id = u.game_id
WHERE s.game_id LIKE 'EPL_2021_%'
ORDER BY u.game_date
LIMIT 20
""")
print("=== 2021 game date range ===")
print(pattern_2021.to_string(index=False))
print()

# Count 2021 games by date range
count_2021 = db.fetch_df("""
SELECT
    CASE
        WHEN u.game_date < '2021-08-01' THEN 'pre-2021-season'
        WHEN u.game_date >= '2021-08-01' AND u.game_date < '2022-08-01' THEN '2021-22 season'
        WHEN u.game_date >= '2022-08-01' THEN '2022+'
    END as period,
    COUNT(*) as rows,
    SUM(CASE WHEN s.xg IS NOT NULL THEN 1 ELSE 0 END) as enriched,
    SUM(CASE WHEN s.xg IS NULL THEN 1 ELSE 0 END) as missing
FROM soccer_team_game_stats_ext s
JOIN unified_games u ON s.game_id = u.game_id
WHERE s.game_id LIKE 'EPL_2021_%'
GROUP BY period
ORDER BY period
""")
print("=== 2021 games by period ===")
print(count_2021.to_string(index=False))
