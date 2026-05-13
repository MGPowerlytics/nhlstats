from __future__ import annotations

import json
from pathlib import Path

from tests.contracts.fixtures.epl_understat_samples import (
    build_epl_understat_api_match,
)
from tests.contracts.helpers import validate_contract_payload

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def test_understat_client_normalizes_raw_match_to_contract() -> None:
    """The real Understat client must emit the frozen normalized payload."""
    from plugins.stats.understat_client import UnderstatLeagueClient

    client = UnderstatLeagueClient()
    payload = client.normalize_match(
        sport="EPL",
        season=2025,
        raw_match=build_epl_understat_api_match(),
    )

    validate_contract_payload(payload, _load_schema("epl_understat_match_v1.json"))


def test_understat_client_resolves_storage_facing_team_names() -> None:
    """Provider output must match the storage-facing EPL team identity semantics."""
    from plugins.stats.understat_client import UnderstatLeagueClient

    client = UnderstatLeagueClient()
    payload = client.normalize_match(
        sport="EPL",
        season=2025,
        raw_match=build_epl_understat_api_match(),
    )

    assert payload["home_team"] == "Manchester City"
    assert payload["away_team"] == "Tottenham Hotspur"
