"""MLB advanced feature-engineering utilities.

These helpers intentionally stay pure and deterministic except for the
repository class that persists already-built feature vectors to PostgreSQL.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from hashlib import sha256
from math import exp
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from plugins.mlb_modeling.public_sources import AvailabilityStatus


@dataclass(frozen=True)
class RelieverAppearance:
    """A reliever's recent appearance used for bullpen fatigue features."""

    pitcher_id: str
    appearance_date: date
    pitch_count: int
    avg_velocity: Optional[float] = None
    baseline_velocity: Optional[float] = None


@dataclass(frozen=True)
class BullpenFatigueSummary:
    """Aggregated bullpen fatigue features for one team."""

    pitches_last_3_days: int
    pitches_last_5_days: int
    relievers_over_15_pitches: int
    relievers_over_20_pitches: int
    velocity_penalty: float

    def to_payload(self, prefix: str) -> Dict[str, Any]:
        """Return schema keys using the provided team prefix."""
        return {
            f"{prefix}_pitches_last_3_days": self.pitches_last_3_days,
            f"{prefix}_pitches_last_5_days": self.pitches_last_5_days,
            f"{prefix}_relievers_over_15_pitches": self.relievers_over_15_pitches,
            f"{prefix}_relievers_over_20_pitches": self.relievers_over_20_pitches,
            f"{prefix}_velocity_penalty": self.velocity_penalty,
        }


def calculate_bullpen_fatigue(
    appearances: Iterable[RelieverAppearance],
    as_of_date: date,
) -> BullpenFatigueSummary:
    """Aggregate reliever workload and velocity penalties.

    Relievers incur a small velocity penalty after crossing 15 pitches in an
    appearance and an amplified penalty above 20 pitches, matching the
    requested fatigue thresholds.
    """
    pitches_3 = 0
    pitches_5 = 0
    over_15 = 0
    over_20 = 0
    penalty = 0.0

    for appearance in appearances:
        days_back = (as_of_date - appearance.appearance_date).days
        if days_back < 0 or days_back > 5:
            continue

        pitch_count = max(0, int(appearance.pitch_count))
        pitches_5 += pitch_count
        if days_back <= 3:
            pitches_3 += pitch_count

        if pitch_count > 15:
            over_15 += 1
            penalty -= 0.05
        if pitch_count > 20:
            over_20 += 1
            penalty -= 0.10

        if (
            appearance.avg_velocity is not None
            and appearance.baseline_velocity is not None
            and appearance.avg_velocity < appearance.baseline_velocity
        ):
            penalty -= min(
                0.25, (appearance.baseline_velocity - appearance.avg_velocity) * 0.05
            )

    return BullpenFatigueSummary(
        pitches_last_3_days=pitches_3,
        pitches_last_5_days=pitches_5,
        relievers_over_15_pitches=over_15,
        relievers_over_20_pitches=over_20,
        velocity_penalty=round(penalty, 4),
    )


def get_recent_bullpen_appearances(
    db: Any,
    team: str,
    as_of_date: date,
    days_back: int = 5,
) -> list[RelieverAppearance]:
    """Query ``mlb_player_game_pitching_stats`` for recent reliever appearances.

    Args:
        db: Database manager with an ``execute(sql, params)`` method.
        team: Team abbreviation or name to filter by.
        as_of_date: Reference date; looks back *days_back* days from here.
        days_back: How many days to look back (default 5).

    Returns:
        List of :class:`RelieverAppearance` instances, newest first.
    """
    sql = """
        SELECT
            ps.pitcher_id,
            g.game_date,
            ps.pitch_count,
            ps.avg_velocity
        FROM mlb_player_game_pitching_stats ps
        JOIN mlb_games g ON g.game_id::text = ps.game_id
        WHERE ps.team = :team
          AND ps.is_starter = FALSE
          AND g.game_date >= :start_date
          AND g.game_date <= :as_of_date
        ORDER BY g.game_date DESC
    """
    start_date = as_of_date - timedelta(days=days_back)
    result = db.execute(
        sql,
        {"team": team, "start_date": start_date.isoformat(), "as_of_date": as_of_date.isoformat()},
    )
    appearances: list[RelieverAppearance] = []
    if result:
        for row_obj in result:
            row = dict(row_obj._mapping) if hasattr(row_obj, "_mapping") else dict(row_obj)
            raw_date = row.get("game_date")
            parsed_date: date | None = None
            if isinstance(raw_date, date):
                parsed_date = raw_date
            elif raw_date is not None:
                try:
                    parsed_date = date.fromisoformat(str(raw_date))
                except (ValueError, TypeError):
                    pass
            if parsed_date is None:
                continue
            appearances.append(
                RelieverAppearance(
                    pitcher_id=str(row.get("pitcher_id", "")),
                    appearance_date=parsed_date,
                    pitch_count=int(row.get("pitch_count", 0) or 0),
                    avg_velocity=(
                        float(row["avg_velocity"])
                        if row.get("avg_velocity") is not None
                        else None
                    ),
                )
            )
    return appearances


def recency_weighted_average(
    observations: Sequence[tuple[float, int]],
    half_life_days: float = 14.0,
) -> Optional[float]:
    """Return an exponentially weighted average.

    Args:
        observations: ``(value, age_days)`` pairs where age 0 is most recent.
        half_life_days: Days until an observation receives half the current-day
            weight.

    Returns:
        Weighted average or ``None`` for no observations.
    """
    if not observations:
        return None
    half_life = max(1.0, float(half_life_days))
    weights = [
        exp(-0.6931471805599453 * max(0, age) / half_life) for _, age in observations
    ]
    total_weight = sum(weights)
    if total_weight == 0:
        return None
    return (
        sum(float(value) * weight for (value, _), weight in zip(observations, weights))
        / total_weight
    )


def stable_feature_hash(payload: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 hash for a feature payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def build_advanced_feature_payload(
    *,
    game_id: str,
    home_team: str,
    away_team: str,
    as_of_ts: datetime,
    sabermetrics: Mapping[str, Any],
    plate_discipline: Mapping[str, Any],
    matchup_dynamics: Mapping[str, Any],
    home_bullpen: BullpenFatigueSummary,
    away_bullpen: BullpenFatigueSummary,
    recency: Mapping[str, Any],
    elo: Mapping[str, Any],
    feature_availability: Mapping[str, AvailabilityStatus | str],
    feature_version: str = "v1",
) -> Dict[str, Any]:
    """Build a contract-shaped MLB advanced feature vector."""
    availability = {
        key: value.value if isinstance(value, AvailabilityStatus) else str(value)
        for key, value in feature_availability.items()
    }
    payload: Dict[str, Any] = {
        "schema_version": "v1",
        "sport": "MLB",
        "payload_kind": "advanced_feature_vector",
        "game_id": game_id,
        "home_team": home_team,
        "away_team": away_team,
        "as_of_ts": as_of_ts.isoformat(),
        "feature_version": feature_version,
        "feature_hash": "pending",
        "feature_availability": availability,
        "elo": dict(elo),
        "sabermetrics": dict(sabermetrics),
        "plate_discipline": dict(plate_discipline),
        "matchup_dynamics": dict(matchup_dynamics),
        "bullpen_fatigue": {
            **home_bullpen.to_payload("home"),
            **away_bullpen.to_payload("away"),
        },
        "recency": dict(recency),
    }
    payload["feature_hash"] = stable_feature_hash(
        {key: value for key, value in payload.items() if key != "feature_hash"}
    )
    return payload


class MLBFeatureRepository:
    """Persist built MLB matchup feature vectors to PostgreSQL."""

    def __init__(self, db: Any) -> None:
        """Initialize with a DBManager-compatible object."""
        self.db = db

    def upsert_matchup_features(self, payload: Mapping[str, Any], side: str) -> None:
        """Upsert a feature payload into ``mlb_matchup_features``."""
        sql = """
            INSERT INTO mlb_matchup_features
                (game_id, side, home_team, away_team, as_of_ts, feature_version,
                 feature_hash, feature_vector, feature_availability, abstention_reasons)
            VALUES
                (:game_id, :side, :home_team, :away_team, :as_of_ts, :feature_version,
                 :feature_hash, CAST(:feature_vector AS JSONB),
                 CAST(:feature_availability AS JSONB),
                 CAST(:abstention_reasons AS JSONB))
            ON CONFLICT (game_id, side, feature_version) DO UPDATE SET
                as_of_ts = EXCLUDED.as_of_ts,
                feature_hash = EXCLUDED.feature_hash,
                feature_vector = EXCLUDED.feature_vector,
                feature_availability = EXCLUDED.feature_availability,
                abstention_reasons = EXCLUDED.abstention_reasons
        """
        abstentions = [
            key
            for key, value in dict(payload["feature_availability"]).items()
            if value == AvailabilityStatus.ABSTAIN_REQUIRED.value
        ]
        self.db.execute(
            sql,
            {
                "game_id": payload["game_id"],
                "side": side,
                "home_team": payload["home_team"],
                "away_team": payload["away_team"],
                "as_of_ts": payload["as_of_ts"],
                "feature_version": payload["feature_version"],
                "feature_hash": payload["feature_hash"],
                "feature_vector": json.dumps(payload, sort_keys=True),
                "feature_availability": json.dumps(
                    payload["feature_availability"], sort_keys=True
                ),
                "abstention_reasons": json.dumps(abstentions),
            },
        )
