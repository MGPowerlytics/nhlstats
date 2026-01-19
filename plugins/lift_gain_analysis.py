#!/usr/bin/env python3
"""
Lift/Gain Analysis by Probability Decile for All Sports.

Calculates cumulative home team wins, cumulative games, gain %, and lift
by decile of Elo probability prediction.

Supports:
- Overall analysis (all historical data)
- Current season to date analysis
"""

import pandas as pd
import numpy as np
import duckdb
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict


# Sport configurations
SPORT_CONFIG = {
    "nba": {
        "elo_module": "nba_elo_rating",
        "elo_class": "NBAEloRating",
        "k_factor": 20,
        "home_advantage": 100,
        "data_source": "json",  # Load from JSON files
        "season_start_month": 10,  # October
    },
    "nhl": {
        "elo_module": "nhl_elo_rating",
        "elo_class": "NHLEloRating",
        "k_factor": 10,
        "home_advantage": 50,
        "data_source": "duckdb",
        "season_start_month": 10,  # October
    },
    "mlb": {
        "elo_module": "mlb_elo_rating",
        "elo_class": "MLBEloRating",
        "k_factor": 20,
        "home_advantage": 50,
        "data_source": "duckdb",
        "season_start_month": 3,  # March
    },
    "nfl": {
        "elo_module": "nfl_elo_rating",
        "elo_class": "NFLEloRating",
        "k_factor": 20,
        "home_advantage": 65,
        "data_source": "duckdb",
        "season_start_month": 9,  # September
    },
    "epl": {
        "elo_module": "epl_elo_rating",
        "elo_class": "EPLEloRating",
        "k_factor": 20,
        "home_advantage": 60,
        "data_source": "csv",
        "season_start_month": 8,  # August
    },
    "ncaab": {
        "elo_module": "ncaab_elo_rating",
        "elo_class": "NCAABEloRating",
        "k_factor": 20,
        "home_advantage": 100,
        "data_source": "csv_ncaab",
        "season_start_month": 11,  # November
    },
}


def get_current_season_start(sport: str) -> str:
    """
    Get the start date of the current season for a sport.

    Returns date string in YYYY-MM-DD format.
    """
    config = SPORT_CONFIG[sport]
    season_start_month = config["season_start_month"]

    today = datetime.now()
    year = today.year

    # If we're before the season start month, the season started last year
    if today.month < season_start_month:
        year = year - 1

    return f"{year}-{season_start_month:02d}-01"


def load_games_from_duckdb(sport: str, season_only: bool = False) -> pd.DataFrame:
    """Load games from DuckDB database."""
    db_path = Path("data/nhlstats.duckdb")

    if not db_path.exists():
        print(f"⚠️  Database not found: {db_path}")
        return pd.DataFrame()

    # Use a temp file to avoid locking issues
    import shutil
    import tempfile

    temp_db = (
        Path(tempfile.gettempdir())
        / f"nhlstats_temp_{datetime.now().timestamp()}.duckdb"
    )
    try:
        shutil.copy2(db_path, temp_db)
        conn = duckdb.connect(str(temp_db), read_only=True)

        # Build query based on sport
        if sport == "nhl":
            # NHL API uses 'OFF' for completed games, 'FINAL' is also valid
            query = """
                SELECT 
                    game_id,
                    game_date,
                    home_team_name as home_team,
                    away_team_name as away_team,
                    home_score,
                    away_score,
                    CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
                FROM games 
                WHERE game_state IN ('OFF', 'FINAL') 
                  AND home_score IS NOT NULL 
                  AND away_score IS NOT NULL
            """
        elif sport == "mlb":
            query = """
                SELECT 
                    game_id,
                    game_date,
                    home_team as home_team,
                    away_team as away_team,
                    home_score,
                    away_score,
                    CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
                FROM mlb_games 
                WHERE status = 'Final'
            """
        elif sport == "nfl":
            query = """
                SELECT 
                    game_id,
                    game_date,
                    home_team as home_team,
                    away_team as away_team,
                    home_score,
                    away_score,
                    CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
                FROM nfl_games 
                WHERE status = 'Final'
            """
        else:
            conn.close()
            return pd.DataFrame()

        # Add season filter if needed
        if season_only:
            season_start = get_current_season_start(sport)
            query += f" AND game_date >= '{season_start}'"

        query += " ORDER BY game_date, game_id"

        try:
            df = conn.execute(query).fetchdf()
        except Exception as e:
            print(f"⚠️  Error loading {sport} games: {e}")
            df = pd.DataFrame()

        conn.close()
        return df

    finally:
        # Cleanup temp file
        if temp_db.exists():
            try:
                temp_db.unlink()
            except:
                pass


def load_games_from_json(sport: str, season_only: bool = False) -> pd.DataFrame:
    """Load games from JSON files (for NBA)."""
    if sport != "nba":
        return pd.DataFrame()

    nba_dir = Path("data/nba")
    games = []

    if not nba_dir.exists():
        print(f"⚠️  NBA data directory not found: {nba_dir}")
        return pd.DataFrame()

    season_start = get_current_season_start("nba") if season_only else None

    # Get all date directories
    date_dirs = sorted([d for d in nba_dir.iterdir() if d.is_dir()])

    for date_dir in date_dirs:
        # Check if within season if filtering
        if season_only and date_dir.name < season_start:
            continue

        scoreboard_file = date_dir / f"scoreboard_{date_dir.name}.json"

        if not scoreboard_file.exists():
            continue

        try:
            with open(scoreboard_file) as f:
                data = json.load(f)

            if "resultSets" not in data:
                continue

            for result_set in data["resultSets"]:
                if result_set["name"] == "GameHeader":
                    headers = result_set["headers"]

                    idx_game_id = headers.index("GAME_ID")
                    idx_game_date = headers.index("GAME_DATE_EST")
                    idx_home_team_id = headers.index("HOME_TEAM_ID")
                    idx_visitor_team_id = headers.index("VISITOR_TEAM_ID")

                    for row in result_set["rowSet"]:
                        # Skip status check - trust boxscore existence

                        game_id = str(row[idx_game_id])
                        game_date = row[idx_game_date]

                        boxscore_file = date_dir / f"boxscore_{game_id}.json"

                        if not boxscore_file.exists():
                            continue

                        with open(boxscore_file) as bf:
                            boxscore = json.load(bf)

                        home_team_name = None
                        away_team_name = None
                        home_score = None
                        away_score = None

                        for bs_result in boxscore["resultSets"]:
                            if bs_result["name"] == "TeamStats":
                                bs_headers = bs_result["headers"]
                                idx_team_id = bs_headers.index("TEAM_ID")
                                idx_team_name = bs_headers.index("TEAM_NAME")
                                idx_pts = bs_headers.index("PTS")

                                for bs_row in bs_result["rowSet"]:
                                    team_id = bs_row[idx_team_id]
                                    team_name = bs_row[idx_team_name]
                                    pts = bs_row[idx_pts]

                                    if team_id == row[idx_home_team_id]:
                                        home_team_name = team_name
                                        home_score = pts
                                    elif team_id == row[idx_visitor_team_id]:
                                        away_team_name = team_name
                                        away_score = pts

                        if all(
                            [
                                home_team_name,
                                away_team_name,
                                home_score is not None,
                                away_score is not None,
                            ]
                        ):
                            games.append(
                                {
                                    "game_id": game_id,
                                    "game_date": game_date,
                                    "home_team": home_team_name,
                                    "away_team": away_team_name,
                                    "home_score": home_score,
                                    "away_score": away_score,
                                    "home_win": 1 if home_score > away_score else 0,
                                }
                            )

        except Exception as e:
            continue

    return pd.DataFrame(games)


def load_games_from_csv(sport: str, season_only: bool = False) -> pd.DataFrame:
    """Load games from CSV files (for EPL)."""
    if sport != "epl":
        return pd.DataFrame()

    try:
        from epl_games import EPLGames

        epl = EPLGames()
        df = epl.load_games()

        # Ensure home_win binary column exists for lift/gain calc
        # For lift/gain, we defined success as Home Win
        df["home_win"] = df["result"].apply(lambda x: 1 if x == "H" else 0)

        # Rename date column if needed
        if "date" in df.columns:
            df["game_date"] = df["date"]

        if season_only:
            # CSV only contains current season anyway
            pass

        return df

    except ImportError:
        print("⚠️  epl_games module not found")
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️  Error loading EPL games: {e}")
        return pd.DataFrame()


def load_games_from_ncaab(sport: str, season_only: bool = False) -> pd.DataFrame:
    """Load NCAAB games using NCAABGames class."""
    if sport != "ncaab":
        return pd.DataFrame()
    try:
        from ncaab_games import NCAABGames

        ng = NCAABGames()
        df = ng.load_games()

        if df.empty:
            return df

        # Standardize columns
        if "date" in df.columns:
            df["game_date"] = df["date"]

        df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)

        if season_only:
            start = get_current_season_start(sport)
            # Ensure datetime type
            df["game_date"] = pd.to_datetime(df["game_date"])
            df = df[df["game_date"] >= pd.to_datetime(start)]

        return df
    except Exception as e:
        print(f"Error loading NCAAB games: {e}")
        return pd.DataFrame()


def load_games(sport: str, season_only: bool = False) -> pd.DataFrame:
    """Load games for a sport from the appropriate data source."""
    config = SPORT_CONFIG[sport]

    if config["data_source"] == "json":
        return load_games_from_json(sport, season_only)
    elif config["data_source"] == "csv":
        return load_games_from_csv(sport, season_only)
    elif config["data_source"] == "csv_ncaab":
        return load_games_from_ncaab(sport, season_only)
    else:
        return load_games_from_duckdb(sport, season_only)


def calculate_elo_predictions(sport: str, games_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Elo predictions for all games.

    Returns DataFrame with elo_prob column added.
    """
    if games_df.empty:
        return games_df

    config = SPORT_CONFIG[sport]

    # Import the Elo class dynamically
    if sport == "nba":
        from nba_elo_rating import NBAEloRating

        elo = NBAEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "nhl":
        from nhl_elo_rating import NHLEloRating

        elo = NHLEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "mlb":
        from mlb_elo_rating import MLBEloRating

        elo = MLBEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "nfl":
        from nfl_elo_rating import NFLEloRating

        elo = NFLEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "epl":
        from epl_elo_rating import EPLEloRating

        elo = EPLEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "ncaab":
        from ncaab_elo_rating import NCAABEloRating

        elo = NCAABEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    else:
        raise ValueError(f"Unknown sport: {sport}")

    # Sort by date
    df = games_df.sort_values(["game_date"]).reset_index(drop=True)

    # Drop rows with missing scores or teams
    df = df.dropna(subset=["home_score", "away_score", "home_team", "away_team"])

    # Ensure home_win column exists and is valid
    if "home_win" not in df.columns:
        if "result" in df.columns:  # EPL style
            df["home_win"] = df["result"].apply(lambda x: 1 if x == "H" else 0)
        else:
            df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)
    else:
        df["home_win"] = df["home_win"].fillna(0).astype(int)

    if df.empty or len(df) < 10:
        print(
            f"⚠️  Not enough valid games for analysis (have {len(df)}, need at least 10)"
        )
        return df

    # Calculate predictions and update ratings
    predictions = []

    # Track dates for season reversion (NHL specifically)
    last_date = None

    for _, game in df.iterrows():
        # Check for new season (NHL only)
        if sport == "nhl":
            game_date_str = str(game["game_date"])[:10]
            try:
                current_date = datetime.strptime(game_date_str, "%Y-%m-%d").date()
                if last_date:
                    days_diff = (current_date - last_date).days
                    if days_diff > 90:
                        # Apply reversion
                        elo.apply_season_reversion(0.35)
                last_date = current_date
            except Exception:
                pass

        # Predict BEFORE updating
        if sport == "ncaab":
            prob = elo.predict(
                game["home_team"],
                game["away_team"],
                is_neutral=game.get("neutral", False),
            )
        else:
            prob = elo.predict(game["home_team"], game["away_team"])

        predictions.append(prob)

        # Update ratings
        if sport in ["mlb", "nfl"]:
            elo.update(
                game["home_team"],
                game["away_team"],
                int(game["home_score"]),
                int(game["away_score"]),
            )
        elif sport == "epl":
            # EPL update needs result char ('H', 'D', 'A')
            result = game.get("result")
            if not result:
                # Infer from binary if missing? But we should have it.
                if game["home_score"] > game["away_score"]:
                    result = "H"
                elif game["home_score"] == game["away_score"]:
                    result = "D"
                else:
                    result = "A"
            elo.update(game["home_team"], game["away_team"], result)
        elif sport == "ncaab":
            elo.update(
                game["home_team"],
                game["away_team"],
                game["home_win"],
                is_neutral=game.get("neutral", False),
            )
        else:
            elo.update(game["home_team"], game["away_team"], game["home_win"])

    df["elo_prob"] = predictions
    return df


def calculate_elo_markov_predictions(
    sport: str,
    games_df: pd.DataFrame,
    markov_alpha: float = 0.35,
    markov_smoothing: float = 2.0,
) -> pd.DataFrame:
    """Calculate Elo and Elo+Markov predictions for all games.

    This function is leakage-safe when called on chronologically ordered games:
    it predicts a game before updating Elo/Markov state with the result.

    Args:
        sport: Sport key (e.g., 'nba', 'nhl').
        games_df: Games dataframe.
        markov_alpha: Strength of Markov momentum logit adjustment.
        markov_smoothing: Prior strength for smoothing conditional probabilities.

    Returns:
        DataFrame with `elo_prob` and `elo_markov_prob` columns added.
    """

    from markov_momentum import MarkovMomentum

    if games_df.empty:
        return games_df

    config = SPORT_CONFIG[sport]

    # Import the Elo class dynamically
    if sport == "nba":
        from nba_elo_rating import NBAEloRating

        elo = NBAEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "nhl":
        from nhl_elo_rating import NHLEloRating

        elo = NHLEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "mlb":
        from mlb_elo_rating import MLBEloRating

        elo = MLBEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "nfl":
        from nfl_elo_rating import NFLEloRating

        elo = NFLEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "epl":
        from epl_elo_rating import EPLEloRating

        elo = EPLEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    elif sport == "ncaab":
        from ncaab_elo_rating import NCAABEloRating

        elo = NCAABEloRating(
            k_factor=config["k_factor"], home_advantage=config["home_advantage"]
        )
    else:
        raise ValueError(f"Unknown sport: {sport}")

    markov = MarkovMomentum(alpha=markov_alpha, smoothing=markov_smoothing)

    # Sort by date
    df = games_df.sort_values(["game_date"]).reset_index(drop=True)

    # Drop rows with missing scores or teams
    df = df.dropna(subset=["home_score", "away_score", "home_team", "away_team"])

    # Ensure home_win column exists and is valid
    if "home_win" not in df.columns:
        if "result" in df.columns:  # EPL style
            df["home_win"] = df["result"].apply(lambda x: 1 if x == "H" else 0)
        else:
            df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)
    else:
        df["home_win"] = df["home_win"].fillna(0).astype(int)

    if df.empty or len(df) < 10:
        print(
            f"⚠️  Not enough valid games for analysis (have {len(df)}, need at least 10)"
        )
        return df

    predictions = []
    markov_predictions = []

    last_date = None

    for _, game in df.iterrows():
        # Detect season gaps and apply Elo season reversion where supported.
        game_date_str = str(game["game_date"])[:10]
        try:
            current_date = datetime.strptime(game_date_str, "%Y-%m-%d").date()
            if last_date:
                days_diff = (current_date - last_date).days
                if days_diff > 90:
                    # Elo season reversion (NHL has explicit support)
                    if sport == "nhl":
                        elo.apply_season_reversion(0.35)
                    # Momentum state should not carry across long offseasons
                    markov.last_outcome.clear()
            last_date = current_date
        except Exception:
            pass

        # Predict BEFORE updating
        if sport == "ncaab":
            elo_prob = elo.predict(
                game["home_team"],
                game["away_team"],
                is_neutral=game.get("neutral", False),
            )
        else:
            elo_prob = elo.predict(game["home_team"], game["away_team"])

        predictions.append(elo_prob)
        markov_predictions.append(
            markov.apply(elo_prob, game["home_team"], game["away_team"])
        )

        # Update ratings
        if sport in ["mlb", "nfl"]:
            elo.update(
                game["home_team"],
                game["away_team"],
                int(game["home_score"]),
                int(game["away_score"]),
            )
        elif sport == "epl":
            result = game.get("result")
            if not result:
                if game["home_score"] > game["away_score"]:
                    result = "H"
                elif game["home_score"] == game["away_score"]:
                    result = "D"
                else:
                    result = "A"
            elo.update(game["home_team"], game["away_team"], result)
        elif sport == "ncaab":
            elo.update(
                game["home_team"],
                game["away_team"],
                game["home_win"],
                is_neutral=game.get("neutral", False),
            )
        else:
            elo.update(game["home_team"], game["away_team"], game["home_win"])

        # Update Markov with realized outcome
        markov.update_game(game["home_team"], game["away_team"], bool(game["home_win"]))

    df["elo_prob"] = predictions
    df["elo_markov_prob"] = markov_predictions
    return df


def calculate_lift_gain_by_decile(
    df: pd.DataFrame, prob_col: str = "elo_prob"
) -> pd.DataFrame:
    """
    Calculate lift and gain statistics by probability decile.

    Returns DataFrame with:
    - decile: 1-10 (1=lowest probability, 10=highest)
    - n_games: number of games in decile
    - n_wins: home team wins in decile
    - cumulative_games: running total of games (from decile 10 down)
    - cumulative_wins: running total of wins (from decile 10 down)
    - win_rate: actual home win rate in decile
    - baseline: overall home win rate
    - lift: win_rate / baseline
    - gain_pct: cumulative_wins / total_wins * 100
    """
    if df.empty or prob_col not in df.columns:
        return pd.DataFrame()

    df = df.copy()

    # Need at least 10 games for decile analysis
    if len(df) < 10:
        print(
            f"⚠️  Not enough games for decile analysis (need at least 10, have {len(df)})"
        )
        return pd.DataFrame()

    # Create deciles (1=lowest, 10=highest)
    df["decile"] = pd.qcut(df[prob_col], q=10, labels=False, duplicates="drop") + 1

    baseline = df["home_win"].mean()
    total_wins = int(df["home_win"].sum())
    total_games = len(df)

    results = []

    # Calculate stats for each decile
    for decile in sorted(df["decile"].unique()):
        decile_df = df[df["decile"] == decile]

        n_games = len(decile_df)
        n_wins = int(decile_df["home_win"].sum())
        win_rate = n_wins / n_games if n_games > 0 else 0
        lift = win_rate / baseline if baseline > 0 else 0

        avg_prob = decile_df[prob_col].mean()
        min_prob = decile_df[prob_col].min()
        max_prob = decile_df[prob_col].max()

        results.append(
            {
                "decile": decile,
                "prob_range": f"{min_prob:.3f}-{max_prob:.3f}",
                "avg_prob": avg_prob,
                "n_games": n_games,
                "n_wins": n_wins,
                "win_rate": win_rate,
                "baseline": baseline,
                "lift": lift,
            }
        )

    results_df = pd.DataFrame(results)

    # Calculate cumulative stats (starting from highest confidence - decile 10)
    results_df = results_df.sort_values("decile", ascending=False)
    results_df["cumulative_games"] = results_df["n_games"].cumsum()
    results_df["cumulative_wins"] = results_df["n_wins"].cumsum()
    results_df["cumulative_win_rate"] = (
        results_df["cumulative_wins"] / results_df["cumulative_games"]
    )
    results_df["gain_pct"] = (
        (results_df["cumulative_wins"] / total_wins * 100) if total_wins > 0 else 0
    )
    results_df["coverage_pct"] = results_df["cumulative_games"] / total_games * 100

    # Sort back by decile ascending for display
    results_df = results_df.sort_values("decile").reset_index(drop=True)

    return results_df


def print_decile_table(decile_df: pd.DataFrame, sport: str, title: str):
    """Print formatted decile analysis table."""
    if decile_df.empty:
        print(f"\n⚠️  No data available for {sport.upper()} {title}")
        return

    baseline = decile_df["baseline"].iloc[0]
    total_games = decile_df["n_games"].sum()
    total_wins = decile_df["n_wins"].sum()

    print(f"\n{'='*110}")
    print(f"🏆 {sport.upper()} - {title}")
    print(f"{'='*110}")
    print(
        f"Total Games: {total_games:,} | Total Home Wins: {total_wins:,} | Baseline Win Rate: {baseline:.1%}"
    )
    print(f"{'='*110}")

    print(
        f"\n{'Decile':<8} {'Prob Range':<16} {'Games':<8} {'Wins':<8} {'Win%':<10} {'Lift':<8} "
        f"{'Cum Games':<12} {'Cum Wins':<10} {'Gain%':<10} {'Coverage%':<10}"
    )
    print(f"{'-'*110}")

    for _, row in decile_df.iterrows():
        # Color indicator for lift
        if row["lift"] >= 1.2:
            indicator = "🟢"
        elif row["lift"] >= 1.0:
            indicator = "🟡"
        elif row["lift"] >= 0.8:
            indicator = "🟠"
        else:
            indicator = "🔴"

        print(
            f"{int(row['decile']):<8} {row['prob_range']:<16} {row['n_games']:<8} {row['n_wins']:<8} "
            f"{row['win_rate']*100:>7.1f}%  {row['lift']:>6.2f}x  "
            f"{row['cumulative_games']:<12} {row['cumulative_wins']:<10} "
            f"{row['gain_pct']:>7.1f}%   {row['coverage_pct']:>7.1f}% {indicator}"
        )

    print(f"{'-'*110}")

    # Summary insights
    top_deciles = decile_df[decile_df["decile"] >= 9]
    if not top_deciles.empty:
        top_games = top_deciles["n_games"].sum()
        top_wins = top_deciles["n_wins"].sum()
        top_rate = top_wins / top_games if top_games > 0 else 0
        top_lift = top_rate / baseline if baseline > 0 else 0
        print(
            f"\n📈 TOP 2 DECILES (9-10): {top_games} games, {top_wins} wins, "
            f"{top_rate:.1%} win rate, {top_lift:.2f}x lift"
        )

    bottom_deciles = decile_df[decile_df["decile"] <= 2]
    if not bottom_deciles.empty:
        bot_games = bottom_deciles["n_games"].sum()
        bot_wins = bottom_deciles["n_wins"].sum()
        bot_rate = bot_wins / bot_games if bot_games > 0 else 0
        bot_lift = bot_rate / baseline if baseline > 0 else 0
        print(
            f"📉 BOTTOM 2 DECILES (1-2): {bot_games} games, {bot_wins} wins, "
            f"{bot_rate:.1%} win rate, {bot_lift:.2f}x lift"
        )


def analyze_sport(sport: str, include_season: bool = True):
    """Run lift/gain analysis for a single sport."""
    print(f"\n{'#'*110}")
    print(f"# {sport.upper()} LIFT/GAIN ANALYSIS")
    print(f"{'#'*110}")

    # Overall analysis
    print(f"\n📊 Loading all {sport.upper()} games...")
    all_games = load_games(sport, season_only=False)

    if all_games.empty:
        print(f"⚠️  No {sport.upper()} games found")
        return None, None

    print(f"   Found {len(all_games):,} games")

    # Calculate Elo predictions
    print(f"🎯 Calculating Elo predictions...")
    all_games_with_pred = calculate_elo_predictions(sport, all_games)

    # Calculate decile stats
    overall_deciles = calculate_lift_gain_by_decile(all_games_with_pred)
    print_decile_table(overall_deciles, sport, "OVERALL (All Historical Data)")

    # Current season analysis
    season_deciles = None
    if include_season:
        season_start = get_current_season_start(sport)
        print(f"\n📅 Loading {sport.upper()} games since {season_start}...")
        season_games = load_games(sport, season_only=True)

        if not season_games.empty:
            print(f"   Found {len(season_games):,} games this season")
            season_games_with_pred = calculate_elo_predictions(sport, season_games)
            season_deciles = calculate_lift_gain_by_decile(season_games_with_pred)
            print_decile_table(
                season_deciles, sport, f"CURRENT SEASON (Since {season_start})"
            )
        else:
            print(f"⚠️  No {sport.upper()} games found for current season")

    return overall_deciles, season_deciles


def save_results(results: dict, output_dir: str = "data"):
    """Save analysis results to JSON and CSV files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d")

    for sport, data in results.items():
        overall, season = data

        if overall is not None and not overall.empty:
            # Save CSV
            csv_path = output_path / f"{sport}_lift_gain_overall.csv"
            overall.to_csv(csv_path, index=False)
            print(f"💾 Saved {csv_path}")

        if season is not None and not season.empty:
            csv_path = output_path / f"{sport}_lift_gain_season.csv"
            season.to_csv(csv_path, index=False)
            print(f"💾 Saved {csv_path}")


def main():
    """Run lift/gain analysis for all sports."""
    print("=" * 110)
    print("🎰 MULTI-SPORT LIFT/GAIN ANALYSIS BY PROBABILITY DECILE")
    print(f"📅 Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 110)

    results = {}

    for sport in ["nba", "nhl", "mlb", "nfl"]:
        try:
            overall, season = analyze_sport(sport, include_season=True)
            results[sport] = (overall, season)
        except Exception as e:
            print(f"⚠️  Error analyzing {sport}: {e}")
            results[sport] = (None, None)

    # Save results
    print(f"\n{'='*110}")
    print("💾 SAVING RESULTS")
    print(f"{'='*110}")
    save_results(results)

    # Summary
    print(f"\n{'='*110}")
    print("📊 SUMMARY")
    print(f"{'='*110}")

    for sport, (overall, season) in results.items():
        if overall is not None and not overall.empty:
            baseline = overall["baseline"].iloc[0]
            top_decile = overall[overall["decile"] == 10]
            if not top_decile.empty:
                top_lift = top_decile["lift"].iloc[0]
                top_rate = top_decile["win_rate"].iloc[0]
                print(
                    f"\n{sport.upper()}: Baseline={baseline:.1%}, Top Decile Lift={top_lift:.2f}x ({top_rate:.1%} win rate)"
                )


if __name__ == "__main__":
    main()
