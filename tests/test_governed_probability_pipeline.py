"""Governed probability hardening regression tests."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from plugins.bet_loader import BetLoader
from plugins.odds_comparator import (
    BettingOpportunityConfig,
    BettingThresholds,
    GameContext,
    OddsComparator,
)
from plugins.portfolio_optimizer import JsonFileParser, PortfolioConfig, PortfolioOptimizer


class _ProbabilityDb:
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
        if "FROM tennis_matchups" in query:
            return pd.DataFrame()
        raise AssertionError(f"Unexpected query: {query}")


def _elo_stub(
    *,
    home_prob: float = 0.62,
    governed: bool = False,
    governed_source: str | None = None,
):
    stub = SimpleNamespace(
        predict=lambda home, away: home_prob,
        predict_3way=lambda home, away: {"home": 0.51, "draw": 0.24, "away": 0.25},
        get_rating=lambda team: 1550.0,
        has_real_rating=lambda *args, **kwargs: True,
    )
    if governed:
        stub.requires_governed_predictions = True
    if governed_source is not None:
        stub.governed_probability_source = governed_source
    return stub


class _CalibratedTennisStub:
    def get_rating(self, player: str, tour: str | None = None) -> float:
        return {"Player A": 1600.0, "Player B": 1500.0}[player]

    def predict(self, player_a: str, player_b: str, *, tour: str) -> float:
        return 0.61

    def predict_with_payload(self, player_a: str, player_b: str, tour: str) -> dict:
        return {
            "player_a": player_a,
            "player_b": player_b,
            "tour": tour.upper(),
            "raw_prob_a": 0.61,
            "calibrated_prob_a": 0.57,
        }


def _market_rows(home_ticker: str = "kalshi-home", away_ticker: str = "kalshi-away") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "bookmaker": "Kalshi",
                "outcome_name": "home",
                "price": 2.0,
                "last_update": "2026-05-10T10:00:00",
                "external_id": home_ticker,
            },
            {
                "bookmaker": "Kalshi",
                "outcome_name": "away",
                "price": 2.2,
                "last_update": "2026-05-10T10:00:00",
                "external_id": away_ticker,
            },
        ]
    )


def _governed_config(sport: str, elo_system) -> BettingOpportunityConfig:
    return BettingOpportunityConfig(
        sport=sport,
        elo_system=elo_system,
        thresholds=BettingThresholds(min_edge=0.03, max_edge=1.0),
        date_str="2026-05-10",
        enforce_governance=True,
    )


def test_governed_mlb_shadow_path_surfaces_probability_lineage(monkeypatch) -> None:
    comparator = OddsComparator(
        db_manager=_ProbabilityDb(
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
            odds=_market_rows(),
            predictions=pd.DataFrame(
                [
                    {
                        "game_id": "mlb-1",
                        "run_date": "2026-05-10",
                        "market_name": "moneyline",
                        "model_version": "mlb_moneyline_public_v3",
                        "outcome_name": "home",
                        "model_prob": 0.68,
                        "abstain": False,
                        "abstention_reason": None,
                        "created_at": "2026-05-10T10:05:00",
                    },
                    {
                        "game_id": "mlb-1",
                        "run_date": "2026-05-10",
                        "market_name": "moneyline",
                        "model_version": "mlb_moneyline_public_v3",
                        "outcome_name": "away",
                        "model_prob": 0.32,
                        "abstain": False,
                        "abstention_reason": None,
                        "created_at": "2026-05-10T10:05:00",
                    },
                ]
            ),
        )
    )
    monkeypatch.setattr(comparator, "_get_source", lambda game_id: "kalshi", raising=False)
    monkeypatch.setattr(
        comparator, "_resolve_name", lambda context: context.name, raising=False
    )

    opportunities = comparator.find_opportunities(
        _governed_config("mlb", _elo_stub(governed=True))
    )

    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity["probability_source"] == "mlb_model_predictions"
    assert opportunity["evidence_state"] == "shadow_only"
    assert opportunity["governance_status"] == "descriptive_only"
    assert opportunity["sizing_eligible"] is False
    assert opportunity["abstain"] is False
    assert (
        opportunity["evidence_state_source_artifact"]
        == "mlb_model_predictions:mlb_moneyline_public_v3@2026-05-10"
    )


def test_governed_mlb_missing_artifact_emits_explicit_abstention(monkeypatch) -> None:
    comparator = OddsComparator(
        db_manager=_ProbabilityDb(
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
            odds=_market_rows(),
        )
    )
    monkeypatch.setattr(comparator, "_get_source", lambda game_id: "kalshi", raising=False)
    monkeypatch.setattr(
        comparator, "_resolve_name", lambda context: context.name, raising=False
    )

    opportunities = comparator.find_opportunities(
        _governed_config("mlb", _elo_stub(governed=True))
    )

    assert len(opportunities) == 1
    abstention = opportunities[0]
    assert abstention["abstain"] is True
    assert abstention["probability_source"] == "mlb_model_predictions"
    assert abstention["sizing_eligible"] is False
    assert abstention["abstention_reason"] == "missing_governed_probability_artifact"


def test_governed_tennis_shadow_path_uses_calibrated_elo_fallback_without_sizing() -> None:
    context = GameContext(
        sport="tennis",
        game_id="TENNIS_ATP_2026-05-10_PlayerA_PlayerB",
        home_team_name="Player A",
        away_team_name="Player B",
        source="kalshi",
        canon_home="Player A",
        canon_away="Player B",
        elo_home="Player A",
        elo_away="Player B",
        odds_by_bm={"Kalshi": {"home": 2.0, "away": 2.1}},
        tickers_by_bm={
            "Kalshi": {
                "home": "KXATPMATCH-26MAY10PA-PB",
                "away": "KXATPMATCH-26MAY10PA-PB",
            }
        },
        elo_system=_CalibratedTennisStub(),
        enforce_governance=True,
    )

    assert context.calculate_probabilities() is True
    opportunities = context.evaluate(BettingThresholds(min_edge=0.03, max_edge=1.0))

    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity["probability_source"] == "tennis_calibrated_elo"
    assert opportunity["evidence_state"] == "shadow_only"
    assert opportunity["sizing_eligible"] is False
    assert opportunity["abstain"] is False


@pytest.mark.parametrize(
    ("sport", "governed_source", "expected_reason"),
    (
        ("epl", None, "runtime_consumer_mismatch"),
        ("ligue1", None, "governed_artifact_not_consumed"),
        ("nba", None, "missing_calibration_evidence"),
    ),
)
def test_governed_paths_fail_closed_when_validation_support_is_missing(
    monkeypatch, sport: str, governed_source: str | None, expected_reason: str
) -> None:
    comparator = OddsComparator(
        db_manager=_ProbabilityDb(
            games=pd.DataFrame(
                [
                    {
                        "game_id": f"{sport}-1",
                        "game_date": "2026-05-10",
                        "home_team_name": "Home",
                        "away_team_name": "Away",
                        "status": "Scheduled",
                    }
                ]
            ),
            odds=_market_rows(),
        )
    )
    monkeypatch.setattr(comparator, "_get_source", lambda game_id: "kalshi", raising=False)
    monkeypatch.setattr(
        comparator, "_resolve_name", lambda context: context.name, raising=False
    )

    opportunities = comparator.find_opportunities(
        _governed_config(sport, _elo_stub(governed_source=governed_source))
    )

    assert len(opportunities) == 1
    abstention = opportunities[0]
    assert abstention["abstain"] is True
    assert abstention["sizing_eligible"] is False
    assert expected_reason in abstention["abstention_reason"]


def test_bet_loader_and_optimizer_keep_shadow_rows_out_of_sizing(monkeypatch) -> None:
    shadow_payload = {
        "sport": "MLB",
        "game_id": "mlb-1",
        "home_team": "Dodgers",
        "away_team": "Padres",
        "bet_on": "Dodgers",
        "side": "home",
        "ticker": "KXMLBGAME-26MAY10LADSD-LAD",
        "elo_prob": 0.68,
        "market_prob": 0.5,
        "market_odds": 2.0,
        "edge": 0.18,
        "confidence": "HIGH",
        "expected_value": 0.36,
        "kelly_fraction": 0.18,
        "probability_source": "mlb_model_predictions",
        "evidence_state": "shadow_only",
        "evidence_state_reason": "MLB remains shadow-only pending approval-grade evidence.",
        "evidence_state_source_artifact": "mlb_model_predictions:mlb_moneyline_public_v3@2026-05-10",
        "governance_status": "descriptive_only",
        "sizing_eligible": False,
        "abstain": False,
        "abstention_reason": None,
    }

    captured: list[dict] = []
    loader = BetLoader()
    loader._table_initialized = True
    loader._upsert_bet = lambda db, params: captured.append(dict(params))
    monkeypatch.setattr(loader, "_lazy_initialize_table", lambda: None)
    monkeypatch.setattr(
        loader, "_load_bets_from_file", lambda sport, date_str: [shadow_payload]
    )

    loaded = loader.load_bets_for_date("mlb", "2026-05-10")

    assert loaded == 1
    assert captured[0]["probability_source"] == "mlb_model_predictions"
    assert captured[0]["sizing_eligible"] is False
    assert (
        captured[0]["evidence_state_source_artifact"]
        == "mlb_model_predictions:mlb_moneyline_public_v3@2026-05-10"
    )

    parser = JsonFileParser()
    opportunity = parser.parse(shadow_payload, "mlb")
    optimizer = PortfolioOptimizer(PortfolioConfig(bankroll=1000.0))

    assert opportunity is not None
    assert optimizer.filter_opportunities([opportunity]) == []
