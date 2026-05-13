# Tier 1 Contract Boundaries

## Status: 1/3 complete

### Boundary 1: KalshiBetting → BetTracker — DONE (46/46 tests)
### Boundary 2: PortfolioOptimizer.calculate_portfolio_allocation() → PortfolioBettingManager._place_optimized_bets() — DONE ✓

**Files created:**
- `tests/contracts/schemas/portfolio_allocation_v1.json` — JSON Schema for PortfolioAllocation + nested BetOpportunity
- `tests/contracts/fixtures/portfolio_samples.py` — Deterministic fixtures with NBA/MLB/Tennis variants
- `tests/contracts/test_portfolio_allocation_consumer.py` — 30 tests: dataclass serialization, schema validation, kelly_fraction/expected_value computation
- `tests/contracts/test_portfolio_allocation_provider.py` — 21 tests: MockPortfolioOptimizer exercising real `calculate_portfolio_allocation()`, schema conformance, edge cases

**Test results:** 51/51 passed, ruff check passed.

### Boundary 3: TBD
