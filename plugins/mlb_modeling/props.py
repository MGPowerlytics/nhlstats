"""Plate-appearance and player-prop modeling helpers for MLB."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


def empirical_bayes_rate(
    observed_successes: float,
    observed_trials: float,
    prior_rate: float,
    prior_strength: float,
) -> float:
    """Shrink an observed rate toward a league/split prior."""
    trials = max(0.0, float(observed_trials))
    prior_n = max(0.0, float(prior_strength))
    if trials + prior_n == 0:
        return float(prior_rate)
    successes = max(0.0, float(observed_successes))
    return (successes + float(prior_rate) * prior_n) / (trials + prior_n)


def log5_probability(
    batter_rate: float,
    pitcher_rate_allowed: float,
    league_rate: float,
) -> float:
    """Combine batter and pitcher rates using the log5 method."""
    batter = _clip_prob(batter_rate)
    pitcher = _clip_prob(pitcher_rate_allowed)
    league = _clip_prob(league_rate)
    numerator = batter * pitcher / league
    denominator = numerator + ((1 - batter) * (1 - pitcher) / (1 - league))
    return numerator / denominator


@dataclass(frozen=True)
class PAOutcomeProbabilities:
    """Probability distribution for a plate appearance."""

    strikeout: float
    walk_hbp: float
    single: float
    double_triple: float
    home_run: float
    ball_in_play_out: float

    def normalized(self) -> "PAOutcomeProbabilities":
        """Return a distribution normalized to sum to one."""
        values = [
            max(0.0, self.strikeout),
            max(0.0, self.walk_hbp),
            max(0.0, self.single),
            max(0.0, self.double_triple),
            max(0.0, self.home_run),
            max(0.0, self.ball_in_play_out),
        ]
        total = sum(values)
        if total <= 0:
            values = [0.22, 0.09, 0.15, 0.05, 0.03, 0.46]
            total = sum(values)
        normalized = [value / total for value in values]
        return PAOutcomeProbabilities(*normalized)

    def to_payload(self) -> Dict[str, float]:
        """Return schema-compatible probability keys."""
        norm = self.normalized()
        return {
            "strikeout": norm.strikeout,
            "walk_hbp": norm.walk_hbp,
            "single": norm.single,
            "double_triple": norm.double_triple,
            "home_run": norm.home_run,
            "ball_in_play_out": norm.ball_in_play_out,
        }

    @property
    def hit_probability(self) -> float:
        """Return probability of any hit outcome."""
        norm = self.normalized()
        return norm.single + norm.double_triple + norm.home_run

    @property
    def total_bases_expectation(self) -> float:
        """Return expected total bases for one plate appearance."""
        norm = self.normalized()
        return norm.single + 2.5 * norm.double_triple + 4.0 * norm.home_run


def build_pa_outcome_probabilities(
    *,
    batter_rates: Mapping[str, float],
    pitcher_rates_allowed: Mapping[str, float],
    league_rates: Mapping[str, float],
) -> PAOutcomeProbabilities:
    """Build PA outcome probabilities with log5 matchup adjustment."""
    strikeout = log5_probability(
        batter_rates["strikeout"],
        pitcher_rates_allowed["strikeout"],
        league_rates["strikeout"],
    )
    walk_hbp = log5_probability(
        batter_rates["walk_hbp"],
        pitcher_rates_allowed["walk_hbp"],
        league_rates["walk_hbp"],
    )
    single = log5_probability(
        batter_rates["single"],
        pitcher_rates_allowed["single"],
        league_rates["single"],
    )
    double_triple = log5_probability(
        batter_rates["double_triple"],
        pitcher_rates_allowed["double_triple"],
        league_rates["double_triple"],
    )
    home_run = log5_probability(
        batter_rates["home_run"],
        pitcher_rates_allowed["home_run"],
        league_rates["home_run"],
    )
    ball_in_play_out = max(
        0.0,
        1.0 - strikeout - walk_hbp - single - double_triple - home_run,
    )
    return PAOutcomeProbabilities(
        strikeout=strikeout,
        walk_hbp=walk_hbp,
        single=single,
        double_triple=double_triple,
        home_run=home_run,
        ball_in_play_out=ball_in_play_out,
    ).normalized()


class PropPredictionBuilder:
    """Build contract-shaped MLB prop prediction payloads."""

    @staticmethod
    def strikeout_over_probability(
        pa_probs: PAOutcomeProbabilities,
        expected_batters_faced: float,
        line: float,
    ) -> float:
        """Approximate P(over strikeouts) from PA K probability."""
        mean = pa_probs.normalized().strikeout * max(0.0, expected_batters_faced)
        return _smooth_threshold_probability(mean, line)

    @staticmethod
    def hits_over_probability(
        pa_probs: PAOutcomeProbabilities,
        expected_plate_appearances: float,
        line: float,
    ) -> float:
        """Approximate P(over hits) from PA hit probability."""
        mean = pa_probs.hit_probability * max(0.0, expected_plate_appearances)
        return _smooth_threshold_probability(mean, line)

    @staticmethod
    def total_bases_over_probability(
        pa_probs: PAOutcomeProbabilities,
        expected_plate_appearances: float,
        line: float,
    ) -> float:
        """Approximate P(over total bases) from PA total-bases expectation."""
        mean = pa_probs.total_bases_expectation * max(0.0, expected_plate_appearances)
        return _smooth_threshold_probability(mean, line)

    @classmethod
    def build_payload(
        cls,
        *,
        prediction_id: str,
        model_version: str,
        game_id: str,
        player_id: str,
        player_name: str,
        prop_type: str,
        over_prob: float,
        line: Optional[float] = None,
        team: Optional[str] = None,
        market_prob: Optional[float] = None,
        simulation_summary: Optional[Dict[str, Any]] = None,
        abstain: bool = False,
        abstention_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a payload matching ``mlb_prop_prediction_v1.json``."""
        over = _clip_unit(over_prob)
        under = 1.0 - over
        edge = over - market_prob if market_prob is not None else None
        expected_value = (
            edge / market_prob if edge is not None and market_prob else None
        )
        return {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "prop_prediction",
            "prediction_id": prediction_id,
            "model_version": model_version,
            "game_id": game_id,
            "player_id": player_id,
            "player_name": player_name,
            "team": team,
            "prop_type": prop_type,
            "line": line,
            "over_prob": over,
            "under_prob": under,
            "market_prob": market_prob,
            "edge": edge,
            "expected_value": expected_value,
            "simulation_summary": simulation_summary,
            "abstain": abstain,
            "abstention_reason": abstention_reason,
        }


def _smooth_threshold_probability(mean: float, line: float) -> float:
    """Convert an expected count and prop line into a smooth over probability."""
    return _clip_unit(1.0 / (1.0 + pow(2.718281828459045, -(mean - float(line)))))


def _clip_prob(value: float) -> float:
    return min(max(float(value), 1e-6), 1.0 - 1e-6)


def _clip_unit(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)
