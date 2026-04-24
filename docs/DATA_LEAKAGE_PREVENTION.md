# Data Leakage Prevention Guide

## What is Data Leakage?

Data leakage occurs when information from the future "leaks" into training or prediction, making models appear more accurate than they actually are.

**Example of leakage:**
```python
# ❌ WRONG - Using Game 5 outcome to predict Game 5
for game in games:
    elo.update(game.home, game.away, game.outcome)  # Update first
    prediction = elo.predict(game.home, game.away)  # Then predict ❌
```

**Correct approach:**
```python
# ✅ CORRECT - Predict BEFORE updating
for game in games:
    prediction = elo.predict(game.home, game.away)  # Predict first ✅
    predictions.append(prediction)
    elo.update(game.home, game.away, game.outcome)  # Then update
```

---

## Why This Matters

### In Backtesting
If historical analysis has leakage, we'll think our system is profitable when it's not.

**Impact:**
- Thresholds chosen based on inflated performance
- System loses money in production
- False confidence in strategy

### In Live Betting
If production predictions have leakage, we're betting on games we already know the outcome of (impossible).

**Impact:**
- System crashes or errors
- Impossible to place bets
- Complete system failure

---

## Our Validation System

### 1. Unit Tests (Automated)

**File:** `tests/test_elo_temporal_integrity.py`

**Run tests:**
```bash
cd /mnt/data2/nhlstats
python -m pytest tests/test_elo_temporal_integrity.py -v
```

**What's tested:**
- ✅ Predict-before-update pattern (all 9 sports)
- ✅ Sequential games reflect previous outcomes
- ✅ Historical simulations maintain chronological order
- ✅ Production DAG uses correct temporal separation
- ✅ predict() doesn't accidentally modify ratings
- ✅ Game processing order matters (validation test)

**Coverage:** 11 tests covering all critical paths

### 2. Code Review Checklist

When adding/modifying Elo predictions:

- [ ] Games processed in chronological order (sort by date)
- [ ] For each game: predict() → store → update()
- [ ] Never: update() → predict() for same game
- [ ] predict() method doesn't modify self.ratings
- [ ] Test added to test_elo_temporal_integrity.py

### 3. Audit Reports

**Latest audit:** `docs/ELO_TEMPORAL_INTEGRITY_AUDIT.md`
**Quick summary:** `docs/TEMPORAL_INTEGRITY_SUMMARY.md`

---

## Critical Code Patterns

### Pattern 1: Historical Analysis (Backtest/Lift-Gain)

```python
def backtest(games_df):
    """Backtest Elo predictions on historical data."""

    # CRITICAL: Sort by date ascending
    games_df = games_df.sort_values('game_date')

    elo = EloRating()
    predictions = []

    for _, game in games_df.iterrows():
        # STEP 1: Predict using ratings from games 1 to N-1
        pred = elo.predict(game['home_team'], game['away_team'])
        predictions.append(pred)

        # STEP 2: Update ratings AFTER prediction stored
        elo.update(game['home_team'], game['away_team'], game['home_won'])

    # STEP 3: Analyze predictions vs actuals
    return analyze(predictions, games_df['home_won'])
```

**Key points:**
- ✅ Sort by date FIRST
- ✅ Predict before update
- ✅ Each prediction uses ratings from all previous games only

### Pattern 2: Production Predictions (DAG)

```python
def update_elo_ratings(sport):
    """Update Elo ratings from all completed games."""

    # Load ALL historical games
    games_df = load_historical_games(sport)
    games_df = games_df.sort_values('game_date')

    elo = EloRating()

    # Process all completed games
    for _, game in games_df.iterrows():
        elo.update(game['home_team'], game['away_team'], game['outcome'])

    # Save ratings for use in identify_good_bets()
    return elo.ratings


def identify_good_bets(sport, elo_ratings):
    """Identify betting opportunities for UPCOMING games."""

    # Restore ratings from historical games only
    elo = EloRating()
    elo.ratings = elo_ratings  # From update_elo_ratings()

    # Load UPCOMING games (not yet started)
    upcoming_games = load_todays_markets(sport)

    for game in upcoming_games:
        # Predict using historical ratings
        pred = elo.predict(game['home_team'], game['away_team'])

        # Do NOT update (game hasn't happened yet)
        if pred > threshold:
            recommend_bet(game, pred)
```

**Key points:**
- ✅ Clear temporal separation: historical vs. upcoming
- ✅ Ratings built from completed games only
- ✅ Never update ratings for pending games

### Pattern 3: Elo Class Implementation

```python
class EloRating:
    """Elo rating system."""

    def predict(self, home_team: str, away_team: str) -> float:
        """
        Predict home team win probability.

        CRITICAL: This method must NOT modify self.ratings.
        """
        home_rating = self.get_rating(home_team)  # Read only
        away_rating = self.get_rating(away_team)  # Read only

        # Calculate probability (no state changes)
        return 1 / (1 + 10 ** ((away_rating - home_rating) / 400))

    def update(self, home_team: str, away_team: str, home_won: bool):
        """
        Update ratings after game result known.

        This is the ONLY method that modifies self.ratings.
        """
        # Calculate expected
        expected = self.predict(home_team, away_team)

        # Get actual
        actual = 1.0 if home_won else 0.0

        # Update ratings (ONLY place self.ratings is modified)
        self.ratings[home_team] += K * (actual - expected)
        self.ratings[away_team] += K * ((1 - actual) - (1 - expected))
```

**Key points:**
- ✅ predict() is read-only (no side effects)
- ✅ update() is the ONLY method that modifies ratings
- ✅ Clear separation of concerns

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Update Before Predict
```python
# ❌ WRONG
for game in games:
    elo.update(game.home, game.away, game.outcome)
    pred = elo.predict(game.home, game.away)  # Uses updated ratings!
```

**Fix:**
```python
# ✅ CORRECT
for game in games:
    pred = elo.predict(game.home, game.away)
    elo.update(game.home, game.away, game.outcome)
```

### ❌ Mistake 2: Processing Games Out of Order
```python
# ❌ WRONG - Random order
games = games_df.sample(frac=1)  # Shuffle
for game in games:
    pred = elo.predict(game.home, game.away)
    elo.update(game.home, game.away, game.outcome)
```

**Fix:**
```python
# ✅ CORRECT - Chronological order
games = games_df.sort_values('game_date')  # Sort by date
for game in games:
    pred = elo.predict(game.home, game.away)
    elo.update(game.home, game.away, game.outcome)
```

### ❌ Mistake 3: Using Future Information
```python
# ❌ WRONG - Loading all games including future
def predict_today():
    games = load_all_games()  # Includes future games
    elo = EloRating()

    # Process all games (including future!)
    for game in games:
        elo.update(game.home, game.away, game.outcome)

    # Now predict today
    return elo.predict("Team A", "Team B")  # Ratings contaminated!
```

**Fix:**
```python
# ✅ CORRECT - Only historical games
def predict_today():
    historical_games = load_games_before_today()  # Only past
    elo = EloRating()

    # Process only completed games
    for game in historical_games:
        elo.update(game.home, game.away, game.outcome)

    # Now predict today
    return elo.predict("Team A", "Team B")  # Clean ratings
```

---

## Validation Checklist

Before deploying changes that affect predictions:

### 1. Run Temporal Integrity Tests
```bash
python -m pytest tests/test_elo_temporal_integrity.py -v
```
**Required:** All tests must pass ✅

### 2. Code Review
- [ ] Games processed chronologically?
- [ ] predict() called before update()?
- [ ] predict() doesn't modify state?
- [ ] Only historical data used for ratings?

### 3. Manual Verification
Test with known sequence:
```python
elo = EloRating()

# Game 1
r1 = elo.get_rating("Team A")  # Should be 1500
pred1 = elo.predict("Team A", "Team B")
elo.update("Team A", "Team B", home_won=True)

# Game 2
r2 = elo.get_rating("Team A")  # Should be > 1500
assert r2 > r1  # Rating should have increased
pred2 = elo.predict("Team A", "Team B")
assert pred2 > pred1  # Prediction should be higher
```

---

## Monitoring

### Continuous Validation

**Add to CI/CD:**
```yaml
- name: Test Temporal Integrity
  run: pytest tests/test_elo_temporal_integrity.py -v
```

**Pre-commit hook:**
```bash
#!/bin/bash
pytest tests/test_elo_temporal_integrity.py -q || exit 1
```

### Regression Testing

When threshold optimization or backtests run:
1. Verify games sorted by date
2. Verify predict-then-update pattern
3. Compare results to baseline
4. Check for unrealistic accuracy (>80% may indicate leakage)

---

## Summary

### Golden Rules

1. **Always predict BEFORE update**
2. **Always process games chronologically**
3. **Never use future information**
4. **Test temporal integrity**

### Validation Tools

- ✅ Automated tests (11 tests)
- ✅ Code review checklist
- ✅ Manual verification examples
- ✅ Audit reports

### Current Status

**Last Audit:** January 19, 2026
**Result:** ✅ **NO DATA LEAKAGE DETECTED**
**Tests:** 11/11 passing
**Confidence:** HIGH

---

## References

- **Test Suite:** `tests/test_elo_temporal_integrity.py`
- **Full Audit:** `docs/ELO_TEMPORAL_INTEGRITY_AUDIT.md`
- **Quick Summary:** `docs/TEMPORAL_INTEGRITY_SUMMARY.md`
- **Changelog:** Search "Temporal Integrity" in `CHANGELOG.md`

---

*Last Updated: January 19, 2026*
