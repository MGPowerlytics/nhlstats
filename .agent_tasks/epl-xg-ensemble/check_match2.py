"""Check how well CSV games match DB xg data."""
import os
os.environ['POSTGRES_HOST'] = '172.20.0.2'
from plugins.db_manager import DBManager
db = DBManager()

import pandas as pd

# Get all EPL xg data with game date
r = db.fetch_df("""
    SELECT t.game_id, t.game_date::text as game_date, s.team, s.xg, s.xga, t.is_home,
           t.points_for, t.points_against, t.opponent
    FROM soccer_team_game_stats_ext s
    JOIN team_game_stats t ON s.game_id = t.game_id AND s.team = t.team
    WHERE t.sport = 'EPL' AND s.xg IS NOT NULL
    ORDER BY t.game_date
""")
print(f"Total xg rows: {len(r)}")

# Build lookup by (game_date, team)
r['key'] = r['game_date'] + '_' + r['team']
print(f"Lookup keys: {len(r)}")

# Check CSV for 2122
csv = pd.read_csv('data/epl/E0_2122.csv')
csv['DateParsed'] = pd.to_datetime(csv['Date'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
csv = csv.dropna(subset=['DateParsed'])
csv['DateStr'] = csv['DateParsed'].dt.strftime('%Y-%m-%d')

# For each CSV row, check if we can find xg for home and away
matched = 0
unmatched = 0
for _, row in csv.iterrows():
    home_key = row['DateStr'] + '_' + str(row['HomeTeam'])
    away_key = row['DateStr'] + '_' + str(row['AwayTeam'])
    home_match = r[r['key'] == home_key]
    away_match = r[r['key'] == away_key]
    if len(home_match) > 0 and len(away_match) > 0:
        matched += 1
    else:
        if unmatched < 5:
            print(f"Unmatched: {row['DateStr']} {row['HomeTeam']} vs {row['AwayTeam']} | home_match={len(home_match)} away_match={len(away_match)}")
        unmatched += 1

print(f"\n2122 season: {matched} matched, {unmatched} unmatched out of {len(csv)}")

# Check 2223
csv2 = pd.read_csv('data/epl/E0_2223.csv')
csv2['DateParsed'] = pd.to_datetime(csv2['Date'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
csv2 = csv2.dropna(subset=['DateParsed'])
csv2['DateStr'] = csv2['DateParsed'].dt.strftime('%Y-%m-%d')

matched2 = 0
unmatched2 = 0
for _, row in csv2.iterrows():
    home_key = row['DateStr'] + '_' + str(row['HomeTeam'])
    away_key = row['DateStr'] + '_' + str(row['AwayTeam'])
    home_match = r[r['key'] == home_key]
    away_match = r[r['key'] == away_key]
    if len(home_match) > 0 and len(away_match) > 0:
        matched2 += 1
    else:
        unmatched2 += 1

print(f"2223 season: {matched2} matched, {unmatched2} unmatched out of {len(csv2)}")

# Check 2324
csv3 = pd.read_csv('data/epl/E0_2324.csv')
csv3['DateParsed'] = pd.to_datetime(csv3['Date'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
csv3 = csv3.dropna(subset=['DateParsed'])
csv3['DateStr'] = csv3['DateParsed'].dt.strftime('%Y-%m-%d')

matched3 = 0
unmatched3 = 0
for _, row in csv3.iterrows():
    home_key = row['DateStr'] + '_' + str(row['HomeTeam'])
    away_key = row['DateStr'] + '_' + str(row['AwayTeam'])
    home_match = r[r['key'] == home_key]
    away_match = r[r['key'] == away_key]
    if len(home_match) > 0 and len(away_match) > 0:
        matched3 += 1
    else:
        unmatched3 += 1

print(f"2324 season: {matched3} matched, {unmatched3} unmatched out of {len(csv3)}")
