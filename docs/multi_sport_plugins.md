# Multi-Sport Data Collection Plugins

Comprehensive data fetchers for MLB, NBA, and NFL with granular play-by-play statistics.

## Overview

All plugins are located in the `plugins/` directory and provide standardized interfaces for collecting official sports data.

## MLB - Baseball Stats (`plugins/mlb_stats.py`)

### Data Sources
- **MLB Stats API**: Official MLB play-by-play and statistics
- **Baseball Savant**: Statcast pitch tracking data

### Features
- ✅ Schedule retrieval by date
- ✅ Play-by-play data
- ✅ Pitch-by-pitch tracking (velocity, spin, location)
- ✅ Game boxscores
- ✅ Live game feeds
- ✅ Statcast metrics (launch angle, exit velocity, etc.)

### Data Granularity
- **Pitch level**: Every pitch with velocity, type, location, outcome
- **Play level**: All at-bats, hits, outs, baserunning
- **Game level**: Complete boxscores and statistics

### Sample Usage
```python
from plugins.mlb_stats import MLBStatsFetcher

fetcher = MLBStatsFetcher()

# Get yesterday's games
games = fetcher.download_daily_games()

# Get specific game
game_data = fetcher.download_game(game_pk=745391)

# Extract pitch data
pitches = fetcher.extract_pitch_data(game_data['feed'])
```

### Test Results
✅ Schedule API working
✅ Game feed retrieval (279 pitches captured)
✅ Pitch tracking data (speed, type, coordinates)

---

## NBA - Basketball Stats (`plugins/nba_stats.py`)

### Data Sources
- **NBA Stats API**: Official NBA play-by-play and advanced metrics

### Features
- ✅ Daily scoreboard
- ✅ Play-by-play data
- ✅ Shot chart with coordinates
- ✅ Traditional box scores
- ✅ Advanced statistics (usage%, +/-, etc.)
- ✅ Player tracking data

### Data Granularity
- **Shot level**: Every shot with X/Y coordinates, distance, player, result
- **Play level**: All possessions, turnovers, rebounds, fouls
- **Game level**: Complete box scores and advanced metrics

### Sample Usage
```python
from plugins.nba_stats import NBAStatsFetcher

fetcher = NBAStatsFetcher()

# Get yesterday's games
games = fetcher.download_daily_games()

# Get specific game
game_data = fetcher.download_game(game_id='0022300500')

# Extract shot data
shots = fetcher.extract_shot_data(game_data['shot_chart'])
```

### Test Results
✅ Scoreboard retrieval (11 games found)
✅ Shot chart data (173 shots with coordinates)
✅ Player and shot location tracking

---

## NFL - Football Stats (`plugins/nfl_stats.py`)

### Data Sources
- **nflfastR**: Comprehensive NFL play-by-play (via nfl_data_py)
- **Historical data**: Back to 1999

### Features
- ✅ Schedule by season
- ✅ Play-by-play data (all plays)
- ✅ Weekly player statistics
- ✅ Seasonal aggregations
- ✅ Roster data
- ✅ Next Gen Stats (player tracking)
- ✅ Injury reports
- ✅ Depth charts

### Data Granularity
- **Play level**: Every snap with down, distance, result, EPA, CPOE
- **Player level**: All touches, targets, tackles
- **Game level**: Complete stats and advanced metrics

### Sample Usage
```python
from plugins.nfl_stats import NFLStatsFetcher

fetcher = NFLStatsFetcher()

# Get full season data
season_data = fetcher.download_season(2023)

# Get specific week
week_pbp = fetcher.download_week_games(season=2023, week=1)

# Extract passing stats
passing = fetcher.extract_passing_stats(week_pbp)
```

### Test Results
✅ Season schedule retrieval
✅ Play-by-play data access
✅ Statistical aggregations (passing, rushing)

---

## Installation

```bash
pip install -r requirements.txt
```

### Required Packages
- `requests` - HTTP requests
- `pandas` - Data manipulation
- `nfl-data-py` - NFL data access

---

## Data Storage

### Default Output Structure
```
data/
├── mlb/
│   ├── {game_pk}_playbyplay.json
│   ├── {game_pk}_feed.json
│   └── {game_pk}_boxscore.json
├── nba/
│   ├── {game_id}_playbyplay.json
│   ├── {game_id}_shotchart.json
│   ├── {game_id}_boxscore.json
│   └── {game_id}_advanced.json
└── nfl/
    ├── {season}_schedule.csv
    ├── {season}_playbyplay.csv
    ├── {season}_weekly_stats.csv
    └── {season}_rosters.csv
```

---

## Testing

Each plugin includes built-in tests:

```bash
# Test MLB fetcher
python3 plugins/mlb_stats.py

# Test NBA fetcher
python3 plugins/nba_stats.py

# Test NFL fetcher
python3 plugins/nfl_stats.py
```

---

## API Rate Limits & Best Practices

### MLB
- No official rate limits documented
- Recommend 1-2 second delays between requests
- Use during off-peak hours for bulk downloads

### NBA
- Rate limited (exact limits undocumented)
- Implement 0.6 second delay between requests
- May block cloud IPs (works from local connections)
- Use proper headers to avoid 403 errors

### NFL (nflfastR)
- No rate limits (static data files)
- Fast bulk downloads supported
- Data updated nightly during season
- Historical data back to 1999 available

---

## Data Freshness

| Sport | Update Frequency | Delay After Game |
|-------|-----------------|------------------|
| MLB   | Real-time       | ~5-15 minutes    |
| NBA   | Real-time       | ~5-15 minutes    |
| NFL   | Daily (season)  | Next day (nightly update) |

---

## Advanced Features

### MLB
- **Statcast metrics**: Exit velocity, launch angle, spin rate
- **Pitch tracking**: Full trajectory data
- **Defensive positioning**: Shift data available

### NBA
- **Shot charts**: Precise X/Y coordinates
- **Player tracking**: Speed, distance traveled
- **Matchup data**: Defender info on shots

### NFL
- **EPA (Expected Points Added)**: Advanced play value
- **CPOE (Completion % Over Expected)**: QB accuracy metric
- **Next Gen Stats**: Player speed and separation
- **Win probability**: Live win% by play

---

## Future Enhancements

### Planned Features
- [ ] Airflow DAGs for automated daily collection
- [ ] DuckDB schema and ETL pipeline
- [ ] Historical data backfill scripts
- [ ] Real-time streaming during live games
- [ ] Cross-sport analytics queries

### Data Normalization
- [ ] Unified event schema across sports
- [ ] Player/team reference tables
- [ ] Performance metrics standardization
- [ ] Shot/scoring location normalization

---

## Error Handling

All fetchers include:
- Automatic retries with exponential backoff
- Graceful handling of missing data
- Detailed error logging
- File-based data persistence (no data loss on errors)

---

## Contributing

To add a new sport:

1. Create `plugins/{sport}_stats.py`
2. Implement `download_daily_games()` method
3. Add data extraction methods
4. Include test function
5. Update this README

---

## References

### MLB
- [MLB Stats API Documentation](https://statsapi.mlb.com/)
- [Baseball Savant](https://baseballsavant.mlb.com/)
- [Statcast Search](https://baseballsavant.mlb.com/statcast_search)

### NBA
- [NBA Stats API](https://stats.nba.com/)
- [nba_api Documentation](https://github.com/swar/nba_api)

### NFL
- [nflfastR Documentation](https://nflfastr.com/)
- [nfl-data-py on PyPI](https://pypi.org/project/nfl-data-py/)
- [Field Descriptions](https://www.nflfastr.com/articles/field_descriptions.html)

---

## License

These plugins interface with official sports APIs. Respect terms of service and rate limits.
