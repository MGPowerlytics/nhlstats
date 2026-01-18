# Hong Kong Horse Racing Data Normalization Plan for DuckDB

## Overview
Transform scraped HKJC race results into a normalized relational schema for analysis alongside NHL data.

## Current Data Source

### Race Results JSON (`{YYYYMMDD}_{VENUE}.json`)
- Race meeting metadata (date, venue)
- Individual race details (class, distance, going, course)
- Horse performance (placing, times, weights, draw)
- Jockey and trainer information
- Dividend/payout data (WIN, PLACE, QUINELLA, etc.)
- Sectional times

---

## Proposed Normalized Schema

### Core Tables

#### `race_meetings`
Top-level meeting/card information.
```sql
CREATE TABLE race_meetings (
    meeting_id VARCHAR PRIMARY KEY,  -- e.g., '20260114_HV'
    meeting_date DATE NOT NULL,
    venue VARCHAR NOT NULL,  -- 'Happy Valley' or 'Sha Tin'
    venue_code CHAR(2) NOT NULL,  -- 'HV' or 'ST'
    total_races INTEGER,
    INDEX idx_meeting_date (meeting_date)
);
```

#### `races`
Individual race information.
```sql
CREATE TABLE races (
    race_id VARCHAR PRIMARY KEY,  -- e.g., '20260114_HV_01'
    meeting_id VARCHAR NOT NULL,
    race_number INTEGER NOT NULL,
    race_date DATE NOT NULL,
    venue_code CHAR(2) NOT NULL,
    race_class INTEGER,  -- Class 1-5
    distance INTEGER,  -- meters
    course CHAR(1),  -- 'A', 'B', 'C'
    going VARCHAR,  -- 'GOOD', 'GOOD TO FIRM', 'YIELDING', etc.
    prize_money INTEGER,
    FOREIGN KEY (meeting_id) REFERENCES race_meetings(meeting_id)
);
CREATE INDEX idx_races_date ON races(race_date);
CREATE INDEX idx_races_venue ON races(venue_code);
CREATE INDEX idx_races_class ON races(race_class);
```

#### `horses`
Horse reference table.
```sql
CREATE TABLE horses (
    horse_id VARCHAR PRIMARY KEY,  -- e.g., 'K103'
    horse_name VARCHAR NOT NULL,
    origin VARCHAR,
    foaling_date DATE,
    color VARCHAR,
    import_type VARCHAR
);
```

#### `jockeys`
Jockey reference table.
```sql
CREATE TABLE jockeys (
    jockey_id VARCHAR PRIMARY KEY,
    jockey_name VARCHAR NOT NULL,
    nationality VARCHAR
);
```

#### `trainers`
Trainer reference table.
```sql
CREATE TABLE trainers (
    trainer_id VARCHAR PRIMARY KEY,
    trainer_name VARCHAR NOT NULL,
    stable_location VARCHAR
);
```

#### `race_results`
Fact table for horse performances in races.
```sql
CREATE TABLE race_results (
    result_id INTEGER PRIMARY KEY,
    race_id VARCHAR NOT NULL,
    horse_id VARCHAR,
    horse_number INTEGER,
    placing INTEGER,
    jockey_id VARCHAR,
    trainer_id VARCHAR,
    actual_weight INTEGER,  -- lbs
    declared_weight INTEGER,  -- lbs (horse body weight)
    draw INTEGER,  -- barrier/gate position
    lengths_behind VARCHAR,  -- e.g., '1-3/4', 'NOSE'
    lengths_behind_numeric DOUBLE,  -- converted to decimal
    finish_time VARCHAR,  -- 'MM:SS.ss'
    finish_time_seconds DOUBLE,
    win_odds DOUBLE,
    running_position VARCHAR,  -- position during race, e.g., '6-6-1-1'
    FOREIGN KEY (race_id) REFERENCES races(race_id),
    FOREIGN KEY (horse_id) REFERENCES horses(horse_id),
    FOREIGN KEY (jockey_id) REFERENCES jockeys(jockey_id),
    FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id)
);
CREATE INDEX idx_results_race ON race_results(race_id);
CREATE INDEX idx_results_horse ON race_results(horse_id);
CREATE INDEX idx_results_jockey ON race_results(jockey_id);
```

#### `sectional_times`
Sectional time splits for races.
```sql
CREATE TABLE sectional_times (
    race_id VARCHAR NOT NULL,
    section_number INTEGER NOT NULL,
    time_seconds DOUBLE NOT NULL,
    PRIMARY KEY (race_id, section_number),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);
```

#### `dividends`
Betting dividend/payout information.
```sql
CREATE TABLE dividends (
    dividend_id INTEGER PRIMARY KEY,
    race_id VARCHAR NOT NULL,
    bet_type VARCHAR NOT NULL,  -- 'WIN', 'PLACE', 'QUINELLA', etc.
    combination VARCHAR,  -- e.g., '3', '3,6', '3,6,4'
    dividend DOUBLE,  -- payout in HKD
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);
CREATE INDEX idx_dividends_race ON dividends(race_id);
CREATE INDEX idx_dividends_type ON dividends(bet_type);
```

---

## Data Transformation Strategy

### 1. Extract Phase
Parse JSON files from scraper output.

### 2. Transform Phase

**Data Cleaning:**
- Parse horse codes from names (e.g., "BLAZING BEAM (K103)" → horse_id: K103)
- Convert lengths behind to numeric (e.g., "1-3/4" → 1.75, "NOSE" → 0.05)
- Parse finish times to seconds (e.g., "1:09.92" → 69.92)
- Extract jockey/trainer IDs from names
- Parse sectional times to floats

**Calculated Fields:**
- Speed ratings
- Beaten margins in seconds
- Class performance metrics

### 3. Load Phase

**Load Order:**
1. `jockeys`
2. `trainers`
3. `horses`
4. `race_meetings`
5. `races`
6. `race_results`
7. `sectional_times`
8. `dividends`

---

## Sample Analysis Queries

```sql
-- Top performing jockeys by strike rate
SELECT j.jockey_name, 
       COUNT(*) as rides,
       SUM(CASE WHEN rr.placing = 1 THEN 1 ELSE 0 END) as wins,
       ROUND(SUM(CASE WHEN rr.placing = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as strike_rate
FROM race_results rr
JOIN jockeys j ON rr.jockey_id = j.jockey_id
JOIN races r ON rr.race_id = r.race_id
WHERE r.race_date >= '2025-01-01'
GROUP BY j.jockey_id, j.jockey_name
HAVING COUNT(*) >= 20
ORDER BY strike_rate DESC;

-- Average winning odds by race class
SELECT r.race_class,
       COUNT(*) as races,
       ROUND(AVG(rr.win_odds), 2) as avg_winner_odds,
       ROUND(MIN(rr.win_odds), 2) as min_odds,
       ROUND(MAX(rr.win_odds), 2) as max_odds
FROM race_results rr
JOIN races r ON rr.race_id = r.race_id
WHERE rr.placing = 1
GROUP BY r.race_class
ORDER BY r.race_class;

-- Horse performance by barrier draw
SELECT rr.draw,
       COUNT(*) as starts,
       SUM(CASE WHEN rr.placing = 1 THEN 1 ELSE 0 END) as wins,
       ROUND(SUM(CASE WHEN rr.placing = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as win_pct
FROM race_results rr
JOIN races r ON rr.race_id = r.race_id
WHERE r.distance = 1200  -- Specific distance
GROUP BY rr.draw
ORDER BY rr.draw;
```

---

## Combined Multi-Sport Schema

The HK racing tables will coexist with NHL tables in the same DuckDB database:

```
nhlstats.duckdb
├── NHL Tables
│   ├── games
│   ├── teams
│   ├── players
│   ├── game_events
│   └── ...
└── Racing Tables
    ├── race_meetings
    ├── races
    ├── horses
    ├── jockeys
    └── ...
```

---

## File Structure Update
```
nhlstats/
├── dags/
│   ├── nhl_daily_download.py
│   ├── hk_racing_daily_download.py    # NEW
│   └── multi_sport_etl.py             # Combined pipeline (future)
├── db/
│   ├── nhl_schema.sql
│   └── hk_racing_schema.sql           # NEW
├── etl/
│   ├── nhl/
│   │   ├── extract.py
│   │   ├── transform.py
│   │   └── load.py
│   └── racing/                        # NEW
│       ├── extract.py
│       ├── transform.py
│       └── load.py
├── hk_racing_scraper.py               # NEW
├── nhl_game_events.py
├── nhl_shifts.py
└── data/
    ├── games/
    ├── shifts/
    ├── hk_racing/                     # NEW
    └── nhlstats.duckdb
```
