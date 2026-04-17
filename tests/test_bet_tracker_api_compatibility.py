"""Regression tests for live Kalshi fill payload compatibility."""

from unittest.mock import Mock

from plugins.bet_tracker import _extract_basic_fill_data, load_fills_from_kalshi


def test_extract_basic_fill_data_supports_decimal_fill_payload():
    """Current Kalshi fill payload uses count_fp and *_price_dollars fields."""
    fill = {
        "ticker": "KXNBAGAME-26APR07CHABOS-BOS",
        "trade_id": "trade-123",
        "side": "yes",
        "count_fp": "7.00",
        "yes_price_dollars": "0.5700",
        "no_price_dollars": "0.4300",
        "fee_cost": "0.130000",
        "created_time": "2026-04-06T05:02:39.520415Z",
    }

    parsed = _extract_basic_fill_data(fill)

    assert parsed.bet_id == "KXNBAGAME-26APR07CHABOS-BOS_trade-123"
    assert parsed.count == 7
    assert parsed.price == 57
    assert parsed.cost == 3.99
    assert parsed.fees == 0.13
    assert parsed.placed_date == "2026-04-06"


def test_load_fills_from_kalshi_paginates_until_cursor_exhausted():
    """Sync must fetch every fills page, not just the newest 500 rows."""
    mock_client = Mock()
    mock_client._get.side_effect = [
        {
            "fills": [{"ticker": "A", "trade_id": "1"}, {"ticker": "B", "trade_id": "2"}],
            "cursor": "cursor-1",
        },
        {
            "fills": [{"ticker": "C", "trade_id": "3"}],
            "cursor": None,
        },
    ]

    fills = load_fills_from_kalshi(mock_client)

    assert fills == [
        {"ticker": "A", "trade_id": "1"},
        {"ticker": "B", "trade_id": "2"},
        {"ticker": "C", "trade_id": "3"},
    ]
    assert mock_client._get.call_count == 2
    assert mock_client._get.call_args_list[0].args[0] == "/trade-api/v2/portfolio/fills?limit=500"
    assert mock_client._get.call_args_list[1].args[0] == (
        "/trade-api/v2/portfolio/fills?limit=500&cursor=cursor-1"
    )
