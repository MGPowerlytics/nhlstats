#!/usr/bin/env python3
"""
Query NHL stats from DuckDB (read-only, no locks!)
Usage: python query_nhl_stats.py
"""
import duckdb
import sys
from pathlib import Path

# Get database path
db_path = Path(__file__).parent / "data" / "nhlstats.duckdb"

if not db_path.exists():
    print(f"❌ Database not found: {db_path}")
    sys.exit(1)

# Read-only connection - multiple sessions can use this simultaneously
conn = duckdb.connect(str(db_path), read_only=True)

print('🏒 === NHL DATABASE STATS ===')
print(f'📊 Games: {conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]}')
print(f'🏒 Teams: {conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]}')
print(f'👤 Players: {conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]}')
print(f'📈 Game Team Stats: {conn.execute("SELECT COUNT(*) FROM game_team_stats").fetchone()[0]}')
print(f'⭐ Player Game Stats: {conn.execute("SELECT COUNT(*) FROM player_game_stats").fetchone()[0]}')
print(f'🎯 Play Events: {conn.execute("SELECT COUNT(*) FROM play_events").fetchone()[0]}')
print(f'⏱️  Player Shifts: {conn.execute("SELECT COUNT(*) FROM player_shifts").fetchone()[0]}')

print('\n🎮 Sample Games:')
games = conn.execute('''
    SELECT game_date, home_team_name, home_score, away_team_name, away_score
    FROM games 
    ORDER BY game_date DESC
    LIMIT 5
''').fetchall()
for date, home, home_score, away, away_score in games:
    print(f'  {date}: {home} {home_score} vs {away} {away_score}')

print('\n⭐ Top Scorers (All Games):')
scorers = conn.execute('''
    SELECT p.first_name || ' ' || p.last_name as player, 
           SUM(COALESCE(pgs.goals, 0)) as goals,
           SUM(COALESCE(pgs.assists, 0)) as assists,
           SUM(COALESCE(pgs.points, 0)) as points
    FROM player_game_stats pgs
    JOIN players p ON pgs.player_id = p.player_id
    GROUP BY player
    HAVING SUM(COALESCE(pgs.points, 0)) > 0
    ORDER BY points DESC
    LIMIT 10
''').fetchall()

for player, goals, assists, points in scorers:
    print(f'  {player:30} {goals or 0:2.0f}G + {assists or 0:2.0f}A = {points or 0:2.0f}P')

print('\n📊 Team Performance:')
teams = conn.execute('''
    SELECT 
        t.team_name,
        COUNT(*) as games_played,
        SUM(CASE WHEN g.winning_team_id = t.team_id THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN g.losing_team_id = t.team_id THEN 1 ELSE 0 END) as losses
    FROM teams t
    LEFT JOIN games g ON g.home_team_id = t.team_id OR g.away_team_id = t.team_id
    GROUP BY t.team_name
    HAVING games_played > 0
    ORDER BY wins DESC
    LIMIT 10
''').fetchall()

for team, gp, wins, losses in teams:
    print(f'  {team:30} {gp}GP {wins}W {losses}L')

conn.close()
print('\n✅ Query complete! Database accessible from multiple sessions.')
