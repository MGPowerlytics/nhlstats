# Team Game Stats Column Specification

**Plan**: 2026-04-17-recon-stats-backfill
**Status**: Wave 1 scaffold — exact columns finalized in Wave 2
**Last updated**: 2026-04-17

---

## Overview

This document defines the canonical column contracts for:
- `team_game_stats` — core per-game team row (all sports)
- Per-sport extension tables — sport-specific box-score columns
- `tennis_player_match_stats` — player-level match stats (ATP/WTA)
- `bet_reconciliation_audit` — immutable append-only audit log for placed_bets corrections

All dollar amounts stored as NUMERIC(18,6). All percentages stored as NUMERIC(5,4)
(e.g., 0.4500 = 45.00%). Possession/pace in possessions-per-48 (basketball) or
possessions-per-game (other). Durations in seconds (integer).

---

## 1. `team_game_stats` — Core Table (All Sports)

**Primary Key**: `(game_id, team)`
**Foreign Key**: `game_id → unified_games(game_id)`
**Indexes**:
- `idx_tgs_sport_date ON (sport, game_date)`
- `idx_tgs_team_date ON (team, game_date)`
- `idx_tgs_sport_season ON (sport, season)`

| Column          | Type                        | Nullable | Meaning                                              | Derivation Source                           |
|-----------------|-----------------------------|----------|------------------------------------------------------|---------------------------------------------|
| `game_id`       | VARCHAR                     | NOT NULL | Unique game identifier (matches unified_games)       | upstream game downloader                    |
| `sport`         | VARCHAR                     | NOT NULL | Sport code: NBA, NHL, MLB, NFL, EPL, Ligue1, NCAAB, WNCAAB, Tennis | upstream game downloader         |
| `team`          | VARCHAR                     | NOT NULL | Canonical team name (same normalisation as Elo)      | upstream game downloader                    |
| `opponent`      | VARCHAR                     | NOT NULL | Canonical opponent name                              | upstream game downloader                    |
| `is_home`       | BOOLEAN                     | NOT NULL | TRUE if this row is the home team                    | derived from unified_games.home_team_name   |
| `game_date`     | DATE                        | NOT NULL | Local date the game was played (YYYY-MM-DD)          | upstream game downloader                    |
| `season`        | VARCHAR                     | NOT NULL | Season identifier (e.g., "2023-24" or "2024")        | upstream game downloader                    |
| `points_for`    | INTEGER                     | YES      | Goals/runs/points scored by this team                | raw box score                               |
| `points_against`| INTEGER                     | YES      | Goals/runs/points scored by opponent                 | raw box score                               |
| `won`           | BOOLEAN                     | YES      | TRUE if this team won the game                       | derived from points_for > points_against    |
| `off_rating`    | NUMERIC(6,2)                | YES      | Offensive rating (pts per 100 possessions; basketball) or NULL | advanced derivation          |
| `def_rating`    | NUMERIC(6,2)                | YES      | Defensive rating (pts allowed per 100 possessions; basketball) or NULL | advanced derivation    |
| `pace`          | NUMERIC(6,2)                | YES      | Possessions per 48 min (basketball) or NULL          | advanced derivation                         |
| `margin`        | INTEGER                     | YES      | points_for − points_against (signed)                 | derived                                     |
| `created_at`    | TIMESTAMP                   | NOT NULL | Row insert time                                      | DEFAULT NOW()                               |
| `updated_at`    | TIMESTAMP                   | NOT NULL | Row last update time                                 | DEFAULT NOW(); updated on upsert            |

---

## 2. Extension Tables

### 2a. `nba_team_game_stats_ext`

**Primary Key**: `(game_id, team)`
**Foreign Key**: `(game_id, team) → team_game_stats(game_id, team)`
**Source**: nba_api (free, public)

| Column              | Type          | Nullable | Meaning                                      |
|---------------------|---------------|----------|----------------------------------------------|
| `game_id`           | VARCHAR       | NOT NULL | FK to team_game_stats                        |
| `team`              | VARCHAR       | NOT NULL | FK to team_game_stats                        |
| `fg_pct`            | NUMERIC(5,4)  | YES      | Field goal percentage                        |
| `fg3m`              | INTEGER       | YES      | 3-point field goals made                     |
| `fg3a`              | INTEGER       | YES      | 3-point field goals attempted                |
| `fg3_pct`           | NUMERIC(5,4)  | YES      | 3-point percentage                           |
| `ast`               | INTEGER       | YES      | Assists                                      |
| `reb`               | INTEGER       | YES      | Total rebounds                               |
| `oreb`              | INTEGER       | YES      | Offensive rebounds                           |
| `dreb`              | INTEGER       | YES      | Defensive rebounds                           |
| `stl`               | INTEGER       | YES      | Steals                                       |
| `blk`               | INTEGER       | YES      | Blocks                                       |
| `tov`               | INTEGER       | YES      | Turnovers                                    |
| `pf`                | INTEGER       | YES      | Personal fouls                               |
| `ts_pct`            | NUMERIC(5,4)  | YES      | True shooting % = pts / (2*(fga + 0.44*fta)) |
| `efg_pct`           | NUMERIC(5,4)  | YES      | eFG% = (fg + 0.5*fg3m) / fga                |
| `usage_pct`         | NUMERIC(5,4)  | YES      | Team usage rate proxy                        |

### 2b. `nhl_team_game_stats_ext`

**Primary Key**: `(game_id, team)`
**Foreign Key**: `(game_id, team) → team_game_stats(game_id, team)`
**Source**: NHL Stats API (free)

| Column              | Type          | Nullable | Meaning                                      |
|---------------------|---------------|----------|----------------------------------------------|
| `game_id`           | VARCHAR       | NOT NULL | FK to team_game_stats                        |
| `team`              | VARCHAR       | NOT NULL | FK to team_game_stats                        |
| `shots`             | INTEGER       | YES      | Total shots on goal attempted                |
| `sog`               | INTEGER       | YES      | Shots on goal (on net)                       |
| `hits`              | INTEGER       | YES      | Body checks / hits                           |
| `blocks`            | INTEGER       | YES      | Shots blocked                                |
| `pim`               | INTEGER       | YES      | Penalty minutes                              |
| `faceoff_pct`       | NUMERIC(5,4)  | YES      | Faceoff win percentage                       |
| `pp_goals`          | INTEGER       | YES      | Power play goals                             |
| `pp_opportunities`  | INTEGER       | YES      | Power play opportunities                     |
| `pp_pct`            | NUMERIC(5,4)  | YES      | Power play percentage                        |
| `pk_goals_against`  | INTEGER       | YES      | Goals allowed while short-handed             |
| `pk_opportunities`  | INTEGER       | YES      | Penalty kill opportunities faced             |
| `pk_pct`            | NUMERIC(5,4)  | YES      | Penalty kill percentage                      |
| `shooting_pct`      | NUMERIC(5,4)  | YES      | goals / shots on goal                        |

### 2c. `mlb_team_game_stats_ext`

**Primary Key**: `(game_id, team)`
**Foreign Key**: `(game_id, team) → team_game_stats(game_id, team)`
**Source**: MLB Stats API (free)

| Column        | Type          | Nullable | Meaning                                      |
|---------------|---------------|----------|----------------------------------------------|
| `game_id`     | VARCHAR       | NOT NULL | FK to team_game_stats                        |
| `team`        | VARCHAR       | NOT NULL | FK to team_game_stats                        |
| `hits`        | INTEGER       | YES      | Total hits                                   |
| `errors`      | INTEGER       | YES      | Fielding errors                              |
| `lob`         | INTEGER       | YES      | Left on base                                 |
| `doubles`     | INTEGER       | YES      | Extra base doubles                           |
| `triples`     | INTEGER       | YES      | Triples                                      |
| `home_runs`   | INTEGER       | YES      | Home runs                                    |
| `rbi`         | INTEGER       | YES      | Runs batted in                               |
| `stolen_bases`| INTEGER       | YES      | Stolen bases                                 |
| `strikeouts`  | INTEGER       | YES      | Batter strikeouts                            |
| `walks`       | INTEGER       | YES      | Walks (BB)                                   |
| `at_bats`     | INTEGER       | YES      | At-bats                                      |
| `obp`         | NUMERIC(5,4)  | YES      | On-base percentage                           |
| `slg`         | NUMERIC(5,4)  | YES      | Slugging percentage                          |
| `ops`         | NUMERIC(5,4)  | YES      | OPS = OBP + SLG                              |
| `woba`        | NUMERIC(5,4)  | YES      | Weighted on-base average (if available)      |
| `era`         | NUMERIC(6,2)  | YES      | Starting pitcher ERA (game-day)              |

### 2d. `nfl_team_game_stats_ext`

**Primary Key**: `(game_id, team)`
**Foreign Key**: `(game_id, team) → team_game_stats(game_id, team)`
**Source**: NFL public API / pro-football-reference scrape

| Column                  | Type          | Nullable | Meaning                                         |
|-------------------------|---------------|----------|-------------------------------------------------|
| `game_id`               | VARCHAR       | NOT NULL | FK to team_game_stats                           |
| `team`                  | VARCHAR       | NOT NULL | FK to team_game_stats                           |
| `passing_yards`         | INTEGER       | YES      | Net passing yards                               |
| `passing_tds`           | INTEGER       | YES      | Passing touchdowns                              |
| `passing_ints`          | INTEGER       | YES      | Interceptions thrown                            |
| `rushing_yards`         | INTEGER       | YES      | Net rushing yards                               |
| `rushing_tds`           | INTEGER       | YES      | Rushing touchdowns                              |
| `rushing_attempts`      | INTEGER       | YES      | Rushing attempts                                |
| `total_yards`           | INTEGER       | YES      | Total net yards                                 |
| `turnovers`             | INTEGER       | YES      | Total turnovers (fumbles lost + ints)           |
| `third_down_conversions`| INTEGER       | YES      | Third down conversions                          |
| `third_down_attempts`   | INTEGER       | YES      | Third down attempts                             |
| `third_down_pct`        | NUMERIC(5,4)  | YES      | Third down conversion rate                      |
| `time_of_possession`    | INTEGER       | YES      | Time of possession in seconds                   |
| `penalties`             | INTEGER       | YES      | Penalty count                                   |
| `penalty_yards`         | INTEGER       | YES      | Penalty yards                                   |
| `sacks_allowed`         | INTEGER       | YES      | Sacks allowed (for offense row)                 |
| `first_downs`           | INTEGER       | YES      | Total first downs                               |

### 2e. `soccer_team_game_stats_ext`

Shared by EPL and Ligue 1 (sport column in core table disambiguates).

**Primary Key**: `(game_id, team)`
**Foreign Key**: `(game_id, team) → team_game_stats(game_id, team)`
**Source**: FBRef (User-Agent: nhlstats-research-bot/1.0, 3s crawl delay) or football-data.co.uk

| Column              | Type          | Nullable | Meaning                                         |
|---------------------|---------------|----------|-------------------------------------------------|
| `game_id`           | VARCHAR       | NOT NULL | FK to team_game_stats                           |
| `team`              | VARCHAR       | NOT NULL | FK to team_game_stats                           |
| `shots`             | INTEGER       | YES      | Total shots                                     |
| `shots_on_target`   | INTEGER       | YES      | Shots on target                                 |
| `possession_pct`    | NUMERIC(5,4)  | YES      | Ball possession percentage (0.0–1.0)            |
| `passes`            | INTEGER       | YES      | Total passes attempted                          |
| `pass_accuracy`     | NUMERIC(5,4)  | YES      | Pass completion rate                            |
| `xg`                | NUMERIC(6,3)  | YES      | Expected goals (if available from FBRef)        |
| `xga`               | NUMERIC(6,3)  | YES      | Expected goals against                          |
| `fouls`             | INTEGER       | YES      | Fouls committed                                 |
| `yellow_cards`      | INTEGER       | YES      | Yellow cards received                           |
| `red_cards`         | INTEGER       | YES      | Red cards received                              |
| `corners`           | INTEGER       | YES      | Corner kicks                                    |
| `offsides`          | INTEGER       | YES      | Offsides                                        |
| `saves`             | INTEGER       | YES      | Goalkeeper saves                                |

### 2f. `ncaab_team_game_stats_ext` and `wncaab_team_game_stats_ext`

Mirror NBA columns; simpler subset (no usage_pct). Both tables share the same schema.

**Primary Key**: `(game_id, team)`
**Foreign Key**: `(game_id, team) → team_game_stats(game_id, team)`
**Source**: ESPN / Sports Reference CBB

| Column      | Type          | Nullable | Meaning                                      |
|-------------|---------------|----------|----------------------------------------------|
| `game_id`   | VARCHAR       | NOT NULL | FK to team_game_stats                        |
| `team`      | VARCHAR       | NOT NULL | FK to team_game_stats                        |
| `fg_pct`    | NUMERIC(5,4)  | YES      | Field goal percentage                        |
| `fg3m`      | INTEGER       | YES      | 3-point field goals made                     |
| `fg3a`      | INTEGER       | YES      | 3-point field goals attempted                |
| `fg3_pct`   | NUMERIC(5,4)  | YES      | 3-point percentage                           |
| `ast`       | INTEGER       | YES      | Assists                                      |
| `reb`       | INTEGER       | YES      | Total rebounds                               |
| `stl`       | INTEGER       | YES      | Steals                                       |
| `blk`       | INTEGER       | YES      | Blocks                                       |
| `tov`       | INTEGER       | YES      | Turnovers                                    |
| `pf`        | INTEGER       | YES      | Personal fouls                               |
| `ts_pct`    | NUMERIC(5,4)  | YES      | True shooting %                              |
| `efg_pct`   | NUMERIC(5,4)  | YES      | eFG%                                         |

---

## 3. `tennis_player_match_stats`

**Primary Key**: `(game_id, player_name)`
**Foreign Key**: `game_id → unified_games(game_id)`
**Indexes**:
- `idx_tpms_game_id ON (game_id)`
- `idx_tpms_player ON (player_name)`

| Column                    | Type          | Nullable | Meaning                                            |
|---------------------------|---------------|----------|----------------------------------------------------|
| `game_id`                 | VARCHAR       | NOT NULL | Match identifier (matches unified_games/tennis_games) |
| `player_name`             | VARCHAR       | NOT NULL | Canonical player name (same normalisation as Elo)  |
| `aces`                    | INTEGER       | YES      | Aces served                                        |
| `double_faults`           | INTEGER       | YES      | Double faults                                      |
| `first_serve_pct`         | NUMERIC(5,4)  | YES      | First serve in percentage                          |
| `first_serve_won_pct`     | NUMERIC(5,4)  | YES      | Points won on first serve                          |
| `second_serve_won_pct`    | NUMERIC(5,4)  | YES      | Points won on second serve                         |
| `break_points_saved`      | INTEGER       | YES      | Break points saved                                 |
| `break_points_faced`      | INTEGER       | YES      | Break points faced                                 |
| `winners`                 | INTEGER       | YES      | Winners hit                                        |
| `unforced_errors`         | INTEGER       | YES      | Unforced errors                                    |
| `sets_won`                | INTEGER       | YES      | Sets won in this match                             |
| `games_won`               | INTEGER       | YES      | Games won across all sets                          |
| `won`                     | BOOLEAN       | YES      | TRUE if this player won the match                  |
| `created_at`              | TIMESTAMP     | NOT NULL | Row insert time (DEFAULT NOW())                    |

---

## 4. `bet_reconciliation_audit`

**Primary Key**: `audit_id SERIAL`
**Indexes**:
- `idx_bra_bet_id ON (bet_id)`
- `idx_bra_reconciled_at ON (reconciled_at)`

Append-only. Rows are never updated or deleted.

| Column              | Type          | Nullable | Meaning                                                          |
|---------------------|---------------|----------|------------------------------------------------------------------|
| `audit_id`          | SERIAL        | NOT NULL | Auto-incrementing surrogate PK                                   |
| `bet_id`            | VARCHAR       | NOT NULL | References placed_bets.bet_id (no FK to allow orphan records)    |
| `field_changed`     | VARCHAR       | NOT NULL | Column name in placed_bets that was corrected                    |
| `old_value`         | TEXT          | YES      | Value before correction (serialised as text)                     |
| `new_value`         | TEXT          | YES      | Value after correction (serialised as text)                      |
| `source`            | VARCHAR       | NOT NULL | Data source that triggered correction (e.g., "kalshi_api")      |
| `reconciled_at`     | TIMESTAMP     | NOT NULL | When the correction was applied (DEFAULT NOW())                  |
| `reason`            | TEXT          | YES      | Human-readable description of discrepancy                        |
| `discrepancy_type`  | VARCHAR       | YES      | Category: status_mismatch, price_drift, fee_correction, etc.     |
| `run_id`            | VARCHAR       | YES      | DAG run ID that triggered reconciliation (for traceability)      |

---

## Index Plan Summary

| Table                         | Index                              | Pattern                              |
|-------------------------------|------------------------------------|--------------------------------------|
| `team_game_stats`             | `(sport, game_date)`               | Filter by sport and date range       |
| `team_game_stats`             | `(team, game_date)`                | Team timeline queries                |
| `team_game_stats`             | `(sport, season)`                  | Season aggregations                  |
| `tennis_player_match_stats`   | `(game_id)`                        | Match lookup                         |
| `tennis_player_match_stats`   | `(player_name)`                    | Player timeline                      |
| `bet_reconciliation_audit`    | `(bet_id)`                         | Per-bet audit history                |
| `bet_reconciliation_audit`    | `(reconciled_at)`                  | Time-range reconciliation reports    |

---

## Query Patterns

```sql
-- All team-game stats for a sport in a date range
SELECT * FROM team_game_stats
WHERE sport = 'NBA' AND game_date BETWEEN '2024-01-01' AND '2024-04-01';

-- Join core + extension for NBA
SELECT t.*, e.*
FROM team_game_stats t
JOIN nba_team_game_stats_ext e USING (game_id, team)
WHERE t.sport = 'NBA' AND t.season = '2023-24';

-- Full audit trail for a bet
SELECT * FROM bet_reconciliation_audit
WHERE bet_id = 'BET_12345'
ORDER BY reconciled_at;
```
