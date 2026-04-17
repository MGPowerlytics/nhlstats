"""
Team Factors Data Pipeline
Fetches and stores daily team-level statistics for use in probability adjustments.
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


def load_historical_team_factors() -> pd.DataFrame:
    """
    Load pre-computed team factors from CSV file.

    This is the primary data source since MLB Stats API requires
    specific season timing. Historical data is pre-fetched and stored.
    """
    # Try multiple locations for team factors data
    possible_paths = [
        Path("/mnt/data2/nhlstats/data/mlb_team_factors.csv"),
        Path("/mnt/data2/nhlstats/plugins/data/mlb_team_factors.csv"),
        Path("data/mlb_team_factors.csv"),
    ]

    for path in possible_paths:
        if path.exists():
            logger.info(f"Loading team factors from {path}")
            df = pd.read_csv(path)
            df['game_date'] = pd.to_datetime(df['game_date'])
            return df

    logger.warning("No historical team factors file found")
    return pd.DataFrame()


def fetch_mlb_team_stats():
    """
    Fetch daily team statistics from MLB Stats API.
    Falls back to historical data if current season stats unavailable.
    """
    # First try to load historical data
    historical_df = load_historical_team_factors()
    if not historical_df.empty:
        # Update date to today for consistency
        historical_df = historical_df.copy()
        historical_df['game_date'] = datetime.now().date()
        return historical_df

    # If no historical data, try API
    teams = []
    current_year = datetime.now().year
    # Use last season's stats (MLB season runs Apr-Oct, so Jan-Mar should use previous year)
    month = datetime.now().month
    season_year = current_year - 1 if month <= 3 else current_year

    url = "https://statsapi.mlb.com/api/v1/teams"
    params = {'sportId': 1, 'season': season_year}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        for team in data.get('teams', []):
            team_id = f"mlb_{team['id']}"
            stats_url = f"https://statsapi.mlb.com/api/v1/teams/{team['id']}/stats"

            # Try multiple seasons
            hitting_stats = {}
            pitching_stats = {}

            for try_season in [season_year, season_year - 1, season_year - 2]:
                # Hitting
                if not hitting_stats:
                    try:
                        hitting_params = {'season': try_season, 'group': 'hitting'}
                        hitting_response = requests.get(stats_url, params=hitting_params, timeout=30)
                        if hitting_response.status_code == 200:
                            hitting_data = hitting_response.json()
                            hitting_stats = hitting_data.get('stats', [{}])[0].get('stats', {})
                    except:
                        pass

                # Pitching
                if not pitching_stats:
                    try:
                        pitching_params = {'season': try_season, 'group': 'pitching'}
                        pitching_response = requests.get(stats_url, params=pitching_params, timeout=30)
                        if pitching_response.status_code == 200:
                            pitching_data = pitching_response.json()
                            pitching_stats = pitching_data.get('stats', [{}])[0].get('stats', {})
                    except:
                        pass

            # Only add if we have at least some stats
            if hitting_stats or pitching_stats:
                teams.append({
                    'team_id': team_id,
                    'game_date': datetime.now().date(),
                    'season': season_year,
                    'team_name': team.get('name', ''),
                    'venue': team.get('venue', {}).get('name', ''),
                    'runs_per_game': hitting_stats.get('runsPerGame'),
                    'obp': hitting_stats.get('onBasePercentage'),
                    'slg': hitting_stats.get('sluggingPercentage'),
                    'ops': hitting_stats.get('ops'),
                    'wOBA': hitting_stats.get('wOBA'),
                    'wRC_plus': hitting_stats.get('wRCPlus'),
                    'era': pitching_stats.get('era'),
                    'fip': pitching_stats.get('fip'),
                    'whip': pitching_stats.get('whip'),
                    'strikeouts_per_nine': pitching_stats.get('strikeoutsPer9'),
                    'walks_per_nine': pitching_stats.get('walksPer9'),
                    'defensive_runs_saved': None,
                    'ultimate_zone_rating': None,
                })

    except Exception as e:
        logger.error(f"Failed to fetch teams from API: {e}")

    return pd.DataFrame(teams) if teams else load_historical_team_factors()


def store_team_factors(df: pd.DataFrame):
    """Store team factors in the database."""
    try:
        from plugins.db_manager import default_db
    except ImportError:
        from db_manager import default_db

    if df.empty:
        logger.warning("No team factors to store")
        return

    # Ensure game_date is a string for SQL
    df = df.copy()
    df['game_date'] = df['game_date'].astype(str)

    for _, row in df.iterrows():
        query = """
        INSERT INTO team_factors (
            team_id, game_date, season, team_name, venue,
            runs_per_game, obp, slg, ops, wOBA, wRC_plus,
            era, fip, whip, strikeouts_per_nine, walks_per_nine,
            defensive_runs_saved, ultimate_zone_rating
        ) VALUES (
            :team_id, :game_date, :season, :team_name, :venue,
            :runs_per_game, :obp, :slg, :ops, :wOBA, :wRC_plus,
            :era, :fip, :whip, :strikeouts_per_nine, :walks_per_nine,
            :defensive_runs_saved, :ultimate_zone_rating
        )
        ON CONFLICT (team_id, game_date) DO UPDATE SET
            runs_per_game = EXCLUDED.runs_per_game,
            obp = EXCLUDED.obp,
            slg = EXCLUDED.slg,
            ops = EXCLUDED.ops,
            wOBA = EXCLUDED.wOBA,
            wRC_plus = EXCLUDED.wRC_plus,
            era = EXCLUDED.era,
            fip = EXCLUDED.fip,
            whip = EXCLUDED.whip,
            strikeouts_per_nine = EXCLUDED.strikeouts_per_nine,
            walks_per_nine = EXCLUDED.walks_per_nine
        """
        try:
            default_db.execute(query, row.to_dict())
        except Exception as e:
            logger.error(f"Failed to insert team factors for {row['team_id']}: {e}")

    logger.info(f"Stored {len(df)} team factor records")


def fetch_team_factors(sport: str, date: str = None):
    """
    Airflow task to fetch team factors for MLB.

    Args:
        sport: Sport name (only 'mlb' supported)
        date: Optional date string (not currently used, maintained for API compatibility)
    """
    if sport != 'mlb':
        logger.info(f"Skipping team factors fetch for sport: {sport}")
        return

    try:
        df = fetch_mlb_team_stats()
        if len(df) > 0:
            store_team_factors(df)
            logger.info(f"Fetched and stored {len(df)} team factor records")
        else:
            logger.warning("No team factors data to store")
    except Exception as e:
        logger.error(f"Failed to fetch team factors: {e}")
        raise


def fetch_team_factors_for_game(sport: str, game_date: str, home_team: str, away_team: str) -> Dict:
    """
    Fetch team factors for a specific game.

    Returns:
        Dictionary with home_adjustment and away_adjustment.
    """
    try:
        from plugins.db_manager import default_db
    except ImportError:
        from db_manager import default_db

    # Query for most recent team factors for both teams
    query = """
    SELECT
        tf_home.team_id as home_team_id,
        tf_home.ops as home_ops,
        tf_home.era as home_era,
        tf_home.runs_per_game as home_runs,
        tf_away.ops as away_ops,
        tf_away.era as away_era,
        tf_away.runs_per_game as away_runs
    FROM team_factors tf_home
    LEFT JOIN team_factors tf_away
        ON tf_away.team_id = :away_team
        AND tf_away.game_date = tf_home.game_date
    WHERE tf_home.team_id = :home_team
        AND tf_home.game_date <= :game_date
    ORDER BY tf_home.game_date DESC
    LIMIT 1
    """

    params = {
        'home_team': home_team,
        'away_team': away_team,
        'game_date': game_date
    }

    result = default_db.fetch_df(query, params)

    if result.empty or result.iloc[0]['home_ops'] is None:
        logger.warning(f"No team factors found for {home_team} vs {away_team}")
        return {'home_adjustment': 0.0, 'away_adjustment': 0.0}

    row = result.iloc[0]

    # Calculate adjustments based on OPS and ERA differentials
    # Normalize by league average (assume ~0.750 OPS, ~4.50 ERA)
    league_avg_ops = 0.750
    league_avg_era = 4.50

    home_ops_adj = (row['home_ops'] - league_avg_ops) if row['home_ops'] else 0
    away_ops_adj = (row['away_ops'] - league_avg_ops) if row['away_ops'] else 0
    home_era_adj = (league_avg_era - row['home_era']) if row['home_era'] else 0  # Lower ERA is better
    away_era_adj = (league_avg_era - row['away_era']) if row['away_era'] else 0

    # Combine OPS and ERA adjustments (weight OPS more)
    home_adjustment = (home_ops_adj * 0.6 + home_era_adj * 0.4) / 10
    away_adjustment = (away_ops_adj * 0.6 + away_era_adj * 0.4) / 10

    # Cap adjustments at +/- 5%
    home_adjustment = min(max(home_adjustment, -0.05), 0.05)
    away_adjustment = min(max(away_adjustment, -0.05), 0.05)

    return {
        'home_adjustment': home_adjustment,
        'away_adjustment': away_adjustment,
        'home_ops': row['home_ops'],
        'away_ops': row['away_ops'],
        'home_era': row['home_era'],
        'away_era': row['away_era']
    }


def create_team_factors_table():
    """Create team_factors table if it doesn't exist."""
    try:
        from plugins.db_manager import default_db
    except ImportError:
        from db_manager import default_db

    query = """
    CREATE TABLE IF NOT EXISTS team_factors (
        factor_id SERIAL PRIMARY KEY,
        team_id VARCHAR NOT NULL,
        game_date DATE NOT NULL,
        season INTEGER,
        team_name VARCHAR,
        venue VARCHAR,
        runs_per_game DECIMAL(5,3),
        obp DECIMAL(5,3),
        slg DECIMAL(5,3),
        ops DECIMAL(5,3),
        wOBA DECIMAL(5,3),
        wRC_plus INTEGER,
        era DECIMAL(5,3),
        fip DECIMAL(5,3),
        whip DECIMAL(5,3),
        strikeouts_per_nine DECIMAL(5,2),
        walks_per_nine DECIMAL(5,2),
        defensive_runs_saved INTEGER,
        ultimate_zone_rating DECIMAL(5,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(team_id, game_date)
    );
    """
    default_db.execute(query)
    logger.info("team_factors table created or already exists")


__all__ = [
    'fetch_mlb_team_stats',
    'store_team_factors',
    'fetch_team_factors',
    'fetch_team_factors_for_game',
    'create_team_factors_table',
    'load_historical_team_factors'
]
