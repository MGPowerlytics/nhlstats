from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

from plugins.football_data_co_uk import FootballDataCoUkGames
from tests.contracts.fixtures.epl_csv_samples import build_epl_csv_row, build_epl_csv_text
from tests.contracts.helpers import validate_contract_payload


SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "epl_csv_ingestion_v1.json"


def _load_epl_csv_ingestion_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _import_csv_history_loader():
    if "csv_processors" not in sys.modules:
        sys.modules["csv_processors"] = importlib.import_module("plugins.csv_processors")
    module = importlib.import_module("plugins.csv_history_loader")
    return module.CSVHistoryLoader


def test_football_data_co_uk_provider_output_matches_canonical_csv_contract(
    tmp_path: Path, monkeypatch
) -> None:
    """Provider output should preserve the canonical CSV ingestion row shape."""
    csv_path = tmp_path / "E0_2526.csv"
    csv_path.write_text(
        build_epl_csv_text(
            build_epl_csv_row(
                Date="16/08/2025",
                HomeTeam="Manchester City",
                AwayTeam="Tottenham Hotspur",
                FTHG=2,
                FTAG=1,
                FTR="H",
            )
        ),
        encoding="utf-8",
    )

    games = FootballDataCoUkGames(sport_id="E0", data_dir=str(tmp_path), seasons=["2526"])
    monkeypatch.setattr(games, "download_games", lambda: True)

    provider_row = games.load_games().iloc[0].to_dict()

    validate_contract_payload(provider_row, _load_epl_csv_ingestion_schema())


def test_csv_history_loader_passes_contract_valid_epl_rows_to_processor(
    tmp_path: Path,
) -> None:
    """CSVHistoryLoader should hand provider rows to EPL processing without row-shape drift."""
    csv_path = tmp_path / "E0_2526.csv"
    csv_path.write_text(
        build_epl_csv_text(
            build_epl_csv_row(
                Date="16/08/2025",
                HomeTeam="Manchester City",
                AwayTeam="Tottenham Hotspur",
                FTHG=2,
                FTAG=1,
                FTR="H",
            )
        ),
        encoding="utf-8",
    )

    CSVHistoryLoader = _import_csv_history_loader()
    loader = CSVHistoryLoader(MagicMock())
    captured_rows: list[tuple] = []

    def capture_row(sport: str, row, **kwargs) -> None:
        captured_rows.append((sport, row, kwargs))

    loader._process_csv_row = capture_row  # type: ignore[method-assign]

    loader._load_csv_for_sport("epl", csv_path)

    assert captured_rows, "Expected CSVHistoryLoader to forward at least one EPL row."
    sport, row, kwargs = captured_rows[0]

    assert sport == "epl"
    assert kwargs == {"season_code": "2526"}
    validate_contract_payload(row.to_dict(), _load_epl_csv_ingestion_schema())
