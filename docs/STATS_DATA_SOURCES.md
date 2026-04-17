# Stats Data Sources

Documentation for all external data sources used in the historical and daily stats
ingestion pipeline.  All sources listed here are **public** (no paid API key required)
unless explicitly noted.

---

## NBA — `nba_api`

| Property | Value |
|---|---|
| Library | `nba_api>=1.4.0` (PyPI) |
| Base URL | `https://stats.nba.com/stats/` |
| Auth | None (public endpoint) |
| Rate limit | ~1 req / 1–2 s recommended; the library handles retry internally |
| Key endpoints | `boxscoretraditionalv2`, `boxscoreadvancedv2`, `leaguegamefinder` |
| Attribution | © NBA.com — data used for non-commercial research |
| Notes | Requires a browser-like `User-Agent` and `Referer: https://stats.nba.com` header to avoid 403s |

---

## NHL — NHL Stats API (official)

| Property | Value |
|---|---|
| Base URL | `https://api-web.nhle.com/v1/` |
| Auth | None (public endpoint) |
| Rate limit | No official limit; use ≤ 2 req / s as courtesy |
| Key endpoints | `/gamecenter/{game_id}/boxscore`, `/schedule/{date}` |
| Attribution | © NHL.com — data used for non-commercial research |
| Notes | New API (post-2023 season); game IDs follow `YYYY0TGGGG` format |

---

## MLB — MLB Stats API (official)

| Property | Value |
|---|---|
| Base URL | `https://statsapi.mlb.com/api/v1/` |
| Auth | None (public endpoint) |
| Rate limit | No official limit; use ≤ 2 req / s as courtesy |
| Key endpoints | `/game/{game_pk}/boxscore`, `/schedule` |
| Attribution | © MLB.com — data used for non-commercial research |

---

## NFL — `nfl_data_py`

| Property | Value |
|---|---|
| Library | `nfl_data_py>=0.3.0` (PyPI) |
| Backing store | nflfastR GitHub releases (parquet files) |
| Auth | None (public GitHub Releases) |
| Rate limit | Parquet bulk download; limit to one concurrent download |
| Key data | Play-by-play, team game logs, advanced box scores |
| Attribution | © nflfastR project (MIT licence) |

---

## Soccer (EPL / Ligue 1) — FBRef

| Property | Value |
|---|---|
| Base URL | `https://fbref.com/en/comps/` |
| Auth | None (public scraping) |
| **User-Agent** | `nhlstats-research-bot/1.0 (+https://github.com/<placeholder>)` |
| Rate limit | **Strict: 1 req / 4 s minimum**; FBRef blocks aggressive scrapers |
| Key pages | Match logs, squad season stats |
| Attribution | Data from FBRef.com (StatHead / Sports-Reference LLC) |
| Notes | Always set a descriptive `User-Agent`; cache responses aggressively to avoid repeat fetches |

---

## College Basketball (NCAAB / WNCAAB) — Sports Reference CBB

| Property | Value |
|---|---|
| Base URL | `https://www.sports-reference.com/cbb/` |
| Auth | None (public scraping) |
| **User-Agent** | `nhlstats-research-bot/1.0 (+https://github.com/<placeholder>)` |
| Rate limit | 1 req / 4 s minimum (same Sports-Reference infrastructure as FBRef) |
| Key pages | Game box scores, team season pages |
| Attribution | Data from Sports-Reference.com |

---

## Tennis — Tennis Abstract / ATP / WTA

| Property | Value |
|---|---|
| Base URL | `https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/` and `tennis_wta` |
| Auth | None (public GitHub raw files) |
| Rate limit | None enforced; reasonable courtesy delays apply |
| Key data | Match results CSVs by year (`atp_matches_YYYY.csv`, `wta_matches_YYYY.csv`) |
| Attribution | Data by Jeff Sackmann / Tennis Abstract (CC BY-NC-SA 4.0) |

---

## Kalshi — Prediction Markets

| Property | Value |
|---|---|
| Base URL | `https://trading-api.kalshi.com/trade-api/v2/` |
| Auth | **RSA private-key** (`KalshiConfig.from_kalshkey()`); key stored in `kalshkey` file |
| Rate limit | See Kalshi API docs; ~10 req / s for market data |
| Key endpoints | `/markets`, `/portfolio/positions`, `/portfolio/orders` |
| Notes | Credentials loaded from `kalshkey` (local) or `/opt/airflow/kalshkey` (Docker) |

---

## Rate-Limit Summary

| Pool name | Source | Slots | Effective rate |
|---|---|---|---|
| `stats_nba_pool` | NBA Stats API | 3 | ~1 req / s |
| `stats_nhl_pool` | NHL API | 1 | ~0.5 req / s |
| `stats_mlb_pool` | MLB Stats API | 2 | ~1 req / s |
| `stats_nfl_pool` | nfl_data_py | 2 | Bulk parquet |
| `stats_fbref_pool` | FBRef / Sports-Ref | 1 | 1 req / 4 s |
| `stats_cbb_pool` | Sports-Ref CBB | 2 | 1 req / 4 s |
| `stats_tennis_pool` | Tennis Abstract | 1 | Bulk CSV |

---

*Last updated: 2026-04-17*
