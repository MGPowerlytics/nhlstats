# Contract Boundary Gap Analysis

## Objective
Identify and fill the highest-impact boundaries in `nhlstats` that lack consumer-driven contract testing.

## Coverage Map
| Sport | Elo Prediction | Bet Opportunity | Kalshi/DB/Stats | Test Files (non-contract) |
|-------|---------------|----------------|-----------------|---------------------------|
| MLB   | ✅ | ✅ | ✅ | - |
| EPL   | ✅ | ✅ | ✅ | - |
| Tennis| ✅ | ✅ | ✅ | - |
| **NHL**  | **✅ NEW** | ❌ | ❌ (boxscore exists) | 2 |
| **NBA**  | **✅ NEW** | ❌ | ❌ | 7 |
| **NFL**  | **✅ NEW** | ❌ | ❌ | 2 |
| NCAAB | ❌ | ❌ | ❌ | 1 |
| WNCAA | ❌ | ❌ | ❌ | 1 |
| Unrivaled | ❌ | ❌ | ❌ | 2 |
| Ligue 1 | ❌ | ❌ | ❌ | 3 |

## Completed (2026-04-23)

### 1. NHL Elo Prediction Boundary
- **Impact**: Highest — project is named `nhlstats`, zero contract coverage existed
- **Files**:
  - `tests/contracts/schemas/nhl_elo_prediction_v1.json`
  - `tests/contracts/fixtures/nhl_elo_samples.py`
  - `tests/contracts/test_nhl_elo_consumer.py`
  - `tests/contracts/test_nhl_elo_provider.py`
- **Tests**: 12/12 passing
- **Details**: k_factor=20.0, home_advantage=65.0, teams (Toronto Maple Leafs vs Boston Bruins). Uses `home_win=1.0` keyword arg (NHL-specific dispatch via ArgumentParser).

### 2. NBA Elo Prediction Boundary
- **Impact**: Second-highest — 7 test files (most test activity of any uncovered sport)
- **Files**:
  - `tests/contracts/schemas/nba_elo_prediction_v1.json`
  - `tests/contracts/fixtures/nba_elo_samples.py`
  - `tests/contracts/test_nba_elo_consumer.py`
  - `tests/contracts/test_nba_elo_provider.py`
- **Tests**: 12/12 passing
- **Details**: k_factor=20.0, home_advantage=100.0, teams (Los Angeles Lakers vs Boston Celtics). Uses `home_won=True` keyword arg.

### 3. NFL Elo Prediction Boundary
- **Impact**: Third — 2 test files, well-defined producer
- **Files**:
  - `tests/contracts/schemas/nfl_elo_prediction_v1.json`
  - `tests/contracts/fixtures/nfl_elo_samples.py`
  - `tests/contracts/test_nfl_elo_consumer.py`
  - `tests/contracts/test_nfl_elo_provider.py`
- **Tests**: 12/12 passing
- **Details**: k_factor=20.0, home_advantage=65.0, teams (Kansas City Chiefs vs San Francisco 49ers). Uses `home_won=True` keyword arg.

## Total Impact
- **12 new files** added
- **36 new tests** (12 per sport boundary)
- **540 total contract tests** in suite, all passing
- **Full suite runtime**: 3.53s

## Remaining Gaps (lower priority)
- NHL/NBA/NFL bet opportunity, Kalshi, DB row, and stats boundaries
- NCAAB, WNCAA, Unrivaled, Ligue 1 Elo boundaries
