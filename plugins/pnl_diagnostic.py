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
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sqlalchemy import text

from plugins.constants import (
    BOOTSTRAP_CONFIDENCE_LEVEL,
    BOOTSTRAP_N_ITERATIONS,
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
    ]

    try:
        col_names = ", ".join(columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        query = f"""
            INSERT INTO diagnostic_results ({col_names})
            VALUES ({placeholders})
        """
        params = {c: results.get(c) for c in columns}
        with default_db.engine.connect() as conn:
            conn.execute(text(query), params)
            conn.commit()
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
    }

    _print_sport_summary(sport_upper, result)
    return result


def _load_full_bets(sport: str) -> pd.DataFrame:
    """Load all settled bets for a sport from DB."""
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
        return default_db.fetch_df(query, {"sport": sport})
    except Exception:
        return pd.DataFrame()


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

    print(f"\n{'=' * 60}\n")
