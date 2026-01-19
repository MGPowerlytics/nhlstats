# Position Analysis Tool

Quick tool to analyze your Kalshi positions against Elo ratings.

## Quick Start

```bash
# Analyze last 7 days (default)
python analyze_positions.py

# Analyze last 30 days
python analyze_positions.py --days 30
```

## Output

Reports saved to: `reports/{timestamp}_positions_report.md`

Example: `reports/20260119_161311_positions_report.md`

## What It Shows

### ✅ Good Positions
- Above Elo threshold
- Betting on favorites
- Aligned with ratings

### ⚠️ Positions with Concerns
- Below threshold (NBA 64%, NCAAB/WNCAAB 65%, Tennis 60%)
- Betting on underdogs
- Contradictory positions

## Example Output

```markdown
✅ **Los Angeles L at Denver Winner?**
- Position: YES × 15
- Elo: Nuggets (1615) vs Lakers (1519) → 75.5%
- ✅ Above threshold (64%)

⚠️ **Will Kimberly Birrell win the Inglis vs Birrell match?**
- Position: NO × 7
- Elo: Birrell K. (1642) vs Inglis M. (1353) → 84.1%
- ⚠️ Betting NO but Elo favors YES 84.1%
```

## Testing

```bash
python -m pytest tests/test_analyze_positions.py -v
```

## Full Documentation

See [docs/POSITION_ANALYSIS.md](docs/POSITION_ANALYSIS.md) for complete details.

## Requirements

- Kalshi API credentials (`kalshkey` file)
- Current Elo ratings in `data/` directory
- Python 3.8+

---

**Run this tool regularly to review position alignment with Elo ratings!**
