from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from tests.contracts.fixtures.epl_understat_samples import (
    build_epl_understat_contract_payload,
)
from tests.contracts.helpers import validate_contract_payload

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def test_epl_understat_schema_defines_canonical_match_contract() -> None:
    """The Understat contract freezes the normalized EPL xG payload shape."""
    schema = _load_schema("epl_understat_match_v1.json")

    assert schema["title"] == "EPL Understat Match Contract"
    assert schema["properties"]["source"]["const"] == "UNDERSTAT"
    assert schema["properties"]["sport"]["const"] == "EPL"


def test_canonical_understat_payload_satisfies_contract() -> None:
    """A deterministic normalized Understat payload must validate cleanly."""
    payload = build_epl_understat_contract_payload()

    validate_contract_payload(payload, _load_schema("epl_understat_match_v1.json"))


@pytest.mark.parametrize(
    "missing_field", ["match_id", "home_team", "home_xg", "away_xg"]
)
def test_understat_contract_rejects_missing_required_fields(missing_field: str) -> None:
    """Consumer must fail fast when the provider omits a required field."""
    payload = build_epl_understat_contract_payload()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        validate_contract_payload(payload, _load_schema("epl_understat_match_v1.json"))


def test_understat_contract_rejects_malformed_probabilities() -> None:
    """Forecast probabilities must stay within the contract bounds."""
    payload = build_epl_understat_contract_payload(forecast_home_win=1.2)

    with pytest.raises(ValidationError):
        validate_contract_payload(payload, _load_schema("epl_understat_match_v1.json"))
