# Odds Feed Schema — Pre-Ingestion Validation

## Purpose

This module provides a **Pandera-based pre-ingestion contract** for odds data
fetched from [The Odds API](https://the-odds-api.com/). It validates the
DataFrame created from `_parse_game()` output **BEFORE** it reaches the
database via `save_to_db()`.

The goal is to catch bad data (null fields, out-of-range odds, future
timestamps, malformed IDs, distribution shifts) at the ingestion boundary,
preventing corrupt data from entering `unified_games` and `game_odds` tables.

## Files

| File | Purpose |
|---|---|
| `plugins/odds_data_schema.py` | **Live source**: Pandera `DataFrameModel`, distribution shift check, validation wrapper |
| `.agent_tasks/odds_schema/test_odds_data_schema.py` | Pytest test suite (24 tests) for schema, wrapper, and distribution shift |
| `.agent_tasks/odds_schema/test_integration_the_odds_api.py` | Integration tests (10 tests) for validation gate in `save_to_db()` |
| `.agent_tasks/odds_schema/__init__.py` | Package marker |

## Migration Status

### The Odds API (odds_data_schema.py) — DONE

The schema was moved from `.agent_tasks/odds_schema/odds_data_schema.py` to
`plugins/odds_data_schema.py` on 2025-07-17. The `.agent_tasks/` copy was
removed — `plugins/odds_data_schema.py` is the single source of truth.

Import path:
```python
from plugins.odds_data_schema import OddsFeedSchema, validate_odds_dataframe
```

### Kalshi (kalshi_ingestion_schema.py) — DONE

The Kalshi-specific schema was created at `plugins/kalshi_ingestion_schema.py`
and validated into `save_to_db()` in `plugins/kalshi_markets.py` on 2026-04-27.

The validation block sits after the tennis early-return and before the main
`for market in markets:` upsert loop. It re-parses markets into a validation
DataFrame (lightweight parsing), runs `validate_odds_ingestion()`, and handles
`SchemaError` (halt) / `SchemaDriftError` (log and continue).

Import path:
```python
from plugins.kalshi_ingestion_schema import validate_odds_ingestion, SchemaDriftError
from pandera.errors import SchemaError
```

## Integration with `save_to_db()`

### The Odds API path (`TheOddsAPI.save_to_db()`)

```
fetch_markets() → _parse_game() → List[Dict]
    → pd.DataFrame(parsed_markets)
    → validate_odds_dataframe(df)    ← NEW: halts on failure, returns 0
    → save_to_db() continues normally on success
```

### Kalshi path (`kalshi_markets.save_to_db()`)

```
markets list (from API)
    → [tennis early return — skip validation, dispatch to _save_tennis_kalshi_markets]
    → rebuild parsed_for_validation (lightweight re-parse before main loop)
    → pd.DataFrame(parsed_for_validation)
    → validate_odds_ingestion(df)    ← NEW: halts on SchemaError, logs on SchemaDriftError
    → main upsert loop (for market in markets: ...)
```

## Schema Fields (Kalshi)

| Column | Type | Constraints | Nullable |
|---|---|---|---|
| `ticker` | `str` | Regex: `^[A-Z0-9]+(?:-[A-Z0-9]+)+-[A-Z0-9]+$` | No |
| `title` | `str` | Non-empty when present | Yes |
| `sport` | `str` | Must be in `VALID_SPORTS` | No |
| `home_team` | `str` | Non-empty | No |
| `away_team` | `str` | Non-empty | No |
| `game_date` | `str` | Regex: `^\d{4}-\d{2}-\d{2}$`, must be parseable | No |
| `yes_ask` | `int` | [0, 99] | No |
| `no_ask` | `int` | [0, 99] | No |
| `outcome_name` | `str` | One of: home, away, draw | No |
| `decimal_odds` | `float` | [0.0, 100.0] | No |
| `bookmaker` | `str` | Must be "Kalshi" | No |
| `market_name` | `str` | Must be "moneyline" | No |

## Custom Checks (Kalshi)

1. **`check_title_nonempty_when_present`**: Ensures title is non-empty when not null.
2. **`check_team_names_nonempty`**: Ensures home/away team names are non-empty.
3. **`check_game_date_parseable`**: Validates date strings are real calendar dates.
4. **`check_decimal_odds_consistency`**: Ensures odds match yes_ask (0 → 0.0, >0 → ≥1.01).
5. **`check_close_time_not_past`**: Ensures close_time (if present) is in the future.
6. **Distribution shift detection**: `_check_categorical_distribution_shift()` for sport and outcome_name.

## Verification (Done When)

All 4 checks pass:

1. `ruff check plugins/odds_data_schema.py plugins/the_odds_api.py .agent_tasks/odds_schema/test_integration_the_odds_api.py` — 0 errors ✅
2. `pytest .agent_tasks/odds_schema/test_odds_data_schema.py -v` — 24/24 pass ✅
3. `pytest .agent_tasks/odds_schema/test_integration_the_odds_api.py -v` — 10/10 pass ✅
4. `python -m pytest tests/test_the_odds_api.py -v` — 27/27 pass ✅
