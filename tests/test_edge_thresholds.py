"""Tests for edge threshold tightening (Phase 0)."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from plugins.odds_comparator import BettingOutcome, BettingThresholds


def _make_outcome(edge: float) -> BettingOutcome:
    """Build a minimal BettingOutcome with a given edge."""
    return BettingOutcome(
        side="home",
        team_name="HomeTeam",
        elo_prob=0.55 + edge,
        market_prob=0.55,
        market_odds=1.82,
        edge=edge,
    )


class TestEdgeThresholds:
    """is_value_bet must enforce [0.05, 0.15] edge band.

    The tests use explicit BettingThresholds values to isolate the
    is_value_bet logic from the constants' defaults.
    """

    def setup_method(self) -> None:
        self.config = BettingThresholds(min_edge=0.05, max_edge=0.15)

    def test_edge_4_percent_is_rejected(self) -> None:
        """Edge below minimum (0.04 < 0.05) must be rejected."""
        outcome = _make_outcome(edge=0.04)
        assert outcome.is_value_bet(self.config) is False

    def test_edge_5_percent_is_accepted(self) -> None:
        """Edge at exactly minimum (0.05 >= 0.05) must be accepted."""
        outcome = _make_outcome(edge=0.05)
        assert outcome.is_value_bet(self.config) is True

    def test_edge_16_percent_is_rejected(self) -> None:
        """Edge above maximum (0.16 > 0.15) must be rejected."""
        outcome = _make_outcome(edge=0.16)
        assert outcome.is_value_bet(self.config) is False

    def test_edge_15_percent_is_accepted(self) -> None:
        """Edge at exactly maximum (0.15 <= 0.15) must be accepted."""
        outcome = _make_outcome(edge=0.15)
        assert outcome.is_value_bet(self.config) is True
