# Portfolio-Level Betting Optimization

## Overview

The multi-sport betting system now includes **portfolio-level bet sizing optimization** using the Kelly Criterion and modern portfolio theory. Instead of placing fixed-size bets per sport independently, the system optimizes allocation across all sports simultaneously.

## Key Features

### 1. **Kelly Criterion Bet Sizing**
Uses the mathematically optimal Kelly formula to size each bet:

```
Kelly Fraction = (p × b - q) / b
```

Where:
- `p` = probability of winning (from Elo)
- `q` = probability of losing (1 - p)
- `b` = net odds (1/market_prob - 1)

For safety, we use **fractional Kelly** (default: 0.25 = quarter Kelly) to reduce volatility.

### 2. **Portfolio-Level Constraints**

- **Daily Risk Limit**: Max 10% of bankroll per day (configurable)
- **Per-Bet Maximum**: Max 5% of bankroll per bet (configurable)
- **Minimum/Maximum Bet Sizes**: $2 - $50 (configurable)
- **Prioritization**: Bets sorted by expected value (EV)

### 3. **Multi-Sport Allocation**

The system:
1. Loads bet opportunities from all sports (NHL, NBA, MLB, NFL)
2. Filters by minimum edge (5%) and confidence (68%)
3. Calculates Kelly fractions for each bet
4. Allocates optimally within portfolio constraints
5. Stops when daily risk limit is reached

## Files

### Core Modules

- **`plugins/portfolio_optimizer.py`**: Core optimization logic
  - `BetOpportunity`: Dataclass for bet opportunities
  - `PortfolioAllocation`: Optimized bet sizes
  - `PortfolioOptimizer`: Main optimization engine

- **`plugins/portfolio_betting.py`**: Integration with Kalshi
  - `PortfolioBettingManager`: Connects optimizer to Kalshi API
  - Handles bet placement, tracking, and reporting

### Data Files

- **Input**: `data/{sport}/bets_{YYYY-MM-DD}.json` (per-sport recommendations)
- **Output**: 
  - `data/portfolio/betting_report_{YYYY-MM-DD}.txt` (human-readable)
  - `data/portfolio/betting_results_{YYYY-MM-DD}.json` (machine-readable)

## Usage

### Command Line

```bash
# Dry run (recommended for testing)
python3 plugins/portfolio_betting.py 2026-01-19 --dry-run

# Live betting (use with caution!)
python3 plugins/portfolio_betting.py 2026-01-19
```

### Python API

```python
from plugins.portfolio_betting import PortfolioBettingManager
from plugins.kalshi_betting import KalshiBetting

# Initialize
kalshi = KalshiBetting(api_key_id='...', private_key_path='...')
manager = PortfolioBettingManager(
    kalshi_client=kalshi,
    max_daily_risk_pct=0.10,  # 10% max per day
    kelly_fraction=0.25,       # Quarter Kelly
    min_bet_size=2.0,
    max_bet_size=50.0,
    dry_run=True
)

# Process bets for a date
results = manager.process_daily_bets('2026-01-19')
```

## Configuration

### Risk Parameters (Adjustable)

```python
PortfolioBettingManager(
    max_daily_risk_pct=0.10,    # Max 10% of bankroll per day
    kelly_fraction=0.25,         # Use 1/4 Kelly (conservative)
    min_bet_size=2.0,            # Minimum $2 per bet
    max_bet_size=50.0,           # Maximum $50 per bet
    max_single_bet_pct=0.05,    # Max 5% per bet
    min_edge=0.05,               # Minimum 5% edge required
    min_confidence=0.68,         # Minimum 68% Elo probability
)
```

### Recommended Settings by Risk Tolerance

| Risk Level | Kelly Fraction | Max Daily Risk | Max Per Bet |
|------------|----------------|----------------|-------------|
| Conservative | 0.10-0.25 | 5-10% | 2-5% |
| Moderate | 0.25-0.50 | 10-15% | 5-10% |
| Aggressive | 0.50-1.00 | 15-25% | 10-15% |

⚠️ **Warning**: Full Kelly (1.0) has high variance. Quarter Kelly (0.25) is recommended.

## Example Output

### Betting Report

```
================================================================================
PORTFOLIO-OPTIMIZED BETTING REPORT
================================================================================
Date: 2026-01-19
Bankroll: $1,000.00
Max Daily Risk: 10.0% ($100.00)
Kelly Fraction: 25.00%

SUMMARY
--------------------------------------------------------------------------------
Opportunities Found:     4
After Filtering:         4
Bets to Place:           2
Total Bet Amount:        $100.00 (10.00% of bankroll)
Expected Profit:         $49.30
Expected ROI:            49.30%
Average Bet Size:        $50.00
Average Edge:            22.40%

BET ALLOCATIONS
--------------------------------------------------------------------------------

NBA:
  Sport Total: $100.00

  1. Nuggets vs Lakers
     Ticker: KXNBAGAME-26JAN20LALDEN-DEN
     Bet Size: $50.00 (5.00% of bankroll)
     Elo Prob: 75.5% | Market: 42.0% | Edge: +33.5%
     Kelly Fraction: 0.578 (scaled: 0.144)
     Expected Value: +79.78%
     Confidence: HIGH

  2. Rockets vs Spurs
     Ticker: KXNBAGAME-26JAN20SASHOU-HOU
     Bet Size: $50.00 (5.00% of bankroll)
     Elo Prob: 71.3% | Market: 60.0% | Edge: +11.3%
     Kelly Fraction: 0.282 (scaled: 0.071)
     Expected Value: +18.83%
     Confidence: MEDIUM
================================================================================
```

## Advantages Over Old System

### Old System (Per-Sport Independent)
- ❌ Fixed bet sizes ($2-$5) regardless of edge
- ❌ No portfolio-level risk management
- ❌ Didn't account for total exposure
- ❌ Could place too many small bets
- ❌ No prioritization by expected value

### New System (Portfolio-Optimized)
- ✅ Kelly Criterion for mathematically optimal sizing
- ✅ Portfolio-level daily risk limits
- ✅ Prioritizes best opportunities by EV
- ✅ Stops when daily limit reached
- ✅ Unified view across all sports
- ✅ Expected ROI tracking

## Integration with Airflow DAG

To integrate into `multi_sport_betting_workflow.py`, replace the `place_bets_on_recommendations` task with:

```python
@task(task_id="place_optimized_portfolio_bets")
def place_portfolio_bets(**context):
    """Place portfolio-optimized bets across all sports."""
    from plugins.portfolio_betting import PortfolioBettingManager
    from plugins.kalshi_betting import KalshiBetting
    from plugins.kalshi_markets import load_kalshi_credentials
    from pathlib import Path
    
    # Load credentials
    api_key_id, private_key = load_kalshi_credentials()
    temp_key = Path('kalshi_private_key.pem')
    temp_key.write_text(private_key)
    
    try:
        # Initialize
        kalshi = KalshiBetting(api_key_id=api_key_id, private_key_path=str(temp_key))
        manager = PortfolioBettingManager(
            kalshi_client=kalshi,
            max_daily_risk_pct=0.10,
            kelly_fraction=0.25,
            dry_run=False  # SET TO TRUE FOR TESTING
        )
        
        # Process bets
        date_str = context['ds']
        results = manager.process_daily_bets(date_str)
        
        return results
    finally:
        if temp_key.exists():
            temp_key.unlink()
```

## Mathematical Background

### Kelly Criterion

The Kelly Criterion maximizes long-term growth rate by betting a fraction of bankroll proportional to edge:

```
f* = (bp - q) / b = edge / odds
```

Where:
- `f*` = fraction of bankroll to bet
- `b` = net odds received on the bet
- `p` = probability of winning
- `q` = 1 - p (probability of losing)

### Why Fractional Kelly?

Full Kelly has high variance. Fractional Kelly (e.g., 1/4 Kelly) reduces volatility while maintaining good growth:

- **Full Kelly**: Maximum growth rate, but ~50% drawdowns possible
- **Half Kelly**: 75% of growth rate, ~25% drawdowns
- **Quarter Kelly**: 50% of growth rate, ~12% drawdowns (recommended)

### Expected Value

Each bet's expected value is calculated as:

```
EV = edge / market_probability
```

Example:
- Elo probability: 75%
- Market probability: 42%
- Edge: 33%
- EV = 33% / 42% = +78.6%

This means for every $1 bet, we expect to profit $0.786 on average.

## Testing

Always test with `--dry-run` first:

```bash
# Test today
python3 plugins/portfolio_betting.py $(date +%Y-%m-%d) --dry-run

# Test specific date
python3 plugins/portfolio_betting.py 2026-01-19 --dry-run
```

Check outputs in `data/portfolio/` before going live.

## Monitoring

Track performance metrics:
- **Actual ROI** vs **Expected ROI**
- **Bankroll growth** over time
- **Hit rate** by confidence level
- **Calibration** of Elo probabilities

Use `plugins/betting_backtest.py` for historical analysis.

## Future Enhancements

Potential improvements:
1. **Correlation modeling**: Reduce bets on correlated outcomes
2. **Dynamic Kelly fraction**: Adjust based on recent performance
3. **Position limits**: Max % in any one sport/game
4. **Time-weighted sizing**: Larger bets when more time to settle
5. **Volatility adjustment**: Reduce sizing in high-variance periods

## References

- Kelly, J. L. (1956). "A New Interpretation of Information Rate"
- Thorp, E. O. (2008). "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market"
- MacLean, L. C., et al. (2011). "The Kelly Capital Growth Investment Criterion"
