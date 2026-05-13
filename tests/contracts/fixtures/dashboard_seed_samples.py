"""Idempotent source-table seed fixtures for dashboard contract/provider tests.

The dashboard read models are PostgreSQL views over source tables.  These
fixtures intentionally populate only those source tables so later provider tests
can catch broken view mappings instead of validating hand-written view rows.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SOURCE_TABLE_KEYS: tuple[str, ...] = (
    "portfolio_value_snapshots",
    "unified_games",
    "game_odds",
    "bet_recommendations",
    "placed_bets",
    "elo_ratings",
    "mlb_model_predictions",
    "tennis_model_evaluations",
)

DASHBOARD_READ_MODEL_COVERAGE: dict[str, tuple[str, ...]] = {
    "dashboard_portfolio_v1": ("portfolio_value_snapshots", "placed_bets"),
    "dashboard_live_markets_v1": (
        "unified_games",
        "game_odds",
        "bet_recommendations",
    ),
    "dashboard_rankings_v1": ("elo_ratings",),
    "dashboard_calibration_v1": ("bet_recommendations", "placed_bets"),
    "dashboard_data_quality_v1": (
        "portfolio_value_snapshots",
        "game_odds",
        "bet_recommendations",
        "elo_ratings",
    ),
    "dashboard_bet_detail_v1": (
        "bet_recommendations",
        "placed_bets",
        "unified_games",
        "game_odds",
    ),
    "dashboard_tennis_predictions_v1": (
        "bet_recommendations",
        "unified_games",
        "game_odds",
    ),
    "dashboard_tennis_model_health_v1": ("tennis_model_evaluations",),
    "dashboard_mlb_model_health_v1": ("mlb_model_predictions",),
}

_PORTFOLIO_SNAPSHOT: dict[str, Any] = {
    "snapshot_hour_utc": "2026-05-03T14:00:00",
    "balance_dollars": 1250.25,
    "portfolio_value_dollars": 1475.75,
    "cumulative_deposits_dollars": 1000.0,
    "drawdown_gate_active": False,
    "drawdown_gate_reason_code": None,
    "drawdown_gate_reason_detail": None,
    "created_at_utc": "2026-05-03T14:01:00",
}

_UNIFIED_GAME: dict[str, Any] = {
    "game_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS",
    "sport": "NHL",
    "game_date": "2026-05-03",
    "season": 2026,
    "status": "scheduled",
    "home_team_id": "NYR",
    "home_team_name": "New York Rangers",
    "away_team_id": "BOS",
    "away_team_name": "Boston Bruins",
    "home_score": None,
    "away_score": None,
    "commence_time": "2026-05-03T23:00:00",
    "venue": "Madison Square Garden",
    "loaded_at": "2026-05-03T13:45:00",
}

_GAME_ODDS: dict[str, Any] = {
    "odds_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-KALSHI-HOME",
    "game_id": _UNIFIED_GAME["game_id"],
    "bookmaker": "Kalshi",
    "market_name": "moneyline",
    "outcome_name": "New York Rangers",
    "price": 0.57,
    "line": None,
    "last_update": "2026-05-03T13:55:00",
    "is_pregame": True,
    "external_id": "KXNHL-26MAY03NYRBOS-NYR",
    "loaded_at": "2026-05-03T13:56:00",
}

_BET_RECOMMENDATION: dict[str, Any] = {
    "bet_id": "DASHBOARD-SEED-NHL-20260503-NYR-BOS-HOME",
    "sport": "NHL",
    "recommendation_date": "2026-05-03",
    "home_team": "New York Rangers",
    "away_team": "Boston Bruins",
    "home_rating": 1582.4,
    "away_rating": 1547.0,
    "bet_on": "New York Rangers",
    "elo_prob": 0.62,
    "market_prob": 0.54,
    "edge": 0.08,
    "expected_value": 0.14,
    "kelly_fraction": 0.11,
    "confidence": "HIGH",
    "yes_ask": 54,
    "no_ask": 46,
    "ticker": _GAME_ODDS["external_id"],
    "quote_price_cents": 54,
    "quote_price_role": "executable",
    "quote_source_system": "bet_recommendation_payload",
    "quote_bookmaker": "Kalshi",
    "quote_observed_at": "2026-05-03T13:55:00",
    "quote_loaded_at": "2026-05-03T13:56:00",
    "quote_payload_ref": _GAME_ODDS["odds_id"],
    "quote_freshness_result": "fresh",
    "quote_fallback_status": "direct_quote",
    "created_at": "2026-05-03T14:00:00",
}

_PLACED_BET_OPEN: dict[str, Any] = {
    "bet_id": _BET_RECOMMENDATION["bet_id"],
    "sport": "NHL",
    "placed_date": "2026-05-03",
    "placed_time_utc": "2026-05-03T14:15:00",
    "ticker": _BET_RECOMMENDATION["ticker"],
    "home_team": _BET_RECOMMENDATION["home_team"],
    "away_team": _BET_RECOMMENDATION["away_team"],
    "bet_on": _BET_RECOMMENDATION["bet_on"],
    "side": "home",
    "contracts": 10,
    "price_cents": 54,
    "cost_dollars": 10.0,
    "fees_dollars": 0.35,
    "elo_prob": _BET_RECOMMENDATION["elo_prob"],
    "market_prob": _BET_RECOMMENDATION["market_prob"],
    "edge": _BET_RECOMMENDATION["edge"],
    "expected_value": _BET_RECOMMENDATION["expected_value"],
    "kelly_fraction": _BET_RECOMMENDATION["kelly_fraction"],
    "confidence": _BET_RECOMMENDATION["confidence"],
    "market_title": "New York Rangers vs Boston Bruins",
    "market_close_time_utc": "2026-05-03T23:00:00",
    "opening_line_prob": 0.52,
    "bet_line_prob": 0.54,
    "closing_line_prob": None,
    "clv": None,
    "status": "open",
    "settled_date": None,
    "payout_dollars": 18.5,
    "profit_dollars": 8.5,
    "source": "dashboard_seed",
    "recommendation_id": _BET_RECOMMENDATION["bet_id"],
    "recommendation_canonical_game_id": _UNIFIED_GAME["game_id"],
    "recommendation_market_ticker": _BET_RECOMMENDATION["ticker"],
    "recommendation_selection_key": _BET_RECOMMENDATION["bet_on"],
    "recommendation_linkage_status": "linked",
    "recommendation_linkage_basis": "market_ticker_selection_key_canonical_game_id",
    "entry_price_cents": 54,
    "entry_quote_role": "executable",
    "entry_price_source": "dashboard_seed",
    "entry_quote_source_system": "kalshi_market_details",
    "entry_quote_bookmaker": "Kalshi",
    "entry_quote_observed_at": "2026-05-03T14:15:00",
    "entry_quote_loaded_at": "2026-05-03T14:15:00",
    "entry_quote_payload_ref": _BET_RECOMMENDATION["bet_id"],
    "entry_quote_freshness_result": "fresh",
    "entry_quote_fallback_status": "direct_market_quote",
    "close_quote_source": None,
    "close_quote_at": None,
    "close_quote_loaded_at": None,
    "close_quote_payload_ref": None,
    "close_price_role": None,
    "close_freshness_result": None,
    "selected_close_rule": None,
    "selected_close_provenance": None,
    "close_fallback_status": None,
    "clv_source_type": None,
    "created_at": "2026-05-03T14:15:00",
    "updated_at": "2026-05-03T14:15:00",
}

_PLACED_BET_WON: dict[str, Any] = {
    **_PLACED_BET_OPEN,
    "bet_id": "DASHBOARD-SEED-NHL-20260501-CAR-NJD-HOME",
    "placed_date": "2026-05-01",
    "placed_time_utc": "2026-05-01T14:15:00",
    "ticker": "KXNHL-26MAY01CARNJD-CAR",
    "home_team": "Carolina Hurricanes",
    "away_team": "New Jersey Devils",
    "bet_on": "Carolina Hurricanes",
    "status": "won",
    "settled_date": "2026-05-02",
    "closing_line_prob": 0.58,
    "clv": 0.04,
    "recommendation_id": "DASHBOARD-SEED-NHL-20260501-CAR-NJD-HOME",
    "recommendation_canonical_game_id": "DASHBOARD-SEED-NHL-20260501-CAR-NJD",
    "recommendation_market_ticker": "KXNHL-26MAY01CARNJD-CAR",
    "recommendation_selection_key": "Carolina Hurricanes",
    "recommendation_linkage_status": "linked",
    "recommendation_linkage_basis": "market_ticker_selection_key_canonical_game_id",
    "entry_price_cents": 54,
    "entry_quote_role": "executable",
    "entry_price_source": "dashboard_seed",
    "entry_quote_source_system": "kalshi_market_details",
    "entry_quote_bookmaker": "Kalshi",
    "entry_quote_observed_at": "2026-05-01T14:15:00",
    "entry_quote_loaded_at": "2026-05-01T14:15:00",
    "entry_quote_payload_ref": "DASHBOARD-SEED-NHL-20260501-CAR-NJD-HOME",
    "entry_quote_freshness_result": "fresh",
    "entry_quote_fallback_status": "direct_market_quote",
    "close_quote_source": "SBR",
    "close_quote_at": "2026-05-01T22:55:00",
    "close_quote_loaded_at": "2026-05-01T22:56:00",
    "close_quote_payload_ref": "DASHBOARD-SEED-NHL-20260501-CAR-NJD-SBR-HOME",
    "close_price_role": "close",
    "close_freshness_result": "fresh",
    "selected_close_rule": "latest_admissible_pregame_quote",
    "selected_close_provenance": "SBR|Carolina Hurricanes|2026-05-01T22:55:00",
    "close_fallback_status": "latest_admissible_pregame_quote",
    "clv_source_type": "market_close",
    "created_at": "2026-05-01T14:15:00",
    "updated_at": "2026-05-02T03:15:00",
}

_CLV_UNIFIED_GAME: dict[str, Any] = {
    "game_id": "DASHBOARD-SEED-NHL-20260501-CAR-NJD",
    "sport": "NHL",
    "game_date": "2026-05-01",
    "season": 2026,
    "status": "scheduled",
    "home_team_id": "CAR",
    "home_team_name": "Carolina Hurricanes",
    "away_team_id": "NJD",
    "away_team_name": "New Jersey Devils",
    "home_score": None,
    "away_score": None,
    "commence_time": "2026-05-01T23:00:00",
    "venue": "PNC Arena",
    "loaded_at": "2026-05-01T20:00:00",
}

_CLV_GAME_ODDS: dict[str, Any] = {
    "odds_id": "DASHBOARD-SEED-NHL-20260501-CAR-NJD-SBR-HOME",
    "game_id": _CLV_UNIFIED_GAME["game_id"],
    "bookmaker": "SBR",
    "market_name": "moneyline",
    "outcome_name": "Carolina Hurricanes",
    "price": 1.72,
    "line": None,
    "last_update": "2026-05-01T22:55:00",
    "is_pregame": True,
    "external_id": _PLACED_BET_WON["ticker"],
    "loaded_at": "2026-05-01T22:56:00",
}

_ELO_RATING_NYR: dict[str, Any] = {
    "sport": "NHL",
    "entity_type": "team",
    "entity_id": "NYR",
    "entity_name": "New York Rangers",
    "rating": 1582.4,
    "valid_from": "2026-04-20T00:00:00",
    "valid_to": None,
    "games_played": 82,
    "created_at": "2026-04-20T00:05:00",
}

_ELO_RATING_BOS: dict[str, Any] = {
    **_ELO_RATING_NYR,
    "entity_id": "BOS",
    "entity_name": "Boston Bruins",
    "rating": 1547.0,
}

_TENNIS_MODEL_EVALUATION: dict[str, Any] = {
    "run_date": "2026-05-11",
    "model_version": "tennis_probability_model_v2",
    "data_source": "postgres_tennis_games",
    "rows": 960,
    "holdout_rows": 192,
    "betmgm_holdout_rows": 144,
    "enabled": True,
    "beats_betmgm": True,
    "baseline_log_loss": 0.6221,
    "ensemble_log_loss": 0.5982,
    "ensemble_market_log_loss": 0.6034,
    "betmgm_log_loss": 0.6178,
    "baseline_brier": 0.2174,
    "ensemble_brier": 0.2091,
    "ensemble_market_brier": 0.2108,
    "betmgm_brier": 0.2156,
    "baseline_accuracy": 0.6771,
    "ensemble_accuracy": 0.6979,
    "ensemble_market_accuracy": 0.6944,
    "betmgm_accuracy": 0.6875,
    "baseline_actionable_count": 81,
    "ensemble_actionable_count": 104,
    "log_loss_delta": -0.0239,
    "brier_delta": -0.0083,
    "accuracy_delta": 0.0208,
    "ensemble_vs_betmgm_log_loss_delta": -0.0144,
    "ensemble_vs_betmgm_brier_delta": -0.0048,
    "ensemble_vs_betmgm_accuracy_delta": 0.0069,
    "created_at": "2026-05-11T19:45:00",
}

_TENNIS_UNIFIED_GAME: dict[str, Any] = {
    "game_id": "DASHBOARD-SEED-TENNIS-20260504-ALP-BRA",
    "sport": "TENNIS",
    "game_date": "2026-05-04",
    "season": 2026,
    "status": "scheduled",
    "home_team_id": "ALP",
    "home_team_name": "Alpha A.",
    "away_team_id": "BRA",
    "away_team_name": "Bravo B.",
    "home_score": None,
    "away_score": None,
    "commence_time": "2026-05-04T16:00:00",
    "venue": "Centre Court",
    "loaded_at": "2026-05-03T13:50:00",
}

_TENNIS_GAME_ODDS: dict[str, Any] = {
    "odds_id": "DASHBOARD-SEED-TENNIS-20260504-ALP-BRA-KALSHI-HOME",
    "game_id": _TENNIS_UNIFIED_GAME["game_id"],
    "bookmaker": "Kalshi",
    "market_name": "match_winner",
    "outcome_name": "Alpha A.",
    "price": 0.56,
    "line": None,
    "last_update": "2026-05-03T13:58:00",
    "is_pregame": True,
    "external_id": "KXATPMATCH-26MAY04ALPBRA-ALP",
    "loaded_at": "2026-05-03T13:59:00",
}

_TENNIS_BET_RECOMMENDATION: dict[str, Any] = {
    "bet_id": "TENNIS_2026-05-04_KXATPMATCH-26MAY04ALPBRA-ALP_home",
    "sport": "TENNIS",
    "recommendation_date": "2026-05-04",
    "home_team": "Alpha A.",
    "away_team": "Bravo B.",
    "home_rating": 1610.2,
    "away_rating": 1548.1,
    "bet_on": "Alpha A.",
    "elo_prob": 0.64,
    "market_prob": 0.56,
    "edge": 0.08,
    "expected_value": 0.1429,
    "kelly_fraction": 0.18,
    "confidence": "HIGH",
    "yes_ask": 56,
    "no_ask": 44,
    "ticker": _TENNIS_GAME_ODDS["external_id"],
    "quote_price_cents": 56,
    "quote_price_role": "executable",
    "quote_source_system": "bet_recommendation_payload",
    "quote_bookmaker": "Kalshi",
    "quote_observed_at": "2026-05-03T13:58:00",
    "quote_loaded_at": "2026-05-03T13:59:00",
    "quote_payload_ref": _TENNIS_GAME_ODDS["odds_id"],
    "quote_freshness_result": "fresh",
    "quote_fallback_status": "direct_quote",
    "created_at": "2026-05-03T14:00:00",
}

_MLB_MODEL_PREDICTION: dict[str, Any] = {
    "prediction_id": "DASHBOARD-SEED-MLB-20260510-CHC-STL-MONEYLINE",
    "model_version": "mlb_moneyline_public_v1",
    "game_id": "DASHBOARD-SEED-MLB-20260510-CHC-STL",
    "market_name": "moneyline",
    "outcome_name": "Chicago Cubs",
    "run_date": "2026-05-10",
    "model_prob": 0.552,
    "market_prob": 0.537,
    "edge": 0.031,
    "expected_value": 0.058,
    "calibration_method": "isotonic",
    "ece_at_train": 0.031,
    "feature_hash": "dashboard-seed-mlb-moneyline-v1",
    "simulation_summary": None,
    "abstain": False,
    "abstention_reason": None,
    "created_at": "2026-05-10T14:00:00",
}


def build_dashboard_source_seed_payload(
    **overrides: Any,
) -> dict[str, list[dict[str, Any]]]:
    """Build deterministic source rows for non-empty dashboard read-model paths.

    Keyword overrides use ``table__index__field`` syntax, for example
    ``placed_bets__0__status="lost"``.
    """

    payload: dict[str, list[dict[str, Any]]] = {
        "portfolio_value_snapshots": [deepcopy(_PORTFOLIO_SNAPSHOT)],
        "unified_games": [
            deepcopy(_UNIFIED_GAME),
            deepcopy(_CLV_UNIFIED_GAME),
            deepcopy(_TENNIS_UNIFIED_GAME),
        ],
        "game_odds": [
            deepcopy(_GAME_ODDS),
            deepcopy(_CLV_GAME_ODDS),
            deepcopy(_TENNIS_GAME_ODDS),
        ],
        "bet_recommendations": [
            deepcopy(_BET_RECOMMENDATION),
            deepcopy(_TENNIS_BET_RECOMMENDATION),
        ],
        "placed_bets": [deepcopy(_PLACED_BET_OPEN), deepcopy(_PLACED_BET_WON)],
        "elo_ratings": [deepcopy(_ELO_RATING_NYR), deepcopy(_ELO_RATING_BOS)],
        "mlb_model_predictions": [deepcopy(_MLB_MODEL_PREDICTION)],
        "tennis_model_evaluations": [deepcopy(_TENNIS_MODEL_EVALUATION)],
    }

    for key, value in overrides.items():
        table, index_text, field = key.split("__", maxsplit=2)
        payload[table][int(index_text)][field] = value

    return payload


def build_dashboard_empty_state_seed_payload() -> dict[str, list[dict[str, Any]]]:
    """Build a zero-row payload for empty-state source-table scenarios."""

    return {table: [] for table in SOURCE_TABLE_KEYS}


def seed_dashboard_source_rows(
    db: Any,
    payload: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, int]:
    """Upsert dashboard fixture rows into source tables using logical keys."""

    rows = payload or build_dashboard_source_seed_payload()
    _upsert_portfolio_snapshots(db, rows["portfolio_value_snapshots"])
    _upsert_unified_games(db, rows["unified_games"])
    _upsert_game_odds(db, rows["game_odds"])
    _upsert_bet_recommendations(db, rows["bet_recommendations"])
    _upsert_placed_bets(db, rows["placed_bets"])
    _upsert_elo_ratings(db, rows["elo_ratings"])
    _upsert_mlb_model_predictions(db, rows["mlb_model_predictions"])
    _upsert_tennis_model_evaluations(db, rows["tennis_model_evaluations"])
    return {table: len(table_rows) for table, table_rows in rows.items()}


def clear_dashboard_source_rows(
    db: Any,
    payload: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, int]:
    """Delete only deterministic dashboard seed rows; schemas/views remain intact."""

    rows = payload or build_dashboard_source_seed_payload()
    for row in rows["placed_bets"]:
        db.execute(
            "DELETE FROM placed_bets WHERE bet_id = :bet_id", {"bet_id": row["bet_id"]}
        )
    for row in rows["bet_recommendations"]:
        db.execute(
            "DELETE FROM bet_recommendations WHERE bet_id = :bet_id",
            {"bet_id": row["bet_id"]},
        )
    for row in rows["game_odds"]:
        db.execute(
            "DELETE FROM game_odds WHERE odds_id = :odds_id",
            {"odds_id": row["odds_id"]},
        )
    for row in rows["unified_games"]:
        db.execute(
            "DELETE FROM unified_games WHERE game_id = :game_id",
            {"game_id": row["game_id"]},
        )
    for row in rows["elo_ratings"]:
        db.execute(
            """
            DELETE FROM elo_ratings
            WHERE sport = :sport
              AND entity_type = :entity_type
              AND entity_id = :entity_id
              AND valid_from = :valid_from
            """,
            row,
        )
    for row in rows["mlb_model_predictions"]:
        db.execute(
            """
            DELETE FROM mlb_model_predictions
            WHERE prediction_id = :prediction_id
            """,
            row,
        )
    for row in rows["tennis_model_evaluations"]:
        db.execute(
            """
            DELETE FROM tennis_model_evaluations
            WHERE run_date = :run_date
              AND model_version = :model_version
              AND data_source = :data_source
            """,
            row,
        )
    for row in rows["portfolio_value_snapshots"]:
        db.execute(
            """
            DELETE FROM portfolio_value_snapshots
            WHERE snapshot_hour_utc = :snapshot_hour_utc
            """,
            row,
        )
    return {table: 0 for table in SOURCE_TABLE_KEYS}


def seed_dashboard_empty_state_source_rows(db: Any) -> dict[str, int]:
    """Prepare zero-row dashboard fixture state without dropping relations."""

    clear_dashboard_source_rows(db)
    return seed_dashboard_source_rows(db, build_dashboard_empty_state_seed_payload())


def _upsert_portfolio_snapshots(db: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.execute(
            """
            INSERT INTO portfolio_value_snapshots (
                snapshot_hour_utc,
                balance_dollars,
                portfolio_value_dollars,
                cumulative_deposits_dollars,
                drawdown_gate_active,
                drawdown_gate_reason_code,
                drawdown_gate_reason_detail,
                created_at_utc
            ) VALUES (
                :snapshot_hour_utc,
                :balance_dollars,
                :portfolio_value_dollars,
                :cumulative_deposits_dollars,
                :drawdown_gate_active,
                :drawdown_gate_reason_code,
                :drawdown_gate_reason_detail,
                :created_at_utc
            )
            ON CONFLICT (snapshot_hour_utc) DO UPDATE SET
                balance_dollars = EXCLUDED.balance_dollars,
                portfolio_value_dollars = EXCLUDED.portfolio_value_dollars,
                cumulative_deposits_dollars = EXCLUDED.cumulative_deposits_dollars,
                drawdown_gate_active = EXCLUDED.drawdown_gate_active,
                drawdown_gate_reason_code = EXCLUDED.drawdown_gate_reason_code,
                drawdown_gate_reason_detail = EXCLUDED.drawdown_gate_reason_detail,
                created_at_utc = EXCLUDED.created_at_utc
            """,
            row,
        )


def _upsert_unified_games(db: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.execute(
            """
            INSERT INTO unified_games (
                game_id,
                sport,
                game_date,
                season,
                status,
                home_team_id,
                home_team_name,
                away_team_id,
                away_team_name,
                home_score,
                away_score,
                commence_time,
                venue,
                loaded_at
            ) VALUES (
                :game_id,
                :sport,
                :game_date,
                :season,
                :status,
                :home_team_id,
                :home_team_name,
                :away_team_id,
                :away_team_name,
                :home_score,
                :away_score,
                :commence_time,
                :venue,
                :loaded_at
            )
            ON CONFLICT (game_id) DO UPDATE SET
                sport = EXCLUDED.sport,
                game_date = EXCLUDED.game_date,
                season = EXCLUDED.season,
                status = EXCLUDED.status,
                home_team_id = EXCLUDED.home_team_id,
                home_team_name = EXCLUDED.home_team_name,
                away_team_id = EXCLUDED.away_team_id,
                away_team_name = EXCLUDED.away_team_name,
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                commence_time = EXCLUDED.commence_time,
                venue = EXCLUDED.venue,
                loaded_at = EXCLUDED.loaded_at
            """,
            row,
        )


def _upsert_game_odds(db: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.execute(
            """
            INSERT INTO game_odds (
                odds_id,
                game_id,
                bookmaker,
                market_name,
                outcome_name,
                price,
                line,
                last_update,
                is_pregame,
                external_id,
                loaded_at
            ) VALUES (
                :odds_id,
                :game_id,
                :bookmaker,
                :market_name,
                :outcome_name,
                :price,
                :line,
                :last_update,
                :is_pregame,
                :external_id,
                :loaded_at
            )
            ON CONFLICT (odds_id) DO UPDATE SET
                game_id = EXCLUDED.game_id,
                bookmaker = EXCLUDED.bookmaker,
                market_name = EXCLUDED.market_name,
                outcome_name = EXCLUDED.outcome_name,
                price = EXCLUDED.price,
                line = EXCLUDED.line,
                last_update = EXCLUDED.last_update,
                is_pregame = EXCLUDED.is_pregame,
                external_id = EXCLUDED.external_id,
                loaded_at = EXCLUDED.loaded_at
            """,
            row,
        )


def _upsert_bet_recommendations(db: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.execute(
            """
            INSERT INTO bet_recommendations (
                bet_id,
                sport,
                recommendation_date,
                home_team,
                away_team,
                home_rating,
                away_rating,
                bet_on,
                elo_prob,
                market_prob,
                edge,
                expected_value,
                kelly_fraction,
                confidence,
                yes_ask,
                no_ask,
                ticker,
                quote_price_cents,
                quote_price_role,
                quote_source_system,
                quote_bookmaker,
                quote_observed_at,
                quote_loaded_at,
                quote_payload_ref,
                quote_freshness_result,
                quote_fallback_status,
                created_at
            ) VALUES (
                :bet_id,
                :sport,
                :recommendation_date,
                :home_team,
                :away_team,
                :home_rating,
                :away_rating,
                :bet_on,
                :elo_prob,
                :market_prob,
                :edge,
                :expected_value,
                :kelly_fraction,
                :confidence,
                :yes_ask,
                :no_ask,
                :ticker,
                :quote_price_cents,
                :quote_price_role,
                :quote_source_system,
                :quote_bookmaker,
                :quote_observed_at,
                :quote_loaded_at,
                :quote_payload_ref,
                :quote_freshness_result,
                :quote_fallback_status,
                :created_at
            )
            ON CONFLICT (bet_id) DO UPDATE SET
                sport = EXCLUDED.sport,
                recommendation_date = EXCLUDED.recommendation_date,
                home_team = EXCLUDED.home_team,
                away_team = EXCLUDED.away_team,
                home_rating = EXCLUDED.home_rating,
                away_rating = EXCLUDED.away_rating,
                bet_on = EXCLUDED.bet_on,
                elo_prob = EXCLUDED.elo_prob,
                market_prob = EXCLUDED.market_prob,
                edge = EXCLUDED.edge,
                expected_value = EXCLUDED.expected_value,
                kelly_fraction = EXCLUDED.kelly_fraction,
                confidence = EXCLUDED.confidence,
                yes_ask = EXCLUDED.yes_ask,
                no_ask = EXCLUDED.no_ask,
                ticker = EXCLUDED.ticker,
                quote_price_cents = EXCLUDED.quote_price_cents,
                quote_price_role = EXCLUDED.quote_price_role,
                quote_source_system = EXCLUDED.quote_source_system,
                quote_bookmaker = EXCLUDED.quote_bookmaker,
                quote_observed_at = EXCLUDED.quote_observed_at,
                quote_loaded_at = EXCLUDED.quote_loaded_at,
                quote_payload_ref = EXCLUDED.quote_payload_ref,
                quote_freshness_result = EXCLUDED.quote_freshness_result,
                quote_fallback_status = EXCLUDED.quote_fallback_status,
                created_at = EXCLUDED.created_at
            """,
            row,
        )


def _upsert_placed_bets(db: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.execute(
            """
            INSERT INTO placed_bets (
                bet_id,
                sport,
                placed_date,
                placed_time_utc,
                ticker,
                home_team,
                away_team,
                bet_on,
                side,
                contracts,
                price_cents,
                cost_dollars,
                fees_dollars,
                elo_prob,
                market_prob,
                edge,
                expected_value,
                kelly_fraction,
                confidence,
                market_title,
                market_close_time_utc,
                opening_line_prob,
                bet_line_prob,
                closing_line_prob,
                clv,
                status,
                settled_date,
                payout_dollars,
                profit_dollars,
                source,
                recommendation_id,
                recommendation_canonical_game_id,
                recommendation_market_ticker,
                recommendation_selection_key,
                recommendation_linkage_status,
                recommendation_linkage_basis,
                entry_price_cents,
                entry_quote_role,
                entry_price_source,
                entry_quote_source_system,
                entry_quote_bookmaker,
                entry_quote_observed_at,
                entry_quote_loaded_at,
                entry_quote_payload_ref,
                entry_quote_freshness_result,
                entry_quote_fallback_status,
                close_quote_source,
                close_quote_at,
                close_quote_loaded_at,
                close_quote_payload_ref,
                close_price_role,
                close_freshness_result,
                selected_close_rule,
                selected_close_provenance,
                close_fallback_status,
                clv_source_type,
                created_at,
                updated_at
            ) VALUES (
                :bet_id,
                :sport,
                :placed_date,
                :placed_time_utc,
                :ticker,
                :home_team,
                :away_team,
                :bet_on,
                :side,
                :contracts,
                :price_cents,
                :cost_dollars,
                :fees_dollars,
                :elo_prob,
                :market_prob,
                :edge,
                :expected_value,
                :kelly_fraction,
                :confidence,
                :market_title,
                :market_close_time_utc,
                :opening_line_prob,
                :bet_line_prob,
                :closing_line_prob,
                :clv,
                :status,
                :settled_date,
                :payout_dollars,
                :profit_dollars,
                :source,
                :recommendation_id,
                :recommendation_canonical_game_id,
                :recommendation_market_ticker,
                :recommendation_selection_key,
                :recommendation_linkage_status,
                :recommendation_linkage_basis,
                :entry_price_cents,
                :entry_quote_role,
                :entry_price_source,
                :entry_quote_source_system,
                :entry_quote_bookmaker,
                :entry_quote_observed_at,
                :entry_quote_loaded_at,
                :entry_quote_payload_ref,
                :entry_quote_freshness_result,
                :entry_quote_fallback_status,
                :close_quote_source,
                :close_quote_at,
                :close_quote_loaded_at,
                :close_quote_payload_ref,
                :close_price_role,
                :close_freshness_result,
                :selected_close_rule,
                :selected_close_provenance,
                :close_fallback_status,
                :clv_source_type,
                :created_at,
                :updated_at
            )
            ON CONFLICT (bet_id) DO UPDATE SET
                sport = EXCLUDED.sport,
                placed_date = EXCLUDED.placed_date,
                placed_time_utc = EXCLUDED.placed_time_utc,
                ticker = EXCLUDED.ticker,
                home_team = EXCLUDED.home_team,
                away_team = EXCLUDED.away_team,
                bet_on = EXCLUDED.bet_on,
                side = EXCLUDED.side,
                contracts = EXCLUDED.contracts,
                price_cents = EXCLUDED.price_cents,
                cost_dollars = EXCLUDED.cost_dollars,
                fees_dollars = EXCLUDED.fees_dollars,
                elo_prob = EXCLUDED.elo_prob,
                market_prob = EXCLUDED.market_prob,
                edge = EXCLUDED.edge,
                expected_value = EXCLUDED.expected_value,
                kelly_fraction = EXCLUDED.kelly_fraction,
                confidence = EXCLUDED.confidence,
                market_title = EXCLUDED.market_title,
                market_close_time_utc = EXCLUDED.market_close_time_utc,
                opening_line_prob = EXCLUDED.opening_line_prob,
                bet_line_prob = EXCLUDED.bet_line_prob,
                closing_line_prob = EXCLUDED.closing_line_prob,
                clv = EXCLUDED.clv,
                status = EXCLUDED.status,
                settled_date = EXCLUDED.settled_date,
                payout_dollars = EXCLUDED.payout_dollars,
                profit_dollars = EXCLUDED.profit_dollars,
                source = EXCLUDED.source,
                recommendation_id = EXCLUDED.recommendation_id,
                recommendation_canonical_game_id = EXCLUDED.recommendation_canonical_game_id,
                recommendation_market_ticker = EXCLUDED.recommendation_market_ticker,
                recommendation_selection_key = EXCLUDED.recommendation_selection_key,
                recommendation_linkage_status = EXCLUDED.recommendation_linkage_status,
                recommendation_linkage_basis = EXCLUDED.recommendation_linkage_basis,
                entry_price_cents = EXCLUDED.entry_price_cents,
                entry_quote_role = EXCLUDED.entry_quote_role,
                entry_price_source = EXCLUDED.entry_price_source,
                entry_quote_source_system = EXCLUDED.entry_quote_source_system,
                entry_quote_bookmaker = EXCLUDED.entry_quote_bookmaker,
                entry_quote_observed_at = EXCLUDED.entry_quote_observed_at,
                entry_quote_loaded_at = EXCLUDED.entry_quote_loaded_at,
                entry_quote_payload_ref = EXCLUDED.entry_quote_payload_ref,
                entry_quote_freshness_result = EXCLUDED.entry_quote_freshness_result,
                entry_quote_fallback_status = EXCLUDED.entry_quote_fallback_status,
                close_quote_source = EXCLUDED.close_quote_source,
                close_quote_at = EXCLUDED.close_quote_at,
                close_quote_loaded_at = EXCLUDED.close_quote_loaded_at,
                close_quote_payload_ref = EXCLUDED.close_quote_payload_ref,
                close_price_role = EXCLUDED.close_price_role,
                close_freshness_result = EXCLUDED.close_freshness_result,
                selected_close_rule = EXCLUDED.selected_close_rule,
                selected_close_provenance = EXCLUDED.selected_close_provenance,
                close_fallback_status = EXCLUDED.close_fallback_status,
                clv_source_type = EXCLUDED.clv_source_type,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            row,
        )


def _upsert_elo_ratings(db: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.execute(
            """
            INSERT INTO elo_ratings (
                sport,
                entity_type,
                entity_id,
                entity_name,
                rating,
                valid_from,
                valid_to,
                games_played,
                created_at
            ) VALUES (
                :sport,
                :entity_type,
                :entity_id,
                :entity_name,
                :rating,
                :valid_from,
                :valid_to,
                :games_played,
                :created_at
            )
            ON CONFLICT (sport, entity_type, entity_id)
            WHERE valid_to IS NULL
            DO UPDATE SET
                entity_name = EXCLUDED.entity_name,
                rating = EXCLUDED.rating,
                valid_from = EXCLUDED.valid_from,
                games_played = EXCLUDED.games_played,
                created_at = EXCLUDED.created_at
            """,
            row,
        )


def _upsert_tennis_model_evaluations(db: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.execute(
            """
            INSERT INTO tennis_model_evaluations (
                run_date,
                model_version,
                data_source,
                rows,
                holdout_rows,
                betmgm_holdout_rows,
                enabled,
                beats_betmgm,
                baseline_log_loss,
                ensemble_log_loss,
                ensemble_market_log_loss,
                betmgm_log_loss,
                baseline_brier,
                ensemble_brier,
                ensemble_market_brier,
                betmgm_brier,
                baseline_accuracy,
                ensemble_accuracy,
                ensemble_market_accuracy,
                betmgm_accuracy,
                baseline_actionable_count,
                ensemble_actionable_count,
                log_loss_delta,
                brier_delta,
                accuracy_delta,
                ensemble_vs_betmgm_log_loss_delta,
                ensemble_vs_betmgm_brier_delta,
                ensemble_vs_betmgm_accuracy_delta,
                created_at
            ) VALUES (
                :run_date,
                :model_version,
                :data_source,
                :rows,
                :holdout_rows,
                :betmgm_holdout_rows,
                :enabled,
                :beats_betmgm,
                :baseline_log_loss,
                :ensemble_log_loss,
                :ensemble_market_log_loss,
                :betmgm_log_loss,
                :baseline_brier,
                :ensemble_brier,
                :ensemble_market_brier,
                :betmgm_brier,
                :baseline_accuracy,
                :ensemble_accuracy,
                :ensemble_market_accuracy,
                :betmgm_accuracy,
                :baseline_actionable_count,
                :ensemble_actionable_count,
                :log_loss_delta,
                :brier_delta,
                :accuracy_delta,
                :ensemble_vs_betmgm_log_loss_delta,
                :ensemble_vs_betmgm_brier_delta,
                :ensemble_vs_betmgm_accuracy_delta,
                :created_at
            )
            ON CONFLICT (run_date, model_version, data_source) DO UPDATE SET
                rows = EXCLUDED.rows,
                holdout_rows = EXCLUDED.holdout_rows,
                betmgm_holdout_rows = EXCLUDED.betmgm_holdout_rows,
                enabled = EXCLUDED.enabled,
                beats_betmgm = EXCLUDED.beats_betmgm,
                baseline_log_loss = EXCLUDED.baseline_log_loss,
                ensemble_log_loss = EXCLUDED.ensemble_log_loss,
                ensemble_market_log_loss = EXCLUDED.ensemble_market_log_loss,
                betmgm_log_loss = EXCLUDED.betmgm_log_loss,
                baseline_brier = EXCLUDED.baseline_brier,
                ensemble_brier = EXCLUDED.ensemble_brier,
                ensemble_market_brier = EXCLUDED.ensemble_market_brier,
                betmgm_brier = EXCLUDED.betmgm_brier,
                baseline_accuracy = EXCLUDED.baseline_accuracy,
                ensemble_accuracy = EXCLUDED.ensemble_accuracy,
                ensemble_market_accuracy = EXCLUDED.ensemble_market_accuracy,
                betmgm_accuracy = EXCLUDED.betmgm_accuracy,
                baseline_actionable_count = EXCLUDED.baseline_actionable_count,
                ensemble_actionable_count = EXCLUDED.ensemble_actionable_count,
                log_loss_delta = EXCLUDED.log_loss_delta,
                brier_delta = EXCLUDED.brier_delta,
                accuracy_delta = EXCLUDED.accuracy_delta,
                ensemble_vs_betmgm_log_loss_delta = EXCLUDED.ensemble_vs_betmgm_log_loss_delta,
                ensemble_vs_betmgm_brier_delta = EXCLUDED.ensemble_vs_betmgm_brier_delta,
                ensemble_vs_betmgm_accuracy_delta = EXCLUDED.ensemble_vs_betmgm_accuracy_delta,
                created_at = EXCLUDED.created_at
            """,
            row,
        )


def _upsert_mlb_model_predictions(db: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        db.execute(
            """
            INSERT INTO mlb_model_predictions (
                prediction_id,
                model_version,
                game_id,
                market_name,
                outcome_name,
                run_date,
                model_prob,
                market_prob,
                edge,
                expected_value,
                calibration_method,
                ece_at_train,
                feature_hash,
                simulation_summary,
                abstain,
                abstention_reason,
                created_at
            ) VALUES (
                :prediction_id,
                :model_version,
                :game_id,
                :market_name,
                :outcome_name,
                :run_date,
                :model_prob,
                :market_prob,
                :edge,
                :expected_value,
                :calibration_method,
                :ece_at_train,
                :feature_hash,
                :simulation_summary,
                :abstain,
                :abstention_reason,
                :created_at
            )
            ON CONFLICT (prediction_id) DO UPDATE SET
                model_version = EXCLUDED.model_version,
                game_id = EXCLUDED.game_id,
                market_name = EXCLUDED.market_name,
                outcome_name = EXCLUDED.outcome_name,
                run_date = EXCLUDED.run_date,
                model_prob = EXCLUDED.model_prob,
                market_prob = EXCLUDED.market_prob,
                edge = EXCLUDED.edge,
                expected_value = EXCLUDED.expected_value,
                calibration_method = EXCLUDED.calibration_method,
                ece_at_train = EXCLUDED.ece_at_train,
                feature_hash = EXCLUDED.feature_hash,
                simulation_summary = EXCLUDED.simulation_summary,
                abstain = EXCLUDED.abstain,
                abstention_reason = EXCLUDED.abstention_reason,
                created_at = EXCLUDED.created_at
            """,
            row,
        )
