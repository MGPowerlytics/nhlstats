# Dashboard Documentation

This directory contains all documentation for the Streamlit analytics dashboard.

## Quick Links

- **[DASHBOARD_QUICKSTART.md](DASHBOARD_QUICKSTART.md)** - Get started in 5 minutes
- **[DASHBOARD_README.md](DASHBOARD_README.md)** - Complete user guide
- **[DASHBOARD_ARCHITECTURE.md](DASHBOARD_ARCHITECTURE.md)** - Technical architecture
- **[DASHBOARD_INDEX.md](DASHBOARD_INDEX.md)** - Feature index
- **[DASHBOARD_SUMMARY.md](DASHBOARD_SUMMARY.md)** - Feature overview

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements_dashboard.txt
   ```

2. Run the dashboard:
   ```bash
   streamlit run dashboard_app.py
   ```

3. Access at: http://localhost:8501

## Features

### Elo Analysis Page
- Lift charts by probability decile
- Calibration plots
- ROI analysis
- Cumulative gain curves
- Elo vs Glicko-2 comparison
- Details table with game-level data
- Season timing analysis

### Betting Performance Page
- Win rate and ROI metrics
- P&L over time
- Breakdown by sport
- All bets table

## Multi-Sport Support

Dashboard supports all 9 sports:
- NBA, NHL, MLB, NFL
- EPL, Ligue 1 (soccer)
- Tennis (ATP/WTA)
- NCAAB, WNCAAB (college basketball)

## Testing

60 comprehensive Playwright tests cover:
- All 9 sports
- All 7 tabs in Elo Analysis
- Chart interactivity
- Data validation
- Responsive design

Run tests:
```bash
pytest tests/test_dashboard_playwright.py -v
```

## Development

The dashboard is built with:
- **Streamlit** - Web framework
- **Plotly** - Interactive charts
- **Pandas** - Data manipulation
- **DuckDB** - Database queries

Main file: `dashboard_app.py` (root directory)

---

For more information, see [README.md](../../README.md) main documentation.
