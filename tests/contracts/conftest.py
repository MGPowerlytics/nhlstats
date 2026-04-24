from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest

from tests.contracts.fixtures import (
    build_epl_game_payload,
    build_epl_governed_row,
    build_epl_market_payload,
)
from tests.contracts.helpers import (
    CONTRACTS_ROOT,
    FIXTURES_ROOT,
    SCHEMAS_ROOT,
    clone_payload,
    load_versioned_schema,
)


@pytest.fixture(scope="session")
def contract_paths() -> dict[str, Path]:
    """Expose canonical EPL contract scaffold paths."""
    return {
        "contracts": CONTRACTS_ROOT,
        "fixtures": FIXTURES_ROOT,
        "schemas": SCHEMAS_ROOT,
    }


@pytest.fixture(scope="session")
def schema_loader() -> Callable[[str, str, str], dict[str, Any]]:
    """Expose the shared versioned schema loader."""
    return load_versioned_schema


@pytest.fixture
def epl_game_payload() -> dict[str, Any]:
    """Return a deterministic EPL game payload sample."""
    return clone_payload(build_epl_game_payload())


@pytest.fixture
def epl_market_payload() -> dict[str, Any]:
    """Return a deterministic EPL market payload sample."""
    return clone_payload(build_epl_market_payload())


@pytest.fixture
def epl_governed_row() -> dict[str, Any]:
    """Return a deterministic EPL governed-row sample."""
    return clone_payload(build_epl_governed_row())
