"""Provider contract tests for TennisFeatureBuilder payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import Draft202012Validator

from plugins.elo.tennis_features import TennisFeatureBuilder


SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "tennis_features_v1.json"


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_tennis_feature_builder_emits_contract_payload() -> None:
    """TennisFeatureBuilder.to_payload output should match the governed schema."""
    builder = TennisFeatureBuilder()
    features = builder.build_matchup_features(
        pd.DataFrame(
            [
                _match("2026-01-01", "Player A", "Common C", winner_rank=12),
                _match("2026-01-02", "Common C", "Player B", loser_rank=21),
                _match("2026-01-03", "Player B", "Player A"),
            ]
        ),
        player_a="Player A",
        player_b="Player B",
        as_of_date="2026-01-10",
        surface="Hard",
        tour="ATP",
    )
    payload = features.to_payload()

    Draft202012Validator(_load_schema()).validate(payload)
    assert payload["sport"] == "TENNIS"
    assert payload["payload_kind"] == "feature_vector"
    assert payload["tour"] == "ATP"


def test_tennis_feature_builder_emits_rank_diff_when_ranks_exist() -> None:
    """Ranking movement inputs should include rank differential when available."""
    builder = TennisFeatureBuilder()
    features = builder.build_matchup_features(
        pd.DataFrame(
            [
                _match("2026-01-01", "Player A", "Opponent X", winner_rank=8),
                _match("2026-01-01", "Player B", "Opponent Y", winner_rank=19),
            ]
        ),
        player_a="Player A",
        player_b="Player B",
        as_of_date="2026-01-10",
        surface="Hard",
        tour="ATP",
    )

    assert features.rank_diff == -11.0


def _match(
    date: str,
    winner: str,
    loser: str,
    *,
    winner_rank: int | None = None,
    loser_rank: int | None = None,
) -> dict[str, Any]:
    return {
        "date": date,
        "winner": winner,
        "loser": loser,
        "surface": "Hard",
        "score": "6-4 6-4",
        "tour": "ATP",
        "winner_rank": winner_rank,
        "loser_rank": loser_rank,
        "winner_age": 28.0,
        "loser_age": 31.0,
        "w_svpt": 80,
        "w_1stWon": 40,
        "w_2ndWon": 16,
        "l_svpt": 76,
        "l_1stWon": 30,
        "l_2ndWon": 12,
    }
