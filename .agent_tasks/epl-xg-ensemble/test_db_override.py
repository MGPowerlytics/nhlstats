"""Test if POSTGRES_HOST env var works for DB connection."""
import os
os.environ['POSTGRES_HOST'] = '172.20.0.2'
from plugins.db_manager import DBManager
db = DBManager()
r = db.fetch_df('SELECT COUNT(*) as cnt FROM soccer_team_game_stats_ext WHERE xg IS NOT NULL')
print(r)
