# Testing Documentation

This directory contains testing documentation, validation reports, and quality assurance information.

## Test Reports

- **[FINAL_TEST_REPORT.md](FINAL_TEST_REPORT.md)** - Comprehensive test suite results
- **[NHL_DATA_VALIDATION_REPORT.md](NHL_DATA_VALIDATION_REPORT.md)** - Data quality validation

For historical test fixes, see: [archive/completed_implementations](../../archive/completed_implementations/)

## Test Coverage

Current test coverage: **85%+**

### Test Categories

1. **Unit Tests** - Individual component testing
   - Elo rating calculations
   - Portfolio optimization
   - Data validation
   - Utility functions

2. **Integration Tests** - End-to-end workflows
   - Multi-sport betting workflow
   - Dashboard data loading
   - Kalshi API integration

3. **Temporal Integrity Tests** - Data leakage prevention
   - 11/11 tests passing
   - See: [docs/ELO_TEMPORAL_INTEGRITY_AUDIT.md](../ELO_TEMPORAL_INTEGRITY_AUDIT.md)

4. **Dashboard Tests** - UI/UX validation
   - 60 Playwright tests
   - All sports, all tabs, all charts

5. **Security Tests** - CodeQL scanning
   - Automated vulnerability detection
   - Input validation checks

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=plugins --cov=dags --cov-report=html

# Specific test file
pytest tests/test_nhl_elo_rating.py -v

# Dashboard tests
pytest tests/test_dashboard_playwright.py -v

# Stop on first failure
pytest tests/ -x
```

## Data Validation

Validate data quality:
```bash
# NHL data validation
python validate_nhl_data.py

# All sports validation (if available)
python check_data_status.py
```

## Test Structure

```
tests/
├── test_*_elo_rating.py      # Elo implementations (9 files)
├── test_portfolio_optimizer.py
├── test_analyze_positions.py
├── test_elo_temporal_integrity.py
├── test_dashboard_playwright.py
└── test_multi_sport_workflow.py
```

## Quality Standards

Before merging code:
- ✅ All tests passing
- ✅ Coverage ≥ 85%
- ✅ No CodeQL vulnerabilities
- ✅ Data validation passing
- ✅ Black formatting applied

---

For more information, see [README.md](../../README.md) development section.
