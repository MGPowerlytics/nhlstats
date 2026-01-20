# Sports Betting Analytics Dashboard

This interactive dashboard allows you to visualize lift/gain charts, analyze model calibration, and check ROI for Elo rating models across different leagues (MLB, NHL, NFL, NBA).

## Features
- **Multi-League Support:** Analyze MLB, NHL, NFL, and NBA data.
- **Historical Analysis:** Filter by specific seasons or analyze all-time history.
- **Elo Parameter Tuning:** Experiment with K-Factor and Home Advantage settings in real-time.
- **Key Metrics:**
  - **Lift/Gain Charts:** Visualize how much better the model is than random guessing.
  - **Calibration Plots:** Check if predicted probabilities match actual win rates.
  - **ROI Analysis:** Estimate profitability based on standard -110 odds.
  - **Cumulative Gain:** See the percentage of wins captured by top-tier predictions.

## Setup & Running

1. **Install Dependencies:**
   ```bash
   pip install -r requirements_dashboard.txt
   ```

2. **Run the Dashboard:**
   ```bash
   streamlit run dashboard_app.py
   ```

3. **Access:**
   Open your browser to `http://localhost:8501`.

## Extensibility
The dashboard is designed to be easily extensible. 
- **New Leagues:** Add new logic in `load_data()` and ensure an Elo class exists in `plugins/`.
- **New Metrics:** Add calculation functions in `dashboard_app.py` and display them in a new tab.
