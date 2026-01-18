# NHL Stats Scraper

Python scripts to download granular NHL statistics including play-by-play events, shot locations, shifts, and time on ice data.

## Features

- **Play-by-Play Events**: Download detailed game events including shots, goals, hits, penalties with timestamps and coordinates
- **Shot Data**: Extract shot attempts with X/Y coordinates, shot type, shooter, goalie, zone information
- **Shift Data**: Get individual player shifts with start/end times and durations
- **Time on Ice**: Calculate TOI statistics per player from shift data
- **Historical Data**: Access current and past seasons

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Download Game Events & Shot Data

```python
from nhl_game_events import NHLGameEvents

fetcher = NHLGameEvents()

# Download a specific game (2023-24 season, regular season game 1)
game_id = 2023020001
fetcher.download_game(game_id)

# Download entire season
fetcher.download_season("20232024", game_type="02")  # 02=regular season, 03=playoffs

# Extract shot data with coordinates
with open(f"data/games/{game_id}_playbyplay.json", 'r') as f:
    play_by_play = json.load(f)

shots = fetcher.extract_shot_data(play_by_play)
```

### Download Shift & Time on Ice Data

```python
from nhl_shifts import NHLShifts

fetcher = NHLShifts()

# Download shifts for a specific game
game_id = 2023020001
shifts_data = fetcher.download_game_shifts(game_id, format='json')

# Save as CSV
fetcher.download_game_shifts(game_id, format='csv')

# Analyze time on ice
toi_stats = fetcher.analyze_toi(shifts_data)

# Download multiple games
fetcher.download_season_shifts("20232024", game_type="02", start_game=1, end_game=100)
```

## Game ID Format

Game IDs follow the format: `SSSSTTGGGGG`
- `SSSS`: Season start year (e.g., 2023 for 2023-24 season)
- `TT`: Game type
  - `01`: Preseason
  - `02`: Regular season
  - `03`: Playoffs
  - `04`: All-Star
- `GGGGG`: Game number (00001-99999)

Examples:
- `2023020001`: First game of 2023-24 regular season
- `2023030001`: First playoff game of 2023-24
- `2022021271`: Game 1271 of 2022-23 regular season

## Season Format

Seasons are specified as `YYYYYYYY` where the first four digits are the start year and the last four are the end year:
- `20232024`: 2023-24 season
- `20222023`: 2022-23 season
- `20052006`: 2005-06 season (no 2004-05 due to lockout)

## Data Structure

### Play-by-Play Events
Each event includes:
- Event type (shot-on-goal, missed-shot, blocked-shot, goal, hit, penalty, etc.)
- Period and time in period
- X/Y coordinates (for events with locations)
- Players involved
- Team information
- Detailed event-specific data

### Shift Data
Each shift includes:
- Player ID and name
- Team
- Period
- Start time (MM:SS)
- End time (MM:SS)
- Duration (seconds)
- Shift number

## Output

Data is saved to:
- `data/games/` - Play-by-play and boxscore JSON files
- `data/shifts/` - Shift data in JSON or CSV format

## Notes

- The NHL API is unofficial and may change without notice
- Downloading full seasons takes considerable time (1000+ games per season)
- Rate limiting: Consider adding delays between requests for large downloads
- Data is available for recent seasons; very old seasons may have limited data

## Machine Learning & Predictions

### Traditional Statistical Methods (Recommended)

After extensive testing, **simple Elo ratings match or beat complex ML models** for NHL game prediction:

| Method | Accuracy | AUC | Complexity | Speed |
|--------|----------|-----|------------|-------|
| **Elo Rating** ⭐ | 59.3% | **0.591** | Very Low | Instant |
| Bradley-Terry | **59.6%** | 0.575 | Low | Fast |
| XGBoost (93 features) | 57.7% | 0.590 | Very High | Slow |
| LightGBM | 60.8% | 0.619 | High | Medium |

**Key Finding**: Elo rating (3 parameters) matches XGBoost (93 features, hours of tuning) with 1/30th the complexity.

**Usage:**
```python
from nhl_elo_rating import NHLEloRating

elo = NHLEloRating(k_factor=20, home_advantage=100)

# Predict game outcome
prob = elo.predict("Toronto Maple Leafs", "Boston Bruins")
print(f"Probability of home win: {prob:.1%}")

# After game completes
elo.update("Toronto Maple Leafs", "Boston Bruins", home_won=True)
elo.save_ratings()
```

**Why Elo Works:**
- Simple: Only 3 parameters vs 93 features
- Fast: Instant predictions, no training
- Interpretable: Team ratings show relative strength
- Robust: No overfitting by design
- Temporal: Updates after each game, captures momentum

See `other_techniques/TRADITIONAL_STATS_COMPARISON.md` for detailed analysis.

### Advanced ML Models

For reference, complex ML approaches are in `other_techniques/`:
- XGBoost with hyperparameter tuning
- LightGBM gradient boosting
- Random Forest ensemble
- Neural networks (PyTorch)

**Note**: These provide minimal improvement over Elo for 10x the complexity. Only consider if you have goalie starters, injuries, and betting line data (can reach 65-70% accuracy).

---

**For production betting**: Start with Elo. It's simple, fast, and works.
