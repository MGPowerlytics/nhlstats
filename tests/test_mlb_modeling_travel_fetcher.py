"""Tests for MLB travel features fetcher."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from tests.contracts.helpers import validate_contract_payload

from plugins.mlb_modeling.travel_fetcher import (
    TEAM_INFO,
    VENUE_TIMEZONE,
    _venue_utc_offset,
    _query_previous_game,
    compute_time_zones_crossed,
    compute_travel_direction,
    fetch_travel_features,
    upsert_travel_features,
)
from plugins.mlb_modeling.public_sources import MLBTravelFatigueBuilder


SCHEMAS_ROOT = Path(__file__).resolve().parent / "contracts" / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_ROOT / filename).read_text(encoding="utf-8"))


class _FakeDb:
    """Fake DB that returns canned DataFrames for previous-game queries."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._prev_game_data: dict[str, pd.DataFrame] = {}

    def set_previous_game(self, team: str, game_id: str, game_date: date, venue_team: str) -> None:
        """Set a canned previous-game result for *team*.

        ``venue_team`` is the home_team of the previous game (used to
        resolve the venue name).
        """
        self._prev_game_data[team] = pd.DataFrame([{
            "game_id": game_id,
            "game_date": game_date,
            "home_team": venue_team,
            "away_team": "Some Team" if team == venue_team else team,
        }])

    def set_no_previous_game(self, team: str) -> None:
        """Set empty result for *team* (no previous game found)."""
        self._prev_game_data[team] = pd.DataFrame()

    def fetch_df(self, sql: str, params: dict) -> pd.DataFrame:
        # Capture the SQL call for assertions
        self.calls.append((sql, params))
        team = params.get("team", "")
        return self._prev_game_data.get(team, pd.DataFrame())

    def execute(self, sql: str, params: dict) -> None:
        self.calls.append((sql, params))


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------


def test_team_info_covers_all_30_mlb_teams() -> None:
    """TEAM_INFO contains exactly 30 teams."""
    assert len(TEAM_INFO) == 30


def test_venue_timezone_has_all_team_venues() -> None:
    """VENUE_TIMEZONE covers every team's venue."""
    for team, info in TEAM_INFO.items():
        assert info["venue"] in VENUE_TIMEZONE, (
            f"Venue {info['venue']!r} for {team} missing from VENUE_TIMEZONE"
        )


def test_team_tz_offsets_are_reasonable() -> None:
    """Team IANA timezone strings resolve to known UTC offsets."""
    for team, info in TEAM_INFO.items():
        offset = _venue_utc_offset(info["venue"], date(2026, 6, 1))  # summer / DST
        assert -10 <= offset <= -4, (
            f"{team} venue {info['venue']!r} has unexpected offset {offset}"
        )


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------


def test_utc_offset_est_winter() -> None:
    """EST (winter) should be UTC-5."""
    offset = _venue_utc_offset("Yankee Stadium", date(2026, 1, 15))
    assert offset == -5.0


def test_utc_offset_edt_summer() -> None:
    """EDT (summer) should be UTC-4."""
    offset = _venue_utc_offset("Yankee Stadium", date(2026, 6, 15))
    assert offset == -4.0


def test_utc_offset_pst_winter() -> None:
    """PST (winter) should be UTC-8."""
    offset = _venue_utc_offset("Dodger Stadium", date(2026, 1, 15))
    assert offset == -8.0


def test_utc_offset_pdt_summer() -> None:
    """PDT (summer) should be UTC-7."""
    offset = _venue_utc_offset("Dodger Stadium", date(2026, 6, 15))
    assert offset == -7.0


def test_utc_offset_phoenix_no_dst() -> None:
    """Arizona (America/Phoenix) does not observe DST; always UTC-7."""
    offset_winter = _venue_utc_offset("Chase Field", date(2026, 1, 15))
    offset_summer = _venue_utc_offset("Chase Field", date(2026, 6, 15))
    assert offset_winter == -7.0
    assert offset_summer == -7.0


# ---------------------------------------------------------------------------
# Compute helpers
# ---------------------------------------------------------------------------


def test_compute_time_zones_crossed_same_venue() -> None:
    """No time zones crossed when staying in the same venue."""
    n = compute_time_zones_crossed(
        "Yankee Stadium", "Yankee Stadium", date(2026, 5, 10),
    )
    assert n == 0


def test_compute_time_zones_crossed_none_prev() -> None:
    """No previous game -> 0 time zones crossed."""
    n = compute_time_zones_crossed(None, "Yankee Stadium", date(2026, 5, 10))
    assert n == 0


def test_compute_time_zones_crossed_three_zones() -> None:
    """PST (LA) to EST (NYC) = 3 time zones summer, 3 zones winter."""
    n_summer = compute_time_zones_crossed(
        "Dodger Stadium", "Yankee Stadium", date(2026, 6, 15),
    )
    assert n_summer == 3

    n_winter = compute_time_zones_crossed(
        "Dodger Stadium", "Yankee Stadium", date(2026, 1, 15),
    )
    assert n_winter == 3


def test_compute_time_zones_crossed_one_zone() -> None:
    """CST (Chicago) to EST (NYC) = 1 time zone."""
    n = compute_time_zones_crossed(
        "Wrigley Field", "Yankee Stadium", date(2026, 6, 15),
    )
    assert n == 1


def test_compute_travel_direction_none() -> None:
    """Same venue -> direction is 'none'."""
    d = compute_travel_direction("Yankee Stadium", "Yankee Stadium", date(2026, 5, 10))
    assert d == "none"


def test_compute_travel_direction_east() -> None:
    """LA to NYC -> traveling east."""
    d = compute_travel_direction(
        "Dodger Stadium", "Yankee Stadium", date(2026, 6, 15),
    )
    assert d == "east"


def test_compute_travel_direction_west() -> None:
    """NYC to LA -> traveling west."""
    d = compute_travel_direction(
        "Yankee Stadium", "Dodger Stadium", date(2026, 6, 15),
    )
    assert d == "west"


def test_compute_travel_direction_no_previous() -> None:
    """No previous game -> direction is 'none'."""
    d = compute_travel_direction(None, "Yankee Stadium", date(2026, 5, 10))
    assert d == "none"


# ---------------------------------------------------------------------------
# Previous game query
# ---------------------------------------------------------------------------


def test_query_previous_game_returns_none_when_empty() -> None:
    """_query_previous_game returns None when no previous game exists."""
    db = _FakeDb()
    db.set_no_previous_game("New York Yankees")

    result = _query_previous_game(db, "New York Yankees", date(2026, 4, 1))
    assert result is None


def test_query_previous_game_returns_game_data() -> None:
    """_query_previous_game returns previous game details."""
    db = _FakeDb()
    db.set_previous_game("New York Yankees", "745430", date(2026, 5, 9), "New York Yankees")

    result = _query_previous_game(db, "New York Yankees", date(2026, 5, 10))
    assert result is not None
    assert result["game_id"] == "745430"
    assert result["home_team"] == "New York Yankees"


# ---------------------------------------------------------------------------
# Full travel feature computation
# ---------------------------------------------------------------------------


def test_fetch_travel_features_no_previous_games() -> None:
    """When neither team has a previous game, both get neutral defaults."""
    db = _FakeDb()
    db.set_no_previous_game("New York Yankees")
    db.set_no_previous_game("Los Angeles Dodgers")

    payloads = fetch_travel_features(
        db,
        game_id="745431",
        home_team="New York Yankees",
        away_team="Los Angeles Dodgers",
        game_date=date(2026, 5, 10),
    )

    assert len(payloads) == 2

    # Home team
    assert payloads[0]["team"] == "New York Yankees"
    assert payloads[0]["is_home"] is True
    assert payloads[0]["time_zones_crossed"] == 0
    assert payloads[0]["travel_direction"] == "none"
    assert payloads[0]["circadian_advantage_hours"] == 0.0
    assert payloads[0]["days_rest"] == 2
    assert payloads[0]["previous_game_id"] is None

    # Away team
    assert payloads[1]["team"] == "Los Angeles Dodgers"
    assert payloads[1]["is_home"] is False
    assert payloads[1]["time_zones_crossed"] == 0
    assert payloads[1]["travel_direction"] == "none"
    assert payloads[1]["days_rest"] == 2


def test_fetch_travel_features_with_previous_game_home_team() -> None:
    """Home team with a previous home game: no time zones, 1 day rest."""
    db = _FakeDb()
    # Home team played at home yesterday
    db.set_previous_game("New York Yankees", "745430", date(2026, 5, 9), "New York Yankees")
    db.set_no_previous_game("Los Angeles Dodgers")

    payloads = fetch_travel_features(
        db,
        game_id="745431",
        home_team="New York Yankees",
        away_team="Los Angeles Dodgers",
        game_date=date(2026, 5, 10),
    )

    home = payloads[0]
    assert home["team"] == "New York Yankees"
    assert home["days_rest"] == 0  # played yesterday, today's game = 0 rest days
    assert home["time_zones_crossed"] == 0
    assert home["previous_game_id"] == "745430"
    assert home["previous_venue"] == "Yankee Stadium"


def test_fetch_travel_features_away_team_travels_east() -> None:
    """Away team traveling from PST to EST gets 3 time zones, east direction."""
    db = _FakeDb()
    db.set_no_previous_game("New York Yankees")
    # Away team was at home (LA) yesterday
    db.set_previous_game("Los Angeles Dodgers", "745400", date(2026, 5, 9), "Los Angeles Dodgers")

    payloads = fetch_travel_features(
        db,
        game_id="745431",
        home_team="New York Yankees",
        away_team="Los Angeles Dodgers",
        game_date=date(2026, 6, 15),  # Summer (PDT vs EDT)
    )

    away = payloads[1]
    assert away["time_zones_crossed"] == 3
    assert away["travel_direction"] == "east"
    assert away["previous_venue"] == "Dodger Stadium"
    assert away["previous_game_id"] == "745400"

    # Circadian advantage: previous offset (-7) - current offset (-4) = -3
    # Team traveled east, losing time -> negative circadian advantage
    assert away["circadian_advantage_hours"] < 0


def test_fetch_travel_features_away_team_travels_west() -> None:
    """Away team traveling from EST to PST gets 3 time zones, west direction."""
    db = _FakeDb()
    db.set_no_previous_game("Los Angeles Dodgers")
    # Away team was at home (NYC) yesterday
    db.set_previous_game("New York Yankees", "745400", date(2026, 6, 14), "New York Yankees")

    payloads = fetch_travel_features(
        db,
        game_id="745431",
        home_team="Los Angeles Dodgers",
        away_team="New York Yankees",
        game_date=date(2026, 6, 15),
    )

    away = payloads[1]
    assert away["time_zones_crossed"] == 3
    assert away["travel_direction"] == "west"

    # Circadian advantage: previous offset (-4) - current offset (-7) = +3
    # Team traveled west, gaining time -> positive circadian advantage
    assert away["circadian_advantage_hours"] > 0


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


def test_travel_payload_matches_contract() -> None:
    """Payload from fetch_travel_features validates against the schema."""
    db = _FakeDb()
    db.set_no_previous_game("New York Yankees")
    db.set_no_previous_game("Los Angeles Dodgers")

    payloads = fetch_travel_features(
        db,
        game_id="745431",
        home_team="New York Yankees",
        away_team="Los Angeles Dodgers",
        game_date=date(2026, 5, 10),
    )

    schema = _load_schema("mlb_travel_fatigue_v1.json")
    for p in payloads:
        validate_contract_payload(p, schema)


def test_travel_payload_with_all_fields() -> None:
    """Payload with travel and start time validates."""
    db = _FakeDb()
    db.set_no_previous_game("New York Yankees")
    db.set_no_previous_game("Los Angeles Dodgers")

    payloads = fetch_travel_features(
        db,
        game_id="745431",
        home_team="New York Yankees",
        away_team="Los Angeles Dodgers",
        game_date=date(2026, 5, 10),
        local_start_time="19:05:00",
    )

    for p in payloads:
        assert p["local_start_time"] == "19:05:00"


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def test_upsert_travel_features_executes_sql() -> None:
    """Upsert should call db.execute with INSERT ... ON CONFLICT for each payload."""
    db = _FakeDb()

    payloads = [
        MLBTravelFatigueBuilder.build_payload(
            game_id="745431",
            team="New York Yankees",
            is_home=True,
            time_zones_crossed=0,
            travel_direction="none",
            circadian_advantage_hours=0.0,
            days_rest=2,
        ),
        MLBTravelFatigueBuilder.build_payload(
            game_id="745431",
            team="Los Angeles Dodgers",
            is_home=False,
            time_zones_crossed=0,
            travel_direction="none",
            circadian_advantage_hours=0.0,
            days_rest=2,
        ),
    ]

    result = upsert_travel_features(db, payloads)
    assert result == 2
    assert len(db.calls) == 2

    sql, params = db.calls[0]
    assert "INSERT INTO mlb_travel_features" in sql
    assert "ON CONFLICT" in sql
    assert params["game_id"] == "745431"
    assert params["team"] == "New York Yankees"
    assert params["is_home"] is True


def test_upsert_empty_list() -> None:
    """Upserting an empty list returns 0 and makes no DB calls."""
    db = _FakeDb()
    result = upsert_travel_features(db, [])
    assert result == 0
    assert db.calls == []


# ---------------------------------------------------------------------------
# West-to-east penalty (from builder)
# ---------------------------------------------------------------------------


def test_west_to_east_penalty_applied() -> None:
    """West-to-east penalty is non-positive for eastward travel."""
    payload = MLBTravelFatigueBuilder.build_payload(
        game_id="745431",
        team="Los Angeles Dodgers",
        is_home=False,
        time_zones_crossed=3,
        travel_direction="east",
        circadian_advantage_hours=-3.0,
        days_rest=0,
    )

    assert payload["west_to_east_penalty"] == pytest.approx(-0.045)
    assert payload["travel_direction"] == "east"
