# Elo System Analysis for TDD Refactor

## Current State Analysis (Updated: 2026-01-23)

### 1. Unified Elo Architecture

**Base Class:** `BaseEloRating` (plugins/elo/base_elo_rating.py)
- Abstract base class defining unified interface
- All sport-specific implementations must inherit from this
- Provides helper methods: `_apply_home_advantage()`, `_calculate_rating_change()`

**Directory Structure:**
```
plugins/elo/
├── __init__.py              # Exports all Elo classes
├── base_elo_rating.py       # BaseEloRating abstract class
├── nba_elo_rating.py        # NBA Elo implementation
├── nhl_elo_rating.py        # NHL Elo implementation
├── mlb_elo_rating.py        # MLB Elo implementation
├── nfl_elo_rating.py        # NFL Elo implementation
├── epl_elo_rating.py        # EPL (soccer) Elo implementation
├── ligue1_elo_rating.py     # Ligue1 (soccer) Elo implementation
├── ncaab_elo_rating.py      # NCAAB Elo implementation
├── wncaab_elo_rating.py     # WNCAAB Elo implementation
└── tennis_elo_rating.py     # Tennis Elo implementation
```

### 2. Refactoring Status (9 sports total)

**✅ COMPLETED (6/9):**
1. **NHLEloRating** - NHL with recency weighting and game history tracking
2. **NBAEloRating** - Canonical implementation, template for other sports
3. **MLBEloRating** - MLB with score-based updates and legacy compatibility
4. **NFLEloRating** - NFL with score-based updates and DuckDB integration
5. **EPLEloRating** - EPL with 3-way outcomes (Home/Draw/Away)
6. **Ligue1EloRating** - Ligue1 with 3-way outcomes and draw probability modeling

**🔄 IN PROGRESS (3/9):**
7. **NCAABEloRating** - College basketball (next to refactor)
8. **WNCAABEloRating** - Women's college basketball
9. **TennisEloRating** - Tennis (no home advantage)

### 3. Unified Interface Requirements

All sport-specific Elo classes must implement these abstract methods:

```python
@abstractmethod
def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float

@abstractmethod
def update(self, home_team: str, away_team: str, home_won: Union[bool, float], is_neutral: bool = False) -> None

@abstractmethod
def get_rating(self, team: str) -> float

@abstractmethod
def expected_score(self, rating_a: float, rating_b: float) -> float

@abstractmethod
def get_all_ratings(self) -> Dict[str, float]
```

### 4. Sport-Specific Features Preserved

**NHL:**
- Recency weighting (`recency_weight` parameter)
- Game history tracking (`game_history` dictionary)
- Season reversion (`apply_season_reversion()` method)
- Load/save ratings from JSON

**NBA:**
- Canonical implementation
- `evaluate_on_games()` method for performance evaluation
- Simple and clean interface

**MLB/NFL:**
- Score-based updates (`update_with_scores()` methods)
- Margin of victory considerations
- `update_legacy()` methods for backward compatibility

**Soccer (EPL, Ligue1):**
- 3-way outcome predictions (`predict_3way()`, `predict_probs()`)
- Draw probability modeling (Gaussian based on rating difference)
- `legacy_update()` for traditional outcome formats ('H', 'D', 'A')

### 5. Import Patterns

**Old (deprecated):**
```python
from nba_elo_rating import NBAEloRating
from nhl_elo_rating import NHLEloRating
```

**New (unified):**
```python
from plugins.elo import BaseEloRating, NBAEloRating, NHLEloRating
from plugins.elo import MLBEloRating, NFLEloRating, EPLEloRating
from plugins.elo import Ligue1EloRating, NCAABEloRating, WNCAABEloRating, TennisEloRating
```

### 6. TDD Approach

**Test Files Created:**
- `tests/test_base_elo_rating_tdd.py` - Base class interface tests
- `tests/test_nhl_elo_tdd.py` - NHL refactoring tests
- `tests/test_nba_elo_tdd.py` - NBA refactoring tests
- `tests/test_epl_elo_tdd.py` - EPL refactoring tests
- `tests/test_ligue1_elo_tdd.py` - Ligue1 refactoring tests

**Test Patterns:**
1. Inheritance test (`issubclass(SportEloRating, BaseEloRating)`)
2. Required methods test (check all 5 abstract methods)
3. Backward compatibility test (sport-specific features)
4. Update functionality test
5. `get_all_ratings()` test

### 7. Backward Compatibility

All refactored classes maintain backward compatibility through:
- `legacy_update()` methods (accept traditional result formats)
- Preservation of sport-specific methods (`predict_3way()`, `update_with_scores()`, etc.)
- Same parameter defaults (k_factor=20, home_advantage sport-specific)
- Existing test suites continue to pass

### 8. Next Steps

**Immediate:**
1. Refactor remaining 3 sports (NCAAB, WNCAAB, Tennis) using TDD
2. Update `SPORTS_CONFIG` to use unified interface
3. Update DAGs to import from `plugins.elo` package
4. Update dashboard to use unified interface

**Future:**
1. Create integration tests for unified interface
2. Update all documentation references
3. Consider adding factory pattern for Elo creation
4. Add type checking for sport-specific parameters

### 9. Key Benefits

1. **Consistency**: All sports use same interface
2. **Maintainability**: Common code in base class, sport-specific in subclasses
3. **Testability**: Easy to write comprehensive tests
4. **Extensibility**: New sports follow established pattern
5. **Documentation**: Clear interface definition

### 10. Files Updated

**Documentation:**
- `.github/copilot-instructions.md` - Updated with unified Elo information
- `.github/skills/elo-rating-systems/SKILL.md` - Updated to v2.0.0
- `.github/skills/test-driven-development/SKILL.md` - Added unified Elo refactoring patterns
- `.github/skills/adding-new-sport/SKILL.md` - Updated to v2.0.0 with unified interface
- `PROJECT_PLAN.md` - Updated refactoring status
- `CHANGELOG.md` - Added soccer Elo refactoring entry

**Code Organization:**
- All Elo files moved to `plugins/elo/` directory
- `plugins/elo/__init__.py` created for clean imports
- Test files organized with TDD approach
