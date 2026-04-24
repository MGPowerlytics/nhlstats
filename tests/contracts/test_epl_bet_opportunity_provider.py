from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import validate

from plugins.odds_comparator import (
    BettingOpportunityConfig,
    BettingThresholds,
    OddsComparator,
)
from tests.contracts.fixtures.epl_elo_samples import (
    EPL_AWAY_TEAM,
    EPL_GAME_ID,
    EPL_HOME_TEAM,
    build_epl_market_odds,
    build_epl_upcoming_games,
    build_trained_epl_elo,
)


CONTRACT_PATH = Path(__file__).parent / "schemas" / "epl_bet_opportunity_v1.json"


class FakeOddsDb:
    """Minimal DB stub for provider-facing OddsComparator contract tests."""

    def __init__(self, games_df: pd.DataFrame, odds_df: pd.DataFrame) -> None:
        self.games_df = games_df
        self.odds_df = odds_df

    def fetch_df(self, query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        if "FROM unified_games" in query:
            return self.games_df.copy()
        if "FROM game_odds" in query:
            return self.odds_df.copy()
        raise AssertionError(f"Unexpected query: {query}")


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _build_comparator(
    home_team: str = EPL_HOME_TEAM,
    away_team: str = EPL_AWAY_TEAM,
    game_id: str = EPL_GAME_ID,
) -> OddsComparator:
    comparator = OddsComparator(
        db_manager=FakeOddsDb(
            games_df=build_epl_upcoming_games(
                home_team=home_team,
                away_team=away_team,
                game_id=game_id,
            ),
            odds_df=build_epl_market_odds(),
        )
    )
    comparator._get_source = lambda _: "kalshi"  # type: ignore[method-assign]
    comparator._resolve_name = lambda context: context.name  # type: ignore[method-assign]
    return comparator


def test_real_epl_opportunity_payload_matches_frozen_contract() -> None:
    comparator = _build_comparator()
    opportunities = comparator.find_opportunities(
        BettingOpportunityConfig(
            sport="epl",
            elo_system=build_trained_epl_elo(),
            thresholds=BettingThresholds(min_edge=0.01, max_edge=1.0),
            date_str="2025-08-16",
        )
    )

    assert opportunities, "Expected a real EPL opportunity payload from OddsComparator"
    validate(opportunities[0], _load_contract())


def test_no_default_elo_guard_blocks_unknown_epl_matchups() -> None:
    comparator = _build_comparator(
        home_team="Liverpool",
        away_team="Ipswich Town",
        game_id="EPL-2025-08-16-LIV-IPS",
    )
    elo = build_trained_epl_elo()

    opportunities = comparator.find_opportunities(
        BettingOpportunityConfig(
            sport="epl",
            elo_system=elo,
            thresholds=BettingThresholds(min_edge=0.01, max_edge=1.0),
            date_str="2025-08-16",
        )
    )

    assert opportunities == []
    assert elo.has_real_rating("Ipswich Town") is False
