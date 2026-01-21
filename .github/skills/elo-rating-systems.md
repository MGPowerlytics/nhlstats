# Elo Rating Systems

## Core Formula

Convert Elo ratings to win probability:

```python
def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability that team A beats team B."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
```

For home games, add home advantage to home team's rating before calculation.

## Sport-Specific Parameters

| Sport | K-Factor | Home Advantage | Threshold | Notes |
|-------|----------|----------------|-----------|-------|
| NBA   | 20       | 100            | 73%       | High-scoring, consistent |
| NHL   | 20       | 100            | 66%       | High variance |
| MLB   | 20       | 50             | 67%       | Lower home advantage |
| NFL   | 20       | 65             | 70%       | Small sample sizes |

## Required Interface

All Elo implementations in `plugins/{sport}_elo_rating.py` must implement:

```python
class SportEloRating:
    def __init__(self, k_factor=20, home_advantage=100, initial_rating=1500):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings = {}

    def get_rating(self, team: str) -> float:
        """Get current rating, initializing if needed."""
        if team not in self.ratings:
            self.ratings[team] = self.initial_rating
        return self.ratings[team]

    def predict(self, home_team: str, away_team: str) -> float:
        """Return P(home wins) from 0.0 to 1.0."""
        home_rating = self.get_rating(home_team) + self.home_advantage
        away_rating = self.get_rating(away_team)
        return self.expected_score(home_rating, away_rating)

    def update(self, home_team: str, away_team: str, home_won: bool) -> dict:
        """Update ratings after game. Return rating changes."""
        expected = self.predict(home_team, away_team)
        actual = 1.0 if home_won else 0.0
        change = self.k_factor * (actual - expected)

        self.ratings[home_team] = self.get_rating(home_team) + change
        self.ratings[away_team] = self.get_rating(away_team) - change
        return {"home_change": change, "away_change": -change}
```

## Threshold Tuning

Use lift/gain analysis to optimize thresholds:

```python
from lift_gain_analysis import analyze_sport

# Analyze prediction quality by decile
overall, current_season = analyze_sport('nba')

# Look for deciles with lift > 1.2
# Set threshold to capture high-lift predictions
```

**Key metrics:**
- **Lift > 1.0**: Predictions better than random
- **Target**: Find threshold where top deciles have lift > 1.3

## Files to Reference

- `plugins/nba_elo_rating.py` - Canonical implementation
- `plugins/lift_gain_analysis.py` - Threshold analysis
- `docs/VALUE_BETTING_THRESHOLDS.md` - Optimization results
