# Odds Feed Ingestion Schema (v2)

## Status: Complete ✅

**File:** `odds_feed_schema_v2.py`
**Tests:** 14/14 passing
**Lint:** `ruff check` — 0 errors

## Objective

Create a Pandera schema to validate incoming DataFrame from The Odds API before it reaches the database. This is the gatekeeper for `TheOddsAPI.save_to_db()`.

## Key Findings

### Primary Ingestion Points

| Pipeline | File | Key Function | Schema Used |
|----------|------|-------------|-------------|
| The Odds API (real-time odds) | `plugins/the_odds_api.py` | `TheOddsAPI.save_to_db()` → `_parse_game()` → `fetch_markets()` | `odds_feed_schema_v2.py` (this) |
| Kalshi prediction markets | `plugins/kalshi_markets.py` | `save_to_db()` → `_parse_market()` | `plugins/kalshi_ingestion_schema.py` |
| CSV historical batch | `plugins/csv_processors.py` | Various CSV processors | No Pandera schema (legacy) |

### What `OddsFeedSchemaV2` Validates

#### Hard Failures (HALT ingestion — SchemaErrors raised)

| Check | What it prevents | Why critical |
|-------|-----------------|--------------|
| `game_id` null + regex | Malformed game IDs break DB JOINs | Cross-table dedup relies on game_id |
| `home_team` / `away_team` non-empty | Empty team names corrupt unified_games | Breaks NamingResolver, Elo, UI |
| `sport` ∈ valid list | Unknown sports can't be routed to correct pipeline | Cross-sport query corruption |
| `commence_time` not future | Games that haven't started would enter Elo system | Corrupts rating updates |
| `last_update` not future | Stale odds would perpetually override valid updates | Freezes odds at stale values |
| `home_odds` / `away_odds` ∈ [1.01, 1000.0] | Out-of-range odds produce nonsensical probabilities | Breaks EV calculations |
| `home_prob` + `away_prob` < 1.10 | Overround > 10% indicates data corruption | Breaks Elo rating adjustments |
| `best_home_odds` >= `home_odds` | Aggregation logic bug in _parse_game() | Pipeline logic error, not data issue |
| Spread: both sides present | Orphaned spread lines can't be used | Unusable for statistical modelling |
| Spread: opposite signs | Both teams can't be favourites simultaneously | Fundamental market logic error |
| Spread: half-integer steps | Non-standard spread values indicate parsing bug | Breaks margin-of-victory models |
| Spread ∈ [-30.0, 30.0] | Out-of-range spreads are invalid for major sports | Data integrity |

#### Warnings (LOG AND CONTINUE — SchemaDriftError raised)

| Check | What it detects | Action |
|-------|----------------|--------|
| `sport` distribution shift | API coverage changed (off-season, new sports) | Log, alert Slack #data-pipeline |
| `bet_type` distribution shift | Market type mix changed unexpectedly | Log, alert if persists >3 batches |

### Integration Pattern

In `plugins/the_odds_api.py`'s `save_to_db()`:

```python
from odds_feed_schema_v2 import validate_odds_feed_v2, SchemaDriftError
from pandera.errors import SchemaErrors

df = pd.DataFrame(parsed_markets)
try:
    validated = validate_odds_feed_v2(df)
except SchemaErrors as e:
    logger.critical("Schema violation — halting ingestion: %s", e)
    pagerduty.trigger("odds-ingestion-v2-failure", e)
    raise
except SchemaDriftError as e:
    logger.warning("Distribution drift — continuing: %s", e)
```

## Files

- `odds_feed_schema_v2.py` — The Pandera schema (901 lines)
- `README.md` — This file
