"""Compare tennis models with recency weighting and momentum overlays.

Goal
----
Evaluate what changes if we weight recent tennis performance more heavily.
This script runs a leakage-safe walk-forward simulation and compares:

1) Baseline Elo (current `TennisEloRating` behavior)
2) Recency-decayed Elo (exponential decay toward mean by inactivity)
3) Elo + Markov-ish momentum overlay (per-player 2-state transition model)
4) Player-level TrueSkill (lightweight, no external dependency)

Data
----
Prefers DuckDB table `tennis_games` in `data/nhlstats.duckdb`.
Falls back to loading CSVs in `data/tennis/*_*.csv`.

Usage
-----
    python3 plugins/compare_tennis_recency_models.py --tour ATP --since 2024-01-01

"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Numerical stability constants
LOGIT_EPSILON = 1e-6  # Minimum probability to avoid log(0) in logit function
LOGLOSS_EPSILON = 1e-9  # Minimum probability to avoid log(0) in log loss
MIN_HALF_LIFE_DAYS = 1e-6  # Minimum half-life to avoid division by zero

# Probability and rating constants
PROBABILITY_THRESHOLD = 0.5  # Threshold for binary classification
ELO_SCALE_FACTOR = (
    400.0  # Elo rating scale factor (standard 400 points per log-odds unit)
)

# Default grid values for parameter search (comma-separated string)
DEFAULT_GRID_VALUES = "0.0,0.05,0.1,0.2,0.35,0.5"

# Mathematical constants
LN2 = math.log(2.0)  # Natural log of 2, used in half-life calculations

# Tennis Elo model defaults
DEFAULT_INITIAL_ELO_RATING = 1500.0
DEFAULT_HALF_LIFE_DAYS = 90.0
DEFAULT_K_FACTOR = 32.0
BLOWOUT_MULTIPLIER = 1.5  # Multiplier for K-factor in blowout games
MIN_MATCHES_FOR_STABLE_RATING = 20  # Minimum matches before removing blowout multiplier


def _logit(p: float) -> float:
    p = float(np.clip(p, LOGIT_EPSILON, 1 - LOGIT_EPSILON))
    return float(math.log(p / (1.0 - p)))


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + math.exp(-x)))


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def _logloss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, LOGLOSS_EPSILON, 1 - LOGLOSS_EPSILON)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _accuracy(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p >= PROBABILITY_THRESHOLD) == (y == 1)))


def _expected_elo(r_a: float, r_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / ELO_SCALE_FACTOR))


@dataclass
class MatchFilter:
    """Filter criteria for loading tennis matches."""

    tour: str = "ALL"
    since: Optional[str] = None
    until: Optional[str] = None


@dataclass
class TennisMatch:
    date: pd.Timestamp
    tour: str
    winner: str
    loser: str


class BaselineTennisElo:
    """Baseline Elo mirroring current `TennisEloRating` logic."""

    def __init__(
        self,
        k_factor: float = DEFAULT_K_FACTOR,
        initial_rating: float = DEFAULT_INITIAL_ELO_RATING,
    ) -> None:
        self.k_factor = float(k_factor)
        self.initial_rating = float(initial_rating)
        self.ratings: Dict[str, float] = {}
        self.matches_played: Dict[str, int] = {}

    def get_rating(self, player: str) -> float:
        if player not in self.ratings:
            self.ratings[player] = self.initial_rating
            self.matches_played[player] = 0
        return float(self.ratings[player])

    def predict(self, player_a: str, player_b: str) -> float:
        ra = self.get_rating(player_a)
        rb = self.get_rating(player_b)
        return float(_expected_elo(ra, rb))

    def update(self, winner: str, loser: str) -> None:
        rw = self.get_rating(winner)
        rl = self.get_rating(loser)
        expected_win = float(_expected_elo(rw, rl))

        k = self.k_factor
        if self.matches_played.get(winner, 0) < MIN_MATCHES_FOR_STABLE_RATING:
            k *= BLOWOUT_MULTIPLIER
        if self.matches_played.get(loser, 0) < MIN_MATCHES_FOR_STABLE_RATING:
            k *= BLOWOUT_MULTIPLIER

        change = k * (1.0 - expected_win)
        self.ratings[winner] = rw + change
        self.ratings[loser] = rl - change

        self.matches_played[winner] = self.matches_played.get(winner, 0) + 1
        self.matches_played[loser] = self.matches_played.get(loser, 0) + 1


class RecencyDecayedElo(BaselineTennisElo):
    """Elo with time-based decay toward mean.

    The idea: older matches should matter less, so if a player hasn't played in a
    while, their rating partially reverts toward the mean before the next match.

    Decay is exponential with a configurable half-life.
    """

    def __init__(
        self,
        k_factor: float = 32.0,
        initial_rating: float = DEFAULT_INITIAL_ELO_RATING,
        half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    ) -> None:
        super().__init__(k_factor=k_factor, initial_rating=initial_rating)
        self.half_life_days = float(half_life_days)
        self.last_played: Dict[str, pd.Timestamp] = {}

    def _apply_decay(self, player: str, now: pd.Timestamp) -> None:
        if player not in self.ratings:
            _ = self.get_rating(player)
            self.last_played[player] = now
            return

        last = self.last_played.get(player)
        if last is None:
            self.last_played[player] = now
            return

        delta_days = float((now - last).days)
        if delta_days <= 0:
            return

        # rating = mean + (rating-mean)*exp(-lambda*dt)
        lam = LN2 / max(self.half_life_days, MIN_HALF_LIFE_DAYS)
        factor = math.exp(-lam * delta_days)
        self.ratings[player] = (
            self.initial_rating + (self.ratings[player] - self.initial_rating) * factor
        )

    def predict(self, player_a: str, player_b: str, match_date: pd.Timestamp) -> float:
        self._apply_decay(player_a, match_date)
        self._apply_decay(player_b, match_date)
        return super().predict(player_a, player_b)

    def update(self, winner: str, loser: str, match_date: pd.Timestamp) -> None:
        self._apply_decay(winner, match_date)
        self._apply_decay(loser, match_date)
        super().update(winner, loser)
        self.last_played[winner] = match_date
        self.last_played[loser] = match_date


class MarkovMomentum:
    """Per-player 2-state Markov momentum model.

    State is last match outcome (W or L). We estimate:
    - P(win next | last=W)
    - P(win next | last=L)

    Online with Beta(1,1) priors.
    """

    def __init__(self) -> None:
        self.last_state: Dict[str, int] = {}  # 1=W, 0=L
        self.counts: Dict[
            Tuple[str, int], Tuple[int, int]
        ] = {}  # (player, state) -> (wins, total)

    def _get(self, player: str, state: int) -> Tuple[int, int]:
        return self.counts.get((player, state), (0, 0))

    def predict_win_prob(self, player: str) -> float:
        state = self.last_state.get(player, 1)  # default assume "good" state
        wins, total = self._get(player, state)
        # Beta(1,1) prior
        return float((wins + 1) / (total + 2))

    def update(self, winner: str, loser: str) -> None:
        # Update transition stats for each player given their prior state
        for player, won in [(winner, 1), (loser, 0)]:
            prev_state = self.last_state.get(player, 1)
            wins, total = self._get(player, prev_state)
            wins += int(won)
            total += 1
            self.counts[(player, prev_state)] = (wins, total)
            self.last_state[player] = int(won)


# Reuse the lightweight TrueSkill implementation from NHL script.
try:
    from compare_elo_trueskill_nhl import TeamTrueSkill  # type: ignore
except Exception:  # pragma: no cover
    TeamTrueSkill = None


def _load_matches_from_db(
    db_path: Path,
    filters: MatchFilter,
) -> pd.DataFrame:
    import duckdb

    conn = duckdb.connect(str(db_path), read_only=True)
    where = []
    params: List[object] = []
    if filters.tour in {"ATP", "WTA"}:
        where.append("tour = ?")
        params.append(filters.tour)
    if filters.since:
        where.append("game_date >= ?")
        params.append(filters.since)
    if filters.until:
        where.append("game_date <= ?")
        params.append(filters.until)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    query = f"""
        SELECT game_date, tour, winner, loser
        FROM tennis_games
        {where_sql}
        ORDER BY game_date ASC
    """
    df = conn.execute(query, params).fetchdf()
    conn.close()
    return df


def _load_matches_from_csv(
    csv_dir: Path,
    filters: MatchFilter,
) -> pd.DataFrame:
    from tennis_games import TennisGames

    tg = TennisGames(data_dir=str(csv_dir))
    raw = tg.load_games()
    if raw.empty:
        return pd.DataFrame()

    raw["game_date"] = pd.to_datetime(raw["date"]).dt.date
    raw["tour"] = raw["tour"].astype(str).str.upper()
    df = raw.rename(columns={"winner": "winner", "loser": "loser"})[
        ["game_date", "tour", "winner", "loser"]
    ]
    df["game_date"] = pd.to_datetime(df["game_date"])

    if filters.tour in {"ATP", "WTA"}:
        df = df[df["tour"] == filters.tour]
    if filters.since:
        df = df[df["game_date"] >= pd.to_datetime(filters.since)]
    if filters.until:
        df = df[df["game_date"] <= pd.to_datetime(filters.until)]

    return df.sort_values("game_date")


def _dataframe_to_matches(df: pd.DataFrame) -> List[TennisMatch]:
    matches: List[TennisMatch] = []
    for _, row in df.iterrows():
        d = pd.to_datetime(row["game_date"])
        matches.append(
            TennisMatch(
                date=d,
                tour=str(row["tour"]).upper(),
                winner=str(row["winner"]).strip(),
                loser=str(row["loser"]).strip(),
            )
        )
    return matches


def load_tennis_matches(
    *,
    db_path: Path = Path("data/nhlstats.duckdb"),
    csv_dir: Path = Path("data/tennis"),
    filters: Optional[MatchFilter] = None,
) -> List[TennisMatch]:
    if filters is None:
        filters = MatchFilter()

    filters.tour = filters.tour.upper()

    if db_path.exists():
        df = _load_matches_from_db(db_path, filters)
    else:
        df = _load_matches_from_csv(csv_dir, filters)

    if df.empty:
        return []

    return _dataframe_to_matches(df)


def evaluate(
    matches: Sequence[TennisMatch],
    *,
    half_life_days: float,
    momentum_gamma: float,
) -> pd.DataFrame:
    """
    Evaluate different tennis prediction models on a sequence of matches.

    Args:
        matches: Sequence of tennis matches to evaluate
        half_life_days: Half-life parameter for recency-decayed Elo
        momentum_gamma: Gamma parameter for momentum overlay

    Returns:
        DataFrame with evaluation metrics for each model
    """
    if not matches:
        raise ValueError("No tennis matches found to evaluate")

    # Initialize all prediction models
    elo, rec, mom, ts = _initialize_models(half_life_days)

    # Process all matches and collect predictions
    rows = _process_all_matches(matches, elo, rec, mom, ts, momentum_gamma)

    # Calculate evaluation metrics
    df = pd.DataFrame(rows)
    metrics = _calculate_model_metrics(df)

    return pd.DataFrame(metrics).sort_values("logloss")


def _initialize_models(half_life_days: float) -> tuple:
    """
    Initialize all tennis prediction models.

    Args:
        half_life_days: Half-life parameter for recency-decayed Elo

    Returns:
        Tuple of (elo, rec, mom, ts) model instances
    """
    elo = BaselineTennisElo()
    rec = RecencyDecayedElo(half_life_days=half_life_days)
    mom = MarkovMomentum()
    ts = TeamTrueSkill() if TeamTrueSkill is not None else None

    return elo, rec, mom, ts


def _process_all_matches(
    matches: Sequence[TennisMatch],
    elo: BaselineTennisElo,
    rec: RecencyDecayedElo,
    mom: MarkovMomentum,
    ts: Optional[Any],
    momentum_gamma: float,
) -> List[Dict[str, float]]:
    """
    Process all matches and collect predictions from all models.

    Args:
        matches: Sequence of tennis matches
        elo: Baseline Elo model
        rec: Recency-decayed Elo model
        mom: Markov momentum model
        ts: TrueSkill model (optional)
        momentum_gamma: Gamma parameter for momentum overlay

    Returns:
        List of prediction rows for each match
    """
    rows: List[Dict[str, float]] = []

    for match in matches:
        # Process single match and get predictions
        row = _process_single_match(match, elo, rec, mom, ts, momentum_gamma)
        rows.append(row)

        # Update all models with actual outcome
        _update_models_with_result(match, elo, rec, mom, ts)

    return rows


def _process_single_match(
    match: TennisMatch,
    elo: BaselineTennisElo,
    rec: RecencyDecayedElo,
    mom: MarkovMomentum,
    ts: Optional[Any],
    momentum_gamma: float,
) -> Dict[str, float]:
    """
    Process a single tennis match and get predictions from all models.

    Args:
        match: Tennis match to process
        elo: Baseline Elo model
        rec: Recency-decayed Elo model
        mom: Markov momentum model
        ts: TrueSkill model (optional)
        momentum_gamma: Gamma parameter for momentum overlay

    Returns:
        Dictionary with predictions from all models
    """
    # Use lexicographic ordering independent of outcome
    a, b = sorted([match.winner, match.loser])
    y = 1.0 if a == match.winner else 0.0

    # Get predictions from each model
    p_elo = float(elo.predict(a, b))
    p_rec = float(rec.predict(a, b, match.date))

    # Momentum overlay on top of recency Elo
    pa_m = mom.predict_win_prob(a)
    pb_m = mom.predict_win_prob(b)
    p_mom = _sigmoid(
        _logit(p_rec) + float(momentum_gamma) * (_logit(pa_m) - _logit(pb_m))
    )

    # TrueSkill prediction (if available)
    p_ts = (
        float(ts.predict(a, b, home_advantage=0.0)) if ts is not None else float("nan")
    )

    return {
        "y": y,
        "p_elo": p_elo,
        "p_rec": p_rec,
        "p_mom": p_mom,
        "p_ts": p_ts,
    }


def _update_models_with_result(
    match: TennisMatch,
    elo: BaselineTennisElo,
    rec: RecencyDecayedElo,
    mom: MarkovMomentum,
    ts: Optional[Any],
) -> None:
    """
    Update all models with the actual match outcome.

    Args:
        match: Tennis match with actual outcome
        elo: Baseline Elo model to update
        rec: Recency-decayed Elo model to update
        mom: Markov momentum model to update
        ts: TrueSkill model to update (optional)
    """
    # Update baseline models
    elo.update(match.winner, match.loser)
    rec.update(match.winner, match.loser, match.date)
    mom.update(match.winner, match.loser)

    # Update TrueSkill if available
    if ts is not None:
        a, b = sorted([match.winner, match.loser])
        home_won = bool(a == match.winner)
        ts.update(a, b, home_won=home_won, home_advantage=0.0)


def _calculate_model_metrics(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Calculate evaluation metrics for each model.

    Args:
        df: DataFrame with predictions from all models

    Returns:
        List of dictionaries with metrics for each model
    """
    metrics = []
    y_arr = df["y"].to_numpy(dtype=float)

    for col in ["p_elo", "p_rec", "p_mom", "p_ts"]:
        p = df[col].to_numpy(dtype=float)
        if np.isnan(p).all():
            continue

        metrics.append(
            {
                "model": col,
                "n": int(len(p)),
                "accuracy": _accuracy(y_arr, p),
                "logloss": _logloss(y_arr, p),
                "brier": _brier(y_arr, p),
            }
        )

    return metrics


def _parse_float_list(value: str) -> List[float]:
    """Parse a comma-separated list of floats."""

    items = [x.strip() for x in str(value).split(",") if x.strip()]
    return [float(x) for x in items]


def grid_search(
    matches: Sequence[TennisMatch],
    *,
    half_life_grid: Sequence[float],
    gamma_grid: Sequence[float],
    top_k: int = 10,
) -> None:
    """
    Run a simple parameter sweep for recency and momentum models.

    Args:
        matches: Sequence of tennis matches to evaluate
        half_life_grid: Grid of half-life values to search
        gamma_grid: Grid of gamma values to search
        top_k: Number of top results to display for each model
    """
    # Print baseline metrics
    _print_baseline_metrics(matches, half_life_grid, gamma_grid)

    # Perform grid search
    rec_rows, mom_rows = _perform_grid_search(matches, half_life_grid, gamma_grid)

    # Print top-k results
    _print_top_results(rec_rows, mom_rows, top_k)


def _print_baseline_metrics(
    matches: Sequence[TennisMatch],
    half_life_grid: Sequence[float],
    gamma_grid: Sequence[float],
) -> None:
    """
    Print baseline metrics for Elo and TrueSkill models.

    Args:
        matches: Sequence of tennis matches
        half_life_grid: Grid of half-life values
        gamma_grid: Grid of gamma values
    """
    baseline = evaluate(
        matches,
        half_life_days=float(half_life_grid[0]),
        momentum_gamma=float(gamma_grid[0]),
    )
    base_rows = baseline[baseline["model"].isin(["p_elo", "p_ts"])].copy()
    if not base_rows.empty:
        print("\n=== Baselines (fixed params) ===")
        print(base_rows.to_string(index=False))


def _perform_grid_search(
    matches: Sequence[TennisMatch],
    half_life_grid: Sequence[float],
    gamma_grid: Sequence[float],
) -> tuple[List[Dict[str, float]], List[Dict[str, float]]]:
    """
    Perform grid search over half-life and gamma parameters.

    Args:
        matches: Sequence of tennis matches
        half_life_grid: Grid of half-life values
        gamma_grid: Grid of gamma values

    Returns:
        Tuple of (rec_rows, mom_rows) - results for recency and momentum models
    """
    rec_rows: List[Dict[str, float]] = []
    mom_rows: List[Dict[str, float]] = []

    for hl in half_life_grid:
        for g in gamma_grid:
            metrics = evaluate(
                matches, half_life_days=float(hl), momentum_gamma=float(g)
            )

            # Extract recency model results
            rec_rows.extend(_extract_model_results(metrics, "p_rec", hl, g))

            # Extract momentum model results
            mom_rows.extend(_extract_model_results(metrics, "p_mom", hl, g))

    return rec_rows, mom_rows


def _extract_model_results(
    metrics: pd.DataFrame,
    model_name: str,
    half_life: float,
    gamma: float,
) -> List[Dict[str, float]]:
    """
    Extract results for a specific model from evaluation metrics.

    Args:
        metrics: DataFrame with evaluation metrics
        model_name: Name of model to extract (e.g., "p_rec", "p_mom")
        half_life: Half-life parameter value
        gamma: Gamma parameter value

    Returns:
        List of result dictionaries (empty list if model not found)
    """
    model_metrics = metrics[metrics["model"] == model_name]
    if model_metrics.empty:
        return []

    r = model_metrics.iloc[0]
    return [
        {
            "half_life_days": float(half_life),
            "gamma": float(gamma),
            "accuracy": float(r["accuracy"]),
            "logloss": float(r["logloss"]),
            "brier": float(r["brier"]),
        }
    ]


def _print_top_results(
    rec_rows: List[Dict[str, float]],
    mom_rows: List[Dict[str, float]],
    top_k: int,
) -> None:
    """
    Print top-k results for recency and momentum models.

    Args:
        rec_rows: Results for recency model
        mom_rows: Results for momentum model
        top_k: Number of top results to display
    """
    if rec_rows:
        df_rec = pd.DataFrame(rec_rows).sort_values("logloss").head(int(top_k))
        print(f"\n=== Top {top_k} recency settings (p_rec) by logloss ===")
        print(df_rec.to_string(index=False))

    if mom_rows:
        df_mom = pd.DataFrame(mom_rows).sort_values("logloss").head(int(top_k))
        print(f"\n=== Top {top_k} momentum settings (p_mom) by logloss ===")
        print(df_mom.to_string(index=False))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare tennis recency/momentum/TrueSkill variants"
    )
    p.add_argument(
        "--db-path",
        default="data/nhlstats.duckdb",
        help="DuckDB path (use a snapshot if the main DB is locked)",
    )
    p.add_argument("--tour", default="ALL", help="ATP|WTA|ALL")
    p.add_argument("--since", default=None, help="YYYY-MM-DD")
    p.add_argument("--until", default=None, help="YYYY-MM-DD")
    p.add_argument("--half-life-days", type=float, default=90.0)
    p.add_argument("--momentum-gamma", type=float, default=0.25)
    p.add_argument(
        "--grid-search",
        action="store_true",
        help="Run a parameter sweep for recency + momentum",
    )
    p.add_argument(
        "--half-life-grid",
        default="15,30,60,90,120,180,240",
        help="Comma-separated half-life days to try (grid-search)",
    )
    p.add_argument(
        "--gamma-grid",
        default=DEFAULT_GRID_VALUES,
        help="Comma-separated momentum gammas to try (grid-search)",
    )
    p.add_argument(
        "--top-k", type=int, default=10, help="Top results to display in grid-search"
    )
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    matches = load_tennis_matches(
        db_path=Path(str(args.db_path)),
        filters=MatchFilter(
            tour=str(args.tour),
            since=args.since,
            until=args.until,
        ),
    )
    print(f"✅ Loaded tennis matches: {len(matches)} (tour={args.tour})")

    if args.grid_search:
        half_life_grid = _parse_float_list(str(args.half_life_grid))
        gamma_grid = _parse_float_list(str(args.gamma_grid))
        grid_search(
            matches,
            half_life_grid=half_life_grid,
            gamma_grid=gamma_grid,
            top_k=int(args.top_k),
        )
        return

    metrics = evaluate(
        matches,
        half_life_days=float(args.half_life_days),
        momentum_gamma=float(args.momentum_gamma),
    )
    print("\n=== Metrics (lower logloss/brier is better) ===")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
