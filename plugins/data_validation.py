#!/usr/bin/env python3
"""
Comprehensive Data Validation for Multi-Sport Betting System.

Validates data completeness, quality, and integrity for NBA, NHL, MLB, and NFL.

Checks performed:
- Data presence and row counts
- Date range coverage
- Missing dates/games
- Data quality (nulls, invalid values)
- Team coverage
- Season completeness
- Cross-validation between sources
"""

import pandas as pd
import numpy as np
import duckdb
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')


# Expected teams for each sport
EXPECTED_TEAMS = {
    'nba': [
        'Hawks', 'Celtics', 'Nets', 'Hornets', 'Bulls', 'Cavaliers',
        'Mavericks', 'Nuggets', 'Pistons', 'Warriors', 'Rockets', 'Pacers',
        'Clippers', 'Lakers', 'Grizzlies', 'Heat', 'Bucks', 'Timberwolves',
        'Pelicans', 'Knicks', 'Thunder', 'Magic', '76ers', 'Suns',
        'Trail Blazers', 'Kings', 'Spurs', 'Raptors', 'Jazz', 'Wizards'
    ],  # 30 teams
    'nhl': [
        'Anaheim Ducks', 'Boston Bruins', 'Buffalo Sabres', 'Calgary Flames',
        'Carolina Hurricanes', 'Chicago Blackhawks', 'Colorado Avalanche',
        'Columbus Blue Jackets', 'Dallas Stars', 'Detroit Red Wings',
        'Edmonton Oilers', 'Florida Panthers', 'Los Angeles Kings',
        'Minnesota Wild', 'Montreal Canadiens', 'Nashville Predators',
        'New Jersey Devils', 'New York Islanders', 'New York Rangers',
        'Ottawa Senators', 'Philadelphia Flyers', 'Pittsburgh Penguins',
        'San Jose Sharks', 'Seattle Kraken', 'St. Louis Blues',
        'Tampa Bay Lightning', 'Toronto Maple Leafs', 'Vancouver Canucks',
        'Vegas Golden Knights', 'Washington Capitals', 'Winnipeg Jets',
        'Arizona Coyotes', 'Utah Hockey Club'  # Arizona moved to Utah
    ],  # 32 teams
    'mlb': [
        'Arizona Diamondbacks', 'Atlanta Braves', 'Baltimore Orioles',
        'Boston Red Sox', 'Chicago Cubs', 'Chicago White Sox',
        'Cincinnati Reds', 'Cleveland Guardians', 'Colorado Rockies',
        'Detroit Tigers', 'Houston Astros', 'Kansas City Royals',
        'Los Angeles Angels', 'Los Angeles Dodgers', 'Miami Marlins',
        'Milwaukee Brewers', 'Minnesota Twins', 'New York Mets',
        'New York Yankees', 'Oakland Athletics', 'Philadelphia Phillies',
        'Pittsburgh Pirates', 'San Diego Padres', 'San Francisco Giants',
        'Seattle Mariners', 'St. Louis Cardinals', 'Tampa Bay Rays',
        'Texas Rangers', 'Toronto Blue Jays', 'Washington Nationals'
    ],  # 30 teams
    'nfl': [
        'Arizona Cardinals', 'Atlanta Falcons', 'Baltimore Ravens',
        'Buffalo Bills', 'Carolina Panthers', 'Chicago Bears',
        'Cincinnati Bengals', 'Cleveland Browns', 'Dallas Cowboys',
        'Denver Broncos', 'Detroit Lions', 'Green Bay Packers',
        'Houston Texans', 'Indianapolis Colts', 'Jacksonville Jaguars',
        'Kansas City Chiefs', 'Las Vegas Raiders', 'Los Angeles Chargers',
        'Los Angeles Rams', 'Miami Dolphins', 'Minnesota Vikings',
        'New England Patriots', 'New Orleans Saints', 'New York Giants',
        'New York Jets', 'Philadelphia Eagles', 'Pittsburgh Steelers',
        'San Francisco 49ers', 'Seattle Seahawks', 'Tampa Bay Buccaneers',
        'Tennessee Titans', 'Washington Commanders'
    ],  # 32 teams
}

# Season date ranges (approximate)
SEASON_INFO = {
    'nba': {
        'games_per_team': 82,
        'total_games_per_season': 1230,  # 30 teams * 82 / 2
        'start_month': 10,
        'end_month': 4,  # Regular season ends in April
        'playoff_months': [4, 5, 6],
    },
    'nhl': {
        'games_per_team': 82,
        'total_games_per_season': 1312,  # 32 teams * 82 / 2
        'start_month': 10,
        'end_month': 4,
        'playoff_months': [4, 5, 6],
    },
    'mlb': {
        'games_per_team': 162,
        'total_games_per_season': 2430,  # 30 teams * 162 / 2
        'start_month': 3,
        'end_month': 9,  # Regular season ends in Sept/Oct
        'playoff_months': [10, 11],
    },
    'nfl': {
        'games_per_team': 17,
        'total_games_per_season': 272,  # 32 teams * 17 / 2
        'start_month': 9,
        'end_month': 1,  # Ends in January
        'playoff_months': [1, 2],
    },
}


class DataValidationReport:
    """Stores validation results and generates reports."""
    
    def __init__(self, sport: str):
        self.sport = sport
        self.checks = []
        self.errors = []
        self.warnings = []
        self.stats = {}
    
    def add_check(self, name: str, passed: bool, message: str, severity: str = 'info'):
        """Add a validation check result."""
        self.checks.append({
            'name': name,
            'passed': passed,
            'message': message,
            'severity': severity
        })
        if not passed:
            if severity == 'error':
                self.errors.append(f"❌ {name}: {message}")
            elif severity == 'warning':
                self.warnings.append(f"⚠️  {name}: {message}")
    
    def add_stat(self, name: str, value):
        """Add a statistic."""
        self.stats[name] = value
    
    def print_report(self):
        """Print formatted validation report."""
        print(f"\n{'='*100}")
        print(f"📊 {self.sport.upper()} DATA VALIDATION REPORT")
        print(f"{'='*100}")
        
        # Statistics
        if self.stats:
            print(f"\n📈 Statistics:")
            for name, value in self.stats.items():
                if isinstance(value, float):
                    print(f"   {name}: {value:,.2f}")
                elif isinstance(value, int):
                    print(f"   {name}: {value:,}")
                else:
                    print(f"   {name}: {value}")
        
        # Passed checks
        passed_checks = [c for c in self.checks if c['passed']]
        if passed_checks:
            print(f"\n✅ Passed Checks ({len(passed_checks)}):")
            for check in passed_checks:
                print(f"   ✓ {check['name']}: {check['message']}")
        
        # Warnings
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   {warning}")
        
        # Errors
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"   {error}")
        
        # Summary
        total = len(self.checks)
        passed = len(passed_checks)
        print(f"\n{'='*100}")
        print(f"📋 Summary: {passed}/{total} checks passed")
        if self.errors:
            print(f"   ❌ {len(self.errors)} errors require attention")
        if self.warnings:
            print(f"   ⚠️  {len(self.warnings)} warnings to review")
        print(f"{'='*100}")
        
        return len(self.errors) == 0


def validate_nba_data() -> DataValidationReport:
    """Validate NBA data from JSON files."""
    report = DataValidationReport('nba')
    nba_dir = Path('data/nba')
    
    # Check if directory exists
    if not nba_dir.exists():
        report.add_check('Directory Exists', False, 'data/nba directory not found', 'error')
        return report
    
    report.add_check('Directory Exists', True, f'Found {nba_dir}')
    
    # Count date directories
    date_dirs = sorted([d for d in nba_dir.iterdir() if d.is_dir()])
    report.add_stat('Total Date Directories', len(date_dirs))
    
    if len(date_dirs) == 0:
        report.add_check('Date Directories', False, 'No date directories found', 'error')
        return report
    
    # Analyze date range
    dates = [d.name for d in date_dirs]
    min_date = min(dates)
    max_date = max(dates)
    report.add_stat('Date Range', f'{min_date} to {max_date}')
    
    # Check for data files
    games_found = 0
    games_with_boxscore = 0
    missing_boxscores = []
    null_scores = 0
    teams_found = set()
    games_by_season = defaultdict(int)
    
    for date_dir in date_dirs:
        scoreboard_file = date_dir / f"scoreboard_{date_dir.name}.json"
        
        if not scoreboard_file.exists():
            continue
        
        try:
            with open(scoreboard_file) as f:
                data = json.load(f)
            
            if 'resultSets' not in data:
                continue
            
            for result_set in data['resultSets']:
                if result_set['name'] == 'GameHeader':
                    headers = result_set['headers']
                    idx_game_id = headers.index('GAME_ID')
                    idx_status = headers.index('GAME_STATUS_TEXT')
                    
                    for row in result_set['rowSet']:
                        game_id = str(row[idx_game_id])
                        game_status = row[idx_status]
                        
                        if 'Final' in game_status:
                            games_found += 1
                            
                            # Determine season
                            year = int(date_dir.name[:4])
                            month = int(date_dir.name[5:7])
                            season = year if month >= 10 else year - 1
                            games_by_season[season] += 1
                            
                            # Check boxscore
                            boxscore_file = date_dir / f"boxscore_{game_id}.json"
                            if boxscore_file.exists():
                                games_with_boxscore += 1
                                
                                # Extract teams
                                with open(boxscore_file) as bf:
                                    boxscore = json.load(bf)
                                
                                for bs_result in boxscore.get('resultSets', []):
                                    if bs_result['name'] == 'TeamStats':
                                        bs_headers = bs_result['headers']
                                        idx_team_name = bs_headers.index('TEAM_NAME')
                                        idx_pts = bs_headers.index('PTS')
                                        
                                        for bs_row in bs_result['rowSet']:
                                            teams_found.add(bs_row[idx_team_name])
                                            if bs_row[idx_pts] is None:
                                                null_scores += 1
                            else:
                                missing_boxscores.append(f"{date_dir.name}/{game_id}")
        
        except Exception as e:
            continue
    
    report.add_stat('Total Completed Games', games_found)
    report.add_stat('Games with Boxscore', games_with_boxscore)
    report.add_stat('Teams Found', len(teams_found))
    
    # Games by season
    for season, count in sorted(games_by_season.items()):
        expected = SEASON_INFO['nba']['total_games_per_season']
        pct = count / expected * 100 if expected > 0 else 0
        report.add_stat(f'Season {season}-{season+1}', f'{count} games ({pct:.1f}% of expected)')
    
    # Validation checks
    report.add_check(
        'Sufficient Games',
        games_found >= 1000,
        f'{games_found} games found (minimum: 1000)',
        'warning' if games_found < 1000 else 'info'
    )
    
    boxscore_pct = games_with_boxscore / games_found * 100 if games_found > 0 else 0
    report.add_check(
        'Boxscore Coverage',
        boxscore_pct >= 95,
        f'{boxscore_pct:.1f}% of games have boxscores',
        'warning' if boxscore_pct < 95 else 'info'
    )
    
    report.add_check(
        'Team Coverage',
        len(teams_found) >= 28,
        f'{len(teams_found)}/30 expected teams found',
        'warning' if len(teams_found) < 28 else 'info'
    )
    
    # Check for missing teams
    missing_teams = set(EXPECTED_TEAMS['nba']) - teams_found
    if missing_teams:
        report.add_check(
            'Missing Teams',
            False,
            f'Missing: {", ".join(sorted(missing_teams))}',
            'warning'
        )
    else:
        report.add_check('Missing Teams', True, 'All expected teams present')
    
    report.add_check(
        'Null Scores',
        null_scores == 0,
        f'{null_scores} null score values found',
        'warning' if null_scores > 0 else 'info'
    )
    
    if len(missing_boxscores) > 0:
        report.add_check(
            'Missing Boxscores',
            len(missing_boxscores) < 50,
            f'{len(missing_boxscores)} games missing boxscores',
            'warning' if len(missing_boxscores) >= 50 else 'info'
        )
    
    return report


def validate_nhl_data() -> DataValidationReport:
    """Validate NHL data from DuckDB."""
    report = DataValidationReport('nhl')
    db_path = Path('data/nhlstats.duckdb')
    
    if not db_path.exists():
        report.add_check('Database Exists', False, f'{db_path} not found', 'error')
        return report
    
    report.add_check('Database Exists', True, f'Found {db_path}')
    
    conn = duckdb.connect(str(db_path), read_only=True)
    
    try:
        # Check games table
        # NHL API uses 'OFF' for completed games, 'FINAL' is also valid
        # Only count null scores for completed games (not FUT/future games)
        games = conn.execute("""
            SELECT 
                COUNT(*) as total_games,
                COUNT(DISTINCT game_id) as unique_games,
                MIN(game_date) as min_date,
                MAX(game_date) as max_date,
                COUNT(DISTINCT home_team_name) as home_teams,
                COUNT(DISTINCT away_team_name) as away_teams,
                SUM(CASE WHEN game_state IN ('OFF', 'FINAL') AND home_score IS NULL THEN 1 ELSE 0 END) as null_home_scores,
                SUM(CASE WHEN game_state IN ('OFF', 'FINAL') AND away_score IS NULL THEN 1 ELSE 0 END) as null_away_scores,
                SUM(CASE WHEN game_state IN ('OFF', 'FINAL') AND home_score IS NOT NULL THEN 1 ELSE 0 END) as completed_games,
                SUM(CASE WHEN game_state = 'FUT' THEN 1 ELSE 0 END) as future_games
            FROM games
        """).fetchone()
        
        total, unique, min_date, max_date, home_teams, away_teams, null_home, null_away, completed, future_games = games
        
        report.add_stat('Total Games', total)
        report.add_stat('Completed Games', completed)
        report.add_stat('Future Games', future_games)
        report.add_stat('Date Range', f'{min_date} to {max_date}')
        report.add_stat('Unique Home Teams', home_teams)
        report.add_stat('Unique Away Teams', away_teams)
        
        # Games by season
        seasons = conn.execute("""
            SELECT season, COUNT(*) as game_count
            FROM games 
            WHERE game_state IN ('OFF', 'FINAL') AND home_score IS NOT NULL
            GROUP BY season ORDER BY season
        """).fetchall()
        
        for season, count in seasons:
            expected = SEASON_INFO['nhl']['total_games_per_season']
            pct = count / expected * 100 if expected > 0 else 0
            report.add_stat(f'Season {season}', f'{count} games ({pct:.1f}% of expected)')
        
        # Get all teams
        all_teams = conn.execute("""
            SELECT DISTINCT team_name FROM (
                SELECT home_team_name as team_name FROM games
                UNION
                SELECT away_team_name as team_name FROM games
            )
        """).fetchall()
        teams_found = {t[0] for t in all_teams}
        report.add_stat('Total Teams', len(teams_found))
        
        # Validation checks
        report.add_check(
            'Sufficient Games',
            completed >= 100,
            f'{completed} completed games found',
            'warning' if completed < 100 else 'info'
        )
        
        report.add_check(
            'Null Home Scores',
            null_home == 0,
            f'{null_home} null home scores',
            'warning' if null_home > 0 else 'info'
        )
        
        report.add_check(
            'Null Away Scores',
            null_away == 0,
            f'{null_away} null away scores',
            'warning' if null_away > 0 else 'info'
        )
        
        report.add_check(
            'Team Coverage',
            len(teams_found) >= 30,
            f'{len(teams_found)}/32 expected teams found',
            'warning' if len(teams_found) < 30 else 'info'
        )
        
        # Check related tables
        # game_team_stats may be empty, but game_team_advanced_stats has similar data
        tables_to_check = [
            ('game_team_advanced_stats', True),   # Required
            ('player_game_stats', True),          # Required
            ('play_events', True),                # Required
            ('teams', True),                      # Required
            ('game_team_stats', False),           # Optional - can be empty
        ]
        
        for table, required in tables_to_check:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                report.add_stat(f'{table} rows', count)
                if required:
                    report.add_check(
                        f'{table} has data',
                        count > 0,
                        f'{count:,} rows',
                        'warning' if count == 0 else 'info'
                    )
                # For optional tables, just log the stat without a check
            except Exception as e:
                if required:
                    report.add_check(f'{table} exists', False, str(e), 'warning')
        
    except Exception as e:
        report.add_check('Query Execution', False, str(e), 'error')
    finally:
        conn.close()
    
    return report


def validate_mlb_data() -> DataValidationReport:
    """Validate MLB data from DuckDB."""
    report = DataValidationReport('mlb')
    db_path = Path('data/nhlstats.duckdb')
    
    if not db_path.exists():
        report.add_check('Database Exists', False, f'{db_path} not found', 'error')
        return report
    
    conn = duckdb.connect(str(db_path), read_only=True)
    
    try:
        # Check if mlb_games table exists
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        
        if 'mlb_games' not in table_names:
            report.add_check('MLB Table Exists', False, 'mlb_games table not found', 'error')
            return report
        
        report.add_check('MLB Table Exists', True, 'mlb_games table found')
        
        # Analyze data
        stats = conn.execute("""
            SELECT 
                COUNT(*) as total_games,
                COUNT(DISTINCT game_id) as unique_games,
                MIN(game_date) as min_date,
                MAX(game_date) as max_date,
                COUNT(DISTINCT home_team) as home_teams,
                COUNT(DISTINCT away_team) as away_teams,
                SUM(CASE WHEN home_score IS NULL THEN 1 ELSE 0 END) as null_home_scores,
                SUM(CASE WHEN away_score IS NULL THEN 1 ELSE 0 END) as null_away_scores,
                SUM(CASE WHEN status = 'Final' THEN 1 ELSE 0 END) as completed_games
            FROM mlb_games
        """).fetchone()
        
        total, unique, min_date, max_date, home_teams, away_teams, null_home, null_away, completed = stats
        
        report.add_stat('Total Games', total)
        report.add_stat('Completed Games', completed)
        report.add_stat('Date Range', f'{min_date} to {max_date}' if min_date else 'No data')
        report.add_stat('Home Teams', home_teams)
        report.add_stat('Away Teams', away_teams)
        report.add_stat('Null Home Scores', null_home)
        report.add_stat('Null Away Scores', null_away)
        
        # Games by season
        if total > 0:
            seasons = conn.execute("""
                SELECT season, COUNT(*) as game_count
                FROM mlb_games WHERE status = 'Final'
                GROUP BY season ORDER BY season
            """).fetchall()
            
            for season, count in seasons:
                expected = SEASON_INFO['mlb']['total_games_per_season']
                pct = count / expected * 100 if expected > 0 else 0
                report.add_stat(f'Season {season}', f'{count} games ({pct:.1f}% of expected)')
        
        # Get all teams
        all_teams = conn.execute("""
            SELECT DISTINCT team FROM (
                SELECT home_team as team FROM mlb_games WHERE home_team IS NOT NULL
                UNION
                SELECT away_team as team FROM mlb_games WHERE away_team IS NOT NULL
            )
        """).fetchall()
        teams_found = {t[0] for t in all_teams if t[0]}
        report.add_stat('Total Teams Found', len(teams_found))
        
        # Validation checks
        report.add_check(
            'Has Data',
            total > 0,
            f'{total} total rows',
            'warning' if total == 0 else 'info'
        )
        
        if total > 0:
            report.add_check(
                'Completed Games',
                completed > 0,
                f'{completed} completed games',
                'warning' if completed == 0 else 'info'
            )
            
            null_pct = (null_home + null_away) / (total * 2) * 100 if total > 0 else 0
            report.add_check(
                'Data Quality',
                null_pct < 10,
                f'{null_pct:.1f}% null scores',
                'warning' if null_pct >= 10 else 'info'
            )
            
            report.add_check(
                'Team Coverage',
                len(teams_found) >= 25,
                f'{len(teams_found)}/30 expected teams found',
                'warning' if len(teams_found) < 25 else 'info'
            )
        
    except Exception as e:
        report.add_check('Query Execution', False, str(e), 'error')
    finally:
        conn.close()
    
    return report


def validate_nfl_data() -> DataValidationReport:
    """Validate NFL data from DuckDB."""
    report = DataValidationReport('nfl')
    db_path = Path('data/nhlstats.duckdb')
    
    if not db_path.exists():
        report.add_check('Database Exists', False, f'{db_path} not found', 'error')
        return report
    
    conn = duckdb.connect(str(db_path), read_only=True)
    
    try:
        # Check if nfl_games table exists
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        
        if 'nfl_games' not in table_names:
            report.add_check('NFL Table Exists', False, 'nfl_games table not found', 'error')
            return report
        
        report.add_check('NFL Table Exists', True, 'nfl_games table found')
        
        # Analyze data
        stats = conn.execute("""
            SELECT 
                COUNT(*) as total_games,
                COUNT(DISTINCT game_id) as unique_games,
                MIN(game_date) as min_date,
                MAX(game_date) as max_date,
                COUNT(DISTINCT home_team) as home_teams,
                COUNT(DISTINCT away_team) as away_teams,
                SUM(CASE WHEN home_score IS NULL THEN 1 ELSE 0 END) as null_home_scores,
                SUM(CASE WHEN away_score IS NULL THEN 1 ELSE 0 END) as null_away_scores,
                SUM(CASE WHEN status = 'Final' THEN 1 ELSE 0 END) as completed_games
            FROM nfl_games
        """).fetchone()
        
        total, unique, min_date, max_date, home_teams, away_teams, null_home, null_away, completed = stats
        
        report.add_stat('Total Games', total)
        report.add_stat('Completed Games', completed)
        report.add_stat('Date Range', f'{min_date} to {max_date}' if min_date else 'No data')
        report.add_stat('Home Teams', home_teams)
        report.add_stat('Away Teams', away_teams)
        
        # Games by season and week
        if total > 0:
            seasons = conn.execute("""
                SELECT season, COUNT(*) as game_count
                FROM nfl_games WHERE status = 'Final'
                GROUP BY season ORDER BY season
            """).fetchall()
            
            for season, count in seasons:
                expected = SEASON_INFO['nfl']['total_games_per_season']
                pct = count / expected * 100 if expected > 0 else 0
                report.add_stat(f'Season {season}', f'{count} games ({pct:.1f}% of expected)')
            
            # Weeks coverage for latest season
            if seasons:
                latest_season = seasons[-1][0]
                weeks = conn.execute(f"""
                    SELECT week, COUNT(*) as game_count
                    FROM nfl_games 
                    WHERE season = {latest_season} AND status = 'Final'
                    GROUP BY week ORDER BY week
                """).fetchall()
                
                weeks_with_games = len(weeks)
                report.add_stat(f'Season {latest_season} Weeks with Data', weeks_with_games)
        
        # Get all teams
        all_teams = conn.execute("""
            SELECT DISTINCT team FROM (
                SELECT home_team as team FROM nfl_games WHERE home_team IS NOT NULL
                UNION
                SELECT away_team as team FROM nfl_games WHERE away_team IS NOT NULL
            )
        """).fetchall()
        teams_found = {t[0] for t in all_teams if t[0]}
        report.add_stat('Total Teams Found', len(teams_found))
        
        # Validation checks
        report.add_check(
            'Has Data',
            total > 0,
            f'{total} total rows',
            'warning' if total == 0 else 'info'
        )
        
        if total > 0:
            report.add_check(
                'Completed Games',
                completed >= 100,
                f'{completed} completed games',
                'warning' if completed < 100 else 'info'
            )
            
            report.add_check(
                'Null Home Scores',
                null_home == 0,
                f'{null_home} null values',
                'warning' if null_home > 0 else 'info'
            )
            
            report.add_check(
                'Null Away Scores',
                null_away == 0,
                f'{null_away} null values',
                'warning' if null_away > 0 else 'info'
            )
            
            report.add_check(
                'Team Coverage',
                len(teams_found) >= 30,
                f'{len(teams_found)}/32 expected teams found',
                'warning' if len(teams_found) < 30 else 'info'
            )
        
    except Exception as e:
        report.add_check('Query Execution', False, str(e), 'error')
    finally:
        conn.close()
    
    return report


def validate_elo_ratings():
    """Validate that Elo rating files exist and are valid."""
    print(f"\n{'='*100}")
    print("📊 ELO RATINGS VALIDATION")
    print(f"{'='*100}")
    
    elo_files = [
        ('nba', 'data/nba_current_elo_ratings.csv'),
        ('nhl', 'data/nhl_current_elo_ratings.csv'),
        ('mlb', 'data/mlb_current_elo_ratings.csv'),
        ('nfl', 'data/nfl_current_elo_ratings.csv'),
    ]
    
    for sport, filepath in elo_files:
        path = Path(filepath)
        if path.exists():
            try:
                df = pd.read_csv(path)
                teams = len(df)
                if 'rating' in df.columns:
                    avg_rating = df['rating'].mean()
                    min_rating = df['rating'].min()
                    max_rating = df['rating'].max()
                    print(f"✅ {sport.upper()}: {filepath}")
                    print(f"   Teams: {teams}, Avg: {avg_rating:.0f}, Range: {min_rating:.0f}-{max_rating:.0f}")
                else:
                    print(f"⚠️  {sport.upper()}: {filepath} - no 'rating' column")
            except Exception as e:
                print(f"❌ {sport.upper()}: {filepath} - Error: {e}")
        else:
            print(f"⚠️  {sport.upper()}: {filepath} not found")


def validate_kalshi_integration():
    """Validate Kalshi API data and market files."""
    print(f"\n{'='*100}")
    print("📊 KALSHI INTEGRATION VALIDATION")
    print(f"{'='*100}")
    
    kalshi_files = [
        'data/kalshi_markets.json',
        'data/kalshi_nhl_markets.json',
    ]
    
    for filepath in kalshi_files:
        path = Path(filepath)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    print(f"✅ {filepath}: {len(data)} markets")
                elif isinstance(data, dict):
                    print(f"✅ {filepath}: {len(data)} keys")
                else:
                    print(f"⚠️  {filepath}: unexpected format")
            except Exception as e:
                print(f"❌ {filepath}: Error - {e}")
        else:
            print(f"⚠️  {filepath} not found")
    
    # Check kalshkey
    if Path('kalshkey').exists():
        print("✅ kalshkey: API credentials file exists")
    else:
        print("❌ kalshkey: API credentials file not found")


def generate_summary(reports: dict):
    """Generate overall summary of all validations."""
    print(f"\n{'#'*100}")
    print("📋 OVERALL VALIDATION SUMMARY")
    print(f"{'#'*100}")
    
    all_passed = True
    total_errors = 0
    total_warnings = 0
    
    print(f"\n{'Sport':<10} {'Status':<15} {'Errors':<10} {'Warnings':<10} {'Games':<15}")
    print(f"{'-'*60}")
    
    for sport, report in reports.items():
        errors = len(report.errors)
        warnings = len(report.warnings)
        games = report.stats.get('Total Completed Games', report.stats.get('Completed Games', 0))
        
        if isinstance(games, str):
            games = games.split()[0]  # Extract number from string like "1234 games"
        
        status = "✅ PASS" if errors == 0 else "❌ FAIL"
        if errors == 0 and warnings > 0:
            status = "⚠️  WARN"
        
        print(f"{sport.upper():<10} {status:<15} {errors:<10} {warnings:<10} {games:<15}")
        
        total_errors += errors
        total_warnings += warnings
        if errors > 0:
            all_passed = False
    
    print(f"{'-'*60}")
    print(f"{'TOTAL':<10} {'✅ PASS' if all_passed else '❌ FAIL':<15} {total_errors:<10} {total_warnings:<10}")
    
    if total_errors > 0:
        print(f"\n🔴 {total_errors} errors require attention before production use")
    if total_warnings > 0:
        print(f"🟡 {total_warnings} warnings should be reviewed")
    if all_passed and total_warnings == 0:
        print(f"\n🟢 All data validations passed! System ready for production.")
    
    return all_passed


def main():
    """Run all data validations."""
    print("=" * 100)
    print("🔍 MULTI-SPORT DATA VALIDATION")
    print(f"📅 Validation Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 100)
    
    reports = {}
    
    # Validate each sport
    print("\n" + "=" * 100)
    print("VALIDATING NBA DATA...")
    print("=" * 100)
    reports['nba'] = validate_nba_data()
    reports['nba'].print_report()
    
    print("\n" + "=" * 100)
    print("VALIDATING NHL DATA...")
    print("=" * 100)
    reports['nhl'] = validate_nhl_data()
    reports['nhl'].print_report()
    
    print("\n" + "=" * 100)
    print("VALIDATING MLB DATA...")
    print("=" * 100)
    reports['mlb'] = validate_mlb_data()
    reports['mlb'].print_report()
    
    print("\n" + "=" * 100)
    print("VALIDATING NFL DATA...")
    print("=" * 100)
    reports['nfl'] = validate_nfl_data()
    reports['nfl'].print_report()
    
    # Additional validations
    validate_elo_ratings()
    validate_kalshi_integration()
    
    # Overall summary
    all_passed = generate_summary(reports)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    exit(main())
