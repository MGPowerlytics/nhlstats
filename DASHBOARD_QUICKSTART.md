# 🚀 Quick Start Guide - Sports Dashboard

Get the Streamlit dashboard running in 5 minutes!

## Installation

```bash
# Install dependencies
pip install -r requirements_dashboard.txt
```

## Running the Dashboard

```bash
# Start the app
streamlit run dashboard_app.py
```

Open your browser to: **http://localhost:8501**

---

## First Steps

### 1. Select a League
Choose from:
- 🏒 **NHL** - National Hockey League
- 🏀 **NBA** - National Basketball Association  
- ⚾ **MLB** - Major League Baseball
- 🏈 **NFL** - National Football League

### 2. Choose a Season
Pick any season with available data in your database.

### 3. Set Analysis Date
- Analyze full season (set to season end)
- Simulate mid-season (set to any date during season)

### 4. Explore Visualizations
6 tabs with different views:
- **📊 Lift Chart** - Model discrimination by confidence level
- **📈 Win Rate** - Actual home team performance
- **💰 ROI** - Profitability analysis
- **🎯 Calibration** - Model accuracy plot
- **📉 Cumulative Gain** - Gains vs random baseline
- **📋 Details** - Full statistics table + CSV download

---

## What Each Chart Shows

### Lift Chart
```
Shows how much better the model is than random guessing
- Bars above 1.0 = Model is good at this confidence level
- Bars below 1.0 = Model performs worse than baseline
```

### Win Rate Chart
```
Displays actual home team win rates by confidence decile
- Green bars = Above average confidence level
- Red bars = Below average confidence level
```

### ROI Chart
```
Estimated return on investment assuming -110 betting odds
- Positive = Profitable picks
- Negative = Losing picks
```

### Calibration Plot
```
Compares predicted probabilities vs actual outcomes
- Points on diagonal = Perfect calibration
- Points above line = Model underconfident
- Points below line = Model overconfident
```

### Cumulative Gain Chart
```
Shows total wins captured by top confidence levels
- Higher curve = Better model discrimination
- Red diagonal = Random selection baseline
```

### Details Table
```
Complete statistics per decile
- Games, Wins, Win Rates, Lift values
- Cumulative gains and ROI calculations
- Download as CSV for further analysis
```

---

## Example Analysis

### Scenario: Analyze NHL 2023 Season

1. **Select League**: NHL
2. **Select Season**: 2023
3. **Set Date**: 2024-04-01 (end of regular season)
4. **View Results**:
   - See which Elo confidence levels predict home wins best
   - Identify profitable betting ranges
   - Check calibration of predictions

### Expected Output
```
Total Games: 1,230
Baseline Win Rate: 50.2%
Top Decile Lift: 1.18x
Top Decile Win Rate: 59.3%
Top Decile ROI: +0.85%
```

---

## Data Requirements

### For DuckDB Sports (NHL, MLB, NFL)
- Database: `data/nhlstats.duckdb`
- Tables: `games`, `mlb_games`, `nfl_games`
- Required columns: dates, teams, scores

### For NBA (JSON)
- Directory: `data/nba/`
- Structure: `data/nba/YYYY-MM-DD/`
- Files: `scoreboard_*.json`, `boxscore_*.json`

---

## Troubleshooting

### "No data available for [Sport]"
❌ Database or JSON files not found  
✅ Verify: `data/nhlstats.duckdb` exists

### "Not enough games for decile analysis"
❌ Selected date has <10 games  
✅ Try: Select later date in season

### Slow first load
❌ First load calculates Elo ratings  
✅ Normal: Takes 5-10 seconds  
✅ Fast: Subsequent loads use cache

### "Refresh Analysis" button
🔄 Clears all caches and reloads data  
🔄 Use if database was updated

---

## Key Metrics Explained

### Lift
```
Formula: Win_Rate_in_Decile / Overall_Baseline_Rate

Example:
- Baseline win rate: 50%
- Top decile win rate: 62%
- Lift = 62% / 50% = 1.24x

Interpretation:
- 1.24x means 24% better than random
- >1.0 = Model is predictive
- <1.0 = Model is counterproductive
```

### ROI (Return on Investment)
```
Formula: (Win_Rate - 50%) × 0.91

Example:
- Win rate: 62%
- ROI = (62% - 50%) × 0.91 = +1.09%

Interpretation:
- +1.09% = Profit on every $100 wagered
- Assumes -110 odds (standard sportsbook)
- 0.91 factor accounts for "vig" (commission)
```

### Cumulative Gain
```
Shows total wins captured by top confidence levels

Example (from high to low confidence):
- Decile 10: 15% of games, 18% of wins
- Deciles 9-10: 30% of games, 35% of wins
- Deciles 8-10: 45% of games, 53% of wins

Interpretation:
- Model concentrates wins in high-confidence picks
- Steeper curve = Better discrimination
```

---

## Tips for Analysis

### 1. Focus on Top Deciles
High-confidence picks (deciles 9-10) are most actionable:
```
If deciles 9-10 have:
- Lift > 1.10 → Strong predictive power
- Lift > 1.05 → Moderate predictive power  
- Lift < 1.00 → Avoid these predictions
```

### 2. Check Calibration
Well-calibrated model predicts 60% when it says 60%:
```
If predicted = 60% but actual = 70% → Underconfident
If predicted = 60% but actual = 50% → Overconfident
```

### 3. Validate Sample Size
Need sufficient games per decile:
```
<10 games per decile = Unreliable estimates
>100 games per decile = Robust conclusions
```

### 4. Compare Across Seasons
Export data and compare year-over-year performance to detect model drift.

---

## Files Created

```
/nhlstats/
├── dashboard_app.py              ← Main Streamlit app
├── requirements_dashboard.txt    ← Install with: pip install -r ...
├── DASHBOARD_README.md           ← Full documentation
├── DASHBOARD_QUICKSTART.md       ← This file!
└── data/
    ├── nhlstats.duckdb          ← Must exist
    └── nba/                      ← Required for NBA analysis
```

---

## Next Steps

### Beginner
1. ✅ Install and run dashboard
2. ✅ Try different leagues
3. ✅ Compare seasons
4. ✅ Download CSV reports

### Intermediate
1. 📊 Analyze specific time periods
2. 💾 Export data for custom analysis
3. 📈 Track model performance over time
4. 🎯 Identify profitable ranges

### Advanced
1. 🔧 Modify Elo parameters
2. 📝 Add custom metrics
3. 🎨 Create additional visualizations
4. 🔌 Integrate with betting systems

---

## Support

### Documentation
- Full guide: `DASHBOARD_README.md`
- Code comments: In `dashboard_app.py`

### Streamlit Help
```bash
streamlit --help
streamlit run dashboard_app.py --logger.level=debug
```

### DuckDB Queries
```bash
# Connect to database
sqlite3 data/nhlstats.duckdb

# List tables
.tables

# Query games
SELECT COUNT(*) FROM games;
```

---

## Performance Tips

| Action | Speed | Why |
|--------|-------|-----|
| First load | 5-10s | Calculates Elo ratings |
| Subsequent loads | <1s | Uses cache |
| Change league | 1-5s | Recalculates for new data |
| Change date | <1s | Same cache |
| Click refresh | 5-10s | Clears cache & reloads |

**Tip:** Cache automatically updates if underlying database changes.

---

**Ready to go!** 🚀

```bash
streamlit run dashboard_app.py
```
