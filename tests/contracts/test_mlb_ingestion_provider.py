"""Wave-3 provider-red contract tests for MLB schedule ingestion.

Exercises the real ``MLBGames`` HTTP path (statsapi.mlb.com) and the
production ``NHLDatabaseLoader._load_mlb_schedule`` row builder against the
frozen Wave-2 schemas:

* ``mlb_schedule_ingestion_v1`` (raw provider-input boundary)
* ``mlb_mlb_games_row_v1``     (persisted ``mlb_games`` row)
* ``mlb_unified_game_row_v1``  (persisted ``unified_games`` MLB subset)

DB row provider coverage is folded in here because the loader writes to both
``mlb_games`` and ``unified_games`` from the same input record, so verifying
both rows in one test exercises the full producer code path on a single
schedule game.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from plugins.db_loader import NHLDatabaseLoader
from plugins.mlb_games import MLBGames
from tests.contracts.fixtures.mlb_schedule_samples import (
    build_mlb_games_row,
    build_mlb_schedule_game,
    build_mlb_unified_games_row,
)
from tests.contracts.helpers import (
    find_execute_params,
    serialize_contract_payload,
    validate_contract_payload,
)


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def _make_loader(tmp_path: Path) -> NHLDatabaseLoader:
    db = MagicMock()
    loader = NHLDatabaseLoader(db_path=str(tmp_path / "unused.db"), db_manager=db)
    return loader


def _write_schedule_file(tmp_path: Path, games: list[dict]) -> Path:
    payload = {"dates": [{"games": games}]}
    schedule_path = tmp_path / "schedule_2024-04-21.json"
    schedule_path.write_text(json.dumps(payload), encoding="utf-8")
    return schedule_path


# ---------------------------------------------------------------------------
# Provider HTTP boundary: MLBGames.get_schedule_for_date
# ---------------------------------------------------------------------------


def test_mlb_games_schedule_response_satisfies_ingestion_contract(
    tmp_path: Path, monkeypatch
) -> None:
    """The real MLBGames request shape must yield records matching the schema."""
    canonical_game = build_mlb_schedule_game()

    captured_calls: list[tuple[str, dict]] = []

    def fake_make_request(self, url, params=None, **kwargs):
        captured_calls.append((url, params or {}))
        return {"dates": [{"date": "2024-04-21", "games": [canonical_game]}]}

    monkeypatch.setattr(MLBGames, "_make_request", fake_make_request)

    fetcher = MLBGames(output_dir=str(tmp_path))
    schedule = fetcher.get_schedule_for_date("2024-04-21")

    assert captured_calls, "Expected MLBGames to issue an HTTP call."
    url, params = captured_calls[0]
    assert url.endswith("/schedule")
    assert params["sportId"] == 1
    assert params["date"] == "2024-04-21"
    assert "probablePitcher" in params["hydrate"]

    games = schedule["dates"][0]["games"]
    schema = _load_schema("mlb_schedule_ingestion_v1.json")
    for game in games:
        validate_contract_payload(game, schema)


# ---------------------------------------------------------------------------
# DB row provider: NHLDatabaseLoader._load_mlb_schedule
# ---------------------------------------------------------------------------


def test_load_mlb_schedule_emits_contract_valid_mlb_games_row(tmp_path: Path) -> None:
    """The real loader must write an mlb_games row matching the frozen contract."""
    schedule_path = _write_schedule_file(tmp_path, [build_mlb_schedule_game()])
    loader = _make_loader(tmp_path)

    loader._load_mlb_schedule(schedule_path)

    rows = find_execute_params(loader.db.execute.call_args_list, "mlb_games")
    assert len(rows) == 1, "Expected exactly one mlb_games insert"

    schema = _load_schema("mlb_mlb_games_row_v1.json")
    validate_contract_payload(serialize_contract_payload(rows[0]), schema)

    expected = build_mlb_games_row()
    for field in (
        "game_id",
        "game_date",
        "season",
        "game_type",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "status",
        "home_pitcher_id",
        "away_pitcher_id",
        "home_pitcher_name",
        "away_pitcher_name",
    ):
        assert rows[0][field] == expected[field], f"mlb_games drift on {field}"


def test_load_mlb_schedule_emits_contract_valid_unified_games_row(
    tmp_path: Path,
) -> None:
    """The real loader must write a unified_games MLB row matching the contract."""
    schedule_path = _write_schedule_file(tmp_path, [build_mlb_schedule_game()])
    loader = _make_loader(tmp_path)

    loader._load_mlb_schedule(schedule_path)

    rows = find_execute_params(loader.db.execute.call_args_list, "unified_games")
    assert len(rows) == 1, "Expected exactly one unified_games insert"

    schema = _load_schema("mlb_unified_game_row_v1.json")
    validate_contract_payload(serialize_contract_payload(rows[0]), schema)

    expected = build_mlb_unified_games_row()
    # game_id may be persisted as int or str — the schema allows both — but
    # when normalised to string it must equal the canonical native gamePk.
    assert str(rows[0]["game_id"]) == expected["game_id"]
    assert rows[0]["sport"] == expected["sport"]
    assert rows[0]["home_team_name"] == expected["home_team_name"]
    assert rows[0]["away_team_name"] == expected["away_team_name"]
    assert rows[0]["home_team_id"] == expected["home_team_id"]
    assert rows[0]["away_team_id"] == expected["away_team_id"]


def test_load_mlb_schedule_skips_excluded_game_types(tmp_path: Path) -> None:
    """Spring training (S), exhibition (E) and All-Star (A) games are filtered."""
    excluded_games = [
        build_mlb_schedule_game(gameType="S", gamePk=999001),
        build_mlb_schedule_game(gameType="E", gamePk=999002),
        build_mlb_schedule_game(gameType="A", gamePk=999003),
    ]
    schedule_path = _write_schedule_file(tmp_path, excluded_games)
    loader = _make_loader(tmp_path)

    loader._load_mlb_schedule(schedule_path)

    assert (
        find_execute_params(loader.db.execute.call_args_list, "mlb_games") == []
    ), "Excluded game types must not be persisted to mlb_games"
    assert (
        find_execute_params(loader.db.execute.call_args_list, "unified_games") == []
    )


def test_load_mlb_schedule_persists_null_scores_for_pregame(tmp_path: Path) -> None:
    """Pre-game schedule rows must persist NULL scores even if the API returns 0."""
    pregame = build_mlb_schedule_game()
    pregame["status"] = {"abstractGameState": "Preview", "detailedState": "Scheduled"}
    pregame["teams"]["home"]["score"] = 0
    pregame["teams"]["away"]["score"] = 0

    schedule_path = _write_schedule_file(tmp_path, [pregame])
    loader = _make_loader(tmp_path)

    loader._load_mlb_schedule(schedule_path)

    rows = find_execute_params(loader.db.execute.call_args_list, "mlb_games")
    assert len(rows) == 1
    assert rows[0]["home_score"] is None
    assert rows[0]["away_score"] is None
    assert rows[0]["status"] == "Preview"
