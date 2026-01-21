---
name: test-driven-development
description: Test-Driven Development workflow and best practices for the betting system, including Red-Green-Refactor cycle, test-first development, and incremental implementation.
version: 1.0.0
---

# Test-Driven Development (TDD)

## Core TDD Workflow

**Red → Green → Refactor**

1. **Red**: Write a failing test for the next piece of functionality
2. **Green**: Write minimal code to make the test pass
3. **Refactor**: Clean up code while keeping tests green
4. **Redeploy**: docker compose down && docker compose up -d
5. **Clear Failed Tasks in DagRun**: Wait for docker containers to start and run the following:
```
airflow tasks clear \
    --dag-id <your_dag_id> \
    --start-date <run_execution_date> \
    --only-failed \
    --recursive
```

## TDD Process for New Features

### Step 1: Write the Test First

Before writing any implementation code, write a test that describes the desired behavior:

```python
# tests/test_new_feature.py
def test_calculate_edge_returns_difference():
    """Edge should be elo_prob minus market_prob."""
    elo_prob = 0.65
    market_prob = 0.55

    edge = calculate_edge(elo_prob, market_prob)

    assert edge == 0.10
```

**Run it** - it should fail (Red):
```bash
pytest tests/test_new_feature.py
# FAILED - function doesn't exist yet
```

### Step 2: Write Minimal Implementation

Write just enough code to make the test pass:

```python
# plugins/betting_logic.py
def calculate_edge(elo_prob: float, market_prob: float) -> float:
    """Calculate betting edge."""
    return elo_prob - market_prob
```

**Run it** - test should pass (Green):
```bash
pytest tests/test_new_feature.py
# PASSED
```

### Step 3: Refactor

Add type hints, docstrings, error handling while keeping tests green:

```python
def calculate_edge(elo_prob: float, market_prob: float) -> float:
    """Calculate betting edge as difference between model and market probabilities.

    Args:
        elo_prob: Elo model probability (0.0 to 1.0)
        market_prob: Market implied probability (0.0 to 1.0)

    Returns:
        Edge value, positive indicates favorable bet

    Raises:
        ValueError: If probabilities outside valid range
    """
    if not (0 <= elo_prob <= 1 and 0 <= market_prob <= 1):
        raise ValueError("Probabilities must be between 0 and 1")
    return elo_prob - market_prob
```

### Step 4: Add More Test Cases

Test edge cases and error conditions:

```python
def test_calculate_edge_negative_edge():
    """Edge can be negative when market is favored."""
    assert calculate_edge(0.45, 0.60) == -0.15

def test_calculate_edge_validates_bounds():
    """Should reject invalid probability values."""
    with pytest.raises(ValueError):
        calculate_edge(1.5, 0.5)
```

## TDD for Airflow Tasks

### Test Task Functions Directly

```python
# tests/test_dag_tasks.py
from unittest.mock import MagicMock, patch

def test_update_elo_task_success():
    """update_elo_ratings should process games and return count."""
    mock_games = pd.DataFrame({
        'home_team': ['Lakers', 'Warriors'],
        'away_team': ['Celtics', 'Suns'],
        'home_won': [True, False]
    })

    with patch('plugins.nba_games.fetch_recent_games', return_value=mock_games):
        result = update_elo_ratings(sport='nba')

    assert result['games_processed'] == 2
    assert 'ratings_updated' in result
```

## Mocking External Dependencies

### Mock Database Queries

```python
@pytest.fixture
def mock_db_manager():
    with patch('plugins.db_manager.DBManager') as mock:
        mock.return_value.fetch_df.return_value = pd.DataFrame()
        yield mock.return_value
```

### Mock Kalshi API

```python
@pytest.fixture
def mock_kalshi_client():
    with patch('plugins.kalshi_markets.KalshiClient') as mock:
        mock.return_value.get_markets.return_value = [
            {'ticker': 'NBA-LAKERS-CELTICS', 'yes_price': 55}
        ]
        yield mock.return_value
```

### Mock External APIs

```python
@patch('requests.get')
def test_fetch_games_handles_api_error(mock_get):
    """Should handle API failures gracefully."""
    mock_get.side_effect = requests.RequestException("API down")

    games = fetch_nba_games()

    assert games.empty
```

## Incremental Development Pattern

Build features one small piece at a time:

1. **Start with core logic** (pure functions, easy to test)
2. **Add data access** (mock database)
3. **Add external integrations** (mock APIs)
4. **Add Airflow orchestration** (task wrappers)

### Example: Adding a New Statistic

```python
# Step 1: Test pure calculation
def test_win_streak_calculates_correctly():
    games = [True, True, False, True]
    assert calculate_win_streak(games) == 1

# Step 2: Test database integration
def test_load_team_recent_games(mock_db):
    mock_db.fetch_df.return_value = sample_games_df
    games = load_recent_games('Lakers', db=mock_db)
    assert len(games) == 5

# Step 3: Test full feature
def test_get_team_win_streak_end_to_end(mock_db):
    result = get_team_win_streak('Lakers', db=mock_db)
    assert result >= 0
```

## Coverage Targets

**Maintain 85%+ coverage** across all modules:

```bash
# Check coverage
pytest --cov=plugins --cov=dags --cov-report=term-missing

# Fail if below threshold
pytest --cov=plugins --cov-fail-under=85
```

**Add tests when coverage drops:**
```bash
# Identify untested lines
pytest --cov=plugins/nba_elo_rating --cov-report=term-missing

# Focus on uncovered lines marked with "Missing"
```

## Code Formatting

**Run Black before committing:**

```bash
black plugins/ dags/ tests/
```

**Check without modifying:**
```bash
black --check plugins/ dags/ tests/
```

## Test Organization Best Practices

### One Test Class per Class

```python
class TestNBAEloRating:
    def test_predict_returns_probability(self):
        ...

    def test_update_modifies_ratings(self):
        ...

    def test_get_rating_initializes_new_teams(self):
        ...
```

### Descriptive Test Names

Use pattern: `test_{function}_{scenario}_{expected}`

```python
def test_predict_home_favorite_returns_high_probability()
def test_predict_even_teams_returns_fifty_fifty()
def test_update_home_win_increases_home_rating()
```

### Arrange-Act-Assert Pattern

```python
def test_example():
    # Arrange - set up test data
    elo = NBAEloRating(k_factor=20)

    # Act - perform the action
    prob = elo.predict('Lakers', 'Celtics')

    # Assert - verify the result
    assert 0.0 <= prob <= 1.0
```

## When to Write Tests

1. **Before writing new features** (true TDD)
2. **Before fixing bugs** (regression tests)
3. **When coverage drops below 85%**
4. **Before refactoring** (safety net)

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_nba_elo_rating.py

# Specific test
pytest tests/test_nba_elo_rating.py::test_predict_returns_probability

# With coverage
pytest --cov=plugins

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Run only failed tests from last run
pytest --lf
```

## Quick Reference

| Phase | Action | Command |
|-------|--------|---------|
| Red | Write failing test | `pytest tests/test_new.py` |
| Green | Implement minimal code | `pytest tests/test_new.py` |
| Refactor | Clean up, add types | `black plugins/` |
| Verify | Check coverage | `pytest --cov=plugins` |
| Commit | All green, 85%+ coverage | `git commit` |

## Key Principles

1. **Write tests first** - drives better design
2. **Small steps** - one test at a time
3. **Keep tests fast** - mock external dependencies
4. **Descriptive names** - tests are documentation
5. **Maintain coverage** - 85% minimum
6. **Run frequently** - fast feedback loop
