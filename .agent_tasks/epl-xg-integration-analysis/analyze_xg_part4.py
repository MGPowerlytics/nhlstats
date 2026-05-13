#!/usr/bin/env python3
"""Part 4: Investigate the 2021 anomalous coverage."""
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

# The 2021 group has 816 total rows but only 366 enriched.
# It includes games from pre-2021 seasons (2005-2020) that have game_id starting with EPL_2021_
# because the game_id format is EPL_<year>-<month>-<day>_<home>_<away>
# So EPL_2021-01-01_... is January 2021 (2020-21 season), not 2021-22 season
# The enrichment only covers 2021-22 season onward (Aug 2021+).

# Let's verify
count_by_date = db.fetch_df("""
SELECT
    CASE
        WHEN u.game_date < '2021-08-01' THEN '2005-2021 (pre-Understat)'
        WHEN u.game_date >= '2021-08-01' AND u.game_date < '2022-08-01' THEN '2021-22 season'
        WHEN u.game_date >= '2022-08-01' AND u.game_date < '2023-08-01' THEN '2022-23 season'
        WHEN u.game_date >= '2023-08-01' AND u.game_date < '2024-08-01' THEN '2023-24 season'
        WHEN u.game_date >= '2024-08-01' AND u.game_date < '2025-08-01' THEN '2024-25 season'
        WHEN u.game_date >= '2025-08-01' THEN '2025-26 season'
    END as period_label,
    COUNT(*) as total_rows,
    SUM(CASE WHEN s.xg IS NOT NULL THEN 1 ELSE 0 END) as enriched,
    SUM(CASE WHEN s.xg IS NULL THEN 1 ELSE 0 END) as missing
FROM soccer_team_game_stats_ext s
JOIN unified_games u ON s.game_id = u.game_id AND u.sport = 'EPL'
WHERE s.game_id LIKE 'EPL_%'
GROUP BY period_label
ORDER BY period_label
""")
print("=== COVERAGE BY ACTUAL SEASON PERIOD ===")
print(count_by_date.to_string(index=False))
print()

# Now let's also check how many games overall exist for seasons 2021+ that could have Understat data
games_2021_plus = db.fetch_df("""
SELECT
    CASE
        WHEN u.game_date >= '2021-08-01' AND u.game_date < '2022-08-01' THEN '2021-22'
        WHEN u.game_date >= '2022-08-01' AND u.game_date < '2023-08-01' THEN '2022-23'
        WHEN u.game_date >= '2023-08-01' AND u.game_date < '2024-08-01' THEN '2023-24'
        WHEN u.game_date >= '2024-08-01' AND u.game_date < '2025-08-01' THEN '2024-25'
        WHEN u.game_date >= '2025-08-01' THEN '2025-26'
    END as season,
    COUNT(DISTINCT s.game_id) as total_games,
    COUNT(DISTINCT CASE WHEN s.xg IS NOT NULL THEN s.game_id END) as enriched_games,
    COUNT(DISTINCT CASE WHEN s.xg IS NULL THEN s.game_id END) as missing_games
FROM soccer_team_game_stats_ext s
JOIN unified_games u ON s.game_id = u.game_id AND u.sport = 'EPL'
WHERE s.game_id LIKE 'EPL_%' AND u.game_date >= '2021-08-01'
GROUP BY season
ORDER BY season
""")
print("=== GAME-LEVEL COVERAGE (Understat era, 2021-22 onwards) ===")
print(games_2021_plus.to_string(index=False))
print()

# Also check if soccer_team_game_stats_ext has a 'goals' column directly
# From the schema output earlier, it doesn't. The goals come from team_game_stats.points_for
# Let's verify the row-level join works for all enriched rows
join_check = db.fetch_df("""
SELECT COUNT(*) as matching_rows
FROM soccer_team_game_stats_ext s
JOIN team_game_stats t ON s.game_id = t.game_id AND s.team = t.team
WHERE s.game_id LIKE 'EPL_%' AND s.xg IS NOT NULL
""")
print(f"Rows matching between soccer_team_game_stats_ext and team_game_stats (xg NOT NULL): {join_check['matching_rows'][0]}")
print()

# Quick check: how many rows in team_game_stats are EPL?
tgs_epl = db.fetch_df("""
SELECT sport, COUNT(*) as cnt
FROM team_game_stats
GROUP BY sport
ORDER BY cnt DESC
""")
print("=== team_game_stats by sport ===")
print(tgs_epl.to_string(index=False))
