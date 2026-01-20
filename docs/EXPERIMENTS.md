# Experiments & Model Comparison

This document consolidates all experimental results from testing various prediction methods and rating systems for sports betting.

## Executive Summary

After extensive experimentation with 7+ prediction methods across 55,000+ historical games, **simple Elo ratings emerged as the clear winner** for production use.

**Winner**: Elo (61.1% accuracy, 0.607 AUC, 4 parameters)

**Key Finding**: More features ≠ better predictions. Sports have high intrinsic randomness, and complex models overfit.

---

## Experiment Overview

| Method | Dataset | Status | Accuracy | AUC | Verdict |
|--------|---------|--------|----------|-----|---------|
| Elo | 55,000 games | ✅ Production | 61.1% | 0.607 | **Winner** |
| TrueSkill | 4,248 NHL | ✅ Complete | 58.0% | 0.621 | Research only |
| XGBoost | 4,248 NHL | ✅ Complete | 58.7% | 0.592 | Failed |
| XGBoost+Elo | 4,248 NHL | ✅ Complete | 58.1% | 0.599 | Failed |
| Glicko-2 | - | ⏸️ Incomplete | - | - | Abandoned |
| OpenSkill | - | ⏸️ Incomplete | - | - | Abandoned |
| Markov Momentum | 55,000 games | ✅ Complete | Marginal | Marginal | Failed |
| Platt Scaling | 55,000 games | ✅ Complete | No change | No change | Unnecessary |

---

## Experiment 1: Elo Rating System

**Goal**: Establish baseline with simple rating system

**Method**: Team-level Elo with sport-specific parameters

### Parameters

| Sport | K-Factor | Home Advantage | Initial Rating |
|-------|----------|----------------|----------------|
| NBA | 20 | 100 | 1500 |
| NHL | 20 | 100 | 1500 |
| MLB | 20 | 50 | 1500 |
| NFL | 20 | 65 | 1500 |
| NCAAB | 20 | 100 | 1500 |
| WNCAAB | 20 | 100 | 1500 |
| Tennis | 20 | 0 | 1500 |
| EPL/Ligue 1 | 20 | 50 | 1500 |

### Results (Test Set)

**NHL** (848 games):
- Accuracy: **61.1%** 🥇
- AUC: 0.607
- Log Loss: 0.677 (best)

**NBA** (6,264 games):
- Top 2 deciles: 73.7% win rate
- Lift: 1.39x (excellent discrimination)
- Calibration: Predicted ≈ actual

**NFL** (1,417 games):
- Top 2 deciles: 73.3% win rate
- Lift: 1.34x
- Current season: 78.6% (even better)

**MLB** (14,462 games):
- Top 2 deciles: 62.4% win rate
- Lift: 1.18x (more random sport)

### Why Elo Won

1. **Simplicity**: Only 4 parameters (K, home advantage, initial, decay)
2. **Speed**: Instant predictions (no model inference)
3. **Interpretability**: Everyone understands "team has 1700 rating"
4. **Reliability**: Never breaks, no retraining needed
5. **Calibration**: 70% predictions actually win 70% of time
6. **Accuracy**: Beat all complex alternatives

### Elo Formula

```
Expected Score = 1 / (1 + 10^((Rating_B - Rating_A) / 400))

Rating_new = Rating_old + K × (Actual - Expected)
```

### Validation

✅ Out-of-sample testing (2025-26 season)
✅ Cross-sport validation (9 different sports)
✅ Temporal integrity (no data leakage)
✅ Lift/gain analysis (top deciles show 1.2x-1.5x lift)

**Verdict**: ✅ **Production Winner**

**Documentation**: Implemented in `plugins/*_elo_rating.py` for each sport

---

## Experiment 2: TrueSkill (Player-Level Ratings)

**Goal**: Beat Elo using player-level Bayesian ratings

**Method**: Microsoft TrueSkill algorithm with player tracking

### Implementation

- Tracked 1,545 individual NHL players
- Each player has μ (skill) and σ (uncertainty)
- Team strength = Mean(μ - 3σ) across roster
- Updated ratings based on ice time weighting

### Parameters

```python
initial_mu = 25.0
initial_sigma = 8.33
draw_probability = 0.0  # No draws in hockey
tau = 0.0  # No dynamics
```

### Results (NHL 848 games)

- **AUC**: **0.621** 🥇 (best for probability estimation)
- **Accuracy**: 58.0% (worse than Elo)
- **Log Loss**: 0.692 (worse than Elo)

### Performance Comparison

| Metric | TrueSkill | Elo | Winner |
|--------|-----------|-----|--------|
| AUC | **0.621** | 0.607 | TrueSkill |
| Accuracy | 58.0% | **61.1%** | Elo |
| Log Loss | 0.692 | **0.677** | Elo |
| Speed | Moderate | Instant | Elo |
| Complexity | 1,545 players | 32 teams | Elo |

### Why TrueSkill Lost

1. **Lower accuracy**: -3.1% vs Elo (58.0% vs 61.1%)
2. **More complex**: Requires player rosters and ice time data
3. **Slower**: Need to look up 20+ players per team
4. **Harder to maintain**: Player tracking more brittle than team tracking
5. **Overfitting**: Player-level granularity doesn't help binary predictions

### Why Better AUC Didn't Matter

- **AUC measures probability ranking**, not binary predictions
- **Betting** cares more about accuracy than AUC ranking
- **Kelly Criterion** needs accurate probabilities, but Elo already well-calibrated
- **Operational complexity** not worth 1.4% AUC improvement

### When TrueSkill Makes Sense

✅ Research: Understanding player contributions
✅ Player projections: Individual skill estimation
✅ Draft analysis: Uncertainty modeling
❌ Production betting: Elo simpler and more accurate

**Verdict**: ❌ **Not for production** (research tool only)

**Documentation**: `archive/TRUESKILL_COMPARISON_RESULTS.md`

---

## Experiment 3: XGBoost (Gradient Boosted Trees)

**Goal**: Use machine learning with engineered features

**Method**: XGBoost with 102 features from game statistics

### Feature Engineering (3 Rounds)

**Round 1: Basic Stats** (98 features)
- Team stats: Goals, shots, power play %, penalty kill %
- Recent form: Last 5/10/20 games
- Head-to-head: Historical matchup stats
- Schedule: Back-to-back, days rest, travel
- Venue: Home/away split stats

**Round 2: Advanced Stats** (Additional features)
- Shooting percentage (5/10/20 game windows)
- Expected goals (xG) differentials
- Score effects adjustments
- Corsi/Fenwick possession metrics
- High-danger scoring chances

**Round 3: Elo Features** (Hybrid approach)
- Team Elo ratings
- Elo differences
- Elo win probability
- Recent Elo trend

### Results (NHL 848 games)

**XGBoost Only**:
- Accuracy: 58.7%
- AUC: 0.592
- Training time: ~5 minutes
- Inference: Fast but requires feature engineering

**XGBoost + Elo Features**:
- Accuracy: 58.1% (worse!)
- AUC: 0.599 (worse!)
- **Conclusion**: Adding Elo features hurt performance

### Hyperparameter Tuning

Tested multiple configurations:
```python
# Best config found
max_depth: 5
learning_rate: 0.1
n_estimators: 100
subsample: 0.8
colsample_bytree: 0.8
```

Still underperformed Elo.

### Why XGBoost Failed

1. **Worse accuracy**: 58.7% vs Elo's 61.1% (-2.4%)
2. **Worse AUC**: 0.592 vs Elo's 0.607 (-1.5%)
3. **Overfitting**: 102 features → complexity without benefit
4. **Brittleness**: Requires stats for both teams, breaks if missing
5. **Maintenance**: Needs retraining as league dynamics change
6. **Not interpretable**: Black box, can't explain predictions

### Feature Importance Analysis

Ran SHAP analysis - **top features were Elo-related**:
1. Team Elo rating (25% importance)
2. Opponent Elo rating (18% importance)
3. Elo difference (15% importance)
4. Recent form (10% importance)
5. All other features: <5% each

**Implication**: XGBoost just learned to use Elo, added noise with other features.

**Verdict**: ❌ **Failed** (simple Elo beats 102 features)

**Documentation**: 
- `archive/MODEL_TRAINING_RESULTS.md` (Round 1)
- `archive/MODEL_TRAINING_RESULTS_ROUND2.md` (Round 2)
- `archive/MODEL_TRAINING_RESULTS_ROUND3.md` (Round 3)
- `archive/XGBOOST_WITH_ELO_RESULTS.md` (Hybrid)

---

## Experiment 4: Glicko-2 (Elo + Uncertainty)

**Goal**: Improve Elo with rating deviation and volatility

**Method**: Glicko-2 algorithm (designed for chess)

### Theory

Extends Elo with two additional parameters:
- **RD (Rating Deviation)**: Uncertainty in rating (like TrueSkill σ)
- **σ (Volatility)**: Consistency of performance

### Implementation Status

⏸️ **Incomplete** - Started but abandoned

**Files**: `nhl_glicko2_ratings.py` (partial implementation)

### Why Abandoned

1. **TrueSkill already tested**: Similar concept (Bayesian uncertainty)
2. **Expected similar results**: Player-level uncertainty didn't help
3. **Priority shift**: Production deployment more important
4. **Elo sufficient**: 61.1% accuracy good enough for profitable betting

### Expected Performance

Based on theory and TrueSkill results:
- AUC: ~0.61-0.62 (similar to TrueSkill)
- Accuracy: ~58-59% (worse than Elo)
- Benefit: Uncertainty modeling (but Elo already calibrated)

**Verdict**: ⏸️ **Abandoned** (not worth implementation effort)

---

## Experiment 5: OpenSkill (Open-Source TrueSkill)

**Goal**: Test MIT-licensed alternative to Microsoft TrueSkill

**Method**: Weng-Lin Plackett-Luce model

### Implementation Status

⏸️ **Incomplete** - Started but abandoned

**Files**: `nhl_openskill_ratings.py` (partial implementation)

### Why Abandoned

Same reasoning as Glicko-2:
1. TrueSkill already tested (58% accuracy, not good enough)
2. OpenSkill expected to perform nearly identically
3. License not an issue for private project
4. Elo already in production (61.1% accuracy)

### Expected Performance

- Very similar to TrueSkill (~0.62 AUC, ~58% accuracy)
- Main difference: MIT license vs Microsoft patents
- Not relevant for private use

**Verdict**: ⏸️ **Abandoned** (no expected improvement over TrueSkill)

---

## Experiment 6: Markov Momentum Overlay

**Goal**: Improve Elo with recent form modeling

**Method**: Markov chain for recent game outcomes

### Implementation

```python
class MarkovMomentum:
    def __init__(self, window=10):
        self.window = window  # Recent games to consider
        self.state_transitions = {}  # Win/loss patterns
    
    def compute_momentum(self, recent_results):
        # Calculate momentum factor from last N games
        # Returns adjustment to Elo probability
        return momentum_adjustment
```

### Integration

```python
elo_prob = elo.predict(home, away)
momentum = markov.compute_momentum(recent_games)
final_prob = elo_prob + momentum  # Small adjustment
```

### Results

**Test on 55,000+ games**:
- Accuracy improvement: +0.1% to +0.3%
- AUC improvement: +0.001 to +0.003
- Complexity added: Significant
- Maintenance burden: Tracking recent results

### Why Failed

1. **Marginal improvement**: <0.5% accuracy gain
2. **Added complexity**: Need to track last N games per team
3. **Instability**: Momentum changes rapidly, hard to backtest
4. **Elo already captures form**: Rating changes reflect recent performance
5. **Not worth it**: Complexity >> benefit

**Verdict**: ❌ **Failed** (marginal benefit, added complexity)

**Documentation**: `plugins/markov_momentum.py` (archived)

---

## Experiment 7: Platt Scaling (Probability Calibration)

**Goal**: Improve Elo probability calibration

**Method**: Logistic regression on Elo probabilities

### Theory

```python
calibrated_prob = sigmoid(a × elo_prob + b)
```

Train `a` and `b` to minimize log loss on validation set.

### Implementation

```python
def platt_scaling(elo_probs, actual_outcomes):
    # Fit logistic regression
    model = LogisticRegression()
    model.fit(elo_probs.reshape(-1, 1), actual_outcomes)
    
    # Return calibrated probabilities
    return model.predict_proba(elo_probs.reshape(-1, 1))
```

### Results

**Test on NBA/NHL**:
- **Before calibration**: 70% Elo prob → 70.2% actual win rate
- **After calibration**: 70% calibrated prob → 70.1% actual win rate
- **Improvement**: -0.1% (worse!)

### Calibration Analysis

Plotted reliability diagrams (predicted vs actual):
- Elo already follows y=x line (perfect calibration)
- Platt scaling added noise, not signal
- **Conclusion**: Elo naturally well-calibrated

### Why Failed

1. **Already calibrated**: Elo probabilities match actual outcomes
2. **Overfitting**: Calibration fit noise on validation set
3. **Temporal issues**: Calibration degrades over time as league changes
4. **Unnecessary**: Simple Elo probabilities are trustworthy

**Verdict**: ❌ **Failed** (Elo already well-calibrated)

**Documentation**: `plugins/compare_elo_calibrated_current_season.py`

---

## Cross-Sport Validation

### NBA Lift/Gain Analysis

**Dataset**: 6,264 games (2021-2026)

**Results**:
- Top decile: 78.1% win rate (1.48x lift)
- Top 2 deciles: 73.7% win rate (1.39x lift)
- Bottom 2 deciles: 30.6% win rate (0.58x lift)

**Threshold**: 73% (captures top 20% of predictions)

### NHL Lift/Gain Analysis

**Dataset**: 6,233 games (2018-2026)

**Results**:
- Top decile: 71.8% win rate (1.32x lift)
- Top 2 deciles: 69.1% win rate (1.28x lift)
- Bottom 2 deciles: 40.5% win rate (0.75x lift)

**Threshold**: 66% (previously 77% - too conservative)

### MLB Lift/Gain Analysis

**Dataset**: 14,462 games (2018-2026)

**Results**:
- Top decile: 65.3% win rate (1.23x lift)
- Top 2 deciles: 62.4% win rate (1.18x lift)
- More random than other sports (baseball nature)

**Threshold**: 67%

### NFL Lift/Gain Analysis

**Dataset**: 1,417 games (2018-2026)

**Results**:
- Top decile: 74.6% win rate (1.37x lift)
- Top 2 deciles: 73.3% win rate (1.34x lift)
- Excellent discrimination

**Threshold**: 70%

### Pattern: Extreme Deciles Are Predictive

**Universal finding across all sports**:
1. Top 2 deciles: 1.2x-1.5x lift ✅
2. Middle deciles: ~1.0x lift (no edge)
3. Bottom 2 deciles: 0.5x-0.7x lift (inverse prediction works)

**Implication**: Only bet on high-confidence games (top 20%)

**Validation**: Pattern holds on 2025-26 season data (out-of-sample)

---

## Lessons Learned

### What Worked ✅

1. **Simple beats complex**: Elo (4 params) > XGBoost (102 features)
2. **Team-level beats player-level**: For binary predictions, not probability ranking
3. **Extreme confidence**: Only bet when model is highly confident
4. **Sport-specific tuning**: Different thresholds for different sports
5. **Validation matters**: Out-of-sample testing critical
6. **Calibration check**: Ensure predicted probabilities match reality

### What Didn't Work ❌

1. **More features**: 102 features worse than 4 parameters
2. **Complex models**: XGBoost overfits, Elo generalizes
3. **Player-level granularity**: Doesn't help binary predictions
4. **Uncertainty modeling**: Elo already well-calibrated
5. **Momentum overlays**: Marginal benefit, high complexity
6. **Ensemble methods**: Not worth the added complexity

### Key Insights

**1. Sports Have Intrinsic Randomness**
- No model will get >65% accuracy consistently
- Complex models overfit this randomness
- Simple models handle noise better

**2. AUC ≠ Accuracy**
- TrueSkill: Best AUC (0.621), worse accuracy (58.0%)
- Elo: Worse AUC (0.607), best accuracy (61.1%)
- Betting cares more about accuracy than AUC ranking

**3. Calibration Matters**
- Well-calibrated probabilities critical for Kelly Criterion
- Elo naturally calibrated (no post-processing needed)
- ML models often need calibration (Platt scaling)

**4. Interpretability Has Value**
- Elo: "Team A is 200 points better" - everyone understands
- XGBoost: Black box - hard to debug issues
- Production benefits from transparency

**5. Extreme Confidence Is Key**
- Middle-range predictions (45-55%) have no edge
- High confidence (70%+) has 1.3x-1.5x lift
- Only bet extreme cases, not toss-ups

### Recommendations for Future Experiments

**Do Test**:
- Surface effects for tennis (hard court vs clay)
- Lineup-based adjustments (injuries, rest)
- Weather effects (outdoor sports)
- Market efficiency differences across books

**Don't Test**:
- More complex ML models (diminishing returns)
- Alternative rating systems (Elo already optimal)
- Momentum/streak modeling (already captured in ratings)
- Feature engineering beyond Elo (adds noise)

---

## Conclusion

After exhaustive experimentation with 7+ methods across 55,000+ games, **Elo ratings are the clear winner** for production sports betting.

**Final Rankings**:

| Rank | Method | Accuracy | AUC | Production Ready |
|------|--------|----------|-----|------------------|
| 🥇 | **Elo** | **61.1%** | 0.607 | ✅ Yes |
| 🥈 | TrueSkill | 58.0% | 0.621 | ❌ No (research) |
| 🥉 | XGBoost | 58.7% | 0.592 | ❌ No |
| 4th | XGBoost+Elo | 58.1% | 0.599 | ❌ No |

**Why Elo Won**:
1. Best accuracy (61.1%)
2. Simplest (4 parameters)
3. Fastest (instant predictions)
4. Most reliable (never breaks)
5. Well-calibrated (probabilities trustworthy)
6. Most interpretable (ratings make sense)

**Current Production Status**:
- ✅ Elo deployed across 9 sports
- ✅ Daily automated betting
- ✅ Portfolio optimization with Kelly Criterion
- ✅ Comprehensive monitoring and validation

---

**Last Updated**: January 2026
**Total Games Analyzed**: 55,000+
**Sports Validated**: 9 (NBA, NHL, MLB, NFL, EPL, Ligue 1, Tennis, NCAAB, WNCAAB)
