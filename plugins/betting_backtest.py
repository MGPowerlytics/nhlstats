"""Betting backtest utilities.

These utilities support leakage-safe backtesting against historical betting lines.
They are intentionally lightweight and dependency-free.

The core assumption is a unit stake per bet (e.g., $1). Profit is computed from
American moneyline odds:
- Positive odds (+150): profit = 1.50 on win, -1.0 on loss
- Negative odds (-150): profit = 100/150 = 0.666... on win, -1.0 on loss

This module does not fetch live odds; it operates on historical line columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


def american_odds_to_win_profit(american_odds: float) -> float:
    """Convert American odds to profit on a $1 stake if the bet wins.

    Args:
        american_odds: American moneyline odds (e.g., -150, +120).

    Returns:
        Profit (not including stake) for a $1 stake if the bet wins.

    Raises:
        ValueError: If american_odds is 0 or NaN.
    """

    if american_odds == 0 or not np.isfinite(american_odds):
        raise ValueError(f"Invalid American odds: {american_odds}")

    if american_odds > 0:
        return float(american_odds) / 100.0

    return 100.0 / float(abs(american_odds))


@dataclass(frozen=True)
class BetDecision:
    """A single-game bet decision."""

    side: str  # "HOME" or "AWAY"
    model_prob: float
    market_prob: float
    american_odds: float


def choose_side_by_edge(
    *,
    home_model_prob: float,
    away_model_prob: float,
    home_market_prob: float,
    away_market_prob: float,
    home_american_odds: float,
    away_american_odds: float,
    min_edge: float,
    min_model_prob: float,
) -> Optional[BetDecision]:
    """Choose the single best bet side for a game, if any.

    This selects the side with the larger edge where:
        edge = model_prob - market_prob

    Args:
        home_model_prob: Model probability home wins.
        away_model_prob: Model probability away wins.
        home_market_prob: Market implied probability home wins.
        away_market_prob: Market implied probability away wins.
        home_american_odds: Home moneyline odds.
        away_american_odds: Away moneyline odds.
        min_edge: Minimum edge required to place a bet.
        min_model_prob: Minimum model probability required to place a bet.

    Returns:
        A BetDecision if criteria is met, else None.
    """

    home_edge = home_model_prob - home_market_prob
    away_edge = away_model_prob - away_market_prob

    candidates: list[BetDecision] = []
    if home_edge >= min_edge and home_model_prob >= min_model_prob:
        candidates.append(
            BetDecision(
                side="HOME",
                model_prob=float(home_model_prob),
                market_prob=float(home_market_prob),
                american_odds=float(home_american_odds),
            )
        )

    if away_edge >= min_edge and away_model_prob >= min_model_prob:
        candidates.append(
            BetDecision(
                side="AWAY",
                model_prob=float(away_model_prob),
                market_prob=float(away_market_prob),
                american_odds=float(away_american_odds),
            )
        )

    if not candidates:
        return None

    # Choose max edge; deterministic tie-breaker prefers HOME.
    def _edge(d: BetDecision) -> float:
        return d.model_prob - d.market_prob

    candidates.sort(key=lambda d: (_edge(d), 1 if d.side == "HOME" else 0), reverse=True)
    return candidates[0]


@dataclass(frozen=True)
class BacktestSummary:
    """Aggregate backtest metrics."""

    n_games: int
    n_with_lines: int
    n_bets: int
    win_rate: float
    total_profit: float
    roi: float
    avg_profit_if_win: float
    avg_edge: float
    avg_model_prob: float
    avg_market_prob: float
    expected_profit_by_model: float
    expected_roi_by_model: float


def simulate_unit_bets(
    *,
    decisions: list[Optional[BetDecision]],
    home_win: np.ndarray,
) -> BacktestSummary:
    """Simulate unit-stake bets for a series of games.

    Args:
        decisions: Per-game bet decisions; None means no bet.
        home_win: Array of outcomes (1 if home won else 0).

    Returns:
        BacktestSummary with realized and model-expected profit.
    """

    if len(decisions) != len(home_win):
        raise ValueError("decisions and home_win must be same length")

    n_games = int(len(home_win))
    n_bets = 0
    wins = 0
    total_profit = 0.0
    expected_profit = 0.0

    edges: list[float] = []
    model_probs: list[float] = []
    market_probs: list[float] = []
    profits_if_win: list[float] = []

    n_with_lines = 0
    for i, decision in enumerate(decisions):
        if decision is None:
            continue

        n_with_lines += 1
        n_bets += 1

        profit_if_win = american_odds_to_win_profit(decision.american_odds)
        profits_if_win.append(profit_if_win)

        did_home_win = int(home_win[i]) == 1
        bet_won = did_home_win if decision.side == "HOME" else (not did_home_win)

        if bet_won:
            wins += 1
            total_profit += profit_if_win
        else:
            total_profit -= 1.0

        expected_profit += decision.model_prob * profit_if_win + (1.0 - decision.model_prob) * (-1.0)

        edges.append(decision.model_prob - decision.market_prob)
        model_probs.append(decision.model_prob)
        market_probs.append(decision.market_prob)

    win_rate = float(wins / n_bets) if n_bets else float("nan")
    roi = float(total_profit / n_bets) if n_bets else float("nan")
    expected_roi = float(expected_profit / n_bets) if n_bets else float("nan")

    return BacktestSummary(
        n_games=n_games,
        n_with_lines=n_with_lines,
        n_bets=n_bets,
        win_rate=win_rate,
        total_profit=float(total_profit),
        roi=roi,
        avg_profit_if_win=float(np.mean(profits_if_win)) if profits_if_win else float("nan"),
        avg_edge=float(np.mean(edges)) if edges else float("nan"),
        avg_model_prob=float(np.mean(model_probs)) if model_probs else float("nan"),
        avg_market_prob=float(np.mean(market_probs)) if market_probs else float("nan"),
        expected_profit_by_model=float(expected_profit),
        expected_roi_by_model=expected_roi,
    )
