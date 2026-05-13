"""Provider contract tests for the KalshiBetting.get_balance() → balance response boundary.

Validates that ``KalshiBetting.get_balance()`` returns a ``Tuple[float, float]``
where both values match schema constraints. Uses a mock Kalshi API client so
tests require no real credentials.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from jsonschema import Draft202012Validator, ValidationError

from plugins.kalshi_betting import KalshiBetting, KalshiConfig

BALANCE_SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / "kalshi_balance_response_v1.json"
)

MOCK_BALANCE_CENTS = 10000
MOCK_PORTFOLIO_VALUE_CENTS = 10500


def _build_balance_response(
    balance: int = MOCK_BALANCE_CENTS,
    portfolio_value: int = MOCK_PORTFOLIO_VALUE_CENTS,
) -> dict[str, Any]:
    """Build a deterministic Kalshi balance response."""
    return {
        "balance": balance,
        "portfolio_value": portfolio_value,
    }


@contextmanager
def _mocked_betting_client() -> Iterator[KalshiBetting]:
    """Create a KalshiBetting instance with all HTTP mocked out.

    The context manager keeps the patches alive for the caller's scope.
    Uses a temporary directory for the order dedup lock to avoid collisions
    with real lock files from production runs.
    """
    import tempfile

    tmp_dedup = tempfile.mkdtemp()
    config = KalshiConfig(
        api_key_id="test_api_key_id",
        private_key_path="/dev/null",
        max_bet_size=100.0,
        production=False,
        dedupe_dir=tmp_dedup,
    )

    def _mock_request(method: str, path: str, data: dict | None = None) -> dict[str, Any]:
        """Single dispatcher that returns deterministic canned responses."""
        if method == "GET" and "/portfolio/balance" in path:
            return _build_balance_response(
                balance=MOCK_BALANCE_CENTS,
                portfolio_value=MOCK_PORTFOLIO_VALUE_CENTS,
            )

        if method == "GET" and "/markets/" in path:
            return {
                "market": {
                    "ticker": path.rsplit("/", 1)[-1],
                    "status": "active",
                    "result": "",
                    "close_time": "2026-01-20T19:00:00Z",
                    "title": "Lakers vs Celtics - Winner",
                    "yes_ask": 60,
                    "no_ask": 45,
                }
            }

        if method == "POST" and "/portfolio/orders" in path:
            return {"order_id": "mock_order_001"}

        if method == "GET" and "/portfolio/positions" in path:
            return {"positions": []}

        if method == "GET" and "/portfolio/orders" in path:
            return {"orders": []}

        return {}

    with (
        patch.object(KalshiBetting, "_load_private_key", return_value=MagicMock()),
        patch.object(KalshiBetting, "_request", side_effect=_mock_request),
    ):
        yield KalshiBetting(config=config)


@contextmanager
def _make_mocked_client_with_balance(
    balance: int, portfolio_value: int
) -> Iterator[KalshiBetting]:
    """Create a mocked client that returns a specific balance response."""
    import tempfile

    tmp_dedup = tempfile.mkdtemp()
    config = KalshiConfig(
        api_key_id="test_api_key_id",
        private_key_path="/dev/null",
        max_bet_size=100.0,
        production=False,
        dedupe_dir=tmp_dedup,
    )

    def _mock_request(method: str, path: str, data: dict | None = None) -> dict[str, Any]:
        if method == "GET" and "/portfolio/balance" in path:
            return {"balance": balance, "portfolio_value": portfolio_value}

        if method == "GET" and "/markets/" in path:
            return {
                "market": {
                    "ticker": path.rsplit("/", 1)[-1],
                    "status": "active",
                    "result": "",
                    "close_time": "2026-01-20T19:00:00Z",
                    "title": "Lakers vs Celtics - Winner",
                    "yes_ask": 60,
                    "no_ask": 45,
                }
            }

        if method == "POST" and "/portfolio/orders" in path:
            return {"order_id": "mock_order_001"}

        if method == "GET" and "/portfolio/positions" in path:
            return {"positions": []}

        if method == "GET" and "/portfolio/orders" in path:
            return {"orders": []}

        return {}

    with (
        patch.object(KalshiBetting, "_load_private_key", return_value=MagicMock()),
        patch.object(KalshiBetting, "_request", side_effect=_mock_request),
    ):
        yield KalshiBetting(config=config)


@pytest.fixture(scope="module")
def balance_schema() -> dict[str, Any]:
    """Load the Kalshi balance response schema."""
    return json.loads(BALANCE_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)


# ---------------------------------------------------------------------------
# Provider: get_balance() output matches the balance schema
# ---------------------------------------------------------------------------


class TestGetBalanceOutput:
    """get_balance() response structure must match the frozen schema."""

    def test_get_balance_returns_tuple_of_two_floats(self) -> None:
        with _mocked_betting_client() as betting:
            balance, portfolio_value = betting.get_balance()

        assert isinstance(balance, float)
        assert isinstance(portfolio_value, float)
        assert isinstance((balance, portfolio_value), tuple)

    def test_get_balance_values_match_schema_constraints(
        self, balance_schema: dict[str, Any]
    ) -> None:
        with _mocked_betting_client() as betting:
            balance, portfolio_value = betting.get_balance()

        # Build the original API response that would have produced these values
        api_response = _build_balance_response()

        # The API response should be schema-compliant
        _validate(balance_schema, api_response)

        # Derived values: balance in cents / 100 = dollars
        assert balance == MOCK_BALANCE_CENTS / 100
        assert portfolio_value == MOCK_PORTFOLIO_VALUE_CENTS / 100

    def test_get_balance_with_default_values(
        self, balance_schema: dict[str, Any]
    ) -> None:
        with _mocked_betting_client() as betting:
            balance, portfolio_value = betting.get_balance()

        assert balance == pytest.approx(100.0)
        assert portfolio_value == pytest.approx(105.0)

    def test_get_balance_response_is_schema_compliant(
        self, balance_schema: dict[str, Any]
    ) -> None:
        """The raw API response behind get_balance() must match the schema."""
        api_response = _build_balance_response()
        _validate(balance_schema, api_response)


class TestGetBalanceVariousValues:
    """get_balance() with various mock return values."""

    def test_normal_balance(self) -> None:
        with _make_mocked_client_with_balance(
            balance=50000, portfolio_value=52300
        ) as betting:
            balance, portfolio_value = betting.get_balance()

        assert balance == 500.0
        assert portfolio_value == 523.0

    def test_zero_balance(self) -> None:
        with _make_mocked_client_with_balance(
            balance=0, portfolio_value=0
        ) as betting:
            balance, portfolio_value = betting.get_balance()

        assert balance == 0.0
        assert portfolio_value == 0.0

    def test_high_value_balance(self) -> None:
        with _make_mocked_client_with_balance(
            balance=10000000, portfolio_value=10500000
        ) as betting:
            balance, portfolio_value = betting.get_balance()

        assert balance == 100000.0
        assert portfolio_value == 105000.0

    def test_portfolio_value_greater_than_balance(self) -> None:
        with _make_mocked_client_with_balance(
            balance=10000, portfolio_value=15000
        ) as betting:
            balance, portfolio_value = betting.get_balance()

        assert balance == 100.0
        assert portfolio_value == 150.0

    def test_balance_greater_than_portfolio_value(self) -> None:
        with _make_mocked_client_with_balance(
            balance=20000, portfolio_value=15000
        ) as betting:
            balance, portfolio_value = betting.get_balance()

        assert balance == 200.0
        assert portfolio_value == 150.0


class TestGetBalanceSchemaRejection:
    """Schema compliance: schema must reject invalid payloads."""

    def test_schema_rejects_missing_balance(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = {"portfolio_value": 10000}
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_schema_rejects_missing_portfolio_value(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = {"balance": 10000}
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_schema_rejects_negative_balance(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = {"balance": -100, "portfolio_value": 0}
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_schema_rejects_negative_portfolio_value(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = {"balance": 0, "portfolio_value": -500}
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)

    def test_schema_rejects_extra_field(
        self, balance_schema: dict[str, Any]
    ) -> None:
        payload = {"balance": 10000, "portfolio_value": 10500, "extra": "data"}
        with pytest.raises(ValidationError):
            _validate(balance_schema, payload)
