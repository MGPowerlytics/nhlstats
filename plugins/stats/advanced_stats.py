"""
Advanced derived statistics for all supported sports.

All public functions accept raw counting stats and return a single float (or
dict for compound metrics).  Implementations are stubbed — each raises
:exc:`NotImplementedError` until Wave 2 fills in the formula bodies.

Formula references
------------------
Basketball:
  eFG%  = (FGM + 0.5 * FG3M) / FGA
  TS%   = PTS / (2 * (FGA + 0.44 * FTA))
  Pace  = 48 * (Poss / MIN) * (Team_MP / 5)  [simplified: Poss / (MIN/48)]
  ORtg  = 100 * PTS / Poss
  DRtg  = 100 * OppPTS / OppPoss

Hockey:
  Corsi% = (SF + BF + MF) / (SF + BF + MF + SA + BA + MA) * 100

Baseball:
  wOBA  = weighted sum of offensive events (weights vary by season)
  FIP   = (13*HR + 3*(BB+HBP) - 2*K) / IP + FIP_constant

Soccer:
  PPDA  = opp_passes_allowed / defensive_actions

NFL:
  EPA aggregate — computed from play-by-play data via nfl_data_py;
  returns per-game and per-play summaries.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Basketball
# ---------------------------------------------------------------------------


def compute_basketball_efg(fgm: float, fg3m: float, fga: float) -> float:
    """Compute effective field-goal percentage (eFG%).

    Adjusts raw FG% to give extra weight to three-pointers because they are
    worth 50 % more than two-pointers.

    Formula::

        eFG% = (FGM + 0.5 * FG3M) / FGA

    Args:
        fgm: Total field goals made (includes 2-pt and 3-pt).
        fg3m: Three-point field goals made.
        fga: Total field goal attempts.

    Returns:
        eFG% as a decimal in [0, 1].
    """
    if fga <= 0:
        return 0.0
    return (fgm + 0.5 * fg3m) / fga


def compute_basketball_ts(pts: float, fga: float, fta: float) -> float:
    """Compute true shooting percentage (TS%).

    Accounts for field goals, three-pointers (implicitly), and free throws.

    Formula::

        TS% = PTS / (2 * (FGA + 0.44 * FTA))

    Args:
        pts: Points scored.
        fga: Field goal attempts.
        fta: Free throw attempts.

    Returns:
        TS% as a decimal in [0, 1].
    """
    denom = 2 * (fga + 0.44 * fta)
    return pts / denom if denom > 0 else 0.0


def compute_basketball_pace(possessions: float, minutes: float) -> float:
    """Estimate team pace (possessions per 48 minutes).

    Formula::

        Pace = 48 * possessions / minutes

    Args:
        possessions: Estimated team possessions for the game.
        minutes: Total team minutes played (typically 240 for a 48-min game).

    Returns:
        Pace as possessions per 48 minutes.
    """
    return 48.0 * possessions / minutes if minutes > 0 else 0.0


def estimate_basketball_possessions(
    fga: float, fta: float, orb: float, tov: float
) -> float:
    """Estimate team possessions using the Dean Oliver formula.

    Formula::

        Poss ≈ FGA - ORB + TOV + 0.44 * FTA

    Args:
        fga: Field goal attempts.
        fta: Free throw attempts.
        orb: Offensive rebounds.
        tov: Turnovers.

    Returns:
        Estimated possessions as a float.
    """
    return fga - orb + tov + 0.44 * fta


def compute_basketball_ortg(pts: float, possessions: float) -> float:
    """Compute offensive rating (ORtg) — points scored per 100 possessions.

    Formula::

        ORtg = 100 * PTS / Poss

    Args:
        pts: Points scored by the team.
        possessions: Team possessions.

    Returns:
        ORtg as points per 100 possessions.
    """
    return 100.0 * pts / possessions if possessions > 0 else 0.0


def compute_basketball_drtg(opp_pts: float, opp_possessions: float) -> float:
    """Compute defensive rating (DRtg) — opponent points per 100 possessions.

    Formula::

        DRtg = 100 * OppPTS / OppPoss

    A lower DRtg indicates a better defence.

    Args:
        opp_pts: Points allowed to the opponent.
        opp_possessions: Opponent possessions.

    Returns:
        DRtg as opponent points per 100 possessions.
    """
    return 100.0 * opp_pts / opp_possessions if opp_possessions > 0 else 0.0


# ---------------------------------------------------------------------------
# Hockey
# ---------------------------------------------------------------------------


def compute_hockey_corsi(
    shots_for: float,
    shots_against: float,
    blocks_for: float,
    blocks_against: float,
    missed_for: float,
    missed_against: float,
) -> float:
    """Compute Corsi percentage (CF%).

    Corsi is the ratio of all shot attempts (on target, blocked, missed) for a
    team to the total shot attempts in the game while that team is on the ice,
    typically at even strength.

    Formula::

        CF% = (SF + BF + MF) / (SF + BF + MF + SA + BA + MA) * 100

    where SF=shots on goal for, BF=blocks for, MF=missed shots for,
    SA/BA/MA are the corresponding against totals.

    Args:
        shots_for: Shots on goal for.
        shots_against: Shots on goal against.
        blocks_for: Shot attempts blocked by the opposition (count for team).
        blocks_against: Shot attempts by the opposition that were blocked.
        missed_for: Missed shots for (wide/over net).
        missed_against: Missed shots against.

    Returns:
        CF% in [0, 100].
    """
    cf = shots_for + blocks_against + missed_for
    ca = shots_against + blocks_for + missed_against
    total = cf + ca
    return cf / total if total > 0 else 0.5


# ---------------------------------------------------------------------------
# Baseball
# ---------------------------------------------------------------------------


def compute_baseball_woba(
    weights: dict[str, float],
    stats: dict[str, float],
) -> float:
    """Compute weighted on-base average (wOBA).

    wOBA assigns a linear weight to each offensive event based on its run
    value.  Weights are season-specific and published annually by FanGraphs.

    Formula (simplified)::

        wOBA = (w_BB*uBB + w_HBP*HBP + w_1B*1B + w_2B*2B + w_3B*3B + w_HR*HR)
               / (AB + BB - IBB + SF + HBP)

    Args:
        weights: Mapping from event key (``"BB"``, ``"HBP"``, ``"1B"``,
            ``"2B"``, ``"3B"``, ``"HR"``…) to linear weight float.
        stats: Mapping from event key to counting-stat value for the player /
            team.

    Returns:
        wOBA as a decimal.
    """
    pa_denom = (
        stats.get("ab", 0)
        + stats.get("bb", 0)
        + stats.get("sf", 0)
        + stats.get("hbp", 0)
    )
    if pa_denom == 0:
        return 0.0
    num = sum(weights.get(k, 0) * stats.get(k, 0) for k in weights)
    return num / pa_denom


def compute_baseball_fip(
    hr: float,
    bb: float,
    hbp: float,
    k: float,
    ip: float,
    fip_constant: float,
) -> float:
    """Compute Fielding Independent Pitching (FIP).

    FIP estimates what a pitcher's ERA *should* have been based only on
    outcomes the pitcher fully controls (strikeouts, walks, HBP, home runs).

    Formula::

        FIP = (13*HR + 3*(BB + HBP) - 2*K) / IP + FIP_constant

    The FIP constant is calibrated so that league-average FIP equals
    league-average ERA for that season (typically ~3.10 in MLB).

    Args:
        hr: Home runs allowed.
        bb: Unintentional walks issued.
        hbp: Hit batters.
        k: Strikeouts recorded.
        ip: Innings pitched (decimal, e.g. 6.2 = 6⅔ innings).
        fip_constant: Season-specific constant from FanGraphs.

    Returns:
        FIP as a float on the ERA scale.
    """
    if ip <= 0:
        return 0.0
    return (13 * hr + 3 * (bb + hbp) - 2 * k) / ip + fip_constant


# ---------------------------------------------------------------------------
# Soccer
# ---------------------------------------------------------------------------


def compute_soccer_ppda(
    opp_passes: float,
    defensive_actions: float,
) -> float:
    """Compute Passes Allowed Per Defensive Action (PPDA).

    PPDA measures pressing intensity.  A lower value indicates more aggressive
    pressing.  Typically computed in the opponent's own half.

    Formula::

        PPDA = opp_passes / defensive_actions

    where defensive_actions = tackles + interceptions (+ fouls in some
    implementations).

    Args:
        opp_passes: Opposition passes allowed in the pressing zone.
        defensive_actions: Team defensive actions (tackles + interceptions).

    Returns:
        PPDA as a float.  Lower is more intense pressing.
    """
    if defensive_actions == 0:
        return 0.0
    return opp_passes / defensive_actions


# ---------------------------------------------------------------------------
# NFL
# ---------------------------------------------------------------------------


def compute_nfl_epa_aggregate(pbp_df: "pd.DataFrame") -> dict[str, float]:
    """Aggregate Expected Points Added (EPA) metrics from play-by-play data.

    The expected return shape is::

        {
            "epa_per_play_off": float,   # offensive EPA per play
            "epa_per_play_def": float,   # defensive EPA per play (neg = good)
            "total_epa_off": float,
            "total_epa_def": float,
            "pass_epa_off": float,
            "rush_epa_off": float,
        }

    Args:
        pbp_df: Play-by-play :class:`~pandas.DataFrame` as returned by
            ``nfl_data_py.import_pbp_data()``.  Expected columns include at
            minimum ``"epa"``, ``"posteam"``, ``"defteam"``, ``"play_type"``.

    Returns:
        Dict of aggregated EPA metrics keyed by metric name.
    """
    empty = {
        "epa_offense_mean": 0.0,
        "epa_defense_mean": 0.0,
        "success_rate": 0.0,
    }
    if pbp_df is None or len(pbp_df) == 0:
        return empty
    if "epa" not in pbp_df.columns:
        return empty
    return {
        "epa_offense_mean": float(pbp_df["epa"].mean()),
        "epa_defense_mean": float(-pbp_df["epa"].mean()),
        "success_rate": float((pbp_df["epa"] > 0).mean()),
    }
