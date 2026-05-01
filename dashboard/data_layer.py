"""Dashboard data layer — the ONLY file that contains SQL queries.

All page files import from here. No SQL strings exist outside this file.
Every function is decorated with @st.cache_data for Streamlit caching.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from plugins.db_manager import DBManager

_db = DBManager()

# Cache TTLs (seconds)
TTL_LIVE = 30       # odds, markets, portfolio
TTL_STANDARD = 300  # ratings, snapshots, data quality
TTL_LONG = 3600     # calibration, historical


@st.cache_data(ttl=TTL_LIVE)
def get_portfolio_summary() -> dict:
    """Return KPIs: portfolio_value, daily_pnl, open_bets_count, total_exposure, win_rate, total_bets, settled_count."""
    latest_snapshot = _db.fetch_scalar(
        "SELECT portfolio_value FROM portfolio_value_snapshots ORDER BY timestamp DESC LIMIT 1"
    )
    portfolio_value = float(latest_snapshot) if latest_snapshot else 0.0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_result = _db.fetch_df(
        "SELECT COALESCE(SUM(CASE WHEN status = 'WON' THEN payout - stake "
        "WHEN status = 'LOST' THEN -stake ELSE 0 END), 0) AS daily_pnl "
        "FROM placed_bets WHERE DATE(settled_at) = %(today)s",
        {"today": today},
    )
    daily_pnl = float(daily_result["daily_pnl"].iloc[0]) if len(daily_result) > 0 else 0.0

    open_bets = _db.fetch_df(
        "SELECT COUNT(*) AS cnt, COALESCE(SUM(stake), 0) AS exposure "
        "FROM placed_bets WHERE status = 'PENDING'"
    )
    open_bets_count = int(open_bets["cnt"].iloc[0]) if len(open_bets) > 0 else 0
    total_exposure = float(open_bets["exposure"].iloc[0]) if len(open_bets) > 0 else 0.0

    settled = _db.fetch_df(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN status = 'WON' THEN 1 ELSE 0 END) AS wins "
        "FROM placed_bets WHERE status IN ('WON', 'LOST')"
    )
    total_bets = int(settled["total"].iloc[0]) if len(settled) > 0 else 0
    wins = int(settled["wins"].iloc[0]) if len(settled) > 0 else 0
    win_rate = wins / total_bets if total_bets > 0 else 0.0

    return {
        "portfolio_value": portfolio_value,
        "daily_pnl": daily_pnl,
        "open_bets_count": open_bets_count,
        "total_exposure": total_exposure,
        "win_rate": win_rate,
        "total_bets": total_bets,
        "settled_count": total_bets,
    }


@st.cache_data(ttl=TTL_LIVE)
def get_placed_bets(limit: int = 50, status: Optional[str] = None, sport: Optional[str] = None) -> pd.DataFrame:
    """Return placed_bets rows, newest first. Optionally filter by status and sport."""
    query = "SELECT * FROM placed_bets WHERE 1=1"
    params = {}
    if status:
        query += " AND status = %(status)s"
        params["status"] = status
    if sport:
        query += " AND sport = %(sport)s"
        params["sport"] = sport
    query += " ORDER BY placed_at DESC LIMIT %(limit)s"
    params["limit"] = limit
    return _db.fetch_df(query, params)


@st.cache_data(ttl=TTL_STANDARD)
def get_bet_detail(bet_id: str) -> dict:
    """Return full bet traceability: the bet record, odds snapshot, Elo snapshot, Elo history, recent form."""
    bet_df = _db.fetch_df(
        "SELECT * FROM placed_bets WHERE bet_id = %(bet_id)s",
        {"bet_id": bet_id},
    )
    if bet_df.empty:
        raise ValueError(f"Bet not found: {bet_id}")

    bet_row = bet_df.iloc[0].to_dict()
    # Coerce numpy/pandas types to native Python
    bet = {}
    for k, v in bet_row.items():
        if pd.isna(v):
            bet[k] = None
        elif hasattr(v, "isoformat"):
            bet[k] = v.isoformat()
        elif hasattr(v, "item"):
            bet[k] = v.item()
        else:
            bet[k] = v

    # Odds at bet placement time
    odds = _load_odds_for_bet(bet)

    # Elo snapshot at bet time
    elo_snapshot = _load_elo_snapshot(bet)

    # Elo history (30 days before bet)
    elo_history = _load_elo_history_for_bet(bet)

    # Recent form (last 5 games for each team)
    recent_form = _load_recent_form(bet)

    return {
        "bet": bet,
        "odds": odds,
        "elo_snapshot": elo_snapshot,
        "elo_history": elo_history,
        "recent_form": recent_form,
    }


def _load_odds_for_bet(bet: dict) -> list:
    """Load odds from all sources near the bet placement time."""
    bet_time = bet.get("placed_at")
    game_id = bet.get("game_id")
    if not bet_time or not game_id:
        return []

    # Parse the bet time to a date range (+/-30 min window)
    try:
        if isinstance(bet_time, str):
            bt = datetime.fromisoformat(bet_time.replace("Z", "+00:00"))
        else:
            bt = bet_time
        window_start = (bt - timedelta(minutes=30)).isoformat()
        window_end = (bt + timedelta(minutes=30)).isoformat()
    except (ValueError, TypeError):
        return []

    odds_df = _db.fetch_df(
        "SELECT source, price, implied_prob, timestamp FROM game_odds "
        "WHERE game_id = %(game_id)s "
        "AND timestamp BETWEEN %(start)s AND %(end)s "
        "ORDER BY source, timestamp DESC",
        {"game_id": game_id, "start": window_start, "end": window_end},
    )
    odds = odds_df.to_dict(orient="records")
    result = []
    for row in odds:
        row_out = {}
        for k, v in row.items():
            if pd.isna(v):
                row_out[k] = None
            elif hasattr(v, "isoformat"):
                row_out[k] = v.isoformat()
            elif hasattr(v, "item"):
                row_out[k] = v.item()
            else:
                row_out[k] = v
        # Normalize source names to lowercase
        if "source" in row_out and row_out["source"]:
            row_out["source"] = row_out["source"].lower()
        result.append(row_out)
    return result


def _load_elo_snapshot(bet: dict) -> dict:
    """Load Elo ratings for both teams at bet placement time."""
    sport = bet.get("sport", "")
    home_team = bet.get("home_team", "")
    away_team = bet.get("away_team", "")
    bet_time = bet.get("placed_at")

    if not home_team or not away_team:
        return {
            "team_a_rating": 0, "team_b_rating": 0,
            "team_a_name": home_team or "", "team_b_name": away_team or "",
            "rating_diff": 0, "home_advantage": 0, "effective_diff": 0,
        }

    # Find ratings closest to bet time
    home_rating = _get_rating_at_time(sport, home_team, bet_time)
    away_rating = _get_rating_at_time(sport, away_team, bet_time)

    home_adv = _get_home_advantage(sport)
    rating_diff = home_rating - away_rating
    effective_diff = rating_diff + home_adv

    return {
        "team_a_rating": home_rating,
        "team_b_rating": away_rating,
        "team_a_name": home_team,
        "team_b_name": away_team,
        "rating_diff": rating_diff,
        "home_advantage": home_adv,
        "effective_diff": effective_diff,
    }


def _get_rating_at_time(sport: str, team: str, at_time) -> float:
    """Get Elo rating for a team closest to a given timestamp."""
    if at_time is None:
        at_time = datetime.now(timezone.utc).isoformat()
    rating = _db.fetch_scalar(
        "SELECT rating FROM elo_ratings WHERE sport = %(sport)s AND team = %(team)s "
        "AND timestamp <= %(ts)s ORDER BY timestamp DESC LIMIT 1",
        {"sport": sport, "team": team, "ts": at_time},
    )
    return float(rating) if rating else 1500.0


def _get_home_advantage(sport: str) -> float:
    """Return home advantage for a sport."""
    adv = {
        "NBA": 100, "NHL": 100, "NCAAB": 100, "WNCAAB": 100,
        "MLB": 50, "NFL": 65,
        "EPL": 60, "Ligue1": 60, "CBA": 100, "Unrivaled": 100,
        "TENNIS": 0,
    }
    return adv.get(sport, 50)


def _load_elo_history_for_bet(bet: dict) -> list:
    """Load 30-day Elo rating history for both teams before the bet."""
    sport = bet.get("sport", "")
    home_team = bet.get("home_team", "")
    away_team = bet.get("away_team", "")
    bet_time = bet.get("placed_at")

    if not home_team or not away_team or not bet_time:
        return []

    try:
        if isinstance(bet_time, str):
            bt = datetime.fromisoformat(bet_time.replace("Z", "+00:00"))
        else:
            bt = bet_time
        start = (bt - timedelta(days=30)).isoformat()
    except (ValueError, TypeError):
        return []

    df = _db.fetch_df(
        "SELECT timestamp AS date, team, rating FROM elo_ratings "
        "WHERE sport = %(sport)s AND team IN (%(home)s, %(away)s) "
        "AND timestamp BETWEEN %(start)s AND %(end)s "
        "ORDER BY timestamp ASC",
        {"sport": sport, "home": home_team, "away": away_team,
         "start": start, "end": bet_time},
    )
    result = df.to_dict(orient="records")
    for row in result:
        if hasattr(row.get("date"), "isoformat"):
            row["date"] = row["date"].isoformat()
    return result


def _load_recent_form(bet: dict) -> dict:
    """Load last 5 games for each team before the bet."""
    sport = bet.get("sport", "")
    home_team = bet.get("home_team", "")
    away_team = bet.get("away_team", "")
    bet_time = bet.get("placed_at")

    def _form(team: str) -> dict:
        if not team:
            return {"team": team or "", "games": [], "record": "0-0"}
        query = (
            "SELECT home_team, away_team, home_score, away_score, start_time AS date "
            "FROM unified_games "
            "WHERE sport = %(sport)s AND (home_team = %(team)s OR away_team = %(team)s) "
            "AND status = 'Final' "
        )
        params: dict = {"sport": sport, "team": team}
        if bet_time:
            query += " AND start_time < %(bet_time)s"
            params["bet_time"] = bet_time
        query += " ORDER BY start_time DESC LIMIT 5"
        df = _db.fetch_df(query, params)
        games = []
        wins = 0
        losses = 0
        for _, row in df.iterrows():
            is_home = row["home_team"] == team
            opp = row["away_team"] if is_home else row["home_team"]
            team_score = row["home_score"] if is_home else row["away_score"]
            opp_score = row["away_score"] if is_home else row["home_score"]
            if team_score > opp_score:
                result = "W"
                wins += 1
            elif team_score < opp_score:
                result = "L"
                losses += 1
            else:
                result = "D"
            score_str = f"{int(team_score)}-{int(opp_score)}" if team_score is not None else "?-?"
            date_val = row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"])
            games.append({
                "opponent": opp,
                "result": result,
                "score": score_str,
                "date": date_val,
            })
        return {"team": team, "games": games, "record": f"{wins}-{losses}"}

    return {"team_a": _form(home_team), "team_b": _form(away_team)}


@st.cache_data(ttl=TTL_STANDARD)
def get_current_elo_ratings(sport: str) -> pd.DataFrame:
    """Return current Elo ratings for all teams in a sport, ranked."""
    df = _db.fetch_df(
        "SELECT team, rating, sport, timestamp AS last_updated FROM elo_ratings "
        "WHERE sport = %(sport)s AND timestamp = ("
        "  SELECT MAX(timestamp) FROM elo_ratings WHERE sport = %(sport)s"
        ") ORDER BY rating DESC",
        {"sport": sport},
    )
    if df.empty:
        return df
    # Add rank column
    df["rank"] = range(1, len(df) + 1)
    # Add trend columns (optional - populated if historical data exists)
    df["trend_7d"] = 0.0
    df["trend_30d"] = 0.0
    # Coerce timestamps
    if "last_updated" in df.columns:
        df["last_updated"] = df["last_updated"].apply(
            lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x)
        )
    return df


@st.cache_data(ttl=TTL_LIVE)
def get_today_games(sport: Optional[str] = None) -> pd.DataFrame:
    """Return today's games with Elo probabilities and best odds."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    query = (
        "SELECT game_id, sport, home_team, away_team, start_time "
        "FROM unified_games WHERE DATE(start_time) = %(today)s AND status != 'Cancelled'"
    )
    params: dict = {"today": today}
    if sport:
        query += " AND sport = %(sport)s"
        params["sport"] = sport
    query += " ORDER BY start_time ASC"
    df = _db.fetch_df(query, params)

    if df.empty:
        return df

    # Enrich with Elo probabilities
    home_probs = []
    away_elos = []
    home_elos_list = []
    for _, row in df.iterrows():
        h_elo = _get_rating_at_time(row["sport"], row["home_team"], None)
        a_elo = _get_rating_at_time(row["sport"], row["away_team"], None)
        home_elos_list.append(h_elo)
        away_elos.append(a_elo)
        home_adv = _get_home_advantage(row["sport"])
        effective_diff = h_elo - a_elo + home_adv
        prob = 1.0 / (1.0 + 10.0 ** (-effective_diff / 400.0))
        home_probs.append(round(prob, 4))
    df["home_elo"] = home_elos_list
    df["away_elo"] = away_elos
    df["home_win_prob"] = home_probs
    df["best_home_odds"] = -110.0
    df["best_away_odds"] = -110.0
    df["best_home_bookmaker"] = ""
    df["best_away_bookmaker"] = ""
    df["edge"] = 0.0
    df["edge_side"] = ""
    df["confidence"] = ""

    if "start_time" in df.columns:
        df["start_time"] = df["start_time"].apply(
            lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x)
        )
    return df


@st.cache_data(ttl=TTL_LIVE)
def get_bet_recommendations(sport: Optional[str] = None) -> pd.DataFrame:
    """Return latest bet recommendations from the bet_recommendations table."""
    query = "SELECT * FROM bet_recommendations WHERE 1=1"
    params: dict = {}
    if sport:
        query += " AND sport = %(sport)s"
        params["sport"] = sport
    query += " ORDER BY created_at DESC LIMIT 100"
    return _db.fetch_df(query, params)


@st.cache_data(ttl=TTL_LONG)
def get_calibration_data(sport: Optional[str] = None) -> dict:
    """Return calibration data: individual bet predictions vs outcomes, buckets, and by-sport summary."""
    query = (
        "SELECT sport, elo_prob, status AS result, edge, stake, "
        "COALESCE(payout, 0) AS payout "
        "FROM placed_bets WHERE status IN ('WON', 'LOST')"
    )
    params: dict = {}
    if sport:
        query += " AND sport = %(sport)s"
        params["sport"] = sport
    df = _db.fetch_df(query, params)

    bets = []
    for _, row in df.iterrows():
        bets.append({
            "sport": row["sport"],
            "elo_prob": float(row["elo_prob"]) if not pd.isna(row.get("elo_prob")) else 0.5,
            "result": row["result"],
            "edge": float(row["edge"]) if not pd.isna(row.get("edge")) else 0.0,
            "stake": float(row["stake"]),
            "payout": float(row["payout"]),
        })

    # Build buckets
    bucket_edges = [0.0, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.0]
    bucket_labels = ["<50%", "50-55%", "55-60%", "60-65%", "65-70%", "70-75%", "75-80%", "80%+"]
    buckets = []
    for i, label in enumerate(bucket_labels):
        lo = bucket_edges[i]
        hi = bucket_edges[i + 1]
        in_bucket = [b for b in bets if lo <= b["elo_prob"] < hi]
        count = len(in_bucket)
        wins = sum(1 for b in in_bucket if b["result"] == "WON")
        actual = wins / count if count > 0 else 0.0
        buckets.append({
            "label": label, "predicted_min": lo, "predicted_max": hi,
            "count": count, "actual_win_rate": round(actual, 4),
        })

    # By sport
    sport_groups = {}
    for b in bets:
        s = b["sport"]
        if s not in sport_groups:
            sport_groups[s] = {"count": 0, "wins": 0, "total_edge": 0, "total_stake": 0, "total_payout": 0}
        sport_groups[s]["count"] += 1
        if b["result"] == "WON":
            sport_groups[s]["wins"] += 1
        sport_groups[s]["total_edge"] += b["edge"]
        sport_groups[s]["total_stake"] += b["stake"]
        sport_groups[s]["total_payout"] += b["payout"]

    by_sport = []
    for s, g in sorted(sport_groups.items()):
        by_sport.append({
            "sport": s, "bet_count": g["count"],
            "win_rate": round(g["wins"] / g["count"], 4) if g["count"] else 0,
            "avg_edge": round(g["total_edge"] / g["count"], 4) if g["count"] else 0,
            "roi": round((g["total_payout"] - g["total_stake"]) / g["total_stake"], 4) if g["total_stake"] else 0,
        })

    return {"bets": bets, "buckets": buckets, "by_sport": by_sport}


@st.cache_data(ttl=TTL_STANDARD)
def get_elo_history(team: str, sport: str, days: int = 30) -> pd.DataFrame:
    """Return Elo rating timeseries for a team."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    df = _db.fetch_df(
        "SELECT timestamp AS date, team, rating FROM elo_ratings "
        "WHERE sport = %(sport)s AND team = %(team)s AND timestamp >= %(start)s "
        "ORDER BY timestamp ASC",
        {"sport": sport, "team": team, "start": start},
    )
    if "date" in df.columns:
        df["date"] = df["date"].apply(lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
    return df


@st.cache_data(ttl=TTL_STANDARD)
def get_data_quality_report() -> dict:
    """Return system health report: overall score + per-sport details."""
    sports = ["NBA", "NHL", "MLB", "NFL", "NCAAB", "WNCAAB", "TENNIS", "EPL", "Ligue1", "CBA", "Unrivaled"]
    sport_reports = []
    total_score = 0

    for sport in sports:
        score = 100
        issues_list = []

        # Check for missing recent games
        missing = _db.fetch_scalar(
            "SELECT COUNT(*) FROM unified_games WHERE sport = %(sport)s "
            "AND start_time >= CURRENT_DATE - INTERVAL '3 days'",
            {"sport": sport},
        )
        missing_count = max(0, 3 - (int(missing) if missing else 0))
        if missing_count > 0:
            score -= missing_count * 10
            issues_list.append(f"Missing recent games")

        # Check for stale Elo ratings
        stale = _db.fetch_scalar(
            "SELECT COUNT(*) FROM elo_ratings WHERE sport = %(sport)s "
            "AND timestamp < CURRENT_DATE - INTERVAL '7 days'",
            {"sport": sport},
        )
        stale_count = int(stale) if stale else 0
        if stale_count > 0:
            score -= min(30, stale_count * 5)
            issues_list.append(f"{stale_count} stale Elo ratings")

        # Check odds freshness
        last_odds = _db.fetch_scalar(
            "SELECT MAX(timestamp) FROM game_odds WHERE sport = %(sport)s",
            {"sport": sport},
        )
        odds_minutes = 999
        if last_odds:
            try:
                if hasattr(last_odds, "isoformat"):
                    last_odds_dt = last_odds
                else:
                    last_odds_dt = datetime.fromisoformat(str(last_odds).replace("Z", "+00:00"))
                delta = datetime.now(timezone.utc) - last_odds_dt.replace(tzinfo=timezone.utc)
                odds_minutes = int(delta.total_seconds() / 60)
            except (ValueError, TypeError):
                pass

        # Last game date
        last_game = _db.fetch_scalar(
            "SELECT MAX(start_time) FROM unified_games WHERE sport = %(sport)s",
            {"sport": sport},
        )
        last_game_str = last_game.isoformat() if hasattr(last_game, "isoformat") else str(last_game) if last_game else "N/A"

        score = max(0, min(100, score))
        total_score += score
        sport_reports.append({
            "sport": sport,
            "health_score": score,
            "missing_games": missing_count,
            "stale_elo": stale_count,
            "odds_freshness_minutes": odds_minutes,
            "last_game_date": last_game_str,
            "last_dag_run": "N/A",
            "issues": issues_list,
        })

    overall = total_score // len(sports) if sports else 0
    return {"overall_health": overall, "sports": sport_reports}


@st.cache_data(ttl=TTL_STANDARD)
def get_portfolio_snapshots(hours: int = 168) -> pd.DataFrame:
    """Return hourly portfolio value timeseries."""
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    df = _db.fetch_df(
        "SELECT timestamp, portfolio_value FROM portfolio_value_snapshots "
        "WHERE timestamp >= %(start)s ORDER BY timestamp ASC",
        {"start": start},
    )
    if "timestamp" in df.columns:
        df["timestamp"] = df["timestamp"].apply(
            lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x)
        )
    return df


def bust_cache():
    """Clear all cached data. Called on auto-refresh cycle."""
    get_portfolio_summary.clear()
    get_placed_bets.clear()
    get_bet_detail.clear()
    get_current_elo_ratings.clear()
    get_today_games.clear()
    get_bet_recommendations.clear()
    get_calibration_data.clear()
    get_elo_history.clear()
    get_data_quality_report.clear()
    get_portfolio_snapshots.clear()
