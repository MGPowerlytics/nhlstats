"""Check DB schema for xg-related tables."""
import os
os.environ['POSTGRES_HOST'] = '172.20.0.2'
from plugins.db_manager import DBManager

db = DBManager()

print("=== soccer_team_game_stats_ext ===")
r = db.fetch_df('SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = \'soccer_team_game_stats_ext\' ORDER BY ordinal_position')
print(r.to_string(index=False))

print("\n=== team_game_stats ===")
r = db.fetch_df('SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = \'team_game_stats\' ORDER BY ordinal_position')
print(r.to_string(index=False))

print("\n=== epl_games ===")
r = db.fetch_df('SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = \'epl_games\' ORDER BY ordinal_position')
print(r.to_string(index=False))

print("\n=== Sample soccer_team_game_stats_ext xg data ===")
r = db.fetch_df("""
    SELECT s.game_id, s.team, s.xg, s.xga, t.is_home, t.game_date, t.points_for, t.points_against
    FROM soccer_team_game_stats_ext s
    JOIN team_game_stats t ON s.game_id = t.game_id AND s.team = t.team
    WHERE s.xg IS NOT NULL AND t.sport = 'EPL'
    LIMIT 10
""")
print(r.to_string(index=False))

print("\n=== Count by sport ===")
r = db.fetch_df("""
    SELECT t.sport, COUNT(*) as rows, COUNT(s.xg) as xg_filled
    FROM soccer_team_game_stats_ext s
    JOIN team_game_stats t ON s.game_id = t.game_id AND s.team = t.team
    GROUP BY t.sport
""")
print(r.to_string(index=False))

print("\n=== EPL games count by season ===")
r = db.fetch_df("""
    SELECT season, COUNT(*) as games
    FROM epl_games
    GROUP BY season
    ORDER BY season
""")
print(r.to_string(index=False))
