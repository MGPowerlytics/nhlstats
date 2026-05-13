"""Check team names in DB vs CSV."""
import os
os.environ['POSTGRES_HOST'] = '172.20.0.2'
from plugins.db_manager import DBManager
db = DBManager()

r = db.fetch_df("""
    SELECT DISTINCT s.team
    FROM soccer_team_game_stats_ext s
    JOIN team_game_stats t ON s.game_id=t.game_id AND s.team=t.team
    WHERE t.sport='EPL' AND s.xg IS NOT NULL
    ORDER BY s.team
""")
print('Teams with xg data:')
print(r.to_string(index=False))
