"""Advanced tennis feature engineering for pre-match predictive models.

The builder in this module turns historical ATP/WTA match rows into honest
pre-match features. It intentionally stays model-agnostic so Elo, tree-based
ensembles, graph models, and Bayesian layers can consume the same feature
vector without duplicating data hygiene rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import math
import re
from typing import Any, Iterable

import pandas as pd


_DEFAULT_SURFACE_CORRELATIONS: dict[str, dict[str, float]] = {
    "Hard": {
        "Hard": 1.00,
        "Grass": 0.72,
        "Clay": 0.48,
        "Carpet": 0.68,
        "Unknown": 0.55,
    },
    "Grass": {
        "Grass": 1.00,
        "Hard": 0.72,
        "Clay": 0.38,
        "Carpet": 0.70,
        "Unknown": 0.50,
    },
    "Clay": {
        "Clay": 1.00,
        "Hard": 0.48,
        "Grass": 0.38,
        "Carpet": 0.42,
        "Unknown": 0.50,
    },
    "Carpet": {
        "Carpet": 1.00,
        "Hard": 0.68,
        "Grass": 0.70,
        "Clay": 0.42,
        "Unknown": 0.55,
    },
    "Unknown": {
        "Unknown": 1.00,
        "Hard": 0.55,
        "Grass": 0.50,
        "Clay": 0.50,
        "Carpet": 0.55,
    },
}

_RETIREMENT_PATTERN = re.compile(
    r"\b(RET|RETIRED|W/O|WALKOVER|DEF|ABD|DEF\.)\b", re.IGNORECASE
)
_SURFACE_ALIASES = {
    "HARD": "Hard",
    "CLAY": "Clay",
    "GRASS": "Grass",
    "CARPET": "Carpet",
}


@dataclass
class TennisFeatureConfig:
    """Configuration for tennis feature generation.

    Args:
        one_year_weight: Exponential recency factor; a match 365.25 days old
            receives this weight before surface adjustment.
        fatigue_window_days: Lookback window for short-term physical fatigue.
        fatigue_half_life_days: Half-life used inside the fatigue window.
        min_certainty_matches: Match count where the data-certainty count
            component saturates.
        surface_correlations: Transferability matrix between court surfaces.
    """

    one_year_weight: float = 0.80
    fatigue_window_days: float = 3.0
    fatigue_half_life_days: float = 1.0
    min_certainty_matches: int = 10
    surface_correlations: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            source: dict(targets)
            for source, targets in _DEFAULT_SURFACE_CORRELATIONS.items()
        }
    )


@dataclass
class TennisMatchupFeatures:
    """Pre-match feature vector for one tennis matchup."""

    schema_version: str
    sport: str
    payload_kind: str
    tour: str
    player_a: str
    player_b: str
    target_surface: str
    match_count_a: int
    match_count_b: int
    weighted_match_count_a: float
    weighted_match_count_b: float
    win_rate_a: float
    win_rate_b: float
    common_opponent_count: int
    common_opponent_win_rate_diff: float
    direct_match_count: int
    direct_win_rate_a: float
    intransitivity_complexity: float
    serve_win_pct_a: float
    serve_win_pct_b: float
    return_win_pct_a: float
    return_win_pct_b: float
    serveadv_a: float
    serveadv_b: float
    complete_a: float
    complete_b: float
    fatigue_a: float
    fatigue_b: float
    fatigue_diff: float
    retired_a: int
    retired_b: int
    age_30_a: float
    age_30_b: float
    rank_a: float | None
    rank_b: float | None
    rank_diff: float | None
    data_certainty: float

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable feature payload."""
        return asdict(self)


@dataclass(frozen=True)
class _PlayerMatch:
    """Normalized row representing one player's view of a historical match."""

    date: pd.Timestamp
    tour: str
    surface: str
    player: str
    opponent: str
    won: bool
    games_played: int
    retired: bool
    serve_win_pct: float | None
    return_win_pct: float | None
    rank: float | None
    age: float | None


class TennisFeatureBuilder:
    """Build honest pre-match features from historical tennis match rows."""

    def __init__(self, config: TennisFeatureConfig | None = None) -> None:
        """Initialize the feature builder.

        Args:
            config: Optional feature-engineering configuration.
        """
        self.config = config or TennisFeatureConfig()

    def time_weight(self, age_days: float) -> float:
        """Return exponential time-decay weight for an observation age."""
        non_negative_age = max(float(age_days), 0.0)
        return float(self.config.one_year_weight ** (non_negative_age / 365.25))

    def surface_weight(
        self, historical_surface: str | None, target_surface: str | None
    ) -> float:
        """Return transfer weight from historical surface to target surface."""
        source = _normalize_surface(historical_surface)
        target = _normalize_surface(target_surface)
        return float(
            self.config.surface_correlations.get(source, {}).get(
                target, self.config.surface_correlations["Unknown"]["Unknown"]
            )
        )

    def build_matchup_features(
        self,
        history: pd.DataFrame,
        player_a: str,
        player_b: str,
        as_of_date: str | datetime | pd.Timestamp,
        surface: str,
        tour: str = "ATP",
    ) -> TennisMatchupFeatures:
        """Build pre-match features for ``player_a`` against ``player_b``.

        Args:
            history: Historical match DataFrame. Supports tennis-data.co.uk
                names (``Winner``/``Loser``) and Sackmann-style names
                (``winner_name``/``loser_name``).
            player_a: First player in the prediction matchup.
            player_b: Second player in the prediction matchup.
            as_of_date: Cutoff date; matches on/after this date are excluded.
            surface: Target court surface.
            tour: ATP or WTA.

        Returns:
            Structured feature vector for the matchup.
        """
        cutoff = pd.Timestamp(as_of_date)
        target_surface = _normalize_surface(surface)
        normalized_tour = str(tour).upper()
        player_rows = self._normalize_history(history)
        eligible_rows = [
            row
            for row in player_rows
            if row.tour == normalized_tour and row.date < cutoff
        ]

        rows_a = [row for row in eligible_rows if row.player == player_a]
        rows_b = [row for row in eligible_rows if row.player == player_b]

        profile_a = self._build_player_profile(rows_a, cutoff, target_surface)
        profile_b = self._build_player_profile(rows_b, cutoff, target_surface)
        common = self._build_common_opponent_features(
            rows_a, rows_b, cutoff, target_surface
        )
        direct = self._build_direct_features(rows_a, player_b, cutoff, target_surface)

        fatigue_a = self._fatigue(rows_a, cutoff)
        fatigue_b = self._fatigue(rows_b, cutoff)
        retired_a = self._retired_last_match(rows_a, cutoff)
        retired_b = self._retired_last_match(rows_b, cutoff)
        data_certainty = self._data_certainty(profile_a, profile_b, common)

        return TennisMatchupFeatures(
            schema_version="v1",
            sport="TENNIS",
            payload_kind="feature_vector",
            tour=normalized_tour,
            player_a=player_a,
            player_b=player_b,
            target_surface=target_surface,
            match_count_a=int(profile_a["match_count"]),
            match_count_b=int(profile_b["match_count"]),
            weighted_match_count_a=float(profile_a["weighted_match_count"]),
            weighted_match_count_b=float(profile_b["weighted_match_count"]),
            win_rate_a=float(profile_a["win_rate"]),
            win_rate_b=float(profile_b["win_rate"]),
            common_opponent_count=int(common["count"]),
            common_opponent_win_rate_diff=float(common["win_rate_diff"]),
            direct_match_count=int(direct["count"]),
            direct_win_rate_a=float(direct["win_rate_a"]),
            intransitivity_complexity=float(
                self._intransitivity_complexity(common, direct)
            ),
            serve_win_pct_a=float(profile_a["serve_win_pct"]),
            serve_win_pct_b=float(profile_b["serve_win_pct"]),
            return_win_pct_a=float(profile_a["return_win_pct"]),
            return_win_pct_b=float(profile_b["return_win_pct"]),
            serveadv_a=float(profile_a["serve_win_pct"] - profile_b["return_win_pct"]),
            serveadv_b=float(profile_b["serve_win_pct"] - profile_a["return_win_pct"]),
            complete_a=float(profile_a["serve_win_pct"] * profile_a["return_win_pct"]),
            complete_b=float(profile_b["serve_win_pct"] * profile_b["return_win_pct"]),
            fatigue_a=fatigue_a,
            fatigue_b=fatigue_b,
            fatigue_diff=float(fatigue_a - fatigue_b),
            retired_a=retired_a,
            retired_b=retired_b,
            age_30_a=float(profile_a["age_30"]),
            age_30_b=float(profile_b["age_30"]),
            rank_a=profile_a["rank"],
            rank_b=profile_b["rank"],
            rank_diff=_rank_diff(profile_a["rank"], profile_b["rank"]),
            data_certainty=data_certainty,
        )

    def _normalize_history(self, history: pd.DataFrame) -> list[_PlayerMatch]:
        """Normalize wide match rows into player-match rows."""
        rows: list[_PlayerMatch] = []
        if history.empty:
            return rows

        for _, row in history.iterrows():
            match_date = _parse_date(
                _first_present(row, ("date", "Date", "game_date", "tourney_date"))
            )
            winner = _clean_player_name(
                _first_present(row, ("winner", "Winner", "winner_name"))
            )
            loser = _clean_player_name(
                _first_present(row, ("loser", "Loser", "loser_name"))
            )
            if match_date is None or not winner or not loser:
                continue

            tour = str(_first_present(row, ("tour", "Tour"), "ATP")).upper()
            surface = _normalize_surface(_first_present(row, ("surface", "Surface")))
            score = str(_first_present(row, ("score", "Score"), ""))
            winner_games, loser_games = _parse_score_games(score)
            games_played = winner_games + loser_games
            retired = _is_retirement_score(score)

            rows.append(
                _PlayerMatch(
                    date=match_date,
                    tour=tour,
                    surface=surface,
                    player=winner,
                    opponent=loser,
                    won=True,
                    games_played=games_played,
                    retired=False,
                    serve_win_pct=_serve_win_pct(row, "w"),
                    return_win_pct=_return_win_pct(row, "w"),
                    rank=_safe_float(
                        _first_present(row, ("winner_rank", "w_rank", "WRank"))
                    ),
                    age=_safe_float(
                        _first_present(row, ("winner_age", "w_age", "WAge"))
                    ),
                )
            )
            rows.append(
                _PlayerMatch(
                    date=match_date,
                    tour=tour,
                    surface=surface,
                    player=loser,
                    opponent=winner,
                    won=False,
                    games_played=games_played,
                    retired=retired,
                    serve_win_pct=_serve_win_pct(row, "l"),
                    return_win_pct=_return_win_pct(row, "l"),
                    rank=_safe_float(
                        _first_present(row, ("loser_rank", "l_rank", "LRank"))
                    ),
                    age=_safe_float(
                        _first_present(row, ("loser_age", "l_age", "LAge"))
                    ),
                )
            )
        return rows

    def _build_player_profile(
        self,
        rows: list[_PlayerMatch],
        cutoff: pd.Timestamp,
        target_surface: str,
    ) -> dict[str, Any]:
        """Compute weighted player strength, age, and rank profile."""
        weights = [
            self._observation_weight(row, cutoff, target_surface) for row in rows
        ]
        return {
            "match_count": len(rows),
            "weighted_match_count": float(sum(weights)),
            "win_rate": _weighted_mean(
                [1.0 if row.won else 0.0 for row in rows], weights, default=0.5
            ),
            "serve_win_pct": _weighted_mean(
                [row.serve_win_pct for row in rows], weights, default=0.5
            ),
            "return_win_pct": _weighted_mean(
                [row.return_win_pct for row in rows], weights, default=0.5
            ),
            "rank": _weighted_mean_or_none([row.rank for row in rows], weights),
            "age_30": _weighted_mean(
                [abs(row.age - 30.0) if row.age is not None else None for row in rows],
                weights,
                default=0.0,
            ),
            "stat_coverage": _coverage(
                [row.serve_win_pct for row in rows]
                + [row.return_win_pct for row in rows]
            ),
        }

    def _build_common_opponent_features(
        self,
        rows_a: list[_PlayerMatch],
        rows_b: list[_PlayerMatch],
        cutoff: pd.Timestamp,
        target_surface: str,
    ) -> dict[str, float | int]:
        """Compute common-opponent adjusted matchup features."""
        opponents_a = {row.opponent for row in rows_a}
        opponents_b = {row.opponent for row in rows_b}
        common_opponents = sorted(opponents_a & opponents_b)

        diffs: list[float] = []
        weights: list[float] = []
        indirect_a: list[float] = []
        indirect_b: list[float] = []

        for opponent in common_opponents:
            a_rows = [row for row in rows_a if row.opponent == opponent]
            b_rows = [row for row in rows_b if row.opponent == opponent]
            a_rate, a_weight = self._weighted_record(a_rows, cutoff, target_surface)
            b_rate, b_weight = self._weighted_record(b_rows, cutoff, target_surface)
            opponent_weight = min(a_weight, b_weight)
            if opponent_weight <= 0:
                continue
            diffs.append(a_rate - b_rate)
            weights.append(opponent_weight)
            indirect_a.append(a_rate * (1.0 - b_rate))
            indirect_b.append(b_rate * (1.0 - a_rate))

        return {
            "count": len(weights),
            "win_rate_diff": _weighted_mean(diffs, weights, default=0.0),
            "indirect_a_support": _weighted_mean(indirect_a, weights, default=0.0),
            "indirect_b_support": _weighted_mean(indirect_b, weights, default=0.0),
        }

    def _build_direct_features(
        self,
        rows_a: list[_PlayerMatch],
        opponent: str,
        cutoff: pd.Timestamp,
        target_surface: str,
    ) -> dict[str, float | int]:
        """Compute direct head-to-head features from player A's perspective."""
        direct_rows = [row for row in rows_a if row.opponent == opponent]
        direct_rate, direct_weight = self._weighted_record(
            direct_rows, cutoff, target_surface
        )
        return {
            "count": len(direct_rows),
            "weight": direct_weight,
            "win_rate_a": direct_rate if direct_rows else 0.5,
        }

    def _weighted_record(
        self,
        rows: list[_PlayerMatch],
        cutoff: pd.Timestamp,
        target_surface: str,
    ) -> tuple[float, float]:
        """Return weighted win rate and total weight for a set of rows."""
        weights = [
            self._observation_weight(row, cutoff, target_surface) for row in rows
        ]
        rate = _weighted_mean([1.0 if row.won else 0.0 for row in rows], weights, 0.5)
        return rate, float(sum(weights))

    def _observation_weight(
        self,
        row: _PlayerMatch,
        cutoff: pd.Timestamp,
        target_surface: str,
    ) -> float:
        """Combine recency and surface-transfer weights for one row."""
        age_days = (cutoff - row.date).total_seconds() / 86400.0
        return self.time_weight(age_days) * self.surface_weight(
            row.surface, target_surface
        )

    def _intransitivity_complexity(
        self,
        common: dict[str, float | int],
        direct: dict[str, float | int],
    ) -> float:
        """Estimate matchup intransitivity from indirect and direct evidence."""
        a_support = float(common["indirect_a_support"])
        b_support = float(common["indirect_b_support"])
        support_total = a_support + b_support
        if support_total <= 0:
            return 0.0

        indirect_a_preference = a_support / support_total
        if int(direct["count"]) > 0:
            direct_a = float(direct["win_rate_a"])
            return _clip01(abs(indirect_a_preference - direct_a))

        ambiguity = 1.0 - abs(indirect_a_preference - 0.5) * 2.0
        return _clip01(ambiguity)

    def _fatigue(self, rows: list[_PlayerMatch], cutoff: pd.Timestamp) -> float:
        """Return recent games-played fatigue with exponential intrawindow decay."""
        total = 0.0
        half_life = max(self.config.fatigue_half_life_days, 1e-6)
        for row in rows:
            age_days = (cutoff - row.date).total_seconds() / 86400.0
            if 0.0 <= age_days <= self.config.fatigue_window_days:
                decay = math.exp(-math.log(2.0) * age_days / half_life)
                total += float(row.games_played) * decay
        return total

    @staticmethod
    def _retired_last_match(rows: list[_PlayerMatch], cutoff: pd.Timestamp) -> int:
        """Return 1 when the player's most recent match ended in retirement."""
        prior_rows = [row for row in rows if row.date < cutoff]
        if not prior_rows:
            return 0
        latest = max(prior_rows, key=lambda row: row.date)
        return int(latest.retired)

    def _data_certainty(
        self,
        profile_a: dict[str, Any],
        profile_b: dict[str, Any],
        common: dict[str, float | int],
    ) -> float:
        """Score whether the matchup has enough historical signal to bet."""
        min_matches = min(int(profile_a["match_count"]), int(profile_b["match_count"]))
        count_score = min(min_matches / max(self.config.min_certainty_matches, 1), 1.0)
        common_score = min(int(common["count"]) / 3.0, 1.0)
        stat_score = (
            float(profile_a["stat_coverage"]) + float(profile_b["stat_coverage"])
        ) / 2.0
        return _clip01(0.50 * count_score + 0.30 * common_score + 0.20 * stat_score)


def _first_present(row: pd.Series, names: Iterable[str], default: Any = None) -> Any:
    """Return the first non-null value for any candidate column name."""
    for name in names:
        if name in row.index:
            value = row.get(name)
            if not _is_missing(value):
                return value
    return default


def _parse_date(value: Any) -> pd.Timestamp | None:
    """Parse a date value into a pandas Timestamp."""
    if _is_missing(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def _clean_player_name(value: Any) -> str:
    """Normalize a raw player-name cell into a stripped string."""
    if _is_missing(value):
        return ""
    return str(value).strip()


def _normalize_surface(value: Any) -> str:
    """Normalize raw surface labels to the configured surface keys."""
    if _is_missing(value):
        return "Unknown"
    normalized = str(value).strip().upper()
    return _SURFACE_ALIASES.get(normalized, "Unknown")


def _is_missing(value: Any) -> bool:
    """Return True for pandas/null-style missing values."""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _safe_float(value: Any) -> float | None:
    """Convert a value to float, returning None for missing/invalid values."""
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_ratio(numerator: Any, denominator: Any) -> float | None:
    """Return numerator / denominator when both are valid and denominator > 0."""
    num = _safe_float(numerator)
    den = _safe_float(denominator)
    if num is None or den is None or den <= 0:
        return None
    return _clip01(num / den)


def _serve_win_pct(row: pd.Series, prefix: str) -> float | None:
    """Extract service-point win percentage for winner or loser."""
    direct_names = (
        ("winner_serve_win_pct", "w_serve_win_pct", "serve_win_pct")
        if prefix == "w"
        else ("loser_serve_win_pct", "l_serve_win_pct", "serve_win_pct")
    )
    direct = _safe_float(_first_present(row, direct_names))
    if direct is not None:
        return _clip01(direct)

    service_points = _first_present(row, (f"{prefix}_svpt",))
    first_won = _first_present(row, (f"{prefix}_1stWon", f"{prefix}_1st_won"))
    second_won = _first_present(row, (f"{prefix}_2ndWon", f"{prefix}_2nd_won"))
    first = _safe_float(first_won)
    second = _safe_float(second_won)
    if first is None or second is None:
        return None
    return _safe_ratio(first + second, service_points)


def _return_win_pct(row: pd.Series, prefix: str) -> float | None:
    """Extract return-point win percentage for winner or loser."""
    direct_names = (
        ("winner_return_win_pct", "w_return_win_pct", "return_win_pct")
        if prefix == "w"
        else ("loser_return_win_pct", "l_return_win_pct", "return_win_pct")
    )
    direct = _safe_float(_first_present(row, direct_names))
    if direct is not None:
        return _clip01(direct)

    opponent_prefix = "l" if prefix == "w" else "w"
    opponent_svpt = _safe_float(_first_present(row, (f"{opponent_prefix}_svpt",)))
    opponent_first = _safe_float(
        _first_present(row, (f"{opponent_prefix}_1stWon", f"{opponent_prefix}_1st_won"))
    )
    opponent_second = _safe_float(
        _first_present(row, (f"{opponent_prefix}_2ndWon", f"{opponent_prefix}_2nd_won"))
    )
    if opponent_svpt is None or opponent_first is None or opponent_second is None:
        return None
    return _safe_ratio(opponent_svpt - opponent_first - opponent_second, opponent_svpt)


def _parse_score_games(score: str) -> tuple[int, int]:
    """Parse a tennis score into winner and loser games won."""
    if not score:
        return 0, 0
    clean = _RETIREMENT_PATTERN.sub("", str(score).strip())
    clean = re.sub(r"\(\d+\)", "", clean)
    winner_games = 0
    loser_games = 0
    for part in clean.split():
        if "-" not in part:
            continue
        left_str, right_str = part.split("-", 1)
        try:
            winner_games += int(left_str)
            loser_games += int(right_str)
        except ValueError:
            continue
    return winner_games, loser_games


def _is_retirement_score(score: str) -> bool:
    """Return True when a score contains a retirement or walkover marker."""
    return bool(score and _RETIREMENT_PATTERN.search(str(score)))


def _weighted_mean(
    values: Iterable[float | int | bool | None],
    weights: Iterable[float],
    default: float,
) -> float:
    """Return weighted mean over non-null values."""
    numerator = 0.0
    denominator = 0.0
    for value, weight in zip(values, weights):
        if value is None or weight <= 0:
            continue
        numerator += float(value) * float(weight)
        denominator += float(weight)
    if denominator <= 0:
        return default
    return numerator / denominator


def _weighted_mean_or_none(
    values: Iterable[float | None],
    weights: Iterable[float],
) -> float | None:
    """Return weighted mean or None when no non-null values are present."""
    sentinel = -1.0
    result = _weighted_mean(values, weights, default=sentinel)
    return None if result == sentinel else result


def _coverage(values: Iterable[Any]) -> float:
    """Return fraction of non-null values in an iterable."""
    values_list = list(values)
    if not values_list:
        return 0.0
    available = sum(0 if value is None else 1 for value in values_list)
    return available / len(values_list)


def _rank_diff(rank_a: float | None, rank_b: float | None) -> float | None:
    """Return rank_a - rank_b when both ranks are available."""
    if rank_a is None or rank_b is None:
        return None
    return float(rank_a - rank_b)


def _clip01(value: float) -> float:
    """Clamp a float to [0, 1]."""
    return max(0.0, min(1.0, float(value)))
