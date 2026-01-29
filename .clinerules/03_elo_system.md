# Elo System

## Overview

The Multi-Sport Betting System uses a unified Elo rating engine to predict win probabilities across 9 sports. All sport-specific Elo implementations inherit from a common abstract base class (`BaseEloRating`) providing consistent interfaces for prediction, rating updates, and probability calculations.

## Unified Interface

### BaseEloRating Abstract Class
**Location**: `plugins/elo/base_elo_rating.py`

**Purpose**: Define a unified interface for all sport-specific Elo implementations.

**Key Methods**:
- `predict(home_team, away_team, is_neutral=False)` → Probability of home team winning (0.0-1.0)
- `update(home_team, away_team, home_won, is_neutral=False, **kwargs)` → Update ratings after game result
- `get_rating(team)` → Current Elo rating for a team/player
- `expected_score(rating_a, rating_b)` → Probability of team A winning given ratings
- `get_all_ratings()` → Dictionary of all current ratings

**Configuration Parameters**:
- `k_factor`: Update sensitivity (default 20.0)
- `home_advantage`: Home court/field advantage in Elo points (default 100.0)
- `initial_rating`: Initial rating for new teams/players (default 1500.0)

## Sport-Specific Implementations

### NHL Elo (`nhl_elo_rating.py`)
- **Sport**: National Hockey League
- **Key Features**: Handles overtime/shootout results, home ice advantage
- **Parameters**: `k_factor=20`, `home_advantage=100`
- **Usage**: Primary for NHL betting recommendations

### NBA Elo (`nba_elo_rating.py`)
- **Sport**: National Basketball Association
- **Key Features**: Court advantage, back-to-back fatigue adjustments
- **Parameters**: `k_factor=20`, `home_advantage=100`

### MLB Elo (`mlb_elo_rating.py`)
- **Sport**: Major League Baseball
- **Key Features**: Pitcher adjustments, ballpark factors
- **Parameters**: `k_factor=20`, `home_advantage=50` (smaller home advantage)

### NFL Elo (`nfl_elo_rating.py`)
- **Sport**: National Football League
- **Key Features**: Home field advantage, margin of victory adjustments
- **Parameters**: `k_factor=20`, `home_advantage=70`

### EPL Elo (`epl_elo_rating.py`)
- **Sport**: English Premier League (soccer)
- **Key Features**: Draw probability, goal difference adjustments
- **Parameters**: `k_factor=30`, `home_advantage=100`

### Ligue1 Elo (`ligue1_elo_rating.py`)
- **Sport**: French Ligue 1 (soccer)
- **Key Features**: Similar to EPL with French league adjustments
- **Parameters**: `k_factor=30`, `home_advantage=100`

### NCAAB Elo (`ncaab_elo_rating.py`)
- **Sport**: NCAA Basketball (men's)
- **Key Features**: Conference adjustments, neutral site handling
- **Parameters**: `k_factor=20`, `home_advantage=100`

### WNCAAB Elo (`wncaab_elo_rating.py`)
- **Sport**: NCAA Basketball (women's)
- **Key Features**: Women's basketball specific adjustments
- **Parameters**: `k_factor=20`, `home_advantage=100`

### Tennis Elo (`tennis_elo_rating.py`)
- **Sport**: Professional Tennis
- **Key Features**: Surface adjustments (clay, grass, hard), player fatigue
- **Parameters**: `k_factor=32`, `home_advantage=0` (no home advantage in tennis)

## Mathematical Foundation

### Expected Score Calculation
```
E_A = 1 / (1 + 10^((R_B - R_A)/400))
```
Where:
- `E_A` = Expected probability of team A winning
- `R_A` = Elo rating of team A
- `R_B` = Elo rating of team B

### Rating Update Formula
```
R'_A = R_A + K * (S_A - E_A)
```
Where:
- `R'_A` = New rating for team A
- `R_A` = Current rating for team A
- `K` = K-factor (update sensitivity)
- `S_A` = Actual result (1 for win, 0 for loss, 0.5 for draw)
- `E_A` = Expected probability of team A winning

### Home Advantage Adjustment
```
R_home_adj = R_home + home_advantage
```
Applied before calculating expected score for home teams, unless `is_neutral=True`.

## Usage Patterns

### 1. Initialization
```python
from plugins.elo import NHL_EloRating

elo = NHL_EloRating(k_factor=20, home_advantage=100)
```

### 2. Making Predictions
```python
# Predict probability of home team winning
prob_home_win = elo.predict("Edmonton Oilers", "Calgary Flames")
```

### 3. Updating Ratings
```python
# Update after a game result (home team won)
elo.update("Edmonton Oilers", "Calgary Flames", home_won=True)

# Update with scores
elo.update_with_scores("Edmonton Oilers", "Calgary Flames", 4, 2)
```

### 4. Retrieving Ratings
```python
# Get specific team rating
rating = elo.get_rating("Edmonton Oilers")

# Get all ratings
all_ratings = elo.get_all_ratings()
```

## Integration with Betting Pipeline

### Probability Calculation Flow
```
1. Game scheduled → Get team ratings
2. Apply home advantage if not neutral site
3. Calculate expected probability using Elo formula
4. Compare with market probability to calculate edge
```

### Edge Calculation
```
edge = elo_probability - market_probability
```
Where:
- `elo_probability` = Probability from Elo model (0.0-1.0)
- `market_probability` = Implied probability from Kalshi market prices

### Bet Recommendation Criteria
- **HIGH confidence**: edge > 0.10 (10%)
- **MEDIUM confidence**: 0.05 < edge ≤ 0.10 (5-10%)
- **No bet**: edge ≤ 0.05

## Configuration Management

### Sport-Specific Parameters
Each sport has optimized parameters stored in their respective classes:

| Sport | K-factor | Home Advantage | Initial Rating |
|-------|----------|----------------|----------------|
| NHL | 20 | 100 | 1500 |
| NBA | 20 | 100 | 1500 |
| MLB | 20 | 50 | 1500 |
| NFL | 20 | 70 | 1500 |
| EPL | 30 | 100 | 1500 |
| Ligue1 | 30 | 100 | 1500 |
| NCAAB | 20 | 100 | 1500 |
| WNCAAB | 20 | 100 | 1500 |
| Tennis | 32 | 0 | 1500 |

### Parameter Tuning
Parameters can be adjusted based on:
- Historical accuracy testing
- Sport-specific characteristics
- Home advantage magnitude in the sport
- Desired rating volatility

## Persistence and State Management

### Rating Storage Options
1. **In-memory**: Ratings stored in Python dictionaries during pipeline execution
2. **JSON files**: `data/{sport}/elo_ratings.json` for persistence between runs
3. **Database table**: `team_elo_ratings` table (if implemented)

### State Recovery
```python
# Load ratings from JSON
import json
with open("data/nhl/elo_ratings.json", "r") as f:
    ratings_dict = json.load(f)
elo.ratings = ratings_dict
```

## Performance Considerations

### Computational Efficiency
- Elo calculations are O(1) per game
- Rating updates are O(1) per game
- Memory usage scales with number of teams/players

### Scaling
- Current: ~500 teams/players across 9 sports
- Future: Can scale to thousands with minimal performance impact

## Testing and Validation

### Accuracy Metrics
- **Brier Score**: Measure probability prediction accuracy
- **Log Loss**: Logarithmic loss for probability predictions
- **Calibration**: Check if predicted probabilities match actual frequencies

### Backtesting
```python
# Example backtesting workflow
for game in historical_games:
    # Predict before game
    predicted_prob = elo.predict(game.home_team, game.away_team)

    # Update after knowing result
    elo.update(game.home_team, game.away_team, game.home_won)

    # Track accuracy
    track_accuracy(predicted_prob, game.home_won)
```

## Common Issues and Solutions

### 1. New Teams/Players
- **Issue**: No rating for new entities
- **Solution**: Use `initial_rating` (default 1500)

### 2. Rating Inflation/Deflation
- **Issue**: Ratings drift over time
- **Solution**: Implement rating regression toward mean between seasons

### 3. Draws (Soccer)
- **Issue**: Binary win/loss doesn't capture draws
- **Solution**: Use `S_A = 0.5` for draws in rating updates

### 4. Neutral Site Games
- **Issue**: Home advantage shouldn't apply
- **Solution**: Use `is_neutral=True` parameter

## Extending the System

### Adding a New Sport
1. Create new class in `plugins/elo/` inheriting from `BaseEloRating`
2. Implement all abstract methods
3. Set sport-specific parameters
4. Add to `plugins/elo/__init__.py` exports
5. Update `plugins/elo/factory.py` if using factory pattern

### Customizing Parameters
```python
class CustomSportElo(BaseEloRating):
    def __init__(self):
        super().__init__(k_factor=25, home_advantage=80)

    # Implement abstract methods...
```

---

*Last Updated: 2026-01-26*
