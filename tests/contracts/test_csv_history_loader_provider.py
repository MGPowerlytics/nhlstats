"""Provider RED tests for the CSVHistoryLoader boundary.

These tests exercise the *real* producer code in ``plugins/csv_history_loader.py``:
- ``CSVHistoryLoader._load_csv_for_sport()`` for EPL
- ``CSVHistoryLoader._load_csv_for_sport()`` for Tennis

The test uses temporary CSV files and a ``MagicMock`` DB manager to avoid
needing a real database. The CSVHistoryLoader reads the temp CSV and passes
rows to the processor; we intercept the processor calls and validate the
output against the frozen contract schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from tests.contracts.helpers import serialize_contract_payload

from tests.contracts.fixtures.csv_history_loader_samples import (
    build_epl_csv_text,
    build_epl_csv_row,
    build_tennis_csv_row,
    build_tennis_csv_text,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "csv_history_loader_contract_v1.json"
)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator(def_name: str) -> Draft202012Validator:
    schema = _load_schema()
    resource = Resource.from_contents(schema)
    registry = Registry().with_resource(uri=schema["$id"], resource=resource)
    return Draft202012Validator(
        {"$ref": f"{schema['$id']}#/$defs/{def_name}"}, registry=registry
    )


def _import_csv_history_loader():
    """Import CSVHistoryLoader, handling the csv_processors mock for isolated testing."""
    import importlib
    import sys

    # Ensure csv_processors module is available
    if "csv_processors" not in sys.modules:
        importlib.import_module("csv_processors")

    if "plugins.csv_history_loader" not in sys.modules:
        importlib.import_module("plugins.csv_history_loader")

    module = sys.modules["plugins.csv_history_loader"]
    return module.CSVHistoryLoader


@pytest.fixture
def mock_db() -> MagicMock:
    """Return a MagicMock DB manager for provider tests."""
    return MagicMock()


@pytest.fixture
def epl_csv_file(tmp_path: Path) -> Path:
    """Create a temporary EPL CSV file for provider testing."""
    csv_path = tmp_path / "E0_2526.csv"
    csv_path.write_text(
        build_epl_csv_text(
            build_epl_csv_row(
                Date="16/08/2025",
                HomeTeam="Liverpool",
                AwayTeam="Bournemouth",
                FTHG=2,
                FTAG=0,
                FTR="H",
            ),
            build_epl_csv_row(
                Date="16/08/2025",
                HomeTeam="Manchester City",
                AwayTeam="Tottenham Hotspur",
                FTHG=3,
                FTAG=1,
                FTR="H",
            ),
        ),
        encoding="utf-8",
    )
    return csv_path


@pytest.fixture
def tennis_csv_file(tmp_path: Path) -> Path:
    """Create a temporary Tennis CSV file for provider testing."""
    csv_path = tmp_path / "ATP_2026.csv"
    # Use overrides dict to pass "Best of" (space) which Python kwargs cannot express
    overrides: dict[str, Any] = {
        "Best of": 3,
    }
    csv_path.write_text(
        build_tennis_csv_text(
            build_tennis_csv_row(
                Date="2026-04-07",
                Winner="Cobolli F.",
                Loser="Blockx A.",
                Tournament="Monte Carlo Masters",
                Surface="Clay",
                Score="6-4 7-5",
                Round="1st Round",
                Series="Masters 1000",
                WRank=32,
                LRank=134,
                **overrides,
            ),
        ),
        encoding="utf-8",
    )
    return csv_path


class TestEplProviderContract:
    """Provider-side guarantees for CSVHistoryLoader EPL ingestion."""

    def test_epl_csv_loader_produces_contract_valid_row(
        self, mock_db: MagicMock, epl_csv_file: Path
    ) -> None:
        """The real CSVHistoryLoader must pass EPL CSV rows to the processor
        that satisfy the epl_csv_row contract."""
        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        captured_rows: list[pd.Series] = []

        def capture_row(sport: str, row: pd.Series, **kwargs: Any) -> None:
            captured_rows.append(row)

        loader._process_csv_row = capture_row  # type: ignore[method-assign]

        loader._load_csv_for_sport("epl", epl_csv_file)

        assert len(captured_rows) == 2, "Expected 2 EPL rows to be processed"
        # Validate each captured row against the contract
        for row in captured_rows:
            row_dict = row.to_dict()
            _validator("epl_csv_row").validate(row_dict)

    def test_epl_csv_loader_passes_correct_season_code(
        self, mock_db: MagicMock, epl_csv_file: Path
    ) -> None:
        """The season_code extracted from filename must be passed through."""
        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        captured_kwargs: list[dict[str, Any]] = []

        def capture_row(sport: str, row: pd.Series, **kwargs: Any) -> None:
            captured_kwargs.append(kwargs)

        loader._process_csv_row = capture_row  # type: ignore[method-assign]

        loader._load_csv_for_sport("epl", epl_csv_file)

        assert len(captured_kwargs) == 2
        for kwargs in captured_kwargs:
            assert kwargs.get("season_code") == "2526"

    def test_epl_csv_loader_normalizes_date(
        self, mock_db: MagicMock, epl_csv_file: Path
    ) -> None:
        """EPL CSV dates must be normalized to YYYY-MM-DD string format
        via _normalize_epl_row_for_processing before processor handoff."""
        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        captured_rows: list[pd.Series] = []

        def capture_row(sport: str, row: pd.Series, **kwargs: Any) -> None:
            captured_rows.append(row)

        loader._process_csv_row = capture_row  # type: ignore[method-assign]

        loader._load_csv_for_sport("epl", epl_csv_file)

        assert len(captured_rows) >= 1
        date_val = captured_rows[0].get("Date")
        assert date_val == "2025-08-16", (
            f"Expected normalized date '2025-08-16', got {date_val!r}"
        )

    def test_epl_csv_loader_preserves_all_required_fields(
        self, mock_db: MagicMock, epl_csv_file: Path
    ) -> None:
        """All contract-required CSV fields must survive the loader pipeline."""
        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        captured_rows: list[pd.Series] = []

        def capture_row(sport: str, row: pd.Series, **kwargs: Any) -> None:
            captured_rows.append(row)

        loader._process_csv_row = capture_row  # type: ignore[method-assign]

        loader._load_csv_for_sport("epl", epl_csv_file)

        required_fields = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"}
        for row in captured_rows:
            present = required_fields & set(row.index)
            assert present == required_fields, (
                f"Missing fields: {required_fields - present}"
            )


class TestTennisProviderContract:
    """Provider-side guarantees for CSVHistoryLoader Tennis ingestion."""

    def test_tennis_csv_loader_produces_contract_valid_row(
        self, mock_db: MagicMock, tennis_csv_file: Path
    ) -> None:
        """The real CSVHistoryLoader must pass Tennis CSV rows to the processor
        that satisfy the tennis_csv_row contract."""
        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        captured_rows: list[pd.Series] = []

        def capture_row(sport: str, row: pd.Series, **kwargs: Any) -> None:
            captured_rows.append(row)

        loader._process_csv_row = capture_row  # type: ignore[method-assign]

        loader._load_csv_for_sport("tennis", tennis_csv_file)

        assert len(captured_rows) == 1, "Expected 1 Tennis row to be processed"
        row_dict = serialize_contract_payload(captured_rows[0].to_dict())
        _validator("tennis_csv_row").validate(row_dict)

    def test_tennis_csv_loader_passes_correct_tour_and_season(
        self, mock_db: MagicMock, tennis_csv_file: Path
    ) -> None:
        """Tour and season extracted from filename must be passed as kwargs."""
        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        captured_kwargs: list[dict[str, Any]] = []

        def capture_row(sport: str, row: pd.Series, **kwargs: Any) -> None:
            captured_kwargs.append(kwargs)

        loader._process_csv_row = capture_row  # type: ignore[method-assign]

        loader._load_csv_for_sport("tennis", tennis_csv_file)

        assert len(captured_kwargs) == 1
        kwargs = captured_kwargs[0]
        assert kwargs.get("tour") == "ATP"
        assert kwargs.get("season") == "2026"

    def test_tennis_csv_loader_preserves_required_fields(
        self, mock_db: MagicMock, tennis_csv_file: Path
    ) -> None:
        """All contract-required CSV fields must survive the loader pipeline."""
        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        captured_rows: list[pd.Series] = []

        def capture_row(sport: str, row: pd.Series, **kwargs: Any) -> None:
            captured_rows.append(row)

        loader._process_csv_row = capture_row  # type: ignore[method-assign]

        loader._load_csv_for_sport("tennis", tennis_csv_file)

        required_fields = {"Date", "Winner", "Loser"}
        for row in captured_rows:
            present = required_fields & set(row.index)
            assert present == required_fields, (
                f"Missing fields: {required_fields - present}"
            )

    def test_tennis_csv_loader_with_winning_player_name(
        self, mock_db: MagicMock, tmp_path: Path
    ) -> None:
        """Winner/Loser names must be preserved through the loader pipeline."""
        csv_path = tmp_path / "WTA_2026.csv"
        csv_path.write_text(
            build_tennis_csv_text(
                build_tennis_csv_row(
                    Date="2026-05-01",
                    Winner="Swiatek I.",
                    Loser="Sabalenka A.",
                ),
            ),
            encoding="utf-8",
        )

        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        captured_rows: list[pd.Series] = []

        def capture_row(sport: str, row: pd.Series, **kwargs: Any) -> None:
            captured_rows.append(row)

        loader._process_csv_row = capture_row  # type: ignore[method-assign]

        loader._load_csv_for_sport("tennis", csv_path)

        assert len(captured_rows) == 1
        row = captured_rows[0]
        assert row["Winner"] == "Swiatek I."
        assert row["Loser"] == "Sabalenka A."


class TestDriftDetection:
    """Tests that detect when the real CSVHistoryLoader output drifts
    from the contract. These should fail if the producer's output shape
    changes."""

    def test_epl_load_csv_for_sport_requires_csv_file(
        self, mock_db: MagicMock
    ) -> None:
        """Loading a non-existent CSV file must not crash the loader."""
        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        fake_path = Path("/nonexistent/E0_9999.csv")

        # Should not raise — the loader silently handles missing files
        loader._load_csv_for_sport("epl", fake_path)

        # Verify no DB interactions happened
        mock_db.execute.assert_not_called()

    def test_epl_loader_output_matches_consumer_contract(self) -> None:
        """The EPL CSV row fixture must validate against the contract
        as a consumer would expect."""
        _validator("epl_csv_row").validate(build_epl_csv_row())

    def test_tennis_loader_output_matches_consumer_contract(self) -> None:
        """The Tennis CSV row fixture must validate against the contract
        as a consumer would expect."""
        _validator("tennis_csv_row").validate(build_tennis_csv_row())

    def test_epl_processor_params_fixture_matches_contract(self) -> None:
        """The EPL processor params fixture must validate against the
        contract definition."""
        from tests.contracts.fixtures.csv_history_loader_samples import (
            build_epl_processor_params,
        )

        _validator("epl_processor_params").validate(build_epl_processor_params())

    def test_tennis_processor_params_fixture_matches_contract(self) -> None:
        """The Tennis processor params fixture must validate against the
        contract definition."""
        from tests.contracts.fixtures.csv_history_loader_samples import (
            build_tennis_processor_params,
        )

        _validator("tennis_processor_params").validate(
            build_tennis_processor_params()
        )

    def test_invalid_csv_row_is_rejected_by_contract(
        self, mock_db: MagicMock, tmp_path: Path
    ) -> None:
        """A CSV row missing a required field must be rejected by the schema."""
        csv_path = tmp_path / "invalid.csv"
        # Write a CSV missing required columns (no Date column)
        csv_path.write_text("HomeTeam,AwayTeam,FTHG,FTAG,FTR\nLiverpool,Bournemouth,2,0,H\n")

        CSVHistoryLoader = _import_csv_history_loader()
        loader = CSVHistoryLoader(mock_db)
        captured_rows: list[pd.Series] = []

        def capture_row(sport: str, row: pd.Series, **kwargs: Any) -> None:
            captured_rows.append(row)

        loader._process_csv_row = capture_row  # type: ignore[method-assign]

        loader._load_csv_for_sport("epl", csv_path)

        # The loader reads the CSV but the row may include the NaN Date;
        # verify the schema rejects it
        if captured_rows:
            row_dict = captured_rows[0].to_dict()
            with pytest.raises(ValidationError):
                _validator("epl_csv_row").validate(row_dict)
