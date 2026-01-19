# GitHub Copilot Instructions - Multi-Sport Betting System

## Project Overview

This is a **multi-sport betting system** that uses Elo ratings to identify betting opportunities on Kalshi prediction markets. The system covers NBA, NHL, MLB, and NFL and runs as an Airflow DAG.

KEEP THIS PROJECT ORGANIZED, NEAT AND WELL-DOCUMENTED. FOLLOW THE CODING CONVENTIONS BELOW. 
1. Run black on new code
2. DO NOT GENERATE MANUAL DAGRUNS. CLEAR OUT THE TASKS AND LET AIRFLOW HANDLE IT.
3. Add type hints and docstrings
4. Use clear, descriptive names for variables and functions
5. Use google docstring style
6. Place code into well-organized files and directories
7. Document all fixes in the CHANGELOG
8. RUN TESTS AND DATA VALIDATION BEFORE COMMITTING
9. Add tests if we drop below 85% coverage
10. Don't ask if you can or should do something - just do it, following these instructions and best practices

## Technology Stack

- **Python 3.10+**
- **Apache Airflow** - Workflow orchestration
- **DuckDB** - Local analytics database
- **Kalshi API** - Prediction market integration
- **Docker/Docker Compose** - Container orchestration

## Project Structure

```
├── dags/                          # Airflow DAGs
│   └── multi_sport_betting_workflow.py  # Main unified betting DAG
├── plugins/                       # Airflow plugins (Python modules)
│   ├── nba_elo_rating.py          # NBA Elo implementation
│   ├── nhl_elo_rating.py          # NHL Elo implementation
│   ├── mlb_elo_rating.py          # MLB Elo implementation
│   ├── nfl_elo_rating.py          # NFL Elo implementation
│   ├── kalshi_markets.py          # Kalshi API integration
│   ├── *_games.py                 # Game data downloaders
│   └── *_stats.py                 # Statistics modules
├── data/                          # Data directory (auto-created)
│   ├── nhlstats.duckdb            # Main DuckDB database
│   └── {sport}/bets_*.json        # Daily bet recommendations
├── archive/                       # Archived/legacy code (NOT active)
├── config/                        # Airflow configuration
├── docker-compose.yaml            # Airflow setup
├── requirements.txt               # Python dependencies
└── kalshkey                       # Kalshi API credentials
```

## Core Concepts

### Elo Rating System

Elo ratings are the primary prediction method. Each sport has its own implementation with tuned parameters.

**Elo to Probability Conversion:**

The system converts Elo ratings to win probabilities using the standard formula:

$$
P(A) = \frac{1}{1 + 10^{\frac{R_B - R_A}{400}}}
$$

Where:
- $P(A)$ is the probability of the home team winning
- $R_A$ is the Elo rating of the home team (with home advantage added)
- $R_B$ is the Elo rating of the away team

**Sport-Specific Parameters:**

| Sport | K-Factor | Home Advantage | Threshold |
|-------|----------|----------------|-----------|
| NBA   | 20       | 100            | 64%       |
| NHL   | 20       | 100            | 77%       |
| MLB   | 20       | 50             | 62%       |
| NFL   | 20       | 65             | 68%       |

### Edge Calculation

```python
edge = elo_probability - market_probability
```

A bet is recommended when:
1. `elo_prob > threshold` (high confidence in outcome)
2. `edge > 0.05` (at least 5% edge over market)

### Confidence Levels

- **HIGH**: `elo_prob > threshold + 0.10`
- **MEDIUM**: `elo_prob > threshold`

### Lift/Gain Analysis

The system includes a lift/gain analysis tool (`plugins/lift_gain_analysis.py`) that evaluates Elo prediction quality by probability decile.

**Key Metrics by Decile:**
- **Lift**: `actual_win_rate / baseline_win_rate` - How much better than random
- **Gain %**: Cumulative percentage of total wins captured starting from highest confidence
- **Coverage %**: Percentage of total games covered

**Usage:**
```python
from lift_gain_analysis import analyze_sport, main

# Analyze single sport
overall_deciles, season_deciles = analyze_sport('nba')

# Analyze all sports
main()
```

**Output includes:**
- Overall analysis (all historical data)
- Current season to date analysis
- Cumulative home wins and games by decile
- Lift values showing prediction strength

## Coding Conventions

### Python Style

- Use type hints for function signatures
- Docstrings for all public functions (Google style)
- f-strings for string formatting
- Emoji prefixes in print statements for status (✓, ⚠️, 📥, etc.)

### Elo Rating Classes

All Elo implementations follow this interface:

```python
class SportEloRating:
    def __init__(self, k_factor, home_advantage, initial_rating=1500):
        ...
    
    def get_rating(self, team: str) -> float:
        """Get current Elo rating for a team."""
        
    def predict(self, home_team: str, away_team: str) -> float:
        """Predict probability of home team winning (0.0 to 1.0)."""
        
    def update(self, home_team: str, away_team: str, home_won: bool) -> dict:
        """Update ratings after a game. Returns rating changes."""
        
    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Calculate expected score using standard Elo formula."""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
```

### Airflow DAG Tasks

Tasks follow naming convention: `{action}_{sport}`

Example: `download_games_nba`, `update_elo_nhl`, `identify_bets_mlb`

## Important Files

### Active Production Code

- `dags/multi_sport_betting_workflow.py` - Main DAG (runs daily at 10 AM)
- `plugins/*_elo_rating.py` - Elo implementations (4 files)
- `plugins/kalshi_markets.py` - Kalshi API integration
- `plugins/*_games.py` - Game data downloaders

### Configuration

- `docker-compose.yaml` - Airflow services
- `requirements.txt` - Python dependencies
- `kalshkey` - API credentials (do not commit)

### Data Storage

- `data/nhlstats.duckdb` - Historical game data
- `data/{sport}_current_elo_ratings.csv` - Current team ratings
- `data/{sport}/bets_YYYY-MM-DD.json` - Daily bet recommendations

## Common Tasks

### Adding a New Sport

1. Create `plugins/{sport}_elo_rating.py` following existing pattern
2. Create `plugins/{sport}_games.py` for data downloading
3. Add sport config to `SPORTS_CONFIG` in the DAG
4. Add Kalshi fetch function to `kalshi_markets.py`
5. Update `docker-compose.yaml` volume mounts

### Modifying Elo Parameters

Parameters are set in two places:
1. Class defaults in `plugins/{sport}_elo_rating.py`
2. `SPORTS_CONFIG` in `dags/multi_sport_betting_workflow.py`

### Running the DAG Manually

```bash
docker exec $(docker ps -qf "name=scheduler") \
  airflow dags trigger multi_sport_betting_workflow
```

## Database Schema

The DuckDB database (`data/nhlstats.duckdb`) contains historical game data. Key tables:

- `games` - Game results with scores
- `teams` - Team information
- `players` - Player data (for future use)

## Testing

When testing Elo predictions:

```python
from nhl_elo_rating import NHLEloRating

elo = NHLEloRating(k_factor=20, home_advantage=100)
prob = elo.predict("Toronto Maple Leafs", "Boston Bruins")
print(f"Home win probability: {prob:.1%}")
```

### Data Validation

Run comprehensive data validation before production use:

```python
from data_validation import main

# Validate all sports data
main()

# Or validate specific sports
from data_validation import validate_nba_data, validate_nhl_data
report = validate_nba_data()
report.print_report()
```

**Validation checks include:**
- Data presence and row counts
- Date range coverage
- Missing games/dates
- Null values and data quality
- Team coverage (all 30-32 teams)
- Season completeness
- Elo ratings files
- Kalshi integration

## Archived Code

The `archive/` directory contains legacy code that is **not active**:
- XGBoost/LightGBM ML models
- TrueSkill/Glicko-2 rating systems
- Old single-sport DAGs
- Training and analysis scripts

Do not modify archived code unless explicitly asked.

## Key Decisions

1. **Elo over ML**: Simple Elo matches XGBoost accuracy (59%) with 1/30th complexity
2. **Sport-specific thresholds**: Higher variance sports (NHL) need higher thresholds
3. **Unified DAG**: Single DAG handles all sports vs. separate DAGs per sport
4. **DuckDB**: Chosen for local analytics without server overhead

## Environment Variables

- `KALSHI_API_KEY` - Loaded from `kalshkey` file
- Airflow variables set in `docker-compose.yaml`

## Dependencies

Key packages from `requirements.txt`:
- `apache-airflow>=2.8.0`
- `pandas>=2.0.0`
- `duckdb>=0.10.0`
- `kalshi-python` - Kalshi API client
- `requests>=2.31.0`
