# Kalshi Contract Tests (Fill/Order Boundary)

## Status: DONE

Created contract tests for the KalshiBetting.place_bet() → BetTracker boundary (Tier 1, highest impact — money-moving).

## Files Created

### Schemas (`tests/contracts/schemas/`)
- `kalshi_fill_payload_v1.json` — Schema for fill payloads from `/portfolio/fills` (ticker, trade_id, side, count, count_fp, yes_price/no_price, yes_price_dollars/no_price_dollars, fee_cost, created_time)
- `kalshi_order_payload_v1.json` — Schema for order payloads from `/portfolio/orders` (order_id, client_order_id, ticker, side, status, fill_count_fp, initial_count_fp, yes_price, yes_price_dollars, no_price, no_price_dollars, taker_fill_cost_dollars, taker_fees_dollars, created_time)
- `kalshi_market_details_v1.json` — Schema for market details (status, result, close_time, title)

All schemas use `additionalProperties: false` and draft/2020-12.

### Fixtures (`tests/contracts/fixtures/`)
- `kalshi_samples.py` — Deterministic sample payloads: `build_kalshi_fill_payload()`, `build_kalshi_order_payload()`, `build_kalshi_market_details_payload()`, `build_kalshi_fill_no_side_payload()`

### Consumer Tests (`tests/contracts/test_kalshi_fill_consumer.py`)
- Fixture conformance tests (fill, order, market_details against schemas)
- `_extract_basic_fill_data()` tests (yes/no sides, ticker sport detection, edge cases)
- `_extract_order_data()` tests (executed/resting/canceled orders, price parsing)
- `_process_fill()` tests (active/closed/won/lost markets)

### Provider Tests (`tests/contracts/test_kalshi_fill_provider.py`)
- `_place_order()` output matches order schema (yes/no sides)
- Response contains expected fields
- Schema rejects invalid payloads (missing order_id, invalid side/status, extra fields)
- `place_bet()` → `_place_order()` end-to-end tests (both sides)
- Uses `_mocked_betting_client()` context manager with full HTTP mock layer
- Uses temp directory for dedup locks to avoid interference with production

## Key Findings
- `_place_order()` output matches the frozen order schema perfectly
- `_extract_basic_fill_data()` correctly parses fill payloads into FillData
- `_extract_order_data()` correctly converts order payloads to BetData
- `_process_fill()` works end-to-end with mocked market data
- Order payload needs `yes_price`/`no_price` fields since `_extract_order_data` calls `_parse_price_cents()`
- Provider tests use `patch.object` context manager pattern (must keep patches alive during method calls)
- `SimpleOrderLock` needs a writable dedupe dir — using `tempfile.mkdtemp()` in tests

## Test Results
- `pytest tests/contracts/test_kalshi_fill_consumer.py tests/contracts/test_kalshi_fill_provider.py -v`: 46 passed
- `ruff check tests/contracts/test_kalshi_fill_consumer.py tests/contracts/test_kalshi_fill_provider.py tests/contracts/fixtures/kalshi_samples.py`: All checks passed
