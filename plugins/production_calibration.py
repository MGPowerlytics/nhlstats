"""Production calibration helpers for Airflow DAG usage.

These helpers are designed to be:
- Robust (safe fallbacks if data is missing)
- Fast (cached to disk under data/calibration/)
- Dependency-light at import time (sklearn only used during fitting)

Calibration method: Platt scaling on logit(prob).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from probability_calibration import PlattParams, apply_platt_params, fit_platt_params


def _calibration_dir() -> Path:
    d = Path("data/calibration")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_json(path: Path) -> Optional[dict]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    tmp.replace(path)


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _safe_int(v) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return None


def get_college_platt_params(
    *,
    league: str,
    train_seasons: int = 3,
    min_train_games: int = 2000,
    platt_c: float = 1.0,
    platt_max_iter: int = 1000,
    force_refit: bool = False,
) -> Optional[PlattParams]:
    """Get (or fit) Platt params for NCAAB/WNCAAB home-win probabilities.

    Training uses seasons strictly before the latest season available.
    """

    league = league.lower().strip()
    if league not in {"ncaab", "wncaab"}:
        raise ValueError(f"Unsupported league: {league}")

    cache_path = _calibration_dir() / f"{league}_platt_home.json"
    cached = _read_json(cache_path)
    if cached and not force_refit:
        alpha = cached.get("alpha")
        beta = cached.get("beta")
        if isinstance(alpha, (int, float)) and isinstance(beta, (int, float)):
            return PlattParams(alpha=float(alpha), beta=float(beta))

    df = _load_college_games_from_cache(league)
    if df.empty:
        return None

    latest_season = int(df["season"].max())
    train_df = df[df["season"] < latest_season].copy()
    if train_df.empty:
        return None

    if train_seasons and train_seasons > 0:
        seasons = sorted(train_df["season"].unique())
        keep = set(seasons[-int(train_seasons) :])
        train_df = train_df[train_df["season"].isin(keep)]

    # Build sequential predictions to match our Elo definition
    p_raw, y = _sequential_college_elo_probs(league, train_df)
    if len(p_raw) < int(min_train_games):
        return None

    params = fit_platt_params(
        y=y, probs=p_raw, c=float(platt_c), max_iter=int(platt_max_iter)
    )
    if params is None:
        return None

    _write_json(
        cache_path,
        {
            **asdict(params),
            "league": league,
            "trained_at": _now_iso(),
            "train_seasons": int(train_seasons),
            "latest_season": int(latest_season),
            "n_train": int(len(p_raw)),
        },
    )
    return params


def get_tennis_bucketed_platt_params(
    *,
    min_train_matches: int = 2000,
    platt_c: float = 1.0,
    platt_max_iter: int = 1000,
    force_refit: bool = False,
) -> Dict[str, PlattParams]:
    """Get (or fit) Platt params for tennis by tour (ATP/WTA).

    Returns:
        Dict mapping {'ATP': PlattParams, 'WTA': PlattParams}. Missing tours are
        omitted.
    """

    cache_path = _calibration_dir() / "tennis_platt_by_tour.json"
    cached = _read_json(cache_path)
    if cached and not force_refit:
        out: Dict[str, PlattParams] = {}
        for tour in ("ATP", "WTA"):
            node = cached.get("tours", {}).get(tour)
            if not isinstance(node, dict):
                continue
            alpha = node.get("alpha")
            beta = node.get("beta")
            if isinstance(alpha, (int, float)) and isinstance(beta, (int, float)):
                out[tour] = PlattParams(alpha=float(alpha), beta=float(beta))
        if out:
            return out

    matches = _load_tennis_matches_from_cache()
    if matches.empty:
        return {}

    out: Dict[str, PlattParams] = {}
    meta: Dict[str, dict] = {}
    for tour in ("ATP", "WTA"):
        tdf = matches[matches["tour"] == tour].copy()
        if tdf.empty:
            continue

        p_raw, y = _sequential_tennis_elo_probs(tdf)
        if len(p_raw) < int(min_train_matches):
            continue

        params = fit_platt_params(
            y=y, probs=p_raw, c=float(platt_c), max_iter=int(platt_max_iter)
        )
        if params is None:
            continue
        out[tour] = params
        meta[tour] = {"n_train": int(len(p_raw))}

    if out:
        _write_json(
            cache_path,
            {
                "trained_at": _now_iso(),
                "tours": {t: {**asdict(p), **meta.get(t, {})} for t, p in out.items()},
            },
        )
    return out


def calibrate_probability(params: Optional[PlattParams], p: float) -> float:
    """Calibrate a single probability with safe fallback."""

    if params is None:
        return float(p)
    return float(apply_platt_params(params, np.asarray([float(p)], dtype=float))[0])


def _load_college_games_from_cache(league: str) -> pd.DataFrame:
    """Load cached Massey CSVs for NCAAB/WNCAAB without re-downloading."""

    data_dir = Path(f"data/{league}")
    if not data_dir.exists():
        return pd.DataFrame()

    game_files = sorted(data_dir.glob("games_*.csv"))
    if not game_files:
        return pd.DataFrame()

    rows: List[dict] = []
    for games_file in game_files:
        season = _safe_int(games_file.stem.split("_")[-1])
        if season is None:
            continue
        teams_file = data_dir / f"teams_{season}.csv"
        if not teams_file.exists():
            continue

        try:
            teams_df = pd.read_csv(
                teams_file, header=None, names=["team_id", "team_name"]
            )
            teams_df["team_name"] = teams_df["team_name"].astype(str).str.strip()
            team_map = dict(zip(teams_df["team_id"], teams_df["team_name"]))

            try:
                games_df = pd.read_csv(games_file, header=None)
            except pd.errors.EmptyDataError:
                continue

            if games_df.shape[1] < 8:
                continue

            for _, row in games_df.iterrows():
                try:
                    date_int = row[1]
                    t1_id = row[2]
                    loc1 = row[3]
                    s1 = row[4]
                    t2_id = row[5]
                    s2 = row[7]

                    t1_name = team_map.get(t1_id)
                    t2_name = team_map.get(t2_id)
                    if not t1_name or not t2_name:
                        continue

                    if loc1 == 1:
                        home_team, away_team = t1_name, t2_name
                        home_score, away_score = float(s1), float(s2)
                        neutral = False
                    elif loc1 == -1:
                        home_team, away_team = t2_name, t1_name
                        home_score, away_score = float(s2), float(s1)
                        neutral = False
                    else:
                        home_team, away_team = t1_name, t2_name
                        home_score, away_score = float(s1), float(s2)
                        neutral = True

                    game_date = pd.to_datetime(
                        str(date_int).strip(), format="%Y%m%d", errors="coerce"
                    )
                    if pd.isna(game_date):
                        continue

                    rows.append(
                        {
                            "date": game_date,
                            "home_team": str(home_team),
                            "away_team": str(away_team),
                            "home_score": float(home_score),
                            "away_score": float(away_score),
                            "neutral": bool(neutral),
                            "season": int(season),
                        }
                    )
                except Exception:
                    continue
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if league == "wncaab":
        # Match WNCAABGames behavior: D1-only filter.
        try:
            from wncaab_games import D1_PROGRAMS

            df = df[
                df["home_team"].isin(D1_PROGRAMS) & df["away_team"].isin(D1_PROGRAMS)
            ].copy()
        except Exception:
            pass

    df["season"] = df["season"].astype(int)
    return df.sort_values("date")


def _sequential_college_elo_probs(
    league: str, df: pd.DataFrame
) -> Tuple[np.ndarray, np.ndarray]:
    league = league.lower().strip()
    if league == "ncaab":
        from plugins.elo import NCAABEloRating

        elo = NCAABEloRating(k_factor=20, home_advantage=100)
    elif league == "wncaab":
        from plugins.elo import WNCAABEloRating

        elo = WNCAABEloRating(k_factor=20, home_advantage=100)
    else:
        raise ValueError(f"Unsupported league: {league}")

    df = df.copy().sort_values(["season", "date"])
    last_season: Optional[int] = None
    probs: List[float] = []
    labels: List[int] = []

    for _, g in df.iterrows():
        season = int(g["season"]) if pd.notna(g.get("season")) else None
        if season is not None and last_season is not None and season != last_season:
            # Revert ratings toward mean between seasons.
            for t in list(getattr(elo, "ratings", {}).keys()):
                elo.ratings[t] = 0.65 * float(elo.ratings[t]) + 0.35 * 1500.0
        if season is not None:
            last_season = season

        home_team = str(g["home_team"])
        away_team = str(g["away_team"])
        neutral = bool(g.get("neutral", False))
        y = 1 if float(g["home_score"]) > float(g["away_score"]) else 0

        p = float(elo.predict(home_team, away_team, is_neutral=neutral))
        probs.append(p)
        labels.append(y)
        elo.update(home_team, away_team, float(y), is_neutral=neutral)

    return np.asarray(probs, dtype=float), np.asarray(labels, dtype=int)


def _load_tennis_matches_from_cache() -> pd.DataFrame:
    data_dir = Path("data/tennis")
    if not data_dir.exists():
        return pd.DataFrame()

    rows: List[dict] = []
    for tour in ("ATP", "WTA"):
        prefix = "atp" if tour == "ATP" else "wta"
        for csv_path in sorted(data_dir.glob(f"{prefix}_*.csv")):
            try:
                try:
                    df = pd.read_csv(csv_path, encoding="latin1")
                except Exception:
                    df = pd.read_csv(csv_path)

                if (
                    "Date" not in df.columns
                    or "Winner" not in df.columns
                    or "Loser" not in df.columns
                ):
                    continue

                df = df.copy()
                df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
                df = df.dropna(subset=["Date", "Winner", "Loser"])
                for _, r in df.iterrows():
                    rows.append(
                        {
                            "date": pd.to_datetime(r["Date"]),
                            "tour": tour,
                            "winner": str(r["Winner"]).strip(),
                            "loser": str(r["Loser"]).strip(),
                        }
                    )
            except Exception:
                continue

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["tour"] = out["tour"].astype(str).str.upper()
    out["date"] = pd.to_datetime(out["date"])
    return out.sort_values("date")


def _sequential_tennis_elo_probs(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    from plugins.elo import TennisEloRating

    df = df.copy().sort_values("date")
    tour = str(df["tour"].iloc[0]).upper() if not df.empty else "ATP"

    elo = TennisEloRating(k_factor=32)
    probs: List[float] = []
    labels: List[int] = []
    for _, g in df.iterrows():
        winner = str(g["winner"])
        loser = str(g["loser"])
        a, b = sorted([winner, loser])
        y = 1 if winner == a else 0
        p = float(elo.predict(a, b, tour=tour))
        probs.append(p)
        labels.append(y)
        elo.update(winner, loser, tour=tour)

    return np.asarray(probs, dtype=float), np.asarray(labels, dtype=int)
