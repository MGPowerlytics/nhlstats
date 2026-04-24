from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pandas as pd

from plugins.elo.elo_update_helpers import process_games_with_elo
from plugins.elo.epl_elo_rating import EPLEloRating


EPL_GAME_ID = "EPL-2025-08-16-LIV-BOU"
EPL_MATCH_DATE = "2025-08-16"
EPL_HOME_TEAM = "Liverpool"
EPL_AWAY_TEAM = "Bournemouth"


def build_epl_training_games() -> pd.DataFrame:
    """Create deterministic completed EPL matches for seeding real Elo ratings."""
    return pd.DataFrame(
        [
            {
                "home_team": "Liverpool",
                "away_team": "Bournemouth",
                "result": "H",
                "game_date": "2025-08-01",
            },
            {
                "home_team": "Liverpool",
                "away_team": "Arsenal",
                "result": "H",
                "game_date": "2025-08-05",
            },
            {
                "home_team": "Arsenal",
                "away_team": "Bournemouth",
                "result": "H",
                "game_date": "2025-08-09",
            },
            {
                "home_team": "Bournemouth",
                "away_team": "Liverpool",
                "result": "D",
                "game_date": "2025-08-12",
            },
        ]
    )


def build_epl_upcoming_games(
    home_team: str = EPL_HOME_TEAM,
    away_team: str = EPL_AWAY_TEAM,
    game_id: str = EPL_GAME_ID,
) -> pd.DataFrame:
    """Create a deterministic upcoming EPL unified_games frame."""
    return pd.DataFrame(
        [
            {
                "game_id": game_id,
                "game_date": EPL_MATCH_DATE,
                "home_team_name": home_team,
                "away_team_name": away_team,
                "status": "Scheduled",
            }
        ]
    )


def build_epl_market_odds() -> pd.DataFrame:
    """Create a deterministic Kalshi-style three-way market for the EPL fixture."""
    return pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 2.4,
                "last_update": "2025-08-15T18:00:00Z",
                "external_id": "KXHEPL-LIVBOU-20250816-HOME",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "draw",
                "price": 4.3,
                "last_update": "2025-08-15T18:00:00Z",
                "external_id": "KXHEPL-LIVBOU-20250816-DRAW",
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 4.7,
                "last_update": "2025-08-15T18:00:00Z",
                "external_id": "KXHEPL-LIVBOU-20250816-AWAY",
            },
        ]
    )


def build_training_config() -> SimpleNamespace:
    """Create the minimal config required by process_games_with_elo."""
    return SimpleNamespace(
        team_mapper=None,
        sport_id="epl",
        use_legacy_update=False,
        season_reversion_factor=None,
    )


def build_trained_epl_elo() -> EPLEloRating:
    """Create a real EPL Elo system with non-default ratings for sample teams."""
    elo = EPLEloRating()
    process_games_with_elo(elo, build_epl_training_games(), build_training_config())
    return elo


def build_epl_prediction_payload() -> dict[str, Any]:
    """Build the canonical Elo payload from real EPLEloRating producer outputs."""
    elo = build_trained_epl_elo()
    probabilities = elo.predict_3way(EPL_HOME_TEAM, EPL_AWAY_TEAM)
    return {
        "schema_version": "v1",
        "sport": "EPL",
        "payload_kind": "elo_prediction",
        "game_id": EPL_GAME_ID,
        "home_team": EPL_HOME_TEAM,
        "away_team": EPL_AWAY_TEAM,
        "home_rating": elo.get_rating(EPL_HOME_TEAM),
        "away_rating": elo.get_rating(EPL_AWAY_TEAM),
        "home_win_probability": probabilities["home"],
        "draw_probability": probabilities["draw"],
        "away_win_probability": probabilities["away"],
    }
