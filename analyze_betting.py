#!/usr/bin/env python3
"""
Betting Analysis - NHL Win Probability

Uses DuckDB read-only connection for concurrent access
"""
import duckdb
from pathlib import Path

db_path = Path(__file__).parent / "data" / "nhlstats.duckdb"
conn = duckdb.connect(str(db_path), read_only=True)

print("🎲 === BETTING ANALYSIS === ")

# Recent team performance
print("\n📊 Team Win % (Last 10 Games):")
results = conn.execute('''
    WITH recent_games AS (
        SELECT 
            t.team_name,
            g.game_id,
            g.game_date,
            CASE WHEN g.winning_team_id = t.team_id THEN 1 ELSE 0 END as won
        FROM teams t
        JOIN games g ON (g.home_team_id = t.team_id OR g.away_team_id = t.team_id)
        WHERE g.winning_team_id IS NOT NULL
        ORDER BY g.game_date DESC
    ),
    team_records AS (
        SELECT 
            team_name,
            COUNT(*) as games,
            SUM(won) as wins,
            ROUND(100.0 * SUM(won) / COUNT(*), 1) as win_pct
        FROM (
            SELECT team_name, won,
                   ROW_NUMBER() OVER (PARTITION BY team_name ORDER BY rowid DESC) as rn
            FROM recent_games
        )
        WHERE rn <= 10
        GROUP BY team_name
    )
    SELECT * FROM team_records
    WHERE games >= 5
    ORDER BY win_pct DESC
    LIMIT 10
''').fetchall()

for team, games, wins, win_pct in results:
    print(f"  {team:30} {wins}-{games-wins:2} ({win_pct}%)")

# High scoring games
print("\n🔥 Highest Scoring Games:")
high_scoring = conn.execute('''
    SELECT 
        game_date,
        home_team_name,
        home_score,
        away_team_name,
        away_score,
        home_score + away_score as total_goals
    FROM games
    WHERE home_score IS NOT NULL
    ORDER BY total_goals DESC
    LIMIT 10
''').fetchall()

for date, home, h_score, away, a_score, total in high_scoring:
    print(f"  {date}: {home} {h_score} vs {away} {a_score} (Total: {total})")

# Player scoring trends
print("\n⭐ Hot Players (Last 5 Games):")
hot_players = conn.execute('''
    WITH recent_player_games AS (
        SELECT 
            p.first_name || ' ' || p.last_name as player,
            pgs.game_id,
            pgs.goals,
            pgs.points,
            g.game_date
        FROM player_game_stats pgs
        JOIN players p ON pgs.player_id = p.player_id
        JOIN games g ON pgs.game_id = g.game_id
        ORDER BY g.game_date DESC
    )
    SELECT 
        player,
        SUM(goals) as goals_last_5,
        SUM(points) as points_last_5
    FROM (
        SELECT player, goals, points,
               ROW_NUMBER() OVER (PARTITION BY player ORDER BY rowid DESC) as rn
        FROM recent_player_games
    )
    WHERE rn <= 5
    GROUP BY player
    HAVING SUM(points) >= 5
    ORDER BY points_last_5 DESC
    LIMIT 10
''').fetchall()

for player, goals, points in hot_players:
    print(f"  {player:30} {goals or 0:.0f}G {points or 0:.0f}P (last 5 games)")

conn.close()
print("\n✅ Analysis complete - ready for betting insights!")
