# MLB Probability Backtesting Plan

## Objective
Test 5 probability improvement suggestions against historical MLB data (2021-present) to determine which enhancements provide measurable lift over pure Elo.

## Backtesting Framework

### Tools
- **backtest_mlb_demo.py**: Demo with synthetic data
- **backtest_mlb_probabilities.py**: Main backtesting engine
- **extract_mlb_data.py**: Data extraction from database

### Data Requirements
To run a full backtest, we need:
1. Historical game results (2021-2024 season)
2. Elo probabilities for each game
3. Market probabilities (Kalshi)
4. Sharp bookmaker probabilities (BetMGM)
5. Game outcomes

### Metrics Tracked
- **Log Loss**: Probability calibration
- **Brier Score**: Mean squared error
- **Accuracy**: Prediction accuracy (>0.5 threshold)
- **ROI**: Simulated betting returns using Kelly criterion
- **Expected Value**: Average EV per bet

## Testing Methodology

### 1. Glicko-2 Blending
**Hypothesis**: Glicko-2's rating reliability improves early-season and for infrequently played teams.

**Backtest**:
- Calculate Glicko-2 ratings alongside Elo
- Test blend ratios: 0% Glicko-2 (pure Elo), 30%, 50%, 70%, 100%
- Compare metrics against pure Elo baseline

**Expected Outcome**: Improved accuracy and ROI, especially for games with teams that have played fewer games.

### 2. Team-Specific Factors
**Hypothesis**: Team-specific performance indicators (home/away splits, offensive/defensive ratings) add predictive value beyond Elo.

**Backtest**:
- Calculate team factors from historical data:
  - Home field advantage (team-specific)
  - Offensive efficiency (runs scored per game)
  - Defensive efficiency (runs allowed per game)
  - Rest day impact (back-to-back games)
- Add these as multiplicative adjustments to base Elo probability
- Test different factor combinations

**Expected Outcome**: Better calibration for extreme probabilities and improved ROI on high-confidence bets.

### 3. Sharp Bookmaker Blending
**Hypothesis**: Blending with sharp market probabilities (BetMGM) improves calibration and reduces model bias.

**Backtest**:
- Test blend ratios: 0% (pure Elo), 30%, 50%, 70%, 100% BetMGM
- Compare against pure Elo baseline
- Analyze sport-specific optimal weights

**Expected Outcome**: Improved log loss and Brier score, especially for games where Elo and market disagree.

### 4. Recency Weighting
**Hypothesis**: More recent games should have greater weight in Elo calculations, allowing faster adaptation to roster changes.

**Backtest**:
- Recalculate Elo ratings with exponential decay: weight = exp(-λ * days_ago)
- Test decay rates: λ = 0.001, 0.005, 0.01, 0.02
- Compare against equal-weighted Elo

**Expected Outcome**: Better performance in second half of season and after major roster changes.

### 5. Situation Adjustments
**Hypothesis**: Specific game situations (back-to-back, rest days, playoffs) systematically affect outcomes beyond Elo.

**Backtest**:
- Identify situations from game schedule:
  - Back-to-back games (teams playing 2nd of a back-to-back)
  - Rest days (4+ days rest)
  - Playoff vs regular season
  - Divisional rivalry games
- Calculate adjustment factors for each situation
- Apply as multiplicative modifiers to base probability
- Test each adjustment separately and in combination

**Expected Outcome**: Improved accuracy for situation-specific games and better overall calibration.

## Execution Plan

### Phase 1: Data Extraction
```bash
python extract_mlb_data.py --start_date 2021-01-01 --end_date 2024-12-31 --output mlb_data_2021_2024.csv
```

### Phase 2: Baseline Backtest
```bash
python backtest_mlb_probabilities.py --db  # Using extracted data
```

### Phase 3: Individual Enhancement Testing
Modify the backtesting script to incorporate each enhancement and test:
1. Add Glicko-2 probability calculation
2. Add team factor adjustments
3. Test different blend ratios with BetMGM
4. Test recency weighting in Elo calculation
5. Add situation-specific adjustments

### Phase 4: Combined Model Optimization
Create a combined model incorporating the best-performing enhancements and optimize hyperparameters.

## Success Criteria
- **Primary**: Improvement in ROI (higher is better)
- **Secondary**: Improvement in log loss and Brier score (lower is better)
- **Tertiary**: Improvement in prediction accuracy (higher is better)

## Timeline
- Data extraction: 1 day
- Baseline backtest: 1 day
- Individual enhancement testing: 3-5 days per enhancement
- Combined model optimization: 2-3 days
- Total: ~2-3 weeks

## Risks
- **Data quality issues**: Missing probabilities or incorrect game results
- **Overfitting**: Optimizing on historical data may not generalize
- **Non-stationarity**: Market dynamics may have changed over time
- **Multicollinearity**: Enhancements may be correlated

## Mitigations
- Use walk-forward validation instead of simple train/test split
- Regularize blend ratios to prevent overfitting
- Test on multiple time periods (2021, 2022, 2023, 2024 separately)
- Use bootstrap resampling for confidence intervals

---

## Next Steps

1. **Extract historical MLB data** from the database using `extract_mlb_data.py`
2. **Run baseline backtest** to establish Elo performance
3. **Implement and test** each enhancement individually
4. **Iterate** based on results to find optimal combination

Would you like me to proceed with any of these steps, or would you prefer to adjust the methodology first?
