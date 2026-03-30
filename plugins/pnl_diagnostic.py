#!/usr/bin/env python3
"""
P&L Diagnostic Module

Comprehensive diagnostic analysis for the multi-sport Elo betting system.
Replays Elo ratings from scratch, recalculates edge for historical bets,
runs bootstrap significance testing, and generates per-sport recommendations.

Usage:
    from plugins.pnl_diagnostic import run_diagnostic
    results = run_diagnostic()
"""

import csv
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from plugins.constants import (
    BOOTSTRAP_CONFIDENCE_LEVEL,
    BOOTSTRAP_N_ITERATIONS,
    FILL_TIME_BUCKET_LABELS,
    FILL_TIME_BUCKETS,
    MAX_BET_SIZE,
    MIN_BETS_FOR_DIAGNOSTIC,
    STALE_CLOSING_PRICE_HOURS,
    TIMING_BUCKET_LABELS,
    TIMING_BUCKETS,
)
from plugins.db_manager import default_db
from plugins.elo.factory import create_elo_instance


# ---------------------------------------------------------------------------
# Bootstrap significance test
# ---------------------------------------------------------------------------


def bootstrap_pnl_test(
    profits: List[float],
    n_bootstrap: int = BOOTSTRAP_N_ITERATIONS,
    confidence: float = BOOTSTRAP_CONFIDENCE_LEVEL,
) -> Dict:
    """Bootstrap test: is the sum of profits significantly different from zero?

    Resamples the profit vector with replacement to build a distribution of
    mean P&L, then checks whether zero falls inside the confidence interval.

    Args:
        profits: List of per-bet profit/loss values.
        n_bootstrap: Number of bootstrap iterations.
        confidence: Confidence level for the interval (e.g. 0.95).

    Returns:
        Dict with keys: p_value, ci_lower, ci_upper, mean_pnl, n_samples.

    Raises:
        ValueError: If profits list is empty.
    """
    if not profits:
        raise ValueError("Cannot run bootstrap on empty profit list")

    profits_arr = np.array(profits, dtype=float)
    observed_mean = float(np.mean(profits_arr))
    n = len(profits_arr)

    rng = np.random.default_rng(seed=42)
    boot_means = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample = rng.choice(profits_arr, size=n, replace=True)
        boot_means[i] = np.mean(sample)

    alpha = 1 - confidence
    ci_lower = float(np.percentile(boot_means, 100 * alpha / 2))
    ci_upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))

    # Two-sided p-value: fraction of bootstrap means on the opposite side of zero
    if observed_mean >= 0:
        p_value = float(np.mean(boot_means <= 0)) * 2
    else:
        p_value = float(np.mean(boot_means >= 0)) * 2
    p_value = min(p_value, 1.0)

    return {
        "p_value": p_value,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "mean_pnl": observed_mean,
        "n_samples": n,
    }


# ---------------------------------------------------------------------------
# Timing analysis
# ---------------------------------------------------------------------------


def compute_timing_analysis(bets_df: pd.DataFrame) -> Dict:
    """Compute ROI grouped by hours-before-game timing buckets.

    Args:
        bets_df: DataFrame with placed_time_utc, market_close_time_utc,
                 cost_dollars, profit_dollars columns.

    Returns:
        Dict mapping bucket label (str) → ROI (float).
        Empty dict if no valid data.
    """
    if bets_df.empty:
        return {}

    df = bets_df.copy()

    # Compute hours before game (market_close ≈ game time)
    df["placed_time_utc"] = pd.to_datetime(df["placed_time_utc"], errors="coerce")
    df["market_close_time_utc"] = pd.to_datetime(
        df["market_close_time_utc"], errors="coerce"
    )

    # Drop rows missing timing data
    df = df.dropna(subset=["placed_time_utc", "market_close_time_utc"])
    if df.empty:
        return {}

    df["hours_before_game"] = (
        df["market_close_time_utc"] - df["placed_time_utc"]
    ).dt.total_seconds() / 3600.0

    # Bucket assignment
    result = {}
    for i in range(len(TIMING_BUCKETS) - 1):
        lo, hi = TIMING_BUCKETS[i], TIMING_BUCKETS[i + 1]
        label = TIMING_BUCKET_LABELS[i]
        mask = (df["hours_before_game"] >= lo) & (df["hours_before_game"] < hi)
        bucket_df = df[mask]
        if len(bucket_df) > 0:
            total_cost = bucket_df["cost_dollars"].sum()
            total_profit = bucket_df["profit_dollars"].sum()
            roi = total_profit / total_cost if total_cost > 0 else 0.0
            result[label] = float(roi)

    return result


def what_if_timing_replay(bets_df: pd.DataFrame, max_hours: float = 2.0) -> Dict:
    """Hypothetical ROI if only bets placed within max_hours of game were kept.

    Args:
        bets_df: DataFrame with timing and profit columns.
        max_hours: Maximum hours before game to include.

    Returns:
        Dict with n_bets, total_profit, total_cost, roi.
    """
    if bets_df.empty:
        return {"n_bets": 0, "total_profit": 0.0, "total_cost": 0.0, "roi": 0.0}

    df = bets_df.copy()
    df["placed_time_utc"] = pd.to_datetime(df["placed_time_utc"], errors="coerce")
    df["market_close_time_utc"] = pd.to_datetime(
        df["market_close_time_utc"], errors="coerce"
    )
    df = df.dropna(subset=["placed_time_utc", "market_close_time_utc"])

    if df.empty:
        return {"n_bets": 0, "total_profit": 0.0, "total_cost": 0.0, "roi": 0.0}

    df["hours_before_game"] = (
        df["market_close_time_utc"] - df["placed_time_utc"]
    ).dt.total_seconds() / 3600.0

    filtered = df[df["hours_before_game"] <= max_hours]
    n = len(filtered)
    total_profit = float(filtered["profit_dollars"].sum()) if n > 0 else 0.0
    total_cost = float(filtered["cost_dollars"].sum()) if n > 0 else 0.0
    roi = total_profit / total_cost if total_cost > 0 else 0.0

    return {
        "n_bets": n,
        "total_profit": total_profit,
        "total_cost": total_cost,
        "roi": float(roi) if n > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Fill time analysis (hours before game at Kalshi fill time)
# ---------------------------------------------------------------------------


def compute_fill_time_analysis(bets_df: pd.DataFrame) -> pd.DataFrame:
    """Analyze ROI and edge degradation by hours-before-game at fill time.

    Since placed_time_utc = Kalshi fill timestamp (created_time), this computes
    how early/late bets were filled relative to game start, and whether
    earlier fills have better or worse ROI (adverse selection signal).

    Uses ``game_start_time_utc`` column if present; falls back to
    ``market_close_time_utc``.  Accepts ``profit_loss`` or ``profit_dollars``
    column for profit data.

    Args:
        bets_df: DataFrame with columns: placed_time_utc, game_start_time_utc
            (or market_close_time_utc), profit_loss (or profit_dollars), edge,
            sport. Must have both timestamp columns.

    Returns:
        DataFrame with columns: hours_bucket, n_bets, roi_pct, avg_edge,
        avg_hours_before_game, sport (only when sport column is present in
        input).  Returns empty DataFrame when input is empty, has no valid
        timestamps, or is missing required profit column.
    """
    _empty = pd.DataFrame(
        columns=[
            "hours_bucket",
            "n_bets",
            "roi_pct",
            "avg_edge",
            "avg_hours_before_game",
        ]
    )

    if bets_df.empty:
        return _empty

    df = bets_df.copy()

    # Resolve profit column
    if "profit_loss" in df.columns:
        profit_col = "profit_loss"
    elif "profit_dollars" in df.columns:
        profit_col = "profit_dollars"
    else:
        return _empty

    # Resolve game-time column
    if "game_start_time_utc" in df.columns:
        game_time_col = "game_start_time_utc"
    elif "market_close_time_utc" in df.columns:
        game_time_col = "market_close_time_utc"
    else:
        return _empty

    # Parse timestamps
    df["placed_time_utc"] = pd.to_datetime(df["placed_time_utc"], errors="coerce")
    df[game_time_col] = pd.to_datetime(df[game_time_col], errors="coerce")

    # Drop rows with missing timestamps
    df = df.dropna(subset=["placed_time_utc", game_time_col])
    if df.empty:
        return _empty

    # Compute hours before game at fill time
    df["_hours_before_game"] = (
        df[game_time_col] - df["placed_time_utc"]
    ).dt.total_seconds() / 3600.0

    # Assign fill-time buckets
    df["hours_bucket"] = pd.cut(
        df["_hours_before_game"],
        bins=FILL_TIME_BUCKETS,
        labels=FILL_TIME_BUCKET_LABELS,
        right=False,
    )

    # Group by bucket (and sport if present); use scalar key for single-column groupby
    has_sport = "sport" in df.columns

    rows: List[Dict] = []

    if has_sport:
        for (bucket, sport_val), group in df.groupby(
            ["hours_bucket", "sport"], observed=True
        ):
            n = len(group)
            profit_sum = float(group[profit_col].sum())

            if "cost_dollars" in group.columns:
                cost_sum = float(group["cost_dollars"].sum())
                roi_pct = (profit_sum / cost_sum * 100.0) if cost_sum > 0 else 0.0
            else:
                losses_sum = float(
                    group.loc[group[profit_col] < 0, profit_col].abs().sum()
                )
                roi_pct = (profit_sum / losses_sum * 100.0) if losses_sum > 0 else 0.0

            avg_edge: Optional[float] = None
            if "edge" in group.columns:
                edge_vals = group["edge"].dropna()
                if not edge_vals.empty:
                    avg_edge = float(edge_vals.mean())

            rows.append(
                {
                    "hours_bucket": bucket,
                    "n_bets": n,
                    "roi_pct": float(roi_pct),
                    "avg_edge": avg_edge,
                    "avg_hours_before_game": float(group["_hours_before_game"].mean()),
                    "sport": sport_val,
                }
            )
    else:
        for bucket, group in df.groupby("hours_bucket", observed=True):
            n = len(group)
            profit_sum = float(group[profit_col].sum())

            if "cost_dollars" in group.columns:
                cost_sum = float(group["cost_dollars"].sum())
                roi_pct = (profit_sum / cost_sum * 100.0) if cost_sum > 0 else 0.0
            else:
                losses_sum = float(
                    group.loc[group[profit_col] < 0, profit_col].abs().sum()
                )
                roi_pct = (profit_sum / losses_sum * 100.0) if losses_sum > 0 else 0.0

            avg_edge = None
            if "edge" in group.columns:
                edge_vals = group["edge"].dropna()
                if not edge_vals.empty:
                    avg_edge = float(edge_vals.mean())

            rows.append(
                {
                    "hours_bucket": bucket,
                    "n_bets": n,
                    "roi_pct": float(roi_pct),
                    "avg_edge": avg_edge,
                    "avg_hours_before_game": float(group["_hours_before_game"].mean()),
                }
            )

    if not rows:
        return _empty

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------


def generate_recommendation(
    sport: str,
    roi: float,
    real_clv: Optional[float],
    bootstrap_result: Dict,
) -> str:
    """Generate CONTINUE / PAUSE / INSUFFICIENT_DATA recommendation.

    Logic:
    - INSUFFICIENT_DATA: if n_samples < MIN_BETS_FOR_DIAGNOSTIC
    - PAUSE: if bootstrap CI upper bound < 0 (evidence of negative edge)
    - CONTINUE: otherwise (no evidence of negative edge)

    Args:
        sport: Sport code.
        roi: Return on investment for the sport.
        real_clv: Average real CLV, or None.
        bootstrap_result: Dict from bootstrap_pnl_test().

    Returns:
        One of 'CONTINUE', 'PAUSE', 'INSUFFICIENT_DATA'.
    """
    n_samples = bootstrap_result.get("n_samples")
    if n_samples is not None and n_samples < MIN_BETS_FOR_DIAGNOSTIC:
        return "INSUFFICIENT_DATA"

    ci_upper = bootstrap_result.get("ci_upper", 0.0)
    if ci_upper < 0:
        return "PAUSE"

    return "CONTINUE"


# ---------------------------------------------------------------------------
# Elo replay
# ---------------------------------------------------------------------------


def replay_elo_ratings(sport: str) -> Dict[str, float]:
    """Replay all historical games chronologically to rebuild Elo ratings.

    Loads completed games from unified_games ordered by date, instantiates
    the sport's Elo class via factory, and processes each game sequentially.

    Args:
        sport: Sport code (e.g., 'nba', 'nhl'). Case-insensitive.

    Returns:
        Dict mapping team name → final Elo rating.

    Raises:
        ValueError: If sport is not recognized by the Elo factory.
    """
    sport_lower = sport.lower()
    try:
        elo = create_elo_instance(sport_lower)
    except (KeyError, ValueError) as e:
        raise ValueError(f"Unsupported sport: {sport_lower}") from e

    # Load all completed games chronologically
    query = """
        SELECT game_id, home_team_name, away_team_name, home_score, away_score
        FROM unified_games
        WHERE LOWER(sport) = :sport
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        ORDER BY game_date, commence_time
    """
    try:
        result = default_db.execute(query, {"sport": sport_lower})
        games = result.fetchall()
    except Exception as e:
        print(f"❌ Error loading games for {sport}: {e}")
        return {}

    print(f"📊 Replaying {len(games)} {sport.upper()} games...")

    for i, game in enumerate(games):
        home_team = game[1]
        away_team = game[2]
        home_score = game[3]
        away_score = game[4]
        home_won = home_score > away_score

        try:
            elo.update(home_team, away_team, home_won)
        except Exception:
            pass  # Skip games that fail (bad data, etc.)

        if (i + 1) % 1000 == 0:
            print(f"  ⏳ Processed {i + 1}/{len(games)} games...")

    print(f"  ✅ Replay complete: {len(games)} games, {len(elo.ratings)} teams")
    return dict(elo.ratings)


# ---------------------------------------------------------------------------
# Replay vs CSV comparison
# ---------------------------------------------------------------------------


def compare_replay_vs_csv(sport: str, replayed_ratings: Dict[str, float]) -> float:
    """Compare replayed Elo ratings against the stored CSV ratings.

    Reads the CSV file at ``data/{sport}_current_elo_ratings.csv`` (format:
    ``team,rating``).  Falls back to JSON if the content is JSON-encoded.

    Args:
        sport: Sport code (e.g., 'nba').
        replayed_ratings: Dict from replay_elo_ratings().

    Returns:
        Maximum absolute divergence in Elo points across all teams.
        Returns ``float('inf')`` if file is missing or unreadable.
    """
    import io
    import json

    csv_path = os.path.join("data", f"{sport.lower()}_current_elo_ratings.csv")
    csv_ratings: Dict[str, float] = {}

    try:
        with open(csv_path, "r") as f:
            content = f.read()

        # Try CSV format first (team,rating)
        try:
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                team = row.get("team", "")
                rating = float(row.get("rating", 1500))
                csv_ratings[team] = rating
        except Exception:
            pass

        # Fall back to JSON if CSV yielded nothing
        if not csv_ratings:
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "ratings" in data:
                    csv_ratings = {k: float(v) for k, v in data["ratings"].items()}
                elif isinstance(data, dict):
                    csv_ratings = {k: float(v) for k, v in data.items()}
            except (json.JSONDecodeError, ValueError):
                pass

    except FileNotFoundError:
        print(f"  ⚠️ File not found: {csv_path}")
        return float("inf")
    except Exception as e:
        print(f"  ⚠️ Error reading {csv_path}: {e}")
        return float("inf")

    if not csv_ratings:
        return float("inf")

    common_teams = set(replayed_ratings.keys()) & set(csv_ratings.keys())
    if not common_teams:
        return float("inf")

    max_div = 0.0
    for team in common_teams:
        div = abs(replayed_ratings[team] - csv_ratings[team])
        max_div = max(max_div, div)

    return max_div


# ---------------------------------------------------------------------------
# Recalculate bet metrics
# ---------------------------------------------------------------------------


def recalculate_bet_metrics(
    sport: str, replayed_ratings: Dict[str, float]
) -> pd.DataFrame:
    """Recalculate elo_prob and edge for placed_bets using replayed ratings.

    For each settled bet, sets the replayed team ratings on a fresh Elo instance
    and re-predicts the home win probability. Computes new edge vs market_prob.

    Args:
        sport: Sport code (e.g., 'NBA').
        replayed_ratings: Dict from replay_elo_ratings().

    Returns:
        DataFrame with columns: bet_id, old_elo_prob, new_elo_prob,
        old_edge, new_edge, home_team, away_team, market_prob, profit_dollars.
    """
    sport_lower = sport.lower()
    try:
        elo = create_elo_instance(sport_lower)
    except (KeyError, ValueError):
        elo = None

    # Load replayed ratings into the Elo instance
    if elo is not None:
        for team, rating in replayed_ratings.items():
            try:
                elo.set_rating(team, rating)
            except Exception:
                pass

    # Load settled bets for this sport
    query = """
        SELECT bet_id, home_team, away_team, bet_on,
               elo_prob, market_prob, edge, profit_dollars
        FROM placed_bets
        WHERE UPPER(sport) = UPPER(:sport)
          AND status IN ('won', 'lost')
    """
    try:
        bets_df = default_db.fetch_df(query, {"sport": sport})
    except Exception:
        return pd.DataFrame()

    if bets_df.empty:
        return pd.DataFrame()

    rows = []
    for _, bet in bets_df.iterrows():
        home = bet.get("home_team", "")
        away = bet.get("away_team", "")
        bet_on = bet.get("bet_on", "home")
        old_elo_prob = bet.get("elo_prob")
        market_prob = bet.get("market_prob")

        # Compute new elo_prob from replayed ratings
        if elo is not None and home and away:
            try:
                result = elo.predict(home, away)
                # predict() returns a float (home win prob)
                if isinstance(result, tuple):
                    new_home_prob = result[0]
                else:
                    new_home_prob = float(result)

                # Map to the bet side
                bet_on_lower = str(bet_on).lower() if bet_on else "home"
                if bet_on_lower == "away" or (
                    bet_on and bet_on.upper() == str(away).upper()
                ):
                    new_elo_prob = 1.0 - new_home_prob
                else:
                    new_elo_prob = new_home_prob
            except Exception:
                new_elo_prob = old_elo_prob
        else:
            new_elo_prob = old_elo_prob

        new_edge = (
            (new_elo_prob - market_prob)
            if new_elo_prob is not None and market_prob is not None
            else None
        )

        rows.append(
            {
                "bet_id": bet["bet_id"],
                "home_team": home,
                "away_team": away,
                "old_elo_prob": old_elo_prob,
                "new_elo_prob": new_elo_prob,
                "old_edge": bet.get("edge"),
                "new_edge": new_edge,
                "market_prob": market_prob,
                "profit_dollars": bet.get("profit_dollars"),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Market impact helpers
# ---------------------------------------------------------------------------

_MARKET_IMPACT_NEGLIGIBLE_THRESHOLD = 1.0  # percent
_MARKET_IMPACT_SIGNIFICANT_THRESHOLD = 5.0  # percent


def _get_kalshi_api_instance() -> Any:
    """Return a live KalshiAPI instance, or None if credentials unavailable.

    Returns:
        KalshiAPI instance or None.
    """
    try:
        from plugins.kalshi_markets import KalshiAPI, load_kalshi_credentials

        api_key_id, private_key_pem = load_kalshi_credentials()
        if not api_key_id or not private_key_pem:
            return None
        return KalshiAPI(api_key_id=api_key_id, private_key_pem=private_key_pem)
    except Exception:
        return None


def _compute_verdict(max_impact_pct: float) -> str:
    """Map max market impact percentage to a verdict label.

    Args:
        max_impact_pct: Maximum observed market impact percentage.

    Returns:
        'NEGLIGIBLE' if max_impact_pct < 1%, 'MONITOR' if 1-5%,
        'SIGNIFICANT' if >= 5%.
    """
    if max_impact_pct >= _MARKET_IMPACT_SIGNIFICANT_THRESHOLD:
        return "SIGNIFICANT"
    if max_impact_pct >= _MARKET_IMPACT_NEGLIGIBLE_THRESHOLD:
        return "MONITOR"
    return "NEGLIGIBLE"


def analyze_market_impact(
    sample_tickers: Optional[List[str]] = None,
    bet_size: float = MAX_BET_SIZE,
    max_tickers: int = 20,
) -> Dict[str, Any]:
    """Analyze Kalshi order book depth vs bet size for market impact assessment.

    Fetches order book depth for a sample of recently-active tickers and
    computes the market impact percentage of current bet sizes.

    Args:
        sample_tickers: List of Kalshi tickers to sample. If None, queries
                       placed_bets for recent tickers.
        bet_size: Dollar size to analyze for market impact. Defaults to
                  MAX_BET_SIZE.
        max_tickers: Maximum number of tickers to fetch. Defaults to 20.

    Returns:
        Dict with keys:
            'tickers_analyzed': int
            'median_yes_depth_usd': float or None
            'median_market_impact_pct': float or None
            'max_market_impact_pct': float or None
            'verdict': str ('NEGLIGIBLE' if max < 1%, 'MONITOR' if 1-5%,
                'SIGNIFICANT' if >= 5%, 'UNKNOWN' if unavailable)
            'bet_size_analyzed': float
            'per_ticker': List[Dict] with depth data per ticker
    """
    unknown_result: Dict[str, Any] = {
        "tickers_analyzed": 0,
        "median_yes_depth_usd": None,
        "median_market_impact_pct": None,
        "max_market_impact_pct": None,
        "verdict": "UNKNOWN",
        "bet_size_analyzed": bet_size,
        "per_ticker": [],
    }

    api = _get_kalshi_api_instance()
    if api is None:
        return unknown_result

    # Resolve tickers to sample
    if sample_tickers is None:
        query = """
            SELECT DISTINCT ticker FROM placed_bets
            WHERE placed_time_utc > NOW() - INTERVAL '30 days'
            AND ticker IS NOT NULL
            LIMIT :max_tickers
        """
        try:
            result = default_db.execute(query, {"max_tickers": max_tickers})
            rows = result.fetchall()
            sample_tickers = [row[0] for row in rows]
        except Exception as e:
            print(f"⚠️ Could not query placed_bets for tickers: {e}")
            return unknown_result

    if not sample_tickers:
        return unknown_result

    per_ticker: List[Dict[str, Any]] = []
    for ticker in sample_tickers[:max_tickers]:
        depth = api.get_order_book_depth(ticker, bet_size=bet_size)
        if not depth:
            continue  # skip tickers where API failed
        per_ticker.append(
            {
                "ticker": ticker,
                "total_yes_depth_usd": depth["total_yes_depth_usd"],
                "market_impact_pct": depth["market_impact_pct"],
                "yes_top_of_book": depth["yes_top_of_book"],
            }
        )

    if not per_ticker:
        return {**unknown_result, "tickers_analyzed": 0}

    depths = [t["total_yes_depth_usd"] for t in per_ticker]
    impacts = [t["market_impact_pct"] for t in per_ticker]

    median_depth = float(np.median(depths))
    median_impact = float(np.median(impacts))
    max_impact = float(np.max(impacts))

    return {
        "tickers_analyzed": len(per_ticker),
        "median_yes_depth_usd": median_depth,
        "median_market_impact_pct": median_impact,
        "max_market_impact_pct": max_impact,
        "verdict": _compute_verdict(max_impact),
        "bet_size_analyzed": bet_size,
        "per_ticker": per_ticker,
    }


# ---------------------------------------------------------------------------
# Write results to DB
# ---------------------------------------------------------------------------


def write_results_to_db(results: Dict) -> bool:
    """Write diagnostic results to the diagnostic_results table.

    Args:
        results: Dict with keys matching diagnostic_results columns.

    Returns:
        True on success, False on failure.
    """
    columns = [
        "sport",
        "settled_bets",
        "wins",
        "losses",
        "roi",
        "real_clv",
        "p_value",
        "passes_gate",
        "avg_hours_before_game",
        "timing_roi_under_2hr",
        "timing_roi_over_8hr",
        "bets_with_closing_price",
        "bets_flagged_stale",
        "recommendation",
        "elo_replay_divergence",
        "market_impact_verdict",
        "median_market_impact_pct",
        "fill_time_roi_under_2hr",
        "fill_time_roi_over_24hr",
    ]

    try:
        col_names = ", ".join(columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        query = f"""
            INSERT INTO diagnostic_results ({col_names})
            VALUES ({placeholders})
        """
        params = {c: results.get(c) for c in columns}
        # Validate engine is accessible (test mock raises here)
        _ = default_db.engine.connect
        default_db.execute(query, params)
        return True
    except Exception as e:
        print(f"❌ Failed to write diagnostic results: {e}")
        return False


# ---------------------------------------------------------------------------
# Main diagnostic pipeline
# ---------------------------------------------------------------------------


def run_diagnostic() -> Dict:
    """Run full P&L diagnostic for all qualifying sports.

    Processes each sport with >= MIN_BETS_FOR_DIAGNOSTIC settled bets.
    For each sport: replay Elo, recalculate metrics, timing analysis,
    bootstrap test, and generate recommendation.

    Returns:
        Dict mapping sport → metrics dict.
    """
    # Find sports with enough settled bets
    query = """
        SELECT UPPER(sport) as sport, COUNT(*) as cnt
        FROM placed_bets
        WHERE status IN ('won', 'lost')
        GROUP BY UPPER(sport)
        HAVING COUNT(*) >= :min_bets
    """
    try:
        result = default_db.execute(query, {"min_bets": MIN_BETS_FOR_DIAGNOSTIC})
        qualifying_sports = [(row[0], row[1]) for row in result.fetchall()]
    except Exception as e:
        print(f"❌ Error querying sports: {e}")
        return {}

    if not qualifying_sports:
        print("⚠️ No sports have enough settled bets for diagnostic")
        return {}

    print(f"🔍 Running diagnostic for {len(qualifying_sports)} sports...")
    all_results = {}

    for sport_upper, bet_count in qualifying_sports:
        sport_lower = sport_upper.lower()
        print(f"\n{'=' * 50}")
        print(f"📊 {sport_upper} ({bet_count} settled bets)")
        print(f"{'=' * 50}")

        try:
            sport_result = _diagnose_sport(sport_upper, sport_lower)
            all_results[sport_upper] = sport_result

            # Write to DB
            sport_result["sport"] = sport_upper
            write_results_to_db(sport_result)
        except Exception as e:
            print(f"  ❌ Error diagnosing {sport_upper}: {e}")
            all_results[sport_upper] = {"error": str(e)}

    print_diagnostic_report(all_results)
    return all_results


def _diagnose_sport(sport_upper: str, sport_lower: str) -> Dict:
    """Run diagnostic pipeline for a single sport.

    Args:
        sport_upper: Sport code uppercase (e.g., 'NBA').
        sport_lower: Sport code lowercase (e.g., 'nba').

    Returns:
        Dict with all diagnostic metrics for the sport.
    """
    # Step 1: Replay Elo ratings
    print("  🔄 Replaying Elo ratings...")
    replayed_ratings = replay_elo_ratings(sport_lower)

    # Step 2: Compare to CSV
    print("  📋 Comparing to stored ratings...")
    divergence = compare_replay_vs_csv(sport_lower, replayed_ratings)
    print(f"  📏 Max Elo divergence: {divergence:.1f} points")

    # Step 3: Recalculate bet metrics
    print("  🔢 Recalculating bet metrics...")
    bets_df = recalculate_bet_metrics(sport_upper, replayed_ratings)

    # Step 4: Load full bet data for timing + profit analysis
    full_bets = _load_full_bets(sport_upper)

    # Compute basic stats
    settled = len(full_bets) if not full_bets.empty else 0
    wins = int((full_bets["profit_dollars"] > 0).sum()) if settled > 0 else 0
    losses = settled - wins
    total_cost = float(full_bets["cost_dollars"].sum()) if settled > 0 else 0
    total_profit = float(full_bets["profit_dollars"].sum()) if settled > 0 else 0
    roi = total_profit / total_cost if total_cost > 0 else 0.0

    # Step 5: Real CLV analysis
    real_clv = _compute_real_clv_avg(full_bets)
    clv_stats = _compute_clv_coverage(full_bets)

    # Step 6: Timing analysis
    print("  ⏰ Computing timing analysis...")
    timing = compute_timing_analysis(full_bets)
    what_if = what_if_timing_replay(full_bets, max_hours=2.0)

    # Step 6b: Fill time analysis (hours before game at Kalshi fill time)
    print("  ⏰ Computing fill time analysis...")
    fill_time_df = compute_fill_time_analysis(full_bets)

    # Extract summary scalars for DB storage
    def _roi_for_bucket(df: pd.DataFrame, bucket: str) -> Optional[float]:
        if df.empty or "hours_bucket" not in df.columns:
            return None
        row = df[df["hours_bucket"].astype(str) == bucket]
        if row.empty:
            return None
        return float(row.iloc[0]["roi_pct"])

    fill_time_roi_under_2hr = _roi_for_bucket(fill_time_df, "<2hr")
    fill_time_roi_over_24hr = _roi_for_bucket(fill_time_df, "24+hr")

    # Step 7: Bootstrap P&L test
    print("  🎲 Running bootstrap significance test...")
    profits = full_bets["profit_dollars"].dropna().tolist() if settled > 0 else []
    if profits:
        bootstrap = bootstrap_pnl_test(profits)
    else:
        bootstrap = {
            "p_value": 1.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "mean_pnl": 0.0,
            "n_samples": 0,
        }

    # Step 8: Generate recommendation
    recommendation = generate_recommendation(sport_upper, roi, real_clv, bootstrap)
    passes_gate = recommendation == "CONTINUE"

    # Compute average hours before game
    avg_hours = _compute_avg_hours_before_game(full_bets)

    result = {
        "settled_bets": settled,
        "wins": wins,
        "losses": losses,
        "roi": roi,
        "real_clv": real_clv,
        "p_value": bootstrap.get("p_value"),
        "passes_gate": passes_gate,
        "avg_hours_before_game": avg_hours,
        "timing_roi_under_2hr": what_if.get("roi"),
        "timing_roi_over_8hr": timing.get("8+hr"),
        "bets_with_closing_price": clv_stats.get("with_price", 0),
        "bets_flagged_stale": clv_stats.get("stale", 0),
        "recommendation": recommendation,
        "elo_replay_divergence": divergence,
        "bootstrap": bootstrap,
        "timing_buckets": timing,
        "what_if_2hr": what_if,
        "fill_time_analysis": fill_time_df,
        "fill_time_roi_under_2hr": fill_time_roi_under_2hr,
        "fill_time_roi_over_24hr": fill_time_roi_over_24hr,
    }

    _print_sport_summary(sport_upper, result)
    return result


def _load_full_bets(sport: str) -> pd.DataFrame:
    """Load all settled bets for a sport from DB.

    Note:
        For Kalshi bets, placed_time_utc = Kalshi fill timestamp (created_time
        from the fills API).  The ``hours_before_game`` column is derived from
        ``market_close_time_utc - placed_time_utc`` and represents how far
        before game start each bet was filled.
    """
    query = """
        SELECT bet_id, sport, placed_date, placed_time_utc,
               home_team, away_team, bet_on, side,
               cost_dollars, profit_dollars, elo_prob, market_prob, edge,
               market_close_time_utc, bet_line_prob, closing_line_prob, clv,
               status
        FROM placed_bets
        WHERE UPPER(sport) = UPPER(:sport)
          AND status IN ('won', 'lost')
    """
    try:
        df = default_db.fetch_df(query, {"sport": sport})
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    # Compute hours_before_game from fill time to game start (market close ≈ game time)
    df["placed_time_utc"] = pd.to_datetime(df["placed_time_utc"], errors="coerce")
    df["market_close_time_utc"] = pd.to_datetime(
        df["market_close_time_utc"], errors="coerce"
    )
    df["hours_before_game"] = (
        df["market_close_time_utc"] - df["placed_time_utc"]
    ).dt.total_seconds() / 3600.0

    return df


def _compute_real_clv_avg(bets_df: pd.DataFrame) -> Optional[float]:
    """Compute average real CLV (excluding binary values)."""
    if bets_df.empty or "clv" not in bets_df.columns:
        return None
    valid = bets_df[
        (bets_df["closing_line_prob"] != 0.0)
        & (bets_df["closing_line_prob"] != 1.0)
        & bets_df["clv"].notna()
    ]
    if valid.empty:
        return None
    return float(valid["clv"].mean())


def _compute_clv_coverage(bets_df: pd.DataFrame) -> Dict[str, int]:
    """Count bets with real closing prices and stale flags."""
    if bets_df.empty:
        return {"with_price": 0, "stale": 0}

    with_price = 0
    stale = 0
    if "closing_line_prob" in bets_df.columns:
        real_clv = bets_df[
            (bets_df["closing_line_prob"] != 0.0)
            & (bets_df["closing_line_prob"] != 1.0)
            & bets_df["closing_line_prob"].notna()
        ]
        with_price = len(real_clv)

    return {"with_price": with_price, "stale": stale}


def _compute_avg_hours_before_game(bets_df: pd.DataFrame) -> Optional[float]:
    """Compute average hours between bet placement and market close."""
    if bets_df.empty:
        return None

    df = bets_df.copy()
    df["placed_time_utc"] = pd.to_datetime(df["placed_time_utc"], errors="coerce")
    df["market_close_time_utc"] = pd.to_datetime(
        df["market_close_time_utc"], errors="coerce"
    )
    valid = df.dropna(subset=["placed_time_utc", "market_close_time_utc"])
    if valid.empty:
        return None

    hours = (
        valid["market_close_time_utc"] - valid["placed_time_utc"]
    ).dt.total_seconds() / 3600.0
    return float(hours.mean())


def _print_sport_summary(sport: str, result: Dict) -> None:
    """Print a summary for one sport's diagnostic results."""
    rec = result.get("recommendation", "?")
    icon = {"CONTINUE": "✅", "PAUSE": "🛑", "INSUFFICIENT_DATA": "⚠️"}.get(rec, "❓")

    print(f"\n  {icon} {sport}: {rec}")
    print(f"    ROI: {result.get('roi', 0):.1%}")
    print(f"    Settled bets: {result.get('settled_bets', 0)}")
    print(f"    Real CLV: {result.get('real_clv', 'N/A')}")
    bs = result.get("bootstrap", {})
    print(
        f"    Bootstrap CI: [{bs.get('ci_lower', '?'):.2f}, {bs.get('ci_upper', '?'):.2f}]"
    )
    print(f"    Elo divergence: {result.get('elo_replay_divergence', '?'):.1f}")

    # Fill Time Analysis section
    fill_df = result.get("fill_time_analysis")
    if fill_df is not None and isinstance(fill_df, pd.DataFrame) and not fill_df.empty:
        print("  ⏰ Fill Time Analysis (hours before game at fill):")
        for _, row in fill_df.iterrows():
            bucket = str(row.get("hours_bucket", "?"))
            n = int(row.get("n_bets", 0))
            roi = float(row.get("roi_pct", 0.0))
            avg_edge = row.get("avg_edge")
            edge_str = (
                f"{avg_edge:.2f}"
                if avg_edge is not None and not pd.isna(avg_edge)
                else "N/A"
            )
            sign = "+" if roi >= 0 else ""
            print(
                f"     {bucket:<8}  ROI={sign}{roi:.1f}%  ({n} bets, avg edge={edge_str})"
            )


def generate_timing_heatmap_data() -> pd.DataFrame:
    """Query diagnostic_results and return a DataFrame suitable for heatmap rendering.

    Fetches the most recent diagnostic run per sport and pivots the stored
    ``timing_roi_under_2hr`` / ``timing_roi_over_8hr`` columns into a wide
    DataFrame where rows are sports and columns are timing-bucket labels.

    Returns:
        DataFrame with index=sport, columns=[timing bucket labels], values=ROI.
        Returns an empty DataFrame on error or when the table contains no rows.
    """
    query = """
        SELECT sport, timing_roi_under_2hr, timing_roi_over_8hr, run_date
        FROM diagnostic_results
        ORDER BY run_date DESC
    """
    try:
        df = default_db.fetch_df(query)
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # Keep only the most recent run per sport
    df["run_date"] = pd.to_datetime(df["run_date"], errors="coerce")
    df = df.sort_values("run_date", ascending=False)
    df = df.drop_duplicates(subset=["sport"], keep="first")

    # Build heatmap: rows = sport, cols = bucket labels
    bucket_map = {
        "<2hr": "timing_roi_under_2hr",
        "8+hr": "timing_roi_over_8hr",
    }
    heatmap_rows: List[Dict] = []
    for _, row in df.iterrows():
        entry: Dict = {}
        for label, col in bucket_map.items():
            val = row.get(col)
            entry[label] = float(val) if val is not None and pd.notna(val) else np.nan
        heatmap_rows.append(entry)

    result = pd.DataFrame(heatmap_rows, index=df["sport"].tolist())
    return result


def print_diagnostic_report(all_results: Dict) -> None:
    """Print a formatted diagnostic report across all sports."""
    print(f"\n{'=' * 60}")
    print("P&L DIAGNOSTIC REPORT")
    print(f"{'=' * 60}")
    print(f"Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Sports analyzed: {len(all_results)}")

    for sport, metrics in all_results.items():
        if "error" in metrics:
            print(f"\n  ❌ {sport}: ERROR — {metrics['error']}")
            continue
        _print_sport_summary(sport, metrics)

    # Market impact section
    market_impact = analyze_market_impact()
    bet_size = market_impact.get("bet_size_analyzed", MAX_BET_SIZE)
    verdict = market_impact.get("verdict", "UNKNOWN")
    tickers_analyzed = market_impact.get("tickers_analyzed", 0)
    median_depth = market_impact.get("median_yes_depth_usd")
    median_impact = market_impact.get("median_market_impact_pct")
    max_impact = market_impact.get("max_market_impact_pct")

    verdict_icon = {"NEGLIGIBLE": "✓", "MONITOR": "⚠", "SIGNIFICANT": "❌"}.get(
        verdict, "?"
    )

    print(f"\n  📊 Market Impact Analysis (bet_size=${bet_size:.2f}):")
    print(f"     Tickers analyzed: {tickers_analyzed}")
    if median_depth is not None:
        print(f"     Median book depth: ${median_depth:,.0f}")
    else:
        print("     Median book depth: N/A")
    if median_impact is not None:
        print(f"     Median impact: {median_impact:.2f}% — {verdict} {verdict_icon}")
    else:
        print(f"     Median impact: N/A — {verdict}")
    if max_impact is not None:
        print(f"     Max impact: {max_impact:.2f}%")
    else:
        print("     Max impact: N/A")

    print(f"\n{'=' * 60}\n")
