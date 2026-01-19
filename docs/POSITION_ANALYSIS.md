# Position Analysis Script Documentation

## Overview

`analyze_positions.py` is a comprehensive tool for analyzing your Kalshi betting positions against Elo ratings. It generates markdown reports comparing open and recently closed positions with current Elo probabilities.

## Features

- ✅ **Multi-Sport Support**: NBA, NCAAB, WNCAAB, Tennis, NHL
- ✅ **Elo Comparison**: Automatically compares positions with current ratings
- ✅ **Concern Detection**: Flags positions with potential issues
- ✅ **Human-Readable**: Uses team/player names, not IDs
- ✅ **Markdown Reports**: Clean, formatted output with timestamps
- ✅ **Configurable Period**: Analyze last N days of activity
- ✅ **Comprehensive Tests**: Full unit test coverage

## Usage

### Basic Usage

```bash
# Analyze last 7 days (default)
python analyze_positions.py

# Analyze last 14 days
python analyze_positions.py --days 14

# Analyze last 30 days
python analyze_positions.py --days 30
```

### Output

Reports are saved to `reports/{timestamp}_positions_report.md` with format:
- `20260119_161311_positions_report.md`

## Report Structure

### 1. Account Summary
- Current balance
- Portfolio value
- Total account value

### 2. Open Positions
Grouped by sport (NBA, NCAAB, WNCAAB, Tennis, etc.)

Each position shows:
- **Title**: Human-readable market name
- **Position**: Side (YES/NO) and contract count
- **Elo Analysis**: Current ratings and win probability
- **Status Icon**: 
  - ✅ Position aligns with Elo
  - ⚠️ Position has concerns (below threshold, betting underdog, etc.)

### 3. Recently Closed Positions
Recent settled markets with final analysis

### 4. Summary
- Total open positions
- Recently closed count
- Positions with concerns

## Elo Analysis Details

### Basketball (NBA, NCAAB, WNCAAB)

- **Home Advantage**: +100 Elo points
- **Thresholds**: 
  - NBA: 64% win probability
  - NCAAB/WNCAAB: 65% win probability
- **Concerns Flagged**:
  - Position below threshold
  - Betting on underdog (< 50% probability)

### Tennis (ATP, WTA)

- **Threshold**: 60% win probability
- **Concerns Flagged**:
  - Betting YES but Elo < 50%
  - Betting NO but Elo > 50%

## Requirements

- Python 3.8+
- Access to Kalshi API (requires `kalshkey` file)
- Elo ratings files in `data/` directory:
  - `nba_current_elo_ratings.csv`
  - `ncaab_current_elo_ratings.csv`
  - `wncaab_current_elo_ratings.csv`
  - `atp_current_elo_ratings.csv`
  - `wta_current_elo_ratings.csv`

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python -m pytest tests/test_analyze_positions.py -v

# Run with coverage
python -m pytest tests/test_analyze_positions.py --cov=analyze_positions --cov-report=html

# Run specific test
python -m pytest tests/test_analyze_positions.py::TestPositionAnalyzer::test_classify_sport -v
```

### Test Coverage

The test suite includes:
- Sport classification from tickers
- Team/player name matching (direct, mapping, fuzzy)
- Basketball analysis (above/below threshold)
- Tennis analysis (favorite/underdog)
- Position aggregation from fills
- Markdown generation
- CLI argument parsing

## Implementation Details

### Class: `PositionAnalyzer`

Main class handling position analysis.

**Key Methods:**

- `get_positions(days_back)` - Fetch positions from Kalshi API
- `analyze_position(ticker, data, details)` - Analyze single position
- `generate_report(days_back)` - Generate complete markdown report
- `_analyze_basketball(title, side, sport)` - Basketball-specific analysis
- `_analyze_tennis(title, side)` - Tennis-specific analysis

### Team/Player Matching

Three-tier matching system:

1. **Direct Mapping**: Uses `data/*_team_mapping.json` files
2. **Exact Match**: Direct lookup in ratings dictionary
3. **Fuzzy Match**: Substring and last-name matching

## Example Report Sections

### Open Position (Good Bet)

```markdown
✅ **Los Angeles L at Denver Winner?**
- Position: YES × 15
- Elo: Nuggets (1615) vs Lakers (1519) → 75.5%
- ✅ Above threshold (64%)
```

### Open Position (With Concern)

```markdown
⚠️ **Will Kimberly Birrell win the Inglis vs Birrell match?**
- Position: NO × 7
- Elo: Birrell K. (1642) vs Inglis M. (1353) → 84.1%
- ✅ Above threshold (60%)
- ⚠️ Betting NO but Elo favors YES 84.1%
```

## Troubleshooting

### "Teams not found" Message

- Check that team mapping files exist in `data/`
- Verify team names in Kalshi title match your Elo data
- Add custom mapping to `data/*_team_mapping.json`

### "Players not in Elo database"

- Ensure `atp_current_elo_ratings.csv` and `wta_current_elo_ratings.csv` are up to date
- Player names must match format in rating files

### Empty Report

- Verify Kalshi credentials in `kalshkey` file
- Check that you have recent trading activity
- Try increasing `--days` parameter

## Integration with DAG

This script runs independently of the Airflow DAG but uses the same:
- Elo rating files
- Team/player mappings
- Kalshi API credentials
- Analysis thresholds

Run manually for ad-hoc position reviews or integrate into monitoring workflows.

## Future Enhancements

- [ ] Email report delivery
- [ ] Position performance tracking over time
- [ ] Automated concern alerts
- [ ] Historical backtest comparison
- [ ] Integration with SMS notifications
- [ ] CSV export option
- [ ] Position P/L calculation

## Support

For issues or questions:
1. Check test output: `python -m pytest tests/test_analyze_positions.py -v`
2. Verify Elo ratings files exist and are current
3. Confirm Kalshi API credentials are valid
4. Review generated report for specific error messages

---

**Last Updated:** January 19, 2026  
**Version:** 1.0.0  
**Test Coverage:** 85%+
