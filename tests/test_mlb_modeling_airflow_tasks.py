"""Tests for MLB predictive-modeling Airflow task helpers."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

from plugins.mlb_modeling.airflow_tasks import (
    MODEL_ARTIFACT_UNAVAILABLE_REASON,
    MODEL_FEATURES_UNAVAILABLE_REASON,
    assemble_mlb_matchup_features,
    build_abstaining_moneyline_payloads,
    compute_mlb_rolling_features,
    fetch_mlb_environment_features,
    fetch_mlb_player_stats,
    fetch_mlb_travel_features,
    score_mlb_moneyline_model,
    train_mlb_model_periodic,
)
from plugins.mlb_modeling.models import (
    MoneylineTrainingRow,
    save_moneyline_model_artifact,
    train_logistic_moneyline_model,
)
from tests.contracts.helpers import validate_contract_payload


SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


class _FakeDb:
    def __init__(
        self,
        games: pd.DataFrame,
        *,
        features: pd.DataFrame | None = None,
        odds: pd.DataFrame | None = None,
    ) -> None:
        self.games = games
        self.features = features if features is not None else pd.DataFrame()
        self.odds = odds if odds is not None else pd.DataFrame()
        self.fetch_calls: list[tuple[str, dict]] = []
        self.execute_calls: list[tuple[str, dict]] = []

    def fetch_df(self, sql: str, params: dict) -> pd.DataFrame:
        self.fetch_calls.append((sql, params))
        if "FROM mlb_matchup_features" in sql:
            return self.features
        if "FROM game_odds" in sql:
            return self.odds
        return self.games

    def execute(self, sql: str, params: dict | None = None) -> None:
        self.execute_calls.append((sql, params or {}))


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


def _build_test_artifact(tmp_path: Path) -> Path:
    artifact = train_logistic_moneyline_model(
        [
            MoneylineTrainingRow(date(2026, 4, 1), {"elo": 0.55, "woba": 0.01}, 1),
            MoneylineTrainingRow(date(2026, 4, 2), {"elo": 0.45, "woba": -0.02}, 0),
            MoneylineTrainingRow(date(2026, 4, 3), {"elo": 0.62, "woba": 0.03}, 1),
            MoneylineTrainingRow(date(2026, 4, 4), {"elo": 0.40, "woba": -0.04}, 0),
        ],
        model_version="mlb_moneyline_public_test_v1",
    )
    model_path = tmp_path / "mlb_moneyline_public_test_v1.joblib"
    save_moneyline_model_artifact(artifact, model_path=model_path)
    return model_path


def test_build_abstaining_moneyline_payloads_match_prediction_contract() -> None:
    """Model-artifact abstentions are explicit, contract-shaped predictions."""
    payloads = build_abstaining_moneyline_payloads(
        game_id="777001",
        home_team="Los Angeles Dodgers",
        away_team="San Diego Padres",
        run_date=date(2026, 5, 10),
    )

    assert [payload["outcome_name"] for payload in payloads] == ["home", "away"]
    for payload in payloads:
        validate_contract_payload(payload, _load_schema("mlb_model_prediction_v1.json"))
        assert payload["model_prob"] == 0.5
        assert payload["abstain"] is True
        assert payload["abstention_reason"] == MODEL_ARTIFACT_UNAVAILABLE_REASON


def test_score_mlb_moneyline_model_upserts_two_abstentions_per_game() -> None:
    """Airflow helper is idempotent and records abstentions for dashboard health."""
    db = _FakeDb(
        pd.DataFrame(
            [
                {
                    "game_id": 777001,
                    "home_team": "Los Angeles Dodgers",
                    "away_team": "San Diego Padres",
                },
                {
                    "game_id": 777002,
                    "home_team": "New York Yankees",
                    "away_team": "Boston Red Sox",
                },
            ]
        )
    )

    result = score_mlb_moneyline_model(run_date="2026-05-10", db=db, horizon_days=2)

    assert result == {
        "games_scored": 2,
        "predictions_written": 4,
        "abstentions_written": 4,
    }
    assert db.fetch_calls
    _, fetch_params = db.fetch_calls[0]
    assert fetch_params == {"run_date": "2026-05-10", "end_date": "2026-05-12"}
    assert len(db.execute_calls) == 4
    sql, params = db.execute_calls[0]
    assert "INSERT INTO mlb_model_predictions" in sql
    assert "ON CONFLICT (prediction_id) DO UPDATE" in sql
    assert params["abstain"] is True


def test_score_mlb_moneyline_model_writes_live_predictions_when_artifact_and_features_exist(
    tmp_path,
) -> None:
    model_path = _build_test_artifact(tmp_path)
    db = _FakeDb(
        pd.DataFrame(
            [
                {
                    "game_id": 777001,
                    "home_team": "Los Angeles Dodgers",
                    "away_team": "San Diego Padres",
                }
            ]
        ),
        features=pd.DataFrame(
            [
                {
                    "feature_hash": "abc123def4567890",
                    "feature_vector": {"elo": 0.58, "woba": 0.02},
                    "feature_availability": {
                        "elo": "available",
                        "woba": "available",
                    },
                    "abstention_reasons": [],
                    "as_of_ts": "2026-05-10T14:00:00",
                }
            ]
        ),
        odds=pd.DataFrame(
            [
                {"outcome_name": "home", "price": 1.9},
                {"outcome_name": "away", "price": 2.1},
            ]
        ),
    )

    result = score_mlb_moneyline_model(
        run_date="2026-05-10",
        db=db,
        horizon_days=2,
        model_path=model_path,
    )

    assert result == {
        "games_scored": 1,
        "predictions_written": 2,
        "abstentions_written": 0,
    }
    assert len(db.execute_calls) == 2
    home_params = db.execute_calls[0][1]
    away_params = db.execute_calls[1][1]
    assert home_params["abstain"] is False
    assert away_params["abstain"] is False
    assert 0.0 < home_params["model_prob"] < 1.0
    assert away_params["model_prob"] == 1.0 - home_params["model_prob"]


def test_score_mlb_moneyline_model_abstains_when_matchup_features_are_stale(
    tmp_path,
) -> None:
    model_path = _build_test_artifact(tmp_path)
    db = _FakeDb(
        pd.DataFrame(
            [
                {
                    "game_id": 777001,
                    "home_team": "Los Angeles Dodgers",
                    "away_team": "San Diego Padres",
                }
            ]
        ),
        features=pd.DataFrame(
            [
                {
                    "game_id": 777001,
                    "side": "home",
                    "feature_hash": "stalehash",
                    "feature_vector": {"elo": 0.58, "woba": 0.02},
                    "feature_availability": {
                        "elo": "available",
                        "woba": "available",
                    },
                    "abstention_reasons": [],
                    "as_of_ts": "2026-05-09T23:59:59",
                }
            ]
        ),
    )

    result = score_mlb_moneyline_model(
        run_date="2026-05-10",
        db=db,
        horizon_days=2,
        model_path=model_path,
    )

    assert result == {
        "games_scored": 1,
        "predictions_written": 2,
        "abstentions_written": 2,
    }
    assert len(db.execute_calls) == 2
    assert all(call[1]["abstain"] is True for call in db.execute_calls)
    assert all(
        call[1]["abstention_reason"] == MODEL_FEATURES_UNAVAILABLE_REASON
        for call in db.execute_calls
    )
    assert db.fetch_calls[1][1] == {
        "game_id": "777001",
        "run_start": "2026-05-10 00:00:00",
        "run_end": "2026-05-11 00:00:00",
    }


def test_score_mlb_moneyline_model_abstains_when_matchup_features_are_absent(
    tmp_path,
) -> None:
    model_path = _build_test_artifact(tmp_path)
    db = _FakeDb(
        pd.DataFrame(
            [
                {
                    "game_id": 777001,
                    "home_team": "Los Angeles Dodgers",
                    "away_team": "San Diego Padres",
                }
            ]
        )
    )

    result = score_mlb_moneyline_model(
        run_date="2026-05-10",
        db=db,
        horizon_days=2,
        model_path=model_path,
    )

    assert result == {
        "games_scored": 1,
        "predictions_written": 2,
        "abstentions_written": 2,
    }
    assert all(call[1]["abstain"] is True for call in db.execute_calls)
    assert all(
        call[1]["abstention_reason"] == MODEL_FEATURES_UNAVAILABLE_REASON
        for call in db.execute_calls
    )


def test_score_mlb_moneyline_model_no_games_is_noop() -> None:
    """No upcoming games should not emit placeholder prediction rows."""
    db = _FakeDb(pd.DataFrame())

    result = score_mlb_moneyline_model(run_date="2026-05-10", db=db)

    assert result == {
        "games_scored": 0,
        "predictions_written": 0,
        "abstentions_written": 0,
    }
    assert db.execute_calls == []


# ---------------------------------------------------------------------------
# Tests for new upstream callables
# ---------------------------------------------------------------------------


class TestFetchMlbPlayerStats:
    def test_no_completed_games_returns_zeros(self) -> None:
        """Empty completed-games query yields zero counts."""
        db = _FakeDb(pd.DataFrame())

        result = fetch_mlb_player_stats(run_date="2026-05-10", db=db)

        assert result == {"games_fetched": 0, "batting_rows": 0, "pitching_rows": 0}


class TestComputeMlbRollingFeatures:
    def test_empty_data_returns_zero_upserted(self) -> None:
        """When no player data exists, zero rows are upserted."""
        db = _FakeDb(pd.DataFrame())
        db.execute_calls = []

        result = compute_mlb_rolling_features(run_date="2026-05-10", db=db)

        assert "rows_upserted" in result
        assert "as_of_date" in result
        assert result["as_of_date"] == "2026-05-10"
        assert isinstance(result["rows_upserted"], int)


class TestAssembleMlbMatchupFeatures:
    def test_no_upcoming_games_returns_zeros(self) -> None:
        """No upcoming games yields zero assembled."""
        db = _FakeDb(pd.DataFrame())

        result = assemble_mlb_matchup_features(run_date="2026-05-10", db=db, horizon_days=2)

        assert result == {"games_assembled": 0}


class TestTrainMlbModelPeriodic:
    def test_no_training_games_returns_skipped(self) -> None:
        """When no completed games exist, returns skipped status instead of raising."""
        db = _FakeDb(pd.DataFrame())
        db.execute_calls = []

        result = train_mlb_model_periodic(run_date="2026-05-10", db=db)

        assert result["skipped"] is True
        assert result["reason"] == "no_training_rows"
        assert result["training_rows"] == 0


class TestFetchMlbEnvironmentFeatures:
    def test_no_upcoming_games_returns_zeros(self) -> None:
        """No upcoming games yields zero features stored."""
        db = _FakeDb(pd.DataFrame())

        result = fetch_mlb_environment_features(run_date="2026-05-10", db=db, horizon_days=2)

        assert result == {"features_stored": 0}


class TestFetchMlbTravelFeatures:
    def test_no_upcoming_games_returns_zeros(self) -> None:
        """No upcoming games yields zero features stored."""
        db = _FakeDb(pd.DataFrame())

        result = fetch_mlb_travel_features(run_date="2026-05-10", db=db, horizon_days=2)

        assert result == {"features_stored": 0}
