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
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


def _logit(p: float) -> float:
    p = float(np.clip(p, 1e-6, 1 - 1e-6))
    return float(math.log(p / (1.0 - p)))


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + math.exp(-x)))


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def _logloss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _accuracy(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p >= 0.5) == (y == 1)))


def _expected_elo(r_a: float, r_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))


@dataclass
class TennisMatch:
    date: pd.Timestamp
    tour: str
    winner: str
    loser: str


class BaselineTennisElo:
    """Baseline Elo mirroring current `TennisEloRating` logic."""

    def __init__(self, k_factor: float = 32.0, initial_rating: float = 1500.0) -> None:
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
        if self.matches_played.get(winner, 0) < 20:
            k *= 1.5
        if self.matches_played.get(loser, 0) < 20:
            k *= 1.5

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
        initial_rating: float = 1500.0,
        half_life_days: float = 90.0,
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
        lam = math.log(2.0) / max(self.half_life_days, 1e-6)
        factor = math.exp(-lam * delta_days)
        self.ratings[player] = self.initial_rating + (self.ratings[player] - self.initial_rating) * factor

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
        self.counts: Dict[Tuple[str, int], Tuple[int, int]] = {}  # (player, state) -> (wins, total)

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


def load_tennis_matches(
    *,
    db_path: Path = Path("data/nhlstats.duckdb"),
    csv_dir: Path = Path("data/tennis"),
    tour: str = "ALL",
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[TennisMatch]:
    tour = tour.upper()

    df: pd.DataFrame

    if db_path.exists():
        import duckdb

        conn = duckdb.connect(str(db_path), read_only=True)
        where = []
        params: List[object] = []
        if tour in {"ATP", "WTA"}:
            where.append("tour = ?")
            params.append(tour)
        if since:
            where.append("game_date >= ?")
            params.append(since)
        if until:
            where.append("game_date <= ?")
            params.append(until)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        query = f"""
            SELECT game_date, tour, winner, loser
            FROM tennis_games
            {where_sql}
            ORDER BY game_date ASC
        """
        df = conn.execute(query, params).fetchdf()
        conn.close()
    else:
        # CSV fallback
        from tennis_games import TennisGames

        tg = TennisGames(data_dir=str(csv_dir))
        raw = tg.load_games()
        if raw.empty:
            return []

        raw["game_date"] = pd.to_datetime(raw["date"]).dt.date
        raw["tour"] = raw["tour"].astype(str).str.upper()
        df = raw.rename(columns={"winner": "winner", "loser": "loser"})[["game_date", "tour", "winner", "loser"]]
        df["game_date"] = pd.to_datetime(df["game_date"])

        if tour in {"ATP", "WTA"}:
            df = df[df["tour"] == tour]
        if since:
            df = df[df["game_date"] >= pd.to_datetime(since)]
        if until:
            df = df[df["game_date"] <= pd.to_datetime(until)]

        df = df.sort_values("game_date")

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


def evaluate(
    matches: Sequence[TennisMatch],
    *,
    half_life_days: float,
    momentum_gamma: float,
) -> pd.DataFrame:
    if not matches:
        raise ValueError("No tennis matches found to evaluate")

    elo = BaselineTennisElo()
    rec = RecencyDecayedElo(half_life_days=half_life_days)
    mom = MarkovMomentum()

    ts = TeamTrueSkill() if TeamTrueSkill is not None else None

    rows: List[Dict[str, float]] = []

    for m in matches:
        # Use an ordering independent of outcome (lexicographic) to avoid y always being 1.
        a, b = sorted([m.winner, m.loser])
        y = 1.0 if a == m.winner else 0.0

        p_elo = elo.predict(a, b)
        p_rec = rec.predict(a, b, m.date)

        # Momentum overlay on top of recency Elo
        pa_m = mom.predict_win_prob(a)
        pb_m = mom.predict_win_prob(b)
        p_mom = _sigmoid(_logit(p_rec) + float(momentum_gamma) * (_logit(pa_m) - _logit(pb_m)))

        if ts is not None:
            p_ts = float(ts.predict(a, b, home_advantage=0.0))
        else:
            p_ts = float("nan")

        rows.append(
            {
                "y": y,
                "p_elo": float(p_elo),
                "p_rec": float(p_rec),
                "p_mom": float(p_mom),
                "p_ts": float(p_ts),
            }
        )

        # Update all models with the actual outcome (winner/loser)
        elo.update(m.winner, m.loser)
        rec.update(m.winner, m.loser, m.date)
        mom.update(m.winner, m.loser)
        if ts is not None:
            # Treat lexicographic 'a' as home for predict; update with same mapping.
            home_won = bool(a == m.winner)
            ts.update(a, b, home_won=home_won, home_advantage=0.0)

    df = pd.DataFrame(rows)

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

    return pd.DataFrame(metrics).sort_values("logloss")


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
    """Run a simple parameter sweep for recency and momentum.

    Prints:
    - Baseline metrics (Elo and TrueSkill if available)
    - Top-k parameter settings for recency decay (p_rec)
    - Top-k parameter settings for momentum overlay (p_mom)
    """

    baseline = evaluate(matches, half_life_days=float(half_life_grid[0]), momentum_gamma=float(gamma_grid[0]))
    base_rows = baseline[baseline["model"].isin(["p_elo", "p_ts"])].copy()
    if not base_rows.empty:
        print("\n=== Baselines (fixed params) ===")
        print(base_rows.to_string(index=False))

    rec_rows: List[Dict[str, float]] = []
    mom_rows: List[Dict[str, float]] = []

    for hl in half_life_grid:
        for g in gamma_grid:
            metrics = evaluate(matches, half_life_days=float(hl), momentum_gamma=float(g))

            rec = metrics[metrics["model"] == "p_rec"]
            if not rec.empty:
                r = rec.iloc[0]
                rec_rows.append(
                    {
                        "half_life_days": float(hl),
                        "gamma": float(g),
                        "accuracy": float(r["accuracy"]),
                        "logloss": float(r["logloss"]),
                        "brier": float(r["brier"]),
                    }
                )

            mom = metrics[metrics["model"] == "p_mom"]
            if not mom.empty:
                r = mom.iloc[0]
                mom_rows.append(
                    {
                        "half_life_days": float(hl),
                        "gamma": float(g),
                        "accuracy": float(r["accuracy"]),
                        "logloss": float(r["logloss"]),
                        "brier": float(r["brier"]),
                    }
                )

    if rec_rows:
        df_rec = pd.DataFrame(rec_rows).sort_values("logloss").head(int(top_k))
        print(f"\n=== Top {top_k} recency settings (p_rec) by logloss ===")
        print(df_rec.to_string(index=False))

    if mom_rows:
        df_mom = pd.DataFrame(mom_rows).sort_values("logloss").head(int(top_k))
        print(f"\n=== Top {top_k} momentum settings (p_mom) by logloss ===")
        print(df_mom.to_string(index=False))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare tennis recency/momentum/TrueSkill variants")
    p.add_argument("--db-path", default="data/nhlstats.duckdb", help="DuckDB path (use a snapshot if the main DB is locked)")
    p.add_argument("--tour", default="ALL", help="ATP|WTA|ALL")
    p.add_argument("--since", default=None, help="YYYY-MM-DD")
    p.add_argument("--until", default=None, help="YYYY-MM-DD")
    p.add_argument("--half-life-days", type=float, default=90.0)
    p.add_argument("--momentum-gamma", type=float, default=0.25)
    p.add_argument("--grid-search", action="store_true", help="Run a parameter sweep for recency + momentum")
    p.add_argument(
        "--half-life-grid",
        default="15,30,60,90,120,180,240",
        help="Comma-separated half-life days to try (grid-search)",
    )
    p.add_argument(
        "--gamma-grid",
        default="0.0,0.05,0.1,0.2,0.35,0.5",
        help="Comma-separated momentum gammas to try (grid-search)",
    )
    p.add_argument("--top-k", type=int, default=10, help="Top results to display in grid-search")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    matches = load_tennis_matches(
        db_path=Path(str(args.db_path)),
        tour=str(args.tour),
        since=args.since,
        until=args.until,
    )
    print(f"✅ Loaded tennis matches: {len(matches)} (tour={args.tour})")

    if args.grid_search:
        half_life_grid = _parse_float_list(str(args.half_life_grid))
        gamma_grid = _parse_float_list(str(args.gamma_grid))
        grid_search(matches, half_life_grid=half_life_grid, gamma_grid=gamma_grid, top_k=int(args.top_k))
        return

    metrics = evaluate(matches, half_life_days=float(args.half_life_days), momentum_gamma=float(args.momentum_gamma))
    print("\n=== Metrics (lower logloss/brier is better) ===")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
