"""Tests for the governed MLB rollout path."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
for relative_path in ("dags", "plugins"):
    candidate = str(REPO_ROOT / relative_path)
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import multi_sport_betting_workflow as workflow
from plugins.odds_comparator import (
    BettingOpportunityConfig,
    BettingThresholds,
    OddsComparator,
)


class _RolloutDb:
    def __init__(
        self,
        *,
        games: pd.DataFrame,
        odds: pd.DataFrame,
        predictions: pd.DataFrame | None = None,
    ) -> None:
        self.games = games
        self.odds = odds
        self.predictions = predictions if predictions is not None else pd.DataFrame()

    def fetch_df(self, query: str, params: dict | None = None) -> pd.DataFrame:
        if "FROM unified_games" in query:
            return self.games.copy()
        if "FROM game_odds" in query:
            return self.odds.copy()
        if "FROM mlb_model_predictions" in query:
            return self.predictions.copy()
        if "FROM mlb_market_signals" in query:
            return pd.DataFrame()
        raise AssertionError(f"Unexpected query: {query}")


def _elo_stub(home_prob: float = 0.2, *, governed: bool = False) -> SimpleNamespace:
    stub = SimpleNamespace(
        predict=lambda home, away: home_prob,
        get_rating=lambda team: 1550.0,
        has_real_rating=lambda *args, **kwargs: True,
    )
    if governed:
        stub.requires_governed_predictions = True
    return stub


def test_governed_mlb_selection_uses_prediction_rows_over_elo_fallback(monkeypatch) -> None:
    comparator = OddsComparator(
        db_manager=_RolloutDb(
            games=pd.DataFrame(
                [
                    {
                        "game_id": "mlb-1",
                        "game_date": "2026-05-10",
                        "home_team_name": "Dodgers",
                        "away_team_name": "Padres",
                        "status": "Scheduled",
                    }
                ]
            ),
            odds=pd.DataFrame(
                [
                    {
                        "bookmaker": "Kalshi",
                        "outcome_name": "home",
                        "price": 2.0,
                        "last_update": "now",
                        "external_id": "kalshi-home",
                    },
                    {
                        "bookmaker": "Kalshi",
                        "outcome_name": "away",
                        "price": 2.1,
                        "last_update": "now",
                        "external_id": "kalshi-away",
                    },
                ]
            ),
            predictions=pd.DataFrame(
                [
                    {"outcome_name": "home", "model_prob": 0.7},
                    {"outcome_name": "away", "model_prob": 0.3},
                ]
            ),
        )
    )
    monkeypatch.setattr(
        comparator, "_get_source", lambda game_id: "kalshi", raising=False
    )
    monkeypatch.setattr(
        comparator, "_resolve_name", lambda context: context.name, raising=False
    )

    opportunities = comparator.find_opportunities(
        BettingOpportunityConfig(
            sport="mlb",
            elo_system=_elo_stub(governed=True),
            thresholds=BettingThresholds(min_edge=0.03, max_edge=1.0),
            date_str="2026-05-10",
        )
    )

    assert len(opportunities) == 1
    assert opportunities[0]["bet_on"] == "Dodgers"
    assert opportunities[0]["elo_prob"] == 0.7


def test_governed_mlb_missing_predictions_returns_zero_picks_and_nba_is_unaffected(
    monkeypatch,
) -> None:
    mlb_comparator = OddsComparator(
        db_manager=_RolloutDb(
            games=pd.DataFrame(
                [
                    {
                        "game_id": "mlb-2",
                        "game_date": "2026-05-10",
                        "home_team_name": "Dodgers",
                        "away_team_name": "Padres",
                        "status": "Scheduled",
                    }
                ]
            ),
            odds=pd.DataFrame(
                [
                    {
                        "bookmaker": "Kalshi",
                        "outcome_name": "home",
                        "price": 2.0,
                        "last_update": "now",
                        "external_id": "kalshi-home",
                    },
                    {
                        "bookmaker": "Kalshi",
                        "outcome_name": "away",
                        "price": 2.1,
                        "last_update": "now",
                        "external_id": "kalshi-away",
                    },
                ]
            ),
        )
    )
    monkeypatch.setattr(
        mlb_comparator, "_get_source", lambda game_id: "kalshi", raising=False
    )
    monkeypatch.setattr(
        mlb_comparator, "_resolve_name", lambda context: context.name, raising=False
    )

    mlb_opportunities = mlb_comparator.find_opportunities(
        BettingOpportunityConfig(
            sport="mlb",
            elo_system=_elo_stub(governed=True),
            thresholds=BettingThresholds(min_edge=0.03, max_edge=1.0),
            date_str="2026-05-10",
        )
    )

    nba_comparator = OddsComparator(
        db_manager=_RolloutDb(
            games=pd.DataFrame(
                [
                    {
                        "game_id": "nba-1",
                        "game_date": "2026-05-10",
                        "home_team_name": "Lakers",
                        "away_team_name": "Celtics",
                        "status": "Scheduled",
                    }
                ]
            ),
            odds=pd.DataFrame(
                [
                    {
                        "bookmaker": "Kalshi",
                        "outcome_name": "home",
                        "price": 2.0,
                        "last_update": "now",
                        "external_id": "kalshi-home",
                    },
                    {
                        "bookmaker": "Kalshi",
                        "outcome_name": "away",
                        "price": 2.3,
                        "last_update": "now",
                        "external_id": "kalshi-away",
                    },
                ]
            ),
        )
    )
    monkeypatch.setattr(
        nba_comparator, "_get_source", lambda game_id: "kalshi", raising=False
    )
    monkeypatch.setattr(
        nba_comparator, "_resolve_name", lambda context: context.name, raising=False
    )

    nba_opportunities = nba_comparator.find_opportunities(
        BettingOpportunityConfig(
            sport="nba",
            elo_system=_elo_stub(home_prob=0.62),
            thresholds=BettingThresholds(min_edge=0.03, max_edge=1.0),
            date_str="2026-05-10",
        )
    )

    assert mlb_opportunities == []
    assert len(nba_opportunities) == 1
    assert nba_opportunities[0]["bet_on"] == "Lakers"


def test_governed_mlb_abstaining_rerun_blocks_stale_same_day_live_predictions(
    monkeypatch,
) -> None:
    comparator = OddsComparator(
        db_manager=_RolloutDb(
            games=pd.DataFrame(
                [
                    {
                        "game_id": "mlb-3",
                        "game_date": "2026-05-10",
                        "home_team_name": "Dodgers",
                        "away_team_name": "Padres",
                        "status": "Scheduled",
                    }
                ]
            ),
            odds=pd.DataFrame(
                [
                    {
                        "bookmaker": "Kalshi",
                        "outcome_name": "home",
                        "price": 2.0,
                        "last_update": "now",
                        "external_id": "kalshi-home",
                    },
                    {
                        "bookmaker": "Kalshi",
                        "outcome_name": "away",
                        "price": 2.1,
                        "last_update": "now",
                        "external_id": "kalshi-away",
                    },
                ]
            ),
            predictions=pd.DataFrame(
                [
                    {
                        "game_id": "mlb-3",
                        "run_date": "2026-05-10",
                        "market_name": "moneyline",
                        "model_version": "live_v1",
                        "outcome_name": "home",
                        "model_prob": 0.7,
                        "abstain": False,
                        "created_at": "2026-05-10T10:00:00",
                    },
                    {
                        "game_id": "mlb-3",
                        "run_date": "2026-05-10",
                        "market_name": "moneyline",
                        "model_version": "live_v1",
                        "outcome_name": "away",
                        "model_prob": 0.3,
                        "abstain": False,
                        "created_at": "2026-05-10T10:00:00",
                    },
                    {
                        "game_id": "mlb-3",
                        "run_date": "2026-05-10",
                        "market_name": "moneyline",
                        "model_version": "mlb_moneyline_public_abstain_v1",
                        "outcome_name": "home",
                        "model_prob": 0.5,
                        "abstain": True,
                        "created_at": "2026-05-10T11:00:00",
                    },
                    {
                        "game_id": "mlb-3",
                        "run_date": "2026-05-10",
                        "market_name": "moneyline",
                        "model_version": "mlb_moneyline_public_abstain_v1",
                        "outcome_name": "away",
                        "model_prob": 0.5,
                        "abstain": True,
                        "created_at": "2026-05-10T11:00:00",
                    },
                ]
            ),
        )
    )
    monkeypatch.setattr(
        comparator, "_get_source", lambda game_id: "kalshi", raising=False
    )
    monkeypatch.setattr(
        comparator, "_resolve_name", lambda context: context.name, raising=False
    )

    opportunities = comparator.find_opportunities(
        BettingOpportunityConfig(
            sport="mlb",
            elo_system=_elo_stub(governed=True),
            thresholds=BettingThresholds(min_edge=0.03, max_edge=1.0),
            date_str="2026-05-10",
        )
    )

    assert opportunities == []


def test_governed_mlb_lookup_scopes_rows_to_run_date_and_latest_model_version() -> None:
    comparator = OddsComparator(db_manager=_RolloutDb(games=pd.DataFrame(), odds=pd.DataFrame()))

    probabilities = comparator._get_governed_mlb_probabilities(
        game_id="mlb-4",
        run_date="2026-05-10",
    )
    assert probabilities is None

    comparator.db.predictions = pd.DataFrame(
        [
            {
                "game_id": "mlb-4",
                "run_date": "2026-05-09",
                "market_name": "moneyline",
                "model_version": "yesterday_v1",
                "outcome_name": "home",
                "model_prob": 0.8,
                "abstain": False,
                "created_at": "2026-05-09T12:00:00",
            },
            {
                "game_id": "mlb-4",
                "run_date": "2026-05-09",
                "market_name": "moneyline",
                "model_version": "yesterday_v1",
                "outcome_name": "away",
                "model_prob": 0.2,
                "abstain": False,
                "created_at": "2026-05-09T12:00:00",
            },
            {
                "game_id": "mlb-4",
                "run_date": "2026-05-10",
                "market_name": "moneyline",
                "model_version": "older_same_day_v1",
                "outcome_name": "home",
                "model_prob": 0.65,
                "abstain": False,
                "created_at": "2026-05-10T09:00:00",
            },
            {
                "game_id": "mlb-4",
                "run_date": "2026-05-10",
                "market_name": "moneyline",
                "model_version": "older_same_day_v1",
                "outcome_name": "away",
                "model_prob": 0.35,
                "abstain": False,
                "created_at": "2026-05-10T09:00:00",
            },
            {
                "game_id": "mlb-4",
                "run_date": "2026-05-10",
                "market_name": "moneyline",
                "model_version": "latest_same_day_v2",
                "outcome_name": "home",
                "model_prob": 0.6,
                "abstain": False,
                "created_at": "2026-05-10T10:00:00",
            },
            {
                "game_id": "mlb-4",
                "run_date": "2026-05-10",
                "market_name": "moneyline",
                "model_version": "latest_same_day_v2",
                "outcome_name": "away",
                "model_prob": 0.4,
                "abstain": False,
                "created_at": "2026-05-10T10:00:00",
            },
        ]
    )

    probabilities = comparator._get_governed_mlb_probabilities(
        game_id="mlb-4",
        run_date="2026-05-10",
    )

    assert probabilities == {"home": 0.6, "away": 0.4}


def test_load_elo_system_marks_mlb_for_governed_predictions(monkeypatch) -> None:
    monkeypatch.setattr(workflow, "_mlb_uses_governed_model", lambda: True)
    monkeypatch.setattr(
        workflow,
        "_maybe_wrap_mlb_with_ensemble",
        lambda elo_system: (_ for _ in ()).throw(
            AssertionError("ensemble wrapper should not run in governed mode")
        ),
    )

    elo_system = workflow._load_elo_system("mlb", {"Dodgers": 1550.0})

    assert getattr(elo_system, "requires_governed_predictions", False) is True
    assert getattr(elo_system, "ratings", {}) == {"Dodgers": 1550.0}
