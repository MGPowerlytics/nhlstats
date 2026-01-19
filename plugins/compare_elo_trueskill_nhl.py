#!/usr/bin/env python3
"""Compare NHL Elo vs team-level TrueSkill vs ensemble blends (current season).

This script is intentionally read-only with respect to production pipelines:
- It does NOT modify any existing prediction logic used by the Airflow DAG.
- It computes Elo and TrueSkill probabilities sequentially (leakage-safe).
- It evaluates models on the current season only.

Why team-level TrueSkill?
- The archived TrueSkill work is player-level and heavier.
- This script starts with a lightweight team-level TrueSkill baseline that
  requires only game outcomes.

Usage:
    python plugins/compare_elo_trueskill_nhl.py

Optional:
    python plugins/compare_elo_trueskill_nhl.py --weights 0.7:0.3,0.6:0.4,0.5:0.5

"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from .lift_gain_analysis import (
        calculate_lift_gain_by_decile,
        get_current_season_start,
        load_games,
        print_decile_table,
    )
    from .nhl_elo_rating import NHLEloRating
except ImportError:  # pragma: no cover
    from lift_gain_analysis import (
        calculate_lift_gain_by_decile,
        get_current_season_start,
        load_games,
        print_decile_table,
    )
    from nhl_elo_rating import NHLEloRating


def _clamp_probs(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    return np.clip(p.astype(float), eps, 1.0 - eps)


@dataclass
class Metrics:
    """Basic prediction metrics."""

    n_games: int
    baseline_home_win_rate: float
    accuracy: float
    brier: float
    log_loss: float


def compute_metrics(df: pd.DataFrame, prob_col: str) -> Metrics:
    """Compute accuracy, Brier score, and log loss."""

    y = df["home_win"].astype(int).to_numpy()
    p = _clamp_probs(df[prob_col].to_numpy())

    preds = (p >= 0.5).astype(int)
    accuracy = float((preds == y).mean()) if len(y) else float("nan")
    brier = float(np.mean((p - y) ** 2)) if len(y) else float("nan")
    log_loss_val = (
        float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        if len(y)
        else float("nan")
    )

    return Metrics(
        n_games=int(len(y)),
        baseline_home_win_rate=float(df["home_win"].mean()) if len(y) else float("nan"),
        accuracy=accuracy,
        brier=brier,
        log_loss=log_loss_val,
    )


def _mcnemar_summary(
    df: pd.DataFrame,
    prob_col_a: str,
    prob_col_b: str,
    threshold: float = 0.5,
) -> Tuple[int, int, float, float]:
    """Compute McNemar disagreement counts and an approximate p-value.

    Returns:
        b: A correct, B wrong
        c: A wrong, B correct
        chi2_cc: continuity-corrected chi-square statistic (df=1)
        p_approx: approximate p-value using chi-square(df=1)
    """

    y = df["home_win"].astype(int).to_numpy()
    pa = _clamp_probs(df[prob_col_a].to_numpy())
    pb = _clamp_probs(df[prob_col_b].to_numpy())

    pred_a = (pa >= float(threshold)).astype(int)
    pred_b = (pb >= float(threshold)).astype(int)

    correct_a = pred_a == y
    correct_b = pred_b == y

    b = int(np.sum(correct_a & (~correct_b)))
    c = int(np.sum((~correct_a) & correct_b))

    n = b + c
    if n == 0:
        return b, c, 0.0, 1.0

    # Continuity-corrected McNemar: (|b-c|-1)^2 / (b+c)
    chi2_cc = (max(abs(b - c) - 1, 0) ** 2) / n

    # For df=1, chi-square survival function: p = 2*(1 - Phi(sqrt(x)))
    z = math.sqrt(chi2_cc)
    p_approx = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))

    return b, c, float(chi2_cc), float(p_approx)


def accuracy_at_threshold(df: pd.DataFrame, prob_col: str, threshold: float) -> float:
    """Compute accuracy at a specific probability threshold."""

    y = df["home_win"].astype(int).to_numpy()
    p = _clamp_probs(df[prob_col].to_numpy())
    preds = (p >= float(threshold)).astype(int)
    return float((preds == y).mean()) if len(y) else float("nan")


def find_best_threshold(
    df: pd.DataFrame,
    prob_col: str,
    step: float = 0.01,
) -> Tuple[float, float]:
    """Find threshold that maximizes accuracy on the provided dataframe."""

    if df.empty:
        return 0.5, float("nan")

    thresholds = np.unique(np.clip(np.arange(0.01, 1.0, step, dtype=float), 0.01, 0.99))
    if 0.5 not in thresholds:
        thresholds = np.sort(np.append(thresholds, 0.5))

    best_t = 0.5
    best_acc = -1.0
    for t in thresholds:
        acc = accuracy_at_threshold(df, prob_col, float(t))
        if acc > best_acc:
            best_acc = acc
            best_t = float(t)
    return best_t, float(best_acc)


@dataclass
class TeamRating:
    """Gaussian belief about team skill: N(mu, sigma^2)."""

    mu: float
    sigma: float


class TeamTrueSkill:
    """Team-level TrueSkill for 1v1 matches (win/loss only).

    This is a lightweight approximation of TrueSkill that treats each team as a
    single participant. It is designed for fast experimentation and ensembling
    with Elo.

    Notes:
        - NHL has no draws (OT/SO break ties), so draw_probability is ignored.
        - Home advantage is modeled as an additive mu bonus in TrueSkill units.
    """

    def __init__(
        self,
        mu0: float = 25.0,
        sigma0: float = 25.0 / 3.0,
        beta: float = 25.0 / 6.0,
        tau: float = 25.0 / 300.0,
    ) -> None:
        self.mu0 = float(mu0)
        self.sigma0 = float(sigma0)
        self.beta = float(beta)
        self.tau = float(tau)
        self.ratings: Dict[str, TeamRating] = {}

    def get_rating(self, team: str) -> TeamRating:
        if team not in self.ratings:
            self.ratings[team] = TeamRating(mu=self.mu0, sigma=self.sigma0)
        return self.ratings[team]

    def predict(self, home_team: str, away_team: str, home_advantage: float) -> float:
        """Predict home win probability using Gaussian CDF."""

        r_home = self.get_rating(home_team)
        r_away = self.get_rating(away_team)

        # Performance distributions: N(mu, sigma^2 + beta^2)
        # For the difference, variances add.
        mu_diff = (r_home.mu + float(home_advantage)) - r_away.mu
        c = math.sqrt(r_home.sigma**2 + r_away.sigma**2 + 2.0 * (self.beta**2))

        # P(diff > 0) = Phi(mu_diff / c)
        z = mu_diff / c if c > 0 else 0.0
        return float(0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))

    def update(
        self,
        home_team: str,
        away_team: str,
        home_won: bool,
        home_advantage: float,
    ) -> None:
        """Update ratings after a game."""

        r_home = self.get_rating(home_team)
        r_away = self.get_rating(away_team)

        # Add dynamics factor (skill drift)
        sigma_home = math.sqrt(r_home.sigma**2 + self.tau**2)
        sigma_away = math.sqrt(r_away.sigma**2 + self.tau**2)

        c = math.sqrt(sigma_home**2 + sigma_away**2 + 2.0 * (self.beta**2))
        mu_diff = (r_home.mu + float(home_advantage)) - r_away.mu

        outcome_sign = 1.0 if home_won else -1.0
        t = (outcome_sign * mu_diff) / c if c > 0 else 0.0

        v = self._v(t)
        w = self._w(t, v)

        mu_home = r_home.mu + outcome_sign * (sigma_home**2 / c) * v
        mu_away = r_away.mu - outcome_sign * (sigma_away**2 / c) * v

        sigma_factor_home = 1.0 - (sigma_home**2 / (c**2)) * w
        sigma_factor_away = 1.0 - (sigma_away**2 / (c**2)) * w

        sigma_home_new = sigma_home * math.sqrt(max(sigma_factor_home, 1e-6))
        sigma_away_new = sigma_away * math.sqrt(max(sigma_factor_away, 1e-6))

        self.ratings[home_team] = TeamRating(mu=mu_home, sigma=sigma_home_new)
        self.ratings[away_team] = TeamRating(mu=mu_away, sigma=sigma_away_new)

    def apply_season_reversion(self, factor: float = 0.35) -> None:
        """Regress mus toward mean and inflate sigma slightly."""

        factor = float(factor)
        for team, rating in list(self.ratings.items()):
            new_mu = self.mu0 + (1.0 - factor) * (rating.mu - self.mu0)
            new_sigma = min(rating.sigma * 1.1, self.sigma0)
            self.ratings[team] = TeamRating(mu=new_mu, sigma=new_sigma)

    @staticmethod
    def _phi(x: float) -> float:
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    @staticmethod
    def _Phi(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _v(self, t: float) -> float:
        denom = self._Phi(t)
        if denom < 1e-12:
            # Asymptotic approximation when denom ~ 0
            return -t
        return self._phi(t) / denom

    @staticmethod
    def _w(t: float, v: float) -> float:
        return v * (v + t)


def _parse_weights(weights_str: Optional[str]) -> List[Tuple[float, float]]:
    """Parse weights like "0.7:0.3,0.6:0.4"."""

    if not weights_str:
        return [(0.7, 0.3), (0.6, 0.4), (0.5, 0.5), (0.4, 0.6), (0.3, 0.7)]

    weights: List[Tuple[float, float]] = []
    for pair in weights_str.split(","):
        pair = pair.strip()
        if not pair:
            continue
        a_str, b_str = pair.split(":")
        w_elo = float(a_str)
        w_ts = float(b_str)
        if abs((w_elo + w_ts) - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0: {pair}")
        weights.append((w_elo, w_ts))

    if not weights:
        raise ValueError("No valid weights provided")

    return weights


def _parse_float_list(values: Optional[str]) -> Optional[List[float]]:
    if values is None:
        return None
    parts = [p.strip() for p in values.split(",") if p.strip()]
    if not parts:
        return None
    return [float(p) for p in parts]


def _generate_weight_sweep(
    w_ts_start: float,
    w_ts_end: float,
    w_ts_step: float,
) -> List[Tuple[float, float]]:
    """Generate (w_elo, w_ts) weights across a TrueSkill-weight range."""

    if w_ts_step <= 0:
        raise ValueError("--sweep-wts-step must be > 0")
    if w_ts_end < w_ts_start:
        raise ValueError("--sweep-wts-end must be >= --sweep-wts-start")
    if w_ts_start < 0 or w_ts_end > 1:
        raise ValueError("--sweep-wts-start/end must be within [0, 1]")

    w_ts_vals = np.unique(
        np.clip(
            np.arange(w_ts_start, w_ts_end + 1e-12, w_ts_step, dtype=float), 0.0, 1.0
        )
    )
    weights: List[Tuple[float, float]] = []
    for w_ts in w_ts_vals:
        w_ts_f = float(w_ts)
        weights.append((float(1.0 - w_ts_f), w_ts_f))
    return weights


def _apply_elo_season_reversion(elo: NHLEloRating, factor: float) -> None:
    factor = float(factor)
    for team, rating in list(elo.ratings.items()):
        elo.ratings[team] = 1500.0 + (1.0 - factor) * (float(rating) - 1500.0)


def calculate_elo_trueskill_predictions(
    games: pd.DataFrame,
    season_reversion_factor: float,
    trueskill_home_advantage: float,
    trueskill_beta: float,
    trueskill_tau: float,
) -> pd.DataFrame:
    """Compute Elo and team-level TrueSkill probabilities sequentially."""

    games = games.copy()
    games["game_date"] = pd.to_datetime(games["game_date"])

    # Stable ordering
    sort_cols = ["game_date"]
    if "game_id" in games.columns:
        sort_cols.append("game_id")
    games = games.sort_values(sort_cols).reset_index(drop=True)

    elo = NHLEloRating(
        k_factor=10, home_advantage=50, initial_rating=1500, recency_weight=0.2
    )
    ts = TeamTrueSkill(beta=trueskill_beta, tau=trueskill_tau)

    elo_probs: List[float] = []
    ts_probs: List[float] = []

    prev_date: Optional[pd.Timestamp] = None

    for _, row in games.iterrows():
        game_date: pd.Timestamp = row["game_date"]

        if prev_date is not None:
            gap_days = int((game_date - prev_date).days)
            if gap_days > 90:
                print(f"🔄 Applied season reversion (factor={season_reversion_factor})")
                _apply_elo_season_reversion(elo, factor=season_reversion_factor)
                ts.apply_season_reversion(factor=season_reversion_factor)

        home = str(row["home_team"])
        away = str(row["away_team"])
        home_won = bool(int(row["home_win"]))

        elo_prob = float(elo.predict(home, away))
        ts_prob = float(ts.predict(home, away, home_advantage=trueskill_home_advantage))

        elo_probs.append(elo_prob)
        ts_probs.append(ts_prob)

        elo.update(home, away, home_won=home_won, game_date=game_date)
        ts.update(
            home, away, home_won=home_won, home_advantage=trueskill_home_advantage
        )

        prev_date = game_date

    games["elo_prob"] = elo_probs
    games["trueskill_prob"] = ts_probs
    return games


def calculate_elo_probabilities(
    games: pd.DataFrame,
    season_reversion_factor: float,
) -> pd.DataFrame:
    """Compute Elo probabilities sequentially (leakage-safe).

    This is separated from TrueSkill so we can reuse Elo results across TrueSkill
    hyperparameter sweeps.
    """

    games = games.copy()
    games["game_date"] = pd.to_datetime(games["game_date"])

    sort_cols = ["game_date"]
    if "game_id" in games.columns:
        sort_cols.append("game_id")
    games = games.sort_values(sort_cols).reset_index(drop=True)

    elo = NHLEloRating(k_factor=10, home_advantage=50, initial_rating=1500, recency_weight=0.2)

    elo_probs: List[float] = []
    prev_date: Optional[pd.Timestamp] = None

    for _, row in games.iterrows():
        game_date: pd.Timestamp = row["game_date"]

        if prev_date is not None:
            gap_days = int((game_date - prev_date).days)
            if gap_days > 90:
                _apply_elo_season_reversion(elo, factor=season_reversion_factor)

        home = str(row["home_team"])
        away = str(row["away_team"])
        home_won = bool(int(row["home_win"]))

        elo_prob = float(elo.predict(home, away))
        elo_probs.append(elo_prob)

        elo.update(home, away, home_won=home_won, game_date=game_date)
        prev_date = game_date

    games["elo_prob"] = elo_probs
    return games


def calculate_trueskill_probabilities(
    games: pd.DataFrame,
    season_reversion_factor: float,
    trueskill_home_advantage: float,
    trueskill_beta: float,
    trueskill_tau: float,
) -> np.ndarray:
    """Compute TrueSkill probabilities sequentially for the provided games order."""

    if "game_date" not in games.columns:
        raise ValueError("games must include 'game_date'")

    ts = TeamTrueSkill(beta=trueskill_beta, tau=trueskill_tau)

    probs: List[float] = []
    prev_date: Optional[pd.Timestamp] = None

    for _, row in games.iterrows():
        game_date: pd.Timestamp = row["game_date"]

        if prev_date is not None:
            gap_days = int((game_date - prev_date).days)
            if gap_days > 90:
                ts.apply_season_reversion(factor=season_reversion_factor)

        home = str(row["home_team"])
        away = str(row["away_team"])
        home_won = bool(int(row["home_win"]))

        prob = float(ts.predict(home, away, home_advantage=trueskill_home_advantage))
        probs.append(prob)

        ts.update(home, away, home_won=home_won, home_advantage=trueskill_home_advantage)
        prev_date = game_date

    return np.asarray(probs, dtype=float)


def add_ensemble_columns(
    df: pd.DataFrame, weights: Iterable[Tuple[float, float]]
) -> pd.DataFrame:
    df = df.copy()
    for w_elo, w_ts in weights:
        col = f"ensemble_{int(round(w_elo * 100))}_{int(round(w_ts * 100))}"
        df[col] = (w_elo * df["elo_prob"] + w_ts * df["trueskill_prob"]).astype(float)
    return df


def _select_train_season_splits(
    df: pd.DataFrame,
    season_start: str,
    train_window_days: Optional[int],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["game_date"] = pd.to_datetime(df["game_date"])
    season_start_dt = pd.to_datetime(season_start)

    train_df = df[df["game_date"] < season_start_dt]
    if train_window_days is not None:
        window_start = season_start_dt - pd.Timedelta(days=int(train_window_days))
        train_df = train_df[train_df["game_date"] >= window_start]

    season_df = df[df["game_date"] >= season_start_dt]
    return train_df, season_df


def _select_fit_val_for_tuning(
    all_with_probs: pd.DataFrame,
    season_start: str,
    tune_scope: str,
    train_window_days: Optional[int],
    val_window_days: Optional[int],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Select fit/validation splits for leakage-safe tuning.

    tune_scope:
        - "preseason": Fit on pre-season before a validation window immediately
          preceding season_start; score on that validation window.
        - "last_season": Fit on all games before the start of the prior season;
          score on the entire prior season (Oct 1 -> season_start).
    """

    df = all_with_probs.copy()
    df["game_date"] = pd.to_datetime(df["game_date"])
    season_start_dt = pd.to_datetime(season_start)

    if tune_scope == "last_season":
        # Prior season starts exactly one year before current season start.
        val_start = season_start_dt - pd.DateOffset(years=1)
        fit_df = df[df["game_date"] < val_start]
        val_df = df[
            (df["game_date"] >= val_start) & (df["game_date"] < season_start_dt)
        ]
        return fit_df, val_df

    if tune_scope == "preseason":
        pre_df = df[df["game_date"] < season_start_dt]
        if train_window_days is not None:
            window_start = season_start_dt - pd.Timedelta(days=int(train_window_days))
            pre_df = pre_df[pre_df["game_date"] >= window_start]

        if val_window_days is not None:
            val_start = season_start_dt - pd.Timedelta(days=int(val_window_days))
            fit_df = pre_df[pre_df["game_date"] < val_start]
            val_df = pre_df[pre_df["game_date"] >= val_start]
        else:
            fit_df = pre_df
            val_df = pre_df

        return fit_df, val_df

    raise ValueError(f"Unknown tune_scope: {tune_scope}")


def _score_objective(
    df: pd.DataFrame,
    prob_col: str,
    objective: str,
    threshold: float,
) -> float:
    if objective == "accuracy":
        return accuracy_at_threshold(df, prob_col, threshold=threshold)
    if objective == "brier":
        return -compute_metrics(df, prob_col).brier
    if objective == "logloss":
        return -compute_metrics(df, prob_col).log_loss
    raise ValueError(f"Unknown objective: {objective}")


def tune_on_preseason(
    all_games: pd.DataFrame,
    season_start: str,
    season_reversion_factor: float,
    trueskill_beta_grid: List[float],
    trueskill_tau_grid: List[float],
    trueskill_home_adv_grid: List[float],
    weight_step: float,
    objective: str,
    tune_threshold: bool,
    threshold_step: float,
    train_window_days: Optional[int],
    val_window_days: Optional[int],
    tune_scope: str,
) -> Tuple[float, float, float, Tuple[float, float], Optional[float]]:
    """Tune TrueSkill home advantage + ensemble weight on pre-season only.

    Returns:
        best_home_adv, best_beta, best_tau, (w_elo, w_ts), best_threshold (or None)
    """

    # Candidate weights: (w_elo, w_ts)
    weights: List[Tuple[float, float]] = []
    w_ts_vals = np.unique(
        np.clip(np.arange(0.0, 1.0 + 1e-9, weight_step, dtype=float), 0.0, 1.0)
    )
    for w_ts in w_ts_vals:
        w_elo = float(1.0 - w_ts)
        weights.append((w_elo, float(w_ts)))

    best_score = -1e18
    best_home_adv = trueskill_home_adv_grid[0]
    best_beta = trueskill_beta_grid[0]
    best_tau = trueskill_tau_grid[0]
    best_weight = (0.5, 0.5)
    best_threshold: Optional[float] = None

    print("\n🧪 Tuning (leakage-safe)...")
    print(
        f"   objective={objective}, tune_threshold={tune_threshold}, "
        f"scope={tune_scope}, train_window_days={train_window_days}, val_window_days={val_window_days}"
    )
    print(f"   home_adv_grid={trueskill_home_adv_grid}")
    print(f"   beta_grid={trueskill_beta_grid}")
    print(f"   tau_grid={trueskill_tau_grid}")
    print(f"   weight_step={weight_step}")

    # Compute Elo once for all games.
    elo_df = calculate_elo_probabilities(all_games, season_reversion_factor)

    for beta in trueskill_beta_grid:
        for tau in trueskill_tau_grid:
            for home_adv in trueskill_home_adv_grid:
                all_with_probs = elo_df.copy()
                all_with_probs["trueskill_prob"] = calculate_trueskill_probabilities(
                    all_with_probs,
                    season_reversion_factor=season_reversion_factor,
                    trueskill_home_advantage=float(home_adv),
                    trueskill_beta=float(beta),
                    trueskill_tau=float(tau),
                )

                fit_df, val_df = _select_fit_val_for_tuning(
                    all_with_probs,
                    season_start=season_start,
                    tune_scope=tune_scope,
                    train_window_days=train_window_days,
                    val_window_days=val_window_days,
                )

                if fit_df.empty or val_df.empty:
                    continue

                fit_elo = fit_df["elo_prob"].to_numpy(dtype=float)
                fit_ts = fit_df["trueskill_prob"].to_numpy(dtype=float)
                val_elo = val_df["elo_prob"].to_numpy(dtype=float)
                val_ts = val_df["trueskill_prob"].to_numpy(dtype=float)

                for w_elo, w_ts in weights:
                    fit_p = w_elo * fit_elo + w_ts * fit_ts
                    val_p = w_elo * val_elo + w_ts * val_ts

                    if tune_threshold and objective == "accuracy":
                        fit_tmp = pd.DataFrame({"home_win": fit_df["home_win"], "p": fit_p})
                        t, _ = find_best_threshold(fit_tmp, "p", step=threshold_step)
                        threshold = float(t)
                    else:
                        threshold = 0.5

                    val_tmp = pd.DataFrame({"home_win": val_df["home_win"], "p": val_p})
                    score = _score_objective(
                        val_tmp, "p", objective=objective, threshold=threshold
                    )

                    if score > best_score:
                        best_score = float(score)
                        best_home_adv = float(home_adv)
                        best_beta = float(beta)
                        best_tau = float(tau)
                        best_weight = (float(w_elo), float(w_ts))
                        best_threshold = (
                            float(threshold)
                            if (tune_threshold and objective == "accuracy")
                            else None
                        )

    print(
        f"✅ Best score={best_score:.4f} @ home_adv={best_home_adv}, beta={best_beta}, tau={best_tau}, "
        f"w_elo={best_weight[0]:.2f}, w_ts={best_weight[1]:.2f}"
    )
    if best_threshold is not None:
        print(f"   tuned_threshold={best_threshold:.2f}")

    return best_home_adv, best_beta, best_tau, best_weight, best_threshold


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help="Comma-separated weight pairs like '0.7:0.3,0.6:0.4'.",
    )
    parser.add_argument(
        "--trueskill-home-adv",
        type=float,
        default=1.5,
        help="Home advantage in TrueSkill units (additive mu bonus).",
    )
    parser.add_argument(
        "--trueskill-beta",
        type=float,
        default=25.0 / 6.0,
        help="TrueSkill beta (performance variance).",
    )
    parser.add_argument(
        "--trueskill-beta-grid",
        type=str,
        default=None,
        help="Comma-separated grid for TrueSkill beta (overrides --trueskill-beta during --tune).",
    )
    parser.add_argument(
        "--trueskill-tau",
        type=float,
        default=25.0 / 300.0,
        help="TrueSkill tau (dynamics / drift).",
    )
    parser.add_argument(
        "--trueskill-tau-grid",
        type=str,
        default=None,
        help="Comma-separated grid for TrueSkill tau (overrides --trueskill-tau during --tune).",
    )
    parser.add_argument(
        "--season-reversion-factor",
        type=float,
        default=0.35,
        help="Season reversion factor applied after 90+ day gaps.",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help=(
            "Tune TrueSkill home advantage and ensemble weight on pre-season only "
            "(leakage-safe), then evaluate the selected config on current season."
        ),
    )
    parser.add_argument(
        "--tune-scope",
        choices=["preseason", "last_season"],
        default="last_season",
        help=(
            "Scope for leakage-safe tuning. 'last_season' tunes on out-of-sample "
            "performance on the prior season (recommended). 'preseason' tunes on the "
            "pre-season window before current season start."
        ),
    )
    parser.add_argument(
        "--objective",
        choices=["accuracy", "brier", "logloss"],
        default="accuracy",
        help="Objective for tuning on pre-season (accuracy, brier, or logloss).",
    )
    parser.add_argument(
        "--weight-step",
        type=float,
        default=0.05,
        help="Grid step for ensemble weight tuning (TrueSkill weight).",
    )
    parser.add_argument(
        "--tune-threshold",
        action="store_true",
        help="When objective=accuracy, tune the decision threshold on pre-season.",
    )
    parser.add_argument(
        "--threshold-step",
        type=float,
        default=0.01,
        help="Grid step for threshold tuning (only used when --tune-threshold).",
    )
    parser.add_argument(
        "--train-window-days",
        type=int,
        default=None,
        help="If set, tune using only the last N days before season start.",
    )
    parser.add_argument(
        "--val-window-days",
        type=int,
        default=365,
        help=(
            "During tuning, score configs on the last N pre-season days before season start. "
            "Set to 0 to score on the full pre-season window."
        ),
    )
    parser.add_argument(
        "--trueskill-home-adv-grid",
        type=str,
        default=None,
        help="Comma-separated grid for TrueSkill home advantage, e.g. '0.5,1.0,1.5,2.0,2.5'.",
    )
    parser.add_argument(
        "--mcnemar",
        action="store_true",
        help="Print McNemar-style comparison between Elo and the best model.",
    )
    parser.add_argument(
        "--sweep-wts-start",
        type=float,
        default=None,
        help="If set, sweep TrueSkill ensemble weight starting here (0..1).",
    )
    parser.add_argument(
        "--sweep-wts-end",
        type=float,
        default=None,
        help="If set, sweep TrueSkill ensemble weight ending here (0..1).",
    )
    parser.add_argument(
        "--sweep-wts-step",
        type=float,
        default=0.02,
        help="Step size for TrueSkill ensemble weight sweep.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)
    weights = _parse_weights(args.weights)

    print("=" * 110)
    print("📊 Elo vs Team-TrueSkill vs Ensemble — NHL Current Season")
    print("=" * 110)

    season_start = get_current_season_start("nhl")

    print("📥 Loading all NHL games...")
    all_games = load_games("nhl", season_only=False)
    if all_games.empty:
        print("⚠️  No NHL games found")
        return

    print(f"   Found {len(all_games):,} games")

    trueskill_home_adv_grid = _parse_float_list(args.trueskill_home_adv_grid)
    if trueskill_home_adv_grid is None:
        trueskill_home_adv_grid = [0.5, 1.0, 1.5, 2.0, 2.5]

    trueskill_beta_grid = _parse_float_list(args.trueskill_beta_grid)
    if trueskill_beta_grid is None:
        trueskill_beta_grid = [float(args.trueskill_beta)]

    trueskill_tau_grid = _parse_float_list(args.trueskill_tau_grid)
    if trueskill_tau_grid is None:
        trueskill_tau_grid = [float(args.trueskill_tau)]

    tuned_threshold: Optional[float] = None
    if args.tune:
        best_home_adv, best_beta, best_tau, best_weight, tuned_threshold = (
            tune_on_preseason(
            all_games,
            season_start=season_start,
            season_reversion_factor=float(args.season_reversion_factor),
            trueskill_beta_grid=trueskill_beta_grid,
            trueskill_tau_grid=trueskill_tau_grid,
            trueskill_home_adv_grid=trueskill_home_adv_grid,
            weight_step=float(args.weight_step),
            objective=str(args.objective),
            tune_threshold=bool(args.tune_threshold),
            threshold_step=float(args.threshold_step),
            train_window_days=args.train_window_days,
            val_window_days=(
                None if int(args.val_window_days) <= 0 else int(args.val_window_days)
            ),
            tune_scope=str(args.tune_scope),
        )
        )
        args.trueskill_home_adv = float(best_home_adv)
        args.trueskill_beta = float(best_beta)
        args.trueskill_tau = float(best_tau)
        weights = [best_weight]

    # Fast sweep of ensemble weights (does not change underlying Elo/TrueSkill probs)
    if args.sweep_wts_start is not None or args.sweep_wts_end is not None:
        if args.sweep_wts_start is None or args.sweep_wts_end is None:
            raise ValueError("Both --sweep-wts-start and --sweep-wts-end must be set")
        weights = _generate_weight_sweep(
            float(args.sweep_wts_start),
            float(args.sweep_wts_end),
            float(args.sweep_wts_step),
        )

    print("🎯 Computing Elo and TrueSkill probabilities (sequential, leakage-safe)...")
    all_with_probs = calculate_elo_probabilities(
        all_games, season_reversion_factor=float(args.season_reversion_factor)
    )
    all_with_probs["trueskill_prob"] = calculate_trueskill_probabilities(
        all_with_probs,
        season_reversion_factor=float(args.season_reversion_factor),
        trueskill_home_advantage=float(args.trueskill_home_adv),
        trueskill_beta=float(args.trueskill_beta),
        trueskill_tau=float(args.trueskill_tau),
    )

    all_with_probs["game_date"] = pd.to_datetime(all_with_probs["game_date"])
    season_df = all_with_probs[
        all_with_probs["game_date"] >= pd.to_datetime(season_start)
    ].copy()

    if season_df.empty:
        print(f"⚠️  No games since {season_start}")
        return

    print(
        f"📅 Evaluating current season since {season_start}: {len(season_df):,} games"
    )

    season_df = add_ensemble_columns(season_df, weights)

    prob_cols = ["elo_prob", "trueskill_prob"] + [
        f"ensemble_{int(round(w_elo * 100))}_{int(round(w_ts * 100))}"
        for w_elo, w_ts in weights
    ]

    print("\n**Metrics (Current Season)**")
    print("-" * 98)
    print(
        f"{'Model':<26} {'N':>6} {'Baseline':>10} {'Accuracy':>10} {'Brier':>10} {'LogLoss':>10}"
    )
    print("-" * 98)

    results: Dict[str, Metrics] = {}
    for col in prob_cols:
        m = compute_metrics(season_df, col)
        results[col] = m
        label = col.replace("_prob", "")
        print(
            f"{label:<26} {m.n_games:>6,} {m.baseline_home_win_rate:>10.3f} "
            f"{m.accuracy:>10.3f} {m.brier:>10.4f} {m.log_loss:>10.4f}"
        )

    print("-" * 98)

    best_acc_col = max(results.keys(), key=lambda c: results[c].accuracy)
    print(f"\n✅ Best Accuracy: {best_acc_col} ({results[best_acc_col].accuracy:.3f})")

    if args.tune and args.objective == "accuracy" and tuned_threshold is not None:
        season_acc = accuracy_at_threshold(
            season_df, best_acc_col, threshold=float(tuned_threshold)
        )
        print(
            f"✅ Tuned-threshold season accuracy: {season_acc:.3f} "
            f"(threshold={float(tuned_threshold):.2f}, tuned on pre-season only)"
        )

    if args.mcnemar and best_acc_col != "elo_prob":
        b, c, chi2_cc, p_approx = _mcnemar_summary(
            season_df, prob_col_a="elo_prob", prob_col_b=best_acc_col, threshold=0.5
        )
        print("\n**McNemar (approx, threshold=0.5)**")
        print(f"- elo_correct_best_wrong: {b}")
        print(f"- elo_wrong_best_correct: {c}")
        print(f"- chi2_cc: {chi2_cc:.3f}")
        print(f"- p_approx: {p_approx:.4f}")

    # Decile tables for Elo, TrueSkill, and best-accuracy model
    for col in ["elo_prob", "trueskill_prob", best_acc_col]:
        if col == best_acc_col and col in {"elo_prob", "trueskill_prob"}:
            continue
        print(f"\n📈 Lift/Gain by decile ({col})")
        deciles = calculate_lift_gain_by_decile(season_df, prob_col=col)
        print_decile_table(
            deciles, "nhl", f"CURRENT SEASON — {col} (Since {season_start})"
        )


if __name__ == "__main__":
    main()
