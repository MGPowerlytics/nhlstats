# GitHub Copilot Instructions - Multi-Sport Betting System

## Project Overview

This is a **multi-sport betting system** that uses Elo ratings to identify betting opportunities on Kalshi prediction markets. The system covers **9 sports**: NBA, NHL, MLB, NFL, EPL, Tennis, NCAAB, WNCAAB, Ligue1 and runs as an Airflow DAG.

## ✅ Unified Elo Engine - COMPLETED

**Status**: ✅ **COMPLETED** - All 9 sport-specific Elo classes have been successfully refactored to inherit from the unified `BaseEloRating` abstract class. All tests passing.

**Key Features**:
- **Consistent Interface**: All sports implement the same 5 abstract methods: `predict()`, `update()`, `get_rating()`, `expected_score()`, `get_all_ratings()`
- **Sport-Specific Adaptations**:
- **Team Sports** (NBA, NHL, MLB, NFL, NCAAB, WNCAAB): Standard home/away interface
- **Soccer** (EPL, Ligue1): 3-way outcome support with Gaussian draw probability
- **Tennis**: Player-based interface with ATP/WTA separation and name normalization
- **Backward Compatibility**: All existing tests pass, `legacy_update()` methods added where needed
- **Code Organization**: All Elo code in `plugins/elo/` directory with clean imports

**Location**: `plugins/elo/base_elo_rating.py` defines the abstract interface

ONCE YOU ARE ASSIGNED A TASK, NEVER, EVER, EVER BOTHER THE PROJECT OWNER UNTIL YOU HAVE COMPLETED THE TASK TO THE BEST OF YOUR ABILITY AND HAVE READ ALL RELEVANT DOCUMENTATION. THIS IS YOUR #1 RESPONSIBILITY AND RULE. YOU DO NOT NEED PERMISSION TO COMPLETE YOUR TASK, I AM NOT YOUR MOTHER. JUST DO IT. IF YOU DON'T KNOW HOW, FIGURE IT OUT YOURSELF. IF YOU CAN'T FIGURE IT OUT, THEN KEEP LEARNING UNTIL YOU DO. IF YOU STILL CAN'T FIGURE IT OUT, ASK FOR HELP. BUT DO NOT EVER, EVER, EVER BOTHER THE PROJECT OWNER BEFORE YOU HAVE DONE ALL OF THE ABOVE. FAILURE TO FOLLOW THIS INSTRUCTION WILL RESULT IN IMMEDIATE REMOVAL FROM THE PROJECT.

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
10. Data goes in the database. That's what it exists for. Do not create random CSVs or JSON files outside of the data/ directory unless absolutely necessary. JSON and CSV are considered RAW and UNCLEAN. THEY ARE NOT ACCEPTABLE FOR PRODUCTION USAGE. ALWAYS USE THE DATABASE FOR PRODUCTION DATA STORAGE.
11. Don't ask if you can or should do something - just do it, following these instructions and best practices

## Technology Stack

- **Python 3.10+**
- **Apache Airflow** - Workflow orchestration
- **PostgreSQL** - Production database (migrated from DuckDB)
- **Kalshi API** - Prediction market integration
- **Docker/Docker Compose** - Container orchestration

## Project Structure

```
├── dags/                          # Airflow DAGs
│   └── multi_sport_betting_workflow.py  # Main unified betting DAG
├── plugins/                       # Airflow plugins (Python modules)
│   ├── elo/                       # Unified Elo rating system
│   │   ├── __init__.py            # Exports all Elo classes
│   │   ├── base_elo_rating.py     # BaseEloRating abstract class
│   │   ├── nba_elo_rating.py      # NBA Elo implementation
│   │   ├── nhl_elo_rating.py      # NHL Elo implementation
│   │   ├── mlb_elo_rating.py      # MLB Elo implementation
│   │   ├── nfl_elo_rating.py      # NFL Elo implementation
│   │   ├── epl_elo_rating.py      # EPL (soccer) Elo implementation
│   │   ├── ligue1_elo_rating.py   # Ligue1 (soccer) Elo implementation
│   │   ├── ncaab_elo_rating.py    # NCAAB Elo implementation
│   │   ├── wncaab_elo_rating.py   # WNCAAB Elo implementation
│   │   └── tennis_elo_rating.py   # Tennis Elo implementation
│   ├── kalshi_markets.py          # Kalshi API integration
│   ├── *_games.py                 # Game data downloaders
│   └── *_stats.py                 # Statistics modules
├── data/                          # Data directory (auto-created)
│   └── {sport}/bets_*.json        # Daily bet recommendations
├── archive/                       # Archived/legacy code (NOT active)
├── config/                        # Airflow configuration
├── docker-compose.yaml            # Airflow setup
├── requirements.txt               # Python dependencies
└── kalshkey                       # Kalshi API credentials
```

## Core Concepts

### Unified Elo Rating System

All sport-specific Elo implementations now inherit from `BaseEloRating` (located in `plugins/elo/base_elo_rating.py`). This provides a consistent interface across all sports.

**BaseEloRating Abstract Interface:**
```python
class BaseEloRating(ABC):
@abstractmethod
def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float:
"""Predict probability of home team winning."""

@abstractmethod
def update(self, home_team: str, away_team: str, home_won: Union[bool, float], is_neutral: bool = False) -> None:
"""Update Elo ratings after a game result."""

@abstractmethod
def get_rating(self, team: str) -> float:
"""Get current Elo rating for a team."""

@abstractmethod
def expected_score(self, rating_a: float, rating_b: float) -> float:
"""Calculate expected score (probability of team A winning)."""

@abstractmethod
def get_all_ratings(self) -> Dict[str, float]:
"""Get all current ratings."""
```

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

| Sport | K-Factor | Home Advantage | Notes |
|-------|----------|----------------|-------|
| NBA   | 20       | 100            | High-scoring, consistent |
| NHL   | 20       | 100            | High variance, recency weighting |
| MLB   | 20       | 50             | Lower home advantage |
| NFL   | 20       | 65             | Small sample sizes |
| EPL   | 20       | 60             | 3-way outcomes (Home/Draw/Away) |
| Ligue1| 20       | 60             | 3-way outcomes (Home/Draw/Away) |
| NCAAB | 20       | 100            | College basketball |
| WNCAAB| 20       | 100            | Women's college basketball |
| Tennis| 20       | 0              | No home advantage |

**Current Refactoring Status (2026-01-23):**

- ✅ **Completed**: All 9 sports (NHL, NBA, MLB, NFL, EPL, Ligue1, NCAAB, WNCAAB, Tennis)

- 🔄 **In Progress**: None (Phase 1.2 Completed)



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

All Elo implementations must inherit from `BaseEloRating` and implement all abstract methods:

```python
from .base_elo_rating import BaseEloRating

class SportEloRating(BaseEloRating):
def __init__(self, k_factor: float = 20.0, home_advantage: float = 100.0, initial_rating: float = 1500.0):
super().__init__(k_factor=k_factor, home_advantage=home_advantage, initial_rating=initial_rating)

def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float:
"""Predict probability of home team winning."""
# Implementation...

def update(self, home_team: str, away_team: str, home_won: Union[bool, float], is_neutral: bool = False) -> None:
"""Update Elo ratings after a game result."""
# Implementation...

# ... other required methods
```

**Backward Compatibility:** When refactoring existing sport classes, add `legacy_update()` methods to maintain compatibility with existing code.

### Airflow DAG Tasks

Tasks follow naming convention: `{action}_{sport}`

Example: `download_games_nba`, `update_elo_nhl`, `identify_bets_mlb`

## Important Files

### Active Production Code

- `dags/multi_sport_betting_workflow.py` - Main DAG (runs daily at 10 AM)
- `plugins/elo/base_elo_rating.py` - Unified Elo base class
- `plugins/elo/*_elo_rating.py` - Sport-specific Elo implementations (9 files)
- `plugins/kalshi_markets.py` - Kalshi API integration
- `plugins/*_games.py` - Game data downloaders

### Configuration

- `docker-compose.yaml` - Airflow services
- `requirements.txt` - Python dependencies
- `kalshkey` - API credentials (do not commit)

### Data Storage

- **PostgreSQL** - Primary production database
- `data/{sport}/bets_YYYY-MM-DD.json` - Daily bet recommendations

## Common Tasks

### Adding a New Sport

1. Create `plugins/elo/{sport}_elo_rating.py` inheriting from `BaseEloRating`
2. Create `plugins/{sport}_games.py` for data downloading
3. Add sport config to `SPORTS_CONFIG` in the DAG
4. Add Kalshi fetch function to `kalshi_markets.py`
5. Update `docker-compose.yaml` volume mounts if needed

### Refactoring Existing Sport Elo Classes

Follow TDD approach:
1. Create TDD test file: `tests/test_{sport}_elo_tdd.py`
2. Write tests for inheritance and required methods
3. Refactor class to inherit from `BaseEloRating`
4. Implement all abstract methods
5. Add `legacy_update()` method for backward compatibility
6. Run tests to ensure all pass
7. Update `PROJECT_PLAN.md` and `CHANGELOG.md`

### Modifying Elo Parameters

Parameters are set in two places:
1. Class defaults in `plugins/elo/{sport}_elo_rating.py`
2. `SPORTS_CONFIG` in `dags/multi_sport_betting_workflow.py`

### Running the DAG Manually

```bash
docker exec $(docker ps -qf "name=scheduler") \
airflow dags trigger multi_sport_betting_workflow
```

### Restarting the System After Code Changes

**IMPORTANT**: After making code changes to plugins, dashboard, or DAGs, you must restart the Docker containers to apply changes:

```bash
docker compose down && docker compose up -d
```

### Development Workflow
1. WE ONLY USE TEST DRIVEN DEVELOPMENT (TDD) FOR THIS PROJECT. ALWAYS WRITE TESTS FIRST.
2. MAKE CODE CHANGES IN `plugins/`, `dags/`, `dashboard/`
3. MAKE ALL UNIT TESTS PASS AND ONLY DELETE/SKIP TESTS IF THEY ARE NO LONGER RELEVANT
4. REDEPLOY ALL CONTAINERS WITH DOCKER COMPOSE
5. RUN INTEGRATION, DASHBOARD, DATA VALIDATION AND END-TO-END TESTS
6. IDENTIFY ISSUES AND RETURN TO STEP 1 UNTIL NO ISSUES FOUND
7. ADD CHANGELOG ENTRIES. MARK PROJECT PLAN COMPLETE.


**When to restart:**
- After editing Python code in `plugins/`, `dags/`, or `dashboard/`
- After modifying `requirements.txt` or Docker configuration
- When troubleshooting unexpected behavior (clears cached modules)

**Note**: The Airflow scheduler and webserver do NOT auto-reload Python modules. Code changes won't take effect until containers are restarted.

## Database Schema

The **PostgreSQL** database contains historical game data. Key tables:
- `games` - Game results with scores
- `teams` - Team information
- `players` - Player data (for future use)

## Testing

When testing Elo predictions:

```python
from plugins.elo import NHLEloRating

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
- Team coverage (all teams)
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

1. **Unified Elo Interface**: All sport classes now inherit from `BaseEloRating` for consistency
2. **TDD Approach**: All refactoring done using Test-Driven Development
3. **Sport-specific thresholds**: Higher variance sports (NHL) need higher thresholds
4. **Unified DAG**: Single DAG handles all sports vs. separate DAGs per sport
5. **PostgreSQL Migration**: Migrated from DuckDB for production reliability

## Environment Variables

- `KALSHI_API_KEY` - Loaded from `kalshkey` file
- Airflow variables set in `docker-compose.yaml`

## Dependencies

Key packages from `requirements.txt`:
- `apache-airflow>=2.8.0`
- `pandas>=2.0.0`
- `psycopg2-binary` - PostgreSQL adapter
- `kalshi-python` - Kalshi API client
- `requests>=2.31.0`
