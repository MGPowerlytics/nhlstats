"""Check how well CSV games match DB xg data."""
import os
os.environ['POSTGRES_HOST'] = '172.20.0.2'
from plugins.db_manager import DBManager
db = DBManager()

# Get all EPL xg data
r = db.fetch_df("""
    SELECT t.game_date::text as game_date, s.team, s.xg, s.xga, t.is_home
    FROM soccer_team_game_stats_ext s
    JOIN team_game_stats t ON s.game_id = t.game_id AND s.team = t.team
    WHERE t.sport = 'EPL' AND s.xg IS NOT NULL
    ORDER BY t.game_date
""")
print(f"Total xg rows: {len(r)}")
print(r.head(10).to_string(index=False))
print()

# Check distinct games (by date, team pair)
r['key'] = r['game_date'] + '_' + r['team']
print(f"Distinct date+team combos: {r['key'].nunique()}")

# Show date range
print(f"Date range: {r['game_date'].min()} to {r['game_date'].max()}")

# Check the CSV for 2122 season has corresponding xg
import pandas as pd
csv = pd.read_csv('data/epl/E0_2122.csv')
csv['DateParsed'] = pd.to_datetime(csv['Date'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
csv = csv.dropna(subset=['DateParsed'])
print(f"\nCSV 2122 dates: {csv['DateParsed'].min()} to {csv['DateParsed'].max()}")
print(f"CSV 2122 rows: {len(csv)}")

# Count games that could be matched
xg_dates = set(r['game_date'].unique())
csv_dates = set(d.strftime('%Y-%m-%d') for d in csv['DateParsed'])
overlap = xg_dates & csv_dates
print(f"Overlapping dates: {len(overlap)}")
print(f"CSV-only dates: {len(csv_dates - overlap)}")
print(f"XG-only dates: {len(xg_dates - overlap)}")
