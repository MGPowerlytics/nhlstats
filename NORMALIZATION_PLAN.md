# NHL Data Normalization Plan for DuckDB

## Overview
Transform raw NHL API JSON/CSV data into a normalized relational schema for efficient analysis in DuckDB.

## Current Data Sources

### 1. Play-by-Play JSON (`{game_id}_playbyplay.json`)
- Game metadata (date, venue, teams, etc.)
- All game events/plays (goals, shots, hits, penalties, faceoffs)
- Event details (coordinates, players involved, time)
- Rosters and team info

### 2. Boxscore JSON (`{game_id}_boxscore.json`)
- Player game statistics (goals, assists, TOI, hits, etc.)
- Team statistics (shots, powerplay, faceoffs)
- Game summary and scoring by period
- Goalie statistics

### 3. Shifts CSV/JSON (`{game_id}_shifts.csv`)
- Individual player shifts with start/end times
- Shift duration
- Player and team info

---

## Proposed Normalized Schema

### Core Tables

#### `games`
Primary table for game metadata.
```sql
CREATE TABLE games (
    game_id BIGINT PRIMARY KEY,
    season INTEGER NOT NULL,
    game_type CHAR(2) NOT NULL,  -- '01'=preseason, '02'=regular, '03'=playoffs
    game_date DATE NOT NULL,
    start_time_utc TIMESTAMP NOT NULL,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    venue_name VARCHAR,
    venue_location VARCHAR,
    home_score INTEGER,
    away_score INTEGER,
    game_state VARCHAR,  -- e.g., 'OFF', 'FINAL'
    periods_played INTEGER,
    -- Foreign keys validated later
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
);
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_games_season ON games(season);
```

#### `teams`
Team reference table.
```sql
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    team_abbrev VARCHAR(3) NOT NULL,
    team_name VARCHAR NOT NULL,
    team_common_name VARCHAR,
    logo_url VARCHAR
);
```

#### `players`
Player reference table.
```sql
CREATE TABLE players (
    player_id INTEGER PRIMARY KEY,
    first_name VARCHAR,
    last_name VARCHAR,
    full_name VARCHAR,
    sweater_number INTEGER,
    position VARCHAR(2),  -- 'C', 'LW', 'RW', 'D', 'G'
    headshot_url VARCHAR
);
```

#### `game_events`
Fact table for all game events (plays).
```sql
CREATE TABLE game_events (
    event_id INTEGER NOT NULL,
    game_id BIGINT NOT NULL,
    period INTEGER NOT NULL,
    period_type VARCHAR(3),  -- 'REG', 'OT', 'SO'
    time_in_period VARCHAR(5),  -- 'MM:SS'
    time_remaining VARCHAR(5),  -- 'MM:SS'
    event_type VARCHAR NOT NULL,  -- 'goal', 'shot-on-goal', 'hit', etc.
    team_id INTEGER,
    x_coord DOUBLE,
    y_coord DOUBLE,
    zone_code VARCHAR(3),  -- 'O', 'D', 'N' (offensive, defensive, neutral)
    sort_order INTEGER,
    situation_code VARCHAR(4),  -- strength state
    description TEXT,
    PRIMARY KEY (game_id, event_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);
CREATE INDEX idx_events_game ON game_events(game_id);
CREATE INDEX idx_events_type ON game_events(event_type);
```

#### `event_players`
Bridge table for players involved in events.
```sql
CREATE TABLE event_players (
    game_id BIGINT NOT NULL,
    event_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    role VARCHAR NOT NULL,  -- 'shooter', 'assist', 'goalie', 'hitter', 'hittee', etc.
    PRIMARY KEY (game_id, event_id, player_id, role),
    FOREIGN KEY (game_id, event_id) REFERENCES game_events(game_id, event_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);
```

#### `shots`
Denormalized shot-specific details.
```sql
CREATE TABLE shots (
    game_id BIGINT NOT NULL,
    event_id INTEGER NOT NULL,
    shooter_id INTEGER,
    goalie_id INTEGER,
    shot_type VARCHAR,  -- 'wrist', 'slap', 'snap', 'backhand', etc.
    result VARCHAR NOT NULL,  -- 'goal', 'saved', 'missed', 'blocked'
    x_coord DOUBLE,
    y_coord DOUBLE,
    distance_feet DOUBLE,  -- calculated
    angle_degrees DOUBLE,  -- calculated
    PRIMARY KEY (game_id, event_id),
    FOREIGN KEY (game_id, event_id) REFERENCES game_events(game_id, event_id),
    FOREIGN KEY (shooter_id) REFERENCES players(player_id),
    FOREIGN KEY (goalie_id) REFERENCES players(player_id)
);
```

#### `shifts`
Player shift data.
```sql
CREATE TABLE shifts (
    shift_id BIGINT PRIMARY KEY,
    game_id BIGINT NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    period INTEGER NOT NULL,
    shift_number INTEGER NOT NULL,
    start_time VARCHAR(5),  -- 'MM:SS'
    end_time VARCHAR(5),  -- 'MM:SS'
    duration_seconds INTEGER,
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);
CREATE INDEX idx_shifts_game_player ON shifts(game_id, player_id);
```

#### `player_game_stats`
Aggregated player statistics per game from boxscore.
```sql
CREATE TABLE player_game_stats (
    game_id BIGINT NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    position VARCHAR(2),
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    plus_minus INTEGER DEFAULT 0,
    pim INTEGER DEFAULT 0,  -- penalties in minutes
    hits INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    blocked_shots INTEGER DEFAULT 0,
    giveaways INTEGER DEFAULT 0,
    takeaways INTEGER DEFAULT 0,
    faceoff_pct DOUBLE,
    toi_seconds INTEGER,  -- time on ice
    shifts INTEGER DEFAULT 0,
    powerplay_goals INTEGER DEFAULT 0,
    shorthanded_goals INTEGER DEFAULT 0,
    PRIMARY KEY (game_id, player_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);
CREATE INDEX idx_player_stats_game ON player_game_stats(game_id);
CREATE INDEX idx_player_stats_player ON player_game_stats(player_id);
```

#### `goalie_game_stats`
Goalie-specific statistics per game.
```sql
CREATE TABLE goalie_game_stats (
    game_id BIGINT NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    shots_against INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    save_pct DOUBLE,
    toi_seconds INTEGER,
    PRIMARY KEY (game_id, player_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);
```

---

## Data Transformation Strategy

### 1. Extract Phase
Read raw JSON/CSV files and parse into Python objects.

**From Play-by-Play:**
- Game metadata → `games` table
- Team info → `teams` table
- Roster data → `players` table
- Play data → `game_events`, `event_players`, `shots` tables

**From Boxscore:**
- Player stats → `player_game_stats`, `goalie_game_stats` tables
- Additional team/game info to enrich `games` table

**From Shifts:**
- Shift records → `shifts` table

### 2. Transform Phase

**Data Cleaning:**
- Handle null/missing values (use NULL or 0 appropriately)
- Normalize text fields (trim, case consistency)
- Parse time strings to seconds (e.g., "15:29" → 929)
- Convert coordinate systems if needed

**Calculations:**
- Shot distance from goal: `sqrt((x - goal_x)^2 + (y - goal_y)^2)`
- Shot angle to goal
- Shift duration from start/end times

**Deduplication:**
- Ensure unique player records (upsert strategy)
- Ensure unique team records

### 3. Load Phase
Use DuckDB's bulk insert capabilities for efficiency.

**Load Order (respect foreign keys):**
1. `teams`
2. `players`
3. `games`
4. `game_events`
5. `event_players`
6. `shots`
7. `player_game_stats`
8. `goalie_game_stats`
9. `shifts`

---

## Implementation Plan

### Phase 1: Schema Creation
- [ ] Create `db/schema.sql` with all table definitions
- [ ] Create `db/init_db.py` to initialize DuckDB database

### Phase 2: Data Extraction Module
- [ ] Create `nhl_extract.py` with classes:
  - `GameExtractor` - parse play-by-play JSON
  - `BoxscoreExtractor` - parse boxscore JSON
  - `ShiftExtractor` - parse shifts CSV/JSON

### Phase 3: Data Transformation Module
- [ ] Create `nhl_transform.py` with:
  - Field mapping functions
  - Data cleaning utilities
  - Type conversion helpers
  - Calculated field generators

### Phase 4: DuckDB Loader
- [ ] Create `nhl_load.py` with:
  - `DuckDBLoader` class
  - Bulk insert methods
  - Upsert logic for reference tables
  - Transaction management

### Phase 5: Airflow Integration
- [ ] Add new DAG tasks:
  - `extract_and_transform` task (after downloads)
  - `load_to_duckdb` task (final step)
- [ ] Update requirements.txt with DuckDB

### Phase 6: Analysis Queries
- [ ] Create `queries/` directory with sample analyses:
  - Shot location heatmaps
  - Player performance trends
  - Team statistics aggregations
  - Time on ice analysis

---

## Sample Analysis Queries

```sql
-- Top goal scorers by season
SELECT p.full_name, COUNT(*) as goals, s.season
FROM player_game_stats pgs
JOIN players p ON pgs.player_id = p.player_id
JOIN games g ON pgs.game_id = g.game_id
GROUP BY p.player_id, p.full_name, g.season
ORDER BY goals DESC
LIMIT 20;

-- Shot location heatmap data
SELECT x_coord, y_coord, COUNT(*) as shot_count,
       SUM(CASE WHEN result = 'goal' THEN 1 ELSE 0 END) as goals
FROM shots
WHERE x_coord IS NOT NULL
GROUP BY x_coord, y_coord;

-- Player time on ice by game
SELECT p.full_name, g.game_date, pgs.toi_seconds / 60.0 as toi_minutes
FROM player_game_stats pgs
JOIN players p ON pgs.player_id = p.player_id
JOIN games g ON pgs.game_id = g.game_id
WHERE p.player_id = 8478402  -- Specific player
ORDER BY g.game_date;
```

---

## File Structure
```
nhlstats/
├── dags/
│   ├── nhl_daily_download.py
│   └── nhl_etl_pipeline.py          # NEW: Complete ETL DAG
├── db/
│   ├── schema.sql                    # NEW: DuckDB schema
│   └── init_db.py                    # NEW: DB initialization
├── etl/
│   ├── __init__.py
│   ├── extract.py                    # NEW: Data extraction
│   ├── transform.py                  # NEW: Data transformation
│   └── load.py                       # NEW: DuckDB loading
├── queries/
│   └── analysis_examples.sql         # NEW: Sample queries
├── nhl_game_events.py
├── nhl_shifts.py
├── data/
│   ├── games/
│   ├── shifts/
│   └── nhlstats.duckdb               # NEW: DuckDB database file
└── requirements.txt
```

---

## Next Steps
1. Review and approve schema design
2. Implement extraction/transformation modules
3. Create DuckDB loader
4. Test with sample game data
5. Integrate into Airflow pipeline
6. Build analysis queries/dashboards
