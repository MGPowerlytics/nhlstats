# Adding a New Sport

## Required Files

### 1. Elo Rating Module
`plugins/{sport}_elo_rating.py`

```python
class {Sport}EloRating:
    def __init__(self, k_factor=20, home_advantage=100, initial_rating=1500):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings = {}

    def get_rating(self, team: str) -> float: ...
    def predict(self, home_team: str, away_team: str) -> float: ...
    def update(self, home_team: str, away_team: str, home_won: bool) -> dict: ...
    def expected_score(self, rating_a: float, rating_b: float) -> float: ...
```

### 2. Games Downloader
`plugins/{sport}_games.py`

```python
def download_{sport}_games(date: str = None) -> list:
    """Download games from API. Returns list of game dicts."""
    # Fetch from official API
    # Parse into standard format
    return games

def load_{sport}_games_to_db(games: list):
    """Load games into unified_games table."""
    from db_manager import default_db
    # Insert with proper game_id format
```

### 3. DAG Configuration
Add to `SPORTS_CONFIG` in `dags/multi_sport_betting_workflow.py`:

```python
SPORTS_CONFIG = {
    # ... existing sports
    "{sport}": {
        "elo_module": "{sport}_elo_rating",
        "games_module": "{sport}_games",
        "kalshi_function": "fetch_{sport}_markets",
        "elo_threshold": 0.70,  # Tune with lift/gain analysis
    },
}
```

### 4. Kalshi Market Function
Add to `plugins/kalshi_markets.py`:

```python
def fetch_{sport}_markets():
    """Fetch {SPORT} markets from Kalshi."""
    return markets_api.get_markets(
        series_ticker="{SPORT}WIN",
        status="open",
        limit=100
    ).to_dict().get("markets", [])
```

### 5. Team Name Mappings
Update `plugins/naming_resolver.py`:

```python
{SPORT}_TEAMS = {
    "ABC": "Full Team Name",
    # ... all teams
}
```

## Game ID Format

Consistent format: `{SPORT}_{YYYYMMDD}_{HOME}_{AWAY}`

```python
def generate_game_id(sport, date, home, away):
    date_str = date.replace('-', '')
    home_slug = "".join(filter(str.isalnum, home)).upper()
    away_slug = "".join(filter(str.isalnum, away)).upper()
    return f"{sport.upper()}_{date_str}_{home_slug}_{away_slug}"
```

## Validation Checklist

- [ ] Elo class implements all required methods
- [ ] Games download returns proper format
- [ ] Team names resolve correctly
- [ ] Kalshi markets parse properly
- [ ] Data loads to database without errors
- [ ] Lift/gain analysis shows positive lift
- [ ] Tests pass with 85%+ coverage
- [ ] DAG parses without errors

## Testing

```bash
# Test DAG parsing
python dags/multi_sport_betting_workflow.py

# Run sport-specific tests
pytest tests/test_{sport}_*.py -v

# Validate data
python -c "from data_validation import validate_{sport}_data; validate_{sport}_data().print_report()"
```

## Files to Reference

- `plugins/nba_elo_rating.py` - Template for Elo class
- `plugins/nba_games.py` - Template for games downloader
- `plugins/kalshi_markets.py` - Add Kalshi function here
