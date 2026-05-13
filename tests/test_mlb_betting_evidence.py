"""Tests for MLB ROI and CLV evidence from real odds snapshots."""

from __future__ import annotations

import pandas as pd
import pytest

from plugins.mlb_modeling.evidence import compute_betting_evidence_metrics


def test_betting_evidence_requires_real_odds_snapshots() -> None:
    """ROI/CLV proof must not be fabricated from result-only data."""
    with pytest.raises(ValueError, match="odds_snapshots"):
        compute_betting_evidence_metrics(
            recommendations=pd.DataFrame({"game_id": ["g1"]}),
            odds_snapshots=pd.DataFrame(),
            games=pd.DataFrame({"game_id": ["g1"]}),
        )


def test_betting_evidence_computes_roi_and_clv_from_opening_and_closing_odds() -> None:
    """Flat ROI and CLV hit rate use actual entry/closing snapshot prices."""
    recommendations = pd.DataFrame(
        [
            {
                "game_id": "g1",
                "bet_on": "Los Angeles Dodgers",
                "edge": 0.08,
                "confidence": "HIGH",
            },
            {
                "game_id": "g2",
                "bet_on": "New York Yankees",
                "edge": 0.04,
                "confidence": "MEDIUM",
            },
        ]
    )
    games = pd.DataFrame(
        [
            {
                "game_id": "g1",
                "home_team": "Los Angeles Dodgers",
                "away_team": "San Diego Padres",
                "home_score": 5,
                "away_score": 3,
            },
            {
                "game_id": "g2",
                "home_team": "New York Yankees",
                "away_team": "Boston Red Sox",
                "home_score": 2,
                "away_score": 4,
            },
        ]
    )
    odds_snapshots = pd.DataFrame(
        [
            {
                "game_id": "g1",
                "outcome_role": "home",
                "source_snapshot_at": "2026-05-10T12:00:00Z",
                "commence_time": "2026-05-10T23:10:00Z",
                "decimal_price": 2.10,
            },
            {
                "game_id": "g1",
                "outcome_role": "home",
                "source_snapshot_at": "2026-05-10T23:00:00Z",
                "commence_time": "2026-05-10T23:10:00Z",
                "decimal_price": 1.90,
            },
            {
                "game_id": "g2",
                "outcome_role": "home",
                "source_snapshot_at": "2026-05-10T12:00:00Z",
                "commence_time": "2026-05-10T23:10:00Z",
                "decimal_price": 1.80,
            },
            {
                "game_id": "g2",
                "outcome_role": "home",
                "source_snapshot_at": "2026-05-10T23:00:00Z",
                "commence_time": "2026-05-10T23:10:00Z",
                "decimal_price": 1.95,
            },
        ]
    )

    metrics = compute_betting_evidence_metrics(
        recommendations=recommendations,
        odds_snapshots=odds_snapshots,
        games=games,
    )

    assert metrics.bet_count == 2
    assert metrics.flat_roi == pytest.approx(0.05)
    assert metrics.clv_hit_rate == pytest.approx(0.5)
    assert metrics.tier_a_roi == pytest.approx(1.10)
