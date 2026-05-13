"""Public/free-source adapters for MLB predictive-modeling inputs.

The production target is public-source-first. Signals that are usually locked
behind licensed feeds (for example ticket-vs-money percentages, catcher
framing, or umpire zone values) are represented with explicit availability and
abstention metadata instead of being silently coerced to neutral values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Any, Dict, Mapping, Optional


class AvailabilityStatus(str, Enum):
    """Availability states shared by MLB public-source adapters."""

    AVAILABLE = "available"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    ABSTAIN_REQUIRED = "abstain_required"


@dataclass(frozen=True)
class DataSourceSnapshot:
    """A timestamped payload plus provenance and availability metadata."""

    source: str
    status: AvailabilityStatus
    observed_at: Optional[datetime] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None

    @property
    def abstain_required(self) -> bool:
        """Return True when downstream high-confidence paths must abstain."""
        return self.status == AvailabilityStatus.ABSTAIN_REQUIRED

    def availability_value(self) -> str:
        """Return the schema-compatible availability string."""
        return self.status.value


class UnavailablePublicSignalAdapter:
    """Adapter for requested signals that public/free sources cannot provide."""

    def __init__(
        self,
        signal_name: str,
        reason: str,
        abstain_required: bool = False,
    ) -> None:
        """Create an unavailable-signal adapter.

        Args:
            signal_name: Human-readable signal identifier.
            reason: Explanation stored in provenance.
            abstain_required: Whether missing this signal should block
                high-confidence betting paths.
        """
        self.signal_name = signal_name
        self.reason = reason
        self.abstain_required = abstain_required

    def fetch(self) -> DataSourceSnapshot:
        """Return an explicit unavailable/abstain snapshot."""
        status = (
            AvailabilityStatus.ABSTAIN_REQUIRED
            if self.abstain_required
            else AvailabilityStatus.UNAVAILABLE
        )
        return DataSourceSnapshot(
            source=self.signal_name,
            status=status,
            payload={self.signal_name: None},
            reason=self.reason,
        )


class MLBEnvironmentFeatureBuilder:
    """Build public-source MLB environment feature payloads."""

    TEMPERATURE_BASELINE_F = 60.0
    FEET_PER_TEN_DEGREES_F = 4.5

    @classmethod
    def temperature_hit_distance_adjustment(
        cls,
        temperature_f: Optional[float],
    ) -> Optional[float]:
        """Return hit-distance adjustment from temperature.

        The requested transform is +4.5 feet for every +10°F relative to a
        60°F baseline. ``None`` remains ``None`` so missing weather can be
        surfaced by availability/provenance gates.
        """
        if temperature_f is None:
            return None
        return ((float(temperature_f) - cls.TEMPERATURE_BASELINE_F) / 10.0) * (
            cls.FEET_PER_TEN_DEGREES_F
        )

    @classmethod
    def build_payload(
        cls,
        *,
        game_id: str,
        game_date: str,
        venue: str,
        park_factors: Mapping[str, float],
        weather: Mapping[str, Optional[float]],
        source: str,
        observed_at: Optional[datetime] = None,
        availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
    ) -> Dict[str, Any]:
        """Build a payload matching ``mlb_environment_features_v1.json``."""
        temperature = weather.get("temperature_f")
        observed_value = observed_at.isoformat() if observed_at else None
        return {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "environment_features",
            "game_id": game_id,
            "game_date": game_date,
            "venue": venue,
            "park_factors": {
                "runs": float(park_factors["runs"]),
                "home_runs": float(park_factors["home_runs"]),
                "doubles_triples": float(park_factors["doubles_triples"]),
                "singles": float(park_factors["singles"]),
            },
            "weather": {
                "temperature_f": temperature,
                "humidity_pct": weather.get("humidity_pct"),
                "wind_speed_mph": weather.get("wind_speed_mph"),
                "wind_direction_degrees": weather.get("wind_direction_degrees"),
                "altitude_ft": weather.get("altitude_ft"),
            },
            "hit_distance_adjustment_ft": cls.temperature_hit_distance_adjustment(
                temperature
            ),
            "source": source,
            "observed_at": observed_value,
            "feature_version": "v1",
            "availability": availability.value,
        }


class MLBTravelFatigueBuilder:
    """Build schedule-derived travel and circadian feature payloads."""

    WEST_TO_EAST_PENALTY_PER_TZ = -0.015

    @classmethod
    def west_to_east_penalty(
        cls,
        time_zones_crossed: int,
        travel_direction: str,
    ) -> float:
        """Return a non-positive penalty for west-to-east travel."""
        zones = max(0, int(time_zones_crossed))
        if travel_direction.lower() != "east":
            return 0.0
        return cls.WEST_TO_EAST_PENALTY_PER_TZ * zones

    @staticmethod
    def circadian_advantage_win_expectation(hours: float) -> Optional[float]:
        """Approximate win expectation for a 3-hour circadian advantage.

        The user-provided benchmark is that teams with a 3-hour circadian
        advantage win about 60.6% of the time. This helper scales linearly near
        zero and clips to a conservative range for use as a feature, not a final
        prediction.
        """
        if hours == 0:
            return 0.5
        scaled = 0.5 + (float(hours) / 3.0) * 0.106
        return max(0.35, min(0.65, scaled))

    @classmethod
    def build_payload(
        cls,
        *,
        game_id: str,
        team: str,
        is_home: bool,
        time_zones_crossed: int,
        travel_direction: str,
        circadian_advantage_hours: float,
        days_rest: int,
        source: str = "schedule_derived",
        previous_game_id: Optional[str] = None,
        previous_game_date: Optional[str] = None,
        previous_venue: Optional[str] = None,
        local_start_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a payload matching ``mlb_travel_fatigue_v1.json``."""
        return {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "travel_fatigue_features",
            "game_id": game_id,
            "team": team,
            "is_home": bool(is_home),
            "previous_game_id": previous_game_id,
            "previous_game_date": previous_game_date,
            "previous_venue": previous_venue,
            "time_zones_crossed": max(0, int(time_zones_crossed)),
            "travel_direction": travel_direction,
            "west_to_east_penalty": cls.west_to_east_penalty(
                time_zones_crossed, travel_direction
            ),
            "circadian_advantage_hours": float(circadian_advantage_hours),
            "local_start_time": local_start_time,
            "days_rest": max(0, min(7, int(days_rest))),
            "source": source,
            "feature_version": "v1",
        }


class MLBMarketSignalBuilder:
    """Build public-source market signal payloads and sharp-money transforms."""

    @staticmethod
    def compute_pro_edge(
        ticket_pct: Optional[float],
        money_pct: Optional[float],
    ) -> Optional[float]:
        """Return money percentage minus ticket percentage when both exist."""
        if ticket_pct is None or money_pct is None:
            return None
        return float(money_pct) - float(ticket_pct)

    @staticmethod
    def detect_reverse_line_movement(
        *,
        public_side: Optional[str],
        outcome_name: str,
        line_move: Optional[float],
    ) -> bool:
        """Detect movement against the public majority.

        ``line_move`` is positive when the outcome became more expensive. If
        the public majority is on the same outcome but the outcome gets cheaper,
        or the public majority is against it while it gets more expensive, this
        flags reverse line movement.
        """
        if public_side is None or line_move is None or line_move == 0:
            return False
        public_matches_outcome = public_side.lower() == outcome_name.lower()
        return (public_matches_outcome and line_move < 0) or (
            not public_matches_outcome and line_move > 0
        )

    @classmethod
    def build_payload(
        cls,
        *,
        game_id: str,
        ticker: str,
        outcome_name: str,
        snapshot_at: datetime,
        market_prob: float,
        source: str,
        ticket_pct: Optional[float] = None,
        money_pct: Optional[float] = None,
        line_move: Optional[float] = None,
        public_side: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a payload matching ``mlb_market_signals_v1.json``."""
        pro_edge = cls.compute_pro_edge(ticket_pct, money_pct)
        availability = (
            AvailabilityStatus.AVAILABLE
            if ticket_pct is not None and money_pct is not None
            else AvailabilityStatus.UNAVAILABLE
        )
        snapshot_key = snapshot_at.strftime("%Y%m%dT%H%M%SZ")
        signal_id_source = f"{game_id}|{ticker}|{outcome_name}|{snapshot_key}"
        market_signal_id = sha256(signal_id_source.encode("utf-8")).hexdigest()[:24]
        return {
            "schema_version": "v1",
            "sport": "MLB",
            "payload_kind": "market_signals",
            "market_signal_id": market_signal_id,
            "game_id": game_id,
            "ticker": ticker,
            "outcome_name": outcome_name,
            "snapshot_at": snapshot_at.isoformat(),
            "market_prob": float(market_prob),
            "ticket_pct": ticket_pct,
            "money_pct": money_pct,
            "pro_edge": pro_edge,
            "line_move": line_move,
            "reverse_line_movement": cls.detect_reverse_line_movement(
                public_side=public_side,
                outcome_name=outcome_name,
                line_move=line_move,
            ),
            "source": source,
            "feature_version": "v1",
            "availability": availability.value,
        }
