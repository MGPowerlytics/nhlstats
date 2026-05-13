"""
Helper functions for Elo rating updates.

This module contains extracted logic from the update_elo_ratings function
to reduce duplication and complexity.
"""

import os
import pandas as pd
from pathlib import Path
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Any

from plugins.elo.elo_update_config import SportEloConfig, get_sport_config


DEFAULT_ELO_ENTITY_TYPE = "team"
DEFAULT_GAMES_PLAYED = 0
NHL_DASHBOARD_SEED_RATINGS = {
    "BOS": 1568.0,
    "NYR": 1549.0,
    "COL": 1536.0,
    "EDM": 1528.0,
}


def load_previous_ratings(sport: str) -> Dict[str, float]:
    """Load previous Elo ratings from CSV file if available."""
    previous_ratings = {}
    csv_path = f"data/{sport}_current_elo_ratings.csv"

    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            previous_ratings = dict(zip(df["team"], df["rating"]))
            print(f"  Loaded {len(previous_ratings)} previous ratings from {csv_path}")
        except Exception as e:
            print(f"  ⚠️  Could not load previous ratings: {e}")

    return previous_ratings


def is_valid_score(score: Any) -> bool:
    """Check if a score is valid (not None, NaN, or inf)."""
    if score is None:
        return False
    try:
        import math

        if isinstance(score, float) and (math.isnan(score) or math.isinf(score)):
            return False
        return True
    except (TypeError, ValueError):
        return False


def _get_team_names(game: pd.Series, team_mapper: Any) -> tuple[str, str] | None:
    """Extract and map team names from game data.

    Args:
        game: Game data series
        team_mapper: Optional function to map team names

    Returns:
        Tuple of (home_team, away_team) or None if mapping fails
    """
    if team_mapper:
        home_team = team_mapper(
            game.get("home_team") or game.get("home_team_name") or game.get("winner")
        )
        away_team = team_mapper(
            game.get("away_team") or game.get("away_team_name") or game.get("loser")
        )

        # Skip if team mapping returns None (e.g., invalid team)
        if home_team is None or away_team is None:
            return None
    else:
        home_team = (
            game.get("home_team") or game.get("home_team_name") or game.get("winner")
        )
        away_team = (
            game.get("away_team") or game.get("away_team_name") or game.get("loser")
        )

    # Skip if either team name is missing
    if not home_team or not away_team:
        return None

    return home_team, away_team


def _check_nba_season_transition(
    game_date: Any,
    last_date: date | None,
    elo_instance: Any,
    season_reversion_factor: float | None,
) -> date:
    """Check for NBA season transition and apply reversion if needed.

    Args:
        game_date: Current game date
        last_date: Last processed game date
        elo_instance: Elo rating instance
        season_reversion_factor: Factor to apply for season reversion

    Returns:
        Updated last_date
    """
    if isinstance(game_date, str):
        current_date = datetime.strptime(game_date, "%Y-%m-%d").date()
    else:
        current_date = game_date

    if last_date and season_reversion_factor:
        days_diff = (current_date - last_date).days
        if days_diff > 120:  # NBA offseason
            print(f"📅 New NBA season detected at {current_date}")
            if hasattr(elo_instance, "apply_season_reversion"):
                elo_instance.apply_season_reversion(season_reversion_factor)
            else:
                print("  ⚠️  NBA Elo class doesn't support season reversion")

    return current_date


def _determine_game_result(game: pd.Series) -> bool | float | None:
    """Determine game result from various data formats.

    Args:
        game: Game data series

    Returns:
        True for home win, False for away win, 0.5 for draw, or None if invalid
    """
    if "home_win" in game:
        return bool(game["home_win"])

    if "winner" in game and "loser" in game:
        # For tennis/sports where winner is explicitly defined as home_team
        return True

    if "result" in game:
        # For sports like EPL with result column
        result = game["result"]
        if result == "H":
            return True
        elif result == "A":
            return False
        else:  # Draw
            return 0.5

    # Calculate from scores
    home_score = game.get("home_score")
    away_score = game.get("away_score")

    if not is_valid_score(home_score) or not is_valid_score(away_score):
        return None

    return home_score > away_score


def _collect_update_kwargs(game: pd.Series, sport_id: str) -> dict[str, Any]:
    """Collect additional kwargs for Elo update method.

    Args:
        game: Game data series
        sport_id: Sport identifier

    Returns:
        Dictionary of kwargs for update method
    """
    update_kwargs = {}

    if "home_score" in game and "away_score" in game:
        update_kwargs["home_score"] = game["home_score"]
        update_kwargs["away_score"] = game["away_score"]

    if "neutral" in game:
        update_kwargs["is_neutral"] = game["neutral"]

    if "game_date" in game:
        update_kwargs["game_date"] = game["game_date"]

    if sport_id == "mlb":
        if "home_pitcher_id" in game:
            update_kwargs["home_pitcher_id"] = game["home_pitcher_id"]
        if "away_pitcher_id" in game:
            update_kwargs["away_pitcher_id"] = game["away_pitcher_id"]

    if sport_id == "tennis" and "tour" in game:
        update_kwargs["tour"] = None if pd.isna(game["tour"]) else game["tour"]

    return update_kwargs


def process_games_with_elo(
    elo_instance: Any,
    games_df: pd.DataFrame,
    config: SportEloConfig,
    progress_interval: int = 1000,
) -> int:
    """Process games through Elo system with sport-specific logic."""
    games_processed = 0
    last_date = None

    for _, game in games_df.iterrows():
        # Extract team names
        team_names = _get_team_names(game, config.team_mapper)
        if team_names is None:
            continue
        home_team, away_team = team_names

        # Handle season detection for NBA
        if config.sport_id == "nba" and config.season_reversion_factor:
            last_date = _check_nba_season_transition(
                game["game_date"],
                last_date,
                elo_instance,
                config.season_reversion_factor,
            )

        # Determine game result
        home_won = _determine_game_result(game)
        if home_won is None:
            continue

        # Update Elo ratings
        if config.use_legacy_update:
            elo_instance.legacy_update(home_team, away_team, home_won)
        else:
            update_kwargs = _collect_update_kwargs(game, config.sport_id)
            elo_instance.update(home_team, away_team, home_won, **update_kwargs)

        games_processed += 1
        if games_processed % progress_interval == 0:
            print(f"    Processed {games_processed} games...")

    return games_processed


def save_elo_ratings(
    sport: str,
    elo_instance: Any,
    previous_ratings: Dict[str, float],
    context: Dict[str, Any],
    db: Any | None = None,
) -> None:
    """Save Elo ratings to PostgreSQL, CSV, and XCom."""
    config = get_sport_config(sport)

    # Handle tennis separately (ATP/WTA split)
    if config.has_separate_ratings and hasattr(elo_instance, "atp_ratings"):
        _save_tennis_ratings(sport, elo_instance, context, db=db)
        return

    # For other sports
    _save_standard_ratings(sport, elo_instance, previous_ratings, context, db=db)


def _save_tennis_ratings(
    sport: str,
    elo_instance: Any,
    context: Dict[str, Any],
    db: Any | None = None,
) -> None:
    """Internal helper to save tennis-specific ratings (ATP/WTA)."""
    Path("data").mkdir(parents=True, exist_ok=True)

    # Save ATP ratings
    with open("data/atp_current_elo_ratings.csv", "w") as f:
        f.write("team,rating\n")
        for player in sorted(elo_instance.atp_ratings.keys()):
            rating = elo_instance.atp_ratings[player]
            if is_valid_score(rating):
                f.write(f"{player},{rating:.2f}\n")

    # Save WTA ratings
    with open("data/wta_current_elo_ratings.csv", "w") as f:
        f.write("team,rating\n")
        for player in sorted(elo_instance.wta_ratings.keys()):
            rating = elo_instance.wta_ratings[player]
            if is_valid_score(rating):
                f.write(f"{player},{rating:.2f}\n")

    # Push to XCom
    context["task_instance"].xcom_push(
        key=f"{sport}_elo_ratings",
        value={
            "ATP": dict(elo_instance.atp_ratings),
            "WTA": dict(elo_instance.wta_ratings),
        },
    )

    # Persist to canonical elo_ratings table so the dashboard read-model
    # views stay current.
    combined_ratings = {}
    combined_ratings.update(elo_instance.atp_ratings)
    combined_ratings.update(elo_instance.wta_ratings)
    persist_elo_ratings(sport, combined_ratings, db=db)

    total_players = len(elo_instance.atp_ratings) + len(elo_instance.wta_ratings)
    print(
        f"✓ {sport.upper()} Elo ratings updated: {total_players} players "
        f"(ATP: {len(elo_instance.atp_ratings)}, WTA: {len(elo_instance.wta_ratings)})"
    )


def _save_standard_ratings(
    sport: str,
    elo_instance: Any,
    previous_ratings: Dict[str, float],
    context: Dict[str, Any],
    db: Any | None = None,
) -> None:
    """Internal helper to save standard Elo ratings."""
    Path(f"data/{sport}_current_elo_ratings.csv").parent.mkdir(
        parents=True, exist_ok=True
    )

    # Get ratings from elo instance
    if hasattr(elo_instance, "ratings"):
        ratings_dict = elo_instance.ratings
    else:
        ratings_dict = elo_instance.get_all_ratings()

    # Filter out invalid values
    valid_ratings = {
        team: rating for team, rating in ratings_dict.items() if is_valid_score(rating)
    }

    # Log changes compared to previous ratings
    if previous_ratings:
        _log_rating_changes(sport, valid_ratings, previous_ratings)

    # Save to CSV
    with open(f"data/{sport}_current_elo_ratings.csv", "w") as f:
        f.write("team,rating\n")
        for team in sorted(valid_ratings.keys()):
            f.write(f"{team},{valid_ratings[team]:.2f}\n")

    # Also call sport-specific save if it exists (e.g. MLB pitcher ratings)
    if hasattr(elo_instance, "save_ratings"):
        # We check if it's the adapter's save_ratings (which takes data_dir)
        # and not just a recursive call to this standard saver.
        try:
            # Most of our elo classes have a ratings property or get_all_ratings.
            # Only the adapter has a custom save_ratings for side data.
            from plugins.elo.mlb_ensemble_adapter import MLBEnsembleAdapter

            if isinstance(elo_instance, MLBEnsembleAdapter):
                elo_instance.save_ratings()
        except ImportError:
            pass

    # Push to XCom
    if context and "task_instance" in context:
        context["task_instance"].xcom_push(
            key=f"{sport}_elo_ratings", value=valid_ratings
        )

    persist_elo_ratings(sport, valid_ratings, db=db)

    print(f"✓ {sport.upper()} Elo ratings updated: {len(valid_ratings)} teams")


def persist_elo_ratings(
    sport: str,
    ratings: Dict[str, float],
    *,
    db: Any | None = None,
    entity_type: str = DEFAULT_ELO_ENTITY_TYPE,
    valid_from: datetime | None = None,
    games_played: int = DEFAULT_GAMES_PLAYED,
) -> dict[str, int]:
    """Persist active Elo ratings to canonical PostgreSQL ``elo_ratings`` rows.

    Re-running with identical active values is a no-op. Changed values close the
    previous active row by setting ``valid_to`` and insert a new active row.
    """
    if db is None:
        from plugins.db_manager import default_db

        db = default_db

    now = valid_from or datetime.now(timezone.utc)
    canonical_sport = _canonical_sport_name(sport)
    canonical_entity_type = _canonical_entity_type(entity_type)
    candidate_rows = _build_canonical_elo_rows(
        canonical_sport,
        canonical_entity_type,
        ratings,
        now,
        games_played,
    )

    if not candidate_rows:
        return {"inserted": 0, "updated": 0, "unchanged": 0}

    active_rows = _fetch_active_elo_rows(
        db,
        canonical_sport,
        canonical_entity_type,
        [row["entity_id"] for row in candidate_rows],
    )
    active_by_entity = {str(row["entity_id"]): row for row in active_rows}

    result = {"inserted": 0, "updated": 0, "unchanged": 0}
    for row in candidate_rows:
        active_row = active_by_entity.get(row["entity_id"])
        if active_row and _same_active_elo_row(active_row, row):
            result["unchanged"] += 1
            continue

        if active_row:
            _close_active_elo_row(db, row, now)
            result["updated"] += 1

        _insert_active_elo_row(db, row)
        result["inserted"] += 1

    return result


def seed_active_nhl_elo_ratings(
    *,
    db: Any | None = None,
    ratings: Dict[str, float] | None = None,
    valid_from: datetime | None = None,
) -> dict[str, int]:
    """Seed active NHL team Elo rows for dashboard rankings provider tests."""
    return persist_elo_ratings(
        "NHL",
        ratings or NHL_DASHBOARD_SEED_RATINGS,
        db=db,
        valid_from=valid_from,
    )


def _canonical_sport_name(sport: str) -> str:
    sport_key = str(sport).strip()
    if sport_key.lower() == "ligue1":
        return "Ligue1"
    return sport_key.upper()


def _canonical_entity_type(entity_type: str) -> str:
    return str(entity_type).strip().lower()


def _build_canonical_elo_rows(
    sport: str,
    entity_type: str,
    ratings: Dict[str, float],
    valid_from: datetime,
    games_played: int,
) -> list[dict[str, Any]]:
    rows = []
    for entity_name in sorted(ratings.keys()):
        rating = ratings[entity_name]
        if not is_valid_score(rating):
            continue
        stable_entity_name = str(entity_name).strip()
        if not stable_entity_name:
            continue
        rows.append(
            {
                "sport": sport,
                "entity_type": entity_type,
                "entity_id": stable_entity_name,
                "entity_name": stable_entity_name,
                "rating": float(rating),
                "valid_from": valid_from,
                "valid_to": None,
                "games_played": int(games_played),
                "created_at": valid_from,
            }
        )
    return rows


def _fetch_active_elo_rows(
    db: Any,
    sport: str,
    entity_type: str,
    entity_ids: list[str],
) -> list[dict[str, Any]]:
    df = db.fetch_df(
        """
        SELECT sport, entity_type, entity_id, entity_name, rating, valid_from,
               valid_to, games_played, created_at
        FROM elo_ratings
        WHERE sport = :sport
          AND entity_type = :entity_type
          AND entity_id = ANY(:entity_ids)
          AND valid_to IS NULL
        """,
        {
            "sport": sport,
            "entity_type": entity_type,
            "entity_ids": entity_ids,
        },
    )
    if df.empty:
        return []
    return df.to_dict(orient="records")


def _same_active_elo_row(
    active_row: dict[str, Any], candidate_row: dict[str, Any]
) -> bool:
    return (
        str(active_row.get("entity_name")) == candidate_row["entity_name"]
        and _decimal_rating(active_row.get("rating"))
        == _decimal_rating(candidate_row["rating"])
        and int(active_row.get("games_played") or 0) == candidate_row["games_played"]
    )


def _decimal_rating(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("NaN")


def _close_active_elo_row(db: Any, row: dict[str, Any], valid_to: datetime) -> None:
    db.execute(
        """
        UPDATE elo_ratings
        SET valid_to = :valid_to
        WHERE sport = :sport
          AND entity_type = :entity_type
          AND entity_id = :entity_id
          AND valid_to IS NULL
        """,
        {
            "valid_to": valid_to,
            "sport": row["sport"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
        },
    )


def _insert_active_elo_row(db: Any, row: dict[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO elo_ratings (
            sport, entity_type, entity_id, entity_name, rating, valid_from,
            valid_to, games_played, created_at
        )
        VALUES (
            :sport, :entity_type, :entity_id, :entity_name, :rating, :valid_from,
            :valid_to, :games_played, :created_at
        )
        """,
        row,
    )


def _log_rating_changes(
    sport: str, current_ratings: Dict[str, float], previous_ratings: Dict[str, float]
) -> None:
    """Log changes in Elo ratings compared to previous version."""
    print(f"\n📊 {sport.upper()} Elo Rating Changes:")
    print("=" * 50)

    common_teams = set(current_ratings.keys()) & set(previous_ratings.keys())
    new_teams = set(current_ratings.keys()) - set(previous_ratings.keys())
    removed_teams = set(previous_ratings.keys()) - set(current_ratings.keys())

    print(
        f"  Teams: {len(current_ratings)} total "
        f"({len(common_teams)} updated, {len(new_teams)} new, {len(removed_teams)} removed)"
    )

    if not common_teams:
        return

    changes = []
    for team in common_teams:
        old = previous_ratings[team]
        new = current_ratings[team]
        change = new - old
        changes.append((team, old, new, change))

    # Sort by absolute change
    changes.sort(key=lambda x: abs(x[3]), reverse=True)

    _print_rating_stats(changes)
    _print_top_movers(changes)


def _print_rating_stats(changes: list) -> None:
    """Print overall rating change statistics."""
    if not changes:
        return

    avg_change = sum(c[3] for c in changes) / len(changes)
    max_increase = max(c[3] for c in changes)
    max_decrease = min(c[3] for c in changes)

    print(f"  Average change: {avg_change:+.2f}")
    print(f"  Maximum increase: {max_increase:+.2f}")
    print(f"  Maximum decrease: {max_decrease:+.2f}")


def _print_top_movers(changes: list) -> None:
    """Print top 3 increases and decreases."""
    print("\n  Top 3 increases:")
    count = 0
    for team, old, new, change in changes:
        if change > 0 and count < 3:
            print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")
            count += 1

    print("\n  Top 3 decreases:")
    count = 0
    for team, old, new, change in changes:
        if change < 0 and count < 3:
            print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")
            count += 1
