"""Seeded Monte Carlo simulation engine for MLB game outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np


MIN_SIMULATIONS = 5000
MAX_SIMULATIONS = 10000


@dataclass(frozen=True)
class MLBGameSimulationResult:
    """Compact summary of a Monte Carlo game simulation."""

    game_id: str
    simulation_count: int
    seed: int
    home_win_prob: float
    away_win_prob: float
    run_distribution: Dict[str, float]
    model_version: str

    def to_payload(self) -> Dict[str, object]:
        """Return a payload matching ``mlb_game_simulation_v1.json``."""
        return {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "game_simulation",
            "game_id": self.game_id,
            "simulation_count": self.simulation_count,
            "seed": self.seed,
            "home_win_prob": self.home_win_prob,
            "away_win_prob": self.away_win_prob,
            "run_distribution": self.run_distribution,
            "model_version": self.model_version,
        }


class MLBMonteCarloSimulator:
    """Monte Carlo simulator for MLB game-level probability distributions."""

    def __init__(
        self,
        simulation_count: int = MIN_SIMULATIONS,
        model_version: str = "mlb_sim_public_v1",
    ) -> None:
        """Initialize simulator with a bounded simulation count."""
        if simulation_count < MIN_SIMULATIONS or simulation_count > MAX_SIMULATIONS:
            raise ValueError(
                f"simulation_count must be between {MIN_SIMULATIONS} and {MAX_SIMULATIONS}"
            )
        self.simulation_count = int(simulation_count)
        self.model_version = model_version

    def simulate_game(
        self,
        *,
        game_id: str,
        home_run_mean: float,
        away_run_mean: float,
        seed: int,
    ) -> MLBGameSimulationResult:
        """Run a deterministic Poisson run-distribution simulation."""
        rng = np.random.default_rng(seed)
        home_runs = rng.poisson(max(0.01, float(home_run_mean)), self.simulation_count)
        away_runs = rng.poisson(max(0.01, float(away_run_mean)), self.simulation_count)

        # Resolve ties as a small extra-inning coin flip, preserving probability mass.
        ties = home_runs == away_runs
        tie_breaks = rng.integers(0, 2, int(np.sum(ties)))
        home_wins = home_runs > away_runs
        if tie_breaks.size:
            home_wins[ties] = tie_breaks == 1

        home_win_prob = float(np.mean(home_wins))
        away_win_prob = 1.0 - home_win_prob
        run_distribution = {
            "home_mean": float(np.mean(home_runs)),
            "away_mean": float(np.mean(away_runs)),
            "total_mean": float(np.mean(home_runs + away_runs)),
            "home_p10": float(np.percentile(home_runs, 10)),
            "home_p90": float(np.percentile(home_runs, 90)),
            "away_p10": float(np.percentile(away_runs, 10)),
            "away_p90": float(np.percentile(away_runs, 90)),
        }
        return MLBGameSimulationResult(
            game_id=game_id,
            simulation_count=self.simulation_count,
            seed=int(seed),
            home_win_prob=home_win_prob,
            away_win_prob=away_win_prob,
            run_distribution=run_distribution,
            model_version=self.model_version,
        )
