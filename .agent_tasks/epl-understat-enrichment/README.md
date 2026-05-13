# EPL Understat Enrichment Script

## Goal
Create a one-shot script at `scripts/enrich_epl_understat.py` that performs a targeted Understat xG/xGA enrichment pass on existing EPL historical data back to 2021.

## Status
**DONE** — Script created, passes ruff check, dry-run verified against live DB.

## Design Decisions
1. **Uses `UnderstatLeagueClient` directly** (not `SoccerBoxScoreFetcher`) to avoid game_id format parsing issues (EPL_ vs E0_ prefixes).
2. **Processes by season** (Understat API returns all matches per-season). Fetches once per season, builds a lookup dict keyed by `(game_date, home_team, away_team)`, then matches DB rows.
3. **Team name resolution**: Uses the same `NamingResolver.resolve(NamingContext("epl", "kalshi", name))` path as `SoccerBoxScoreFetcher._canonical_epl_team_name()` to ensure consistent naming.
4. **UPDATE only** (not INSERT/upsert) — data already exists in `soccer_team_game_stats_ext`, we only need to set `xg`/`xga` columns.
5. **Progress tracking**: `data/understat_enrichment_progress.json` keys by season start year (e.g. `"2021"` -> `"complete"`). Resume skips completed seasons.
6. **Already-done detection**: Pre-fetches all existing `(game_id, team)` pairs that already have `xg IS NOT NULL` to avoid redundant UPDATEs.

## Key Findings
- 1,849 EPL games need enrichment across 5 seasons (2021-22 through 2025-26)
- 380 games/season for completed seasons, 329 for current (2025-26)
- Understat resolution chain: understat name -> NamingResolver (understat source, falls through) -> NamingResolver (kalshi source) -> kalshi canonical name override

## Files Modified
- `scripts/enrich_epl_understat.py` (new)

## Verification
- `ruff check scripts/enrich_epl_understat.py` — passes
- `mypy scripts/enrich_epl_understat.py --ignore-missing-imports` — clean (only pre-existing error in understat_client.py)
- `python scripts/enrich_epl_understat.py --dry-run --start 2021-08-01` — correctly shows 1,849 games across 5 seasons
