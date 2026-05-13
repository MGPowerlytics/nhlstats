"""Consumer contract tests for the CSVHistoryLoader boundary.

Consumers (e.g. EPLCSVProcessor, TennisCSVProcessor, DB loaders) trust
that CSV row inputs and processor params outputs satisfy the frozen
schema definitions in ``csv_history_loader_contract_v1.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from tests.contracts.fixtures.csv_history_loader_samples import (
    build_epl_csv_row,
    build_epl_processor_params,
    build_load_csv_summary,
    build_tennis_csv_row,
    build_tennis_processor_params,
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


# ---------------------------------------------------------------------------
# EPL CSV row contract
# ---------------------------------------------------------------------------


class TestEplCsvRowContract:
    """Consumer guarantees for the EPL CSV row shape."""

    def test_canonical_epl_csv_row_satisfies_contract(self) -> None:
        _validator("epl_csv_row").validate(build_epl_csv_row())

    def test_minimal_epl_csv_row_satisfies_contract(self) -> None:
        row = build_epl_csv_row()
        _validator("epl_csv_row").validate(row)

    @pytest.mark.parametrize(
        "missing_field",
        ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"],
    )
    def test_missing_required_field_is_rejected(
        self, missing_field: str
    ) -> None:
        row = build_epl_csv_row()
        row.pop(missing_field)
        with pytest.raises(ValidationError):
            _validator("epl_csv_row").validate(row)

    @pytest.mark.parametrize("invalid_result", ["", "X", "HOME", "DRAW"])
    def test_invalid_full_time_result_is_rejected(
        self, invalid_result: str
    ) -> None:
        row = build_epl_csv_row(FTR=invalid_result)
        with pytest.raises(ValidationError):
            _validator("epl_csv_row").validate(row)

    def test_negative_goals_is_rejected(self) -> None:
        row = build_epl_csv_row(FTHG=-1)
        with pytest.raises(ValidationError):
            _validator("epl_csv_row").validate(row)

    def test_blank_team_name_is_rejected(self) -> None:
        row = build_epl_csv_row(HomeTeam="")
        with pytest.raises(ValidationError):
            _validator("epl_csv_row").validate(row)

    def test_extra_columns_are_allowed(self) -> None:
        row = build_epl_csv_row(HTHG=1, HTAG=0, HS=15, AS=10)
        _validator("epl_csv_row").validate(row)


# ---------------------------------------------------------------------------
# Tennis CSV row contract
# ---------------------------------------------------------------------------


class TestTennisCsvRowContract:
    """Consumer guarantees for the Tennis CSV row shape."""

    def test_canonical_tennis_csv_row_satisfies_contract(self) -> None:
        _validator("tennis_csv_row").validate(build_tennis_csv_row())

    def test_minimal_tennis_csv_row_satisfies_contract(self) -> None:
        row = build_tennis_csv_row(
            Tournament=None, Surface=None, Score=None,
            Round=None, Series=None, Best_of=None, WRank=None, LRank=None,
        )
        _validator("tennis_csv_row").validate(row)

    @pytest.mark.parametrize("missing_field", ["Date", "Winner", "Loser"])
    def test_missing_required_field_is_rejected(
        self, missing_field: str
    ) -> None:
        row = build_tennis_csv_row()
        row.pop(missing_field)
        with pytest.raises(ValidationError):
            _validator("tennis_csv_row").validate(row)

    def test_blank_winner_is_rejected(self) -> None:
        row = build_tennis_csv_row(Winner="")
        with pytest.raises(ValidationError):
            _validator("tennis_csv_row").validate(row)

    def test_blank_loser_is_rejected(self) -> None:
        row = build_tennis_csv_row(Loser="")
        with pytest.raises(ValidationError):
            _validator("tennis_csv_row").validate(row)

    def test_extra_columns_are_allowed(self) -> None:
        row = build_tennis_csv_row(AceW=5, AceL=2)
        _validator("tennis_csv_row").validate(row)


# ---------------------------------------------------------------------------
# EPL processor params contract
# ---------------------------------------------------------------------------


class TestEplProcessorParamsContract:
    """Consumer guarantees for the EPL processor params dict."""

    def test_canonical_epl_processor_params_satisfies_contract(self) -> None:
        _validator("epl_processor_params").validate(build_epl_processor_params())

    def test_man_city_name_resolution(self) -> None:
        params = build_epl_processor_params(
            game_id="EPL_20250816_MANCITY_TOTTENHAM",
            home_team="Man City",
            away_team="Tottenham",
            home_team_full="Manchester City",
            away_team_full="Tottenham Hotspur",
        )
        _validator("epl_processor_params").validate(params)

    @pytest.mark.parametrize(
        "missing_field",
        [
            "game_id", "game_date", "season", "home_team", "away_team",
            "home_team_full", "away_team_full", "home_score", "away_score", "result",
        ],
    )
    def test_missing_required_field_is_rejected(
        self, missing_field: str
    ) -> None:
        params = build_epl_processor_params()
        params.pop(missing_field)
        with pytest.raises(ValidationError):
            _validator("epl_processor_params").validate(params)

    @pytest.mark.parametrize("invalid_result", ["", "X", "WIN", "LOSS"])
    def test_invalid_result_is_rejected(self, invalid_result: str) -> None:
        params = build_epl_processor_params(result=invalid_result)
        with pytest.raises(ValidationError):
            _validator("epl_processor_params").validate(params)

    def test_extra_field_is_rejected(self) -> None:
        params = build_epl_processor_params(unexpected_field="stowaway")
        with pytest.raises(ValidationError):
            _validator("epl_processor_params").validate(params)


# ---------------------------------------------------------------------------
# Tennis processor params contract
# ---------------------------------------------------------------------------


class TestTennisProcessorParamsContract:
    """Consumer guarantees for the Tennis processor params dict."""

    def test_canonical_tennis_processor_params_satisfies_contract(self) -> None:
        _validator("tennis_processor_params").validate(
            build_tennis_processor_params()
        )

    @pytest.mark.parametrize(
        "missing_field",
        [
            "game_id", "game_date", "season", "tour", "tournament",
            "surface", "winner", "loser", "score",
        ],
    )
    def test_missing_required_field_is_rejected(
        self, missing_field: str
    ) -> None:
        params = build_tennis_processor_params()
        params.pop(missing_field)
        with pytest.raises(ValidationError):
            _validator("tennis_processor_params").validate(params)

    def test_extra_field_is_rejected(self) -> None:
        params = build_tennis_processor_params(unexpected_field="stowaway")
        with pytest.raises(ValidationError):
            _validator("tennis_processor_params").validate(params)

    def test_blank_winner_is_rejected(self) -> None:
        params = build_tennis_processor_params(winner="")
        with pytest.raises(ValidationError):
            _validator("tennis_processor_params").validate(params)


# ---------------------------------------------------------------------------
# Load CSV summary contract
# ---------------------------------------------------------------------------


class TestLoadCsvSummaryContract:
    """Consumer guarantees for the load_csv_summary payload."""

    def test_canonical_summary_satisfies_contract(self) -> None:
        _validator("load_csv_summary").validate(build_load_csv_summary())

    def test_zero_rows_loaded_is_valid(self) -> None:
        summary = build_load_csv_summary(rows_loaded=0)
        _validator("load_csv_summary").validate(summary)

    def test_missing_sport_is_rejected(self) -> None:
        summary = build_load_csv_summary()
        summary.pop("sport")
        with pytest.raises(ValidationError):
            _validator("load_csv_summary").validate(summary)

    def test_negative_rows_loaded_is_rejected(self) -> None:
        summary = build_load_csv_summary(rows_loaded=-1)
        with pytest.raises(ValidationError):
            _validator("load_csv_summary").validate(summary)

    def test_extra_field_is_rejected(self) -> None:
        summary = build_load_csv_summary(extra="data")
        with pytest.raises(ValidationError):
            _validator("load_csv_summary").validate(summary)
