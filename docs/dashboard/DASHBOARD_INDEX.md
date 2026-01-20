# 📇 Dashboard Documentation Index

Quick navigation guide to all Streamlit dashboard resources.

---

## 🚀 Getting Started (Choose Your Path)

### Path 1: I Want to Run It NOW (5 minutes)
1. Read: [`DASHBOARD_QUICKSTART.md`](DASHBOARD_QUICKSTART.md)
2. Install: `pip install -r requirements_dashboard.txt`
3. Run: `streamlit run dashboard_app.py`
4. Open: `http://localhost:8501`

### Path 2: I Want to Understand It First (20 minutes)
1. Read: [`DASHBOARD_README.md`](DASHBOARD_README.md) - User Guide
2. Skim: [`DASHBOARD_ARCHITECTURE.md`](DASHBOARD_ARCHITECTURE.md) - Technical Overview
3. Then: Run the app and explore

### Path 3: I Want Complete Documentation (1 hour)
1. Read: [`DASHBOARD_README.md`](DASHBOARD_README.md) - Full guide
2. Read: [`DASHBOARD_ARCHITECTURE.md`](DASHBOARD_ARCHITECTURE.md) - Technical deep dive
3. Review: Code comments in [`dashboard_app.py`](dashboard_app.py)
4. Reference: Elo classes in `plugins/`

---

## 📚 Documentation Files

| File | Size | Purpose | Read Time |
|------|------|---------|-----------|
| **DASHBOARD_QUICKSTART.md** | 7 KB | Get running in 5 minutes | 5 min |
| **DASHBOARD_README.md** | 12 KB | Complete user guide | 15 min |
| **DASHBOARD_ARCHITECTURE.md** | 18 KB | Technical architecture | 30 min |
| **DASHBOARD_SUMMARY.md** | 11 KB | Implementation overview | 10 min |
| **DASHBOARD_INDEX.md** | This file | Navigation guide | 3 min |

---

## 🎯 By Use Case

### "How do I run the dashboard?"
→ **DASHBOARD_QUICKSTART.md** (Installation section)

### "What does each visualization show?"
→ **DASHBOARD_README.md** (Dashboard Tabs section)

### "How do I add a new league?"
→ **DASHBOARD_ARCHITECTURE.md** (Extensibility section)

### "What are the system requirements?"
→ **DASHBOARD_README.md** (Installation section)

### "How does caching work?"
→ **DASHBOARD_ARCHITECTURE.md** (Caching Strategy section)

### "What's the code structure?"
→ **DASHBOARD_ARCHITECTURE.md** (Component Breakdown)

### "How do I troubleshoot issues?"
→ **DASHBOARD_README.md** (Troubleshooting section)

### "What metrics are calculated?"
→ **DASHBOARD_README.md** (Metrics Definitions section)

### "Can I modify the Elo parameters?"
→ **DASHBOARD_ARCHITECTURE.md** (Configuration Details section)

### "How is the data loaded?"
→ **DASHBOARD_ARCHITECTURE.md** (Data Loading Module section)

---

## 📊 Feature Reference

### Visualizations
- **Lift Chart** → DASHBOARD_README.md
- **Win Rate Chart** → DASHBOARD_README.md
- **ROI Chart** → DASHBOARD_README.md
- **Calibration Plot** → DASHBOARD_README.md
- **Cumulative Gain** → DASHBOARD_README.md
- **Details Table** → DASHBOARD_README.md

### Metrics
- **Lift** → DASHBOARD_QUICKSTART.md or DASHBOARD_README.md
- **ROI** → DASHBOARD_QUICKSTART.md or DASHBOARD_README.md
- **Win Rate** → DASHBOARD_README.md
- **Calibration** → DASHBOARD_README.md
- **Cumulative Gain** → DASHBOARD_README.md

### Sports
- **NHL** → DASHBOARD_ARCHITECTURE.md (Sport Config)
- **MLB** → DASHBOARD_ARCHITECTURE.md (Sport Config)
- **NFL** → DASHBOARD_ARCHITECTURE.md (Sport Config)
- **NBA** → DASHBOARD_ARCHITECTURE.md (Sport Config)

---

## 🔧 Technical Reference

### Architecture
- System design → DASHBOARD_ARCHITECTURE.md (System Architecture)
- Component breakdown → DASHBOARD_ARCHITECTURE.md (Component Breakdown)
- Data flow → DASHBOARD_ARCHITECTURE.md (Data Flow Example)

### Implementation
- Data loading → DASHBOARD_ARCHITECTURE.md (Data Loading Module)
- Analytics → DASHBOARD_ARCHITECTURE.md (Analytics Module)
- Visualization → DASHBOARD_ARCHITECTURE.md (Visualization Module)

### Configuration
- Sport settings → DASHBOARD_ARCHITECTURE.md (Configuration Details)
- Elo parameters → DASHBOARD_ARCHITECTURE.md (Configuration Details)
- Cache strategy → DASHBOARD_ARCHITECTURE.md (Caching Strategy)

### Extension
- Add new league → DASHBOARD_ARCHITECTURE.md (Extensibility Points)
- Add new metric → DASHBOARD_ARCHITECTURE.md (Extensibility Points)
- Add new visualization → DASHBOARD_ARCHITECTURE.md (Extensibility Points)

---

## 📁 Code Files Reference

### Main Application
**`dashboard_app.py`** (28 KB)
- Main Streamlit app
- All UI and interactions
- 800+ lines of code

### Dependencies
**`requirements_dashboard.txt`**
- Install with: `pip install -r requirements_dashboard.txt`
- Contains: Streamlit, Plotly, Pandas, NumPy, DuckDB

### Elo Rating Classes
- `plugins/nhl_elo_rating.py` - NHL Elo system
- `plugins/nba_elo_rating.py` - NBA Elo system
- `plugins/mlb_elo_rating.py` - MLB Elo system
- `plugins/nfl_elo_rating.py` - NFL Elo system

### Data Storage
- `data/nhlstats.duckdb` - Main database
- `data/nba/` - NBA JSON files

---

## 🎓 Learning Paths

### For End Users (Non-Technical)
1. DASHBOARD_QUICKSTART.md - Get it running
2. Dashboard UI - Explore the interface
3. DASHBOARD_README.md - Learn what charts mean

### For Data Analysts
1. DASHBOARD_README.md - Understand metrics
2. Dashboard UI - Analyze different sports/seasons
3. Export CSV - Further analysis

### For Software Developers
1. DASHBOARD_QUICKSTART.md - Get it running
2. Review dashboard_app.py - Understand code
3. DASHBOARD_ARCHITECTURE.md - System design
4. Customize and extend

### For Data Scientists
1. DASHBOARD_ARCHITECTURE.md - Analytics module
2. Review plugins/ - Elo implementations
3. dashboard_app.py - Metrics calculation
4. Modify/extend analysis

---

## ⚡ Quick Commands

### Installation
```bash
pip install -r requirements_dashboard.txt
```

### Running
```bash
streamlit run dashboard_app.py
```

### Debugging
```bash
streamlit run dashboard_app.py --logger.level=debug
```

### Clear Cache
- Click "🔄 Refresh Analysis" in sidebar
- Or: `st.cache_data.clear()` in code

---

## 🔍 Search Guide

| Topic | Search In |
|-------|-----------|
| Installation | DASHBOARD_README.md or DASHBOARD_QUICKSTART.md |
| Troubleshooting | DASHBOARD_README.md |
| Features | DASHBOARD_README.md |
| Architecture | DASHBOARD_ARCHITECTURE.md |
| Metrics | DASHBOARD_QUICKSTART.md or DASHBOARD_README.md |
| Extending | DASHBOARD_ARCHITECTURE.md |
| Configuration | DASHBOARD_ARCHITECTURE.md |
| Data | DASHBOARD_ARCHITECTURE.md |
| Code | dashboard_app.py |

---

## 📞 Support Flowchart

```
Have a question?
│
├─ Is it "How do I run this?"
│  └─ → DASHBOARD_QUICKSTART.md
│
├─ Is it about features/UI?
│  └─ → DASHBOARD_README.md
│
├─ Is it about code/architecture?
│  └─ → DASHBOARD_ARCHITECTURE.md
│
├─ Is it about metrics?
│  └─ → DASHBOARD_QUICKSTART.md or DASHBOARD_README.md
│
├─ Is it a technical problem?
│  └─ → DASHBOARD_README.md (Troubleshooting)
│
├─ Do you want to extend it?
│  └─ → DASHBOARD_ARCHITECTURE.md (Extensibility)
│
└─ Still stuck?
   └─ → Review code comments in dashboard_app.py
```

---

## ✅ Verification Checklist

Before running the dashboard, verify:
- [ ] Python 3.8+ installed
- [ ] Dependencies installed: `pip install -r requirements_dashboard.txt`
- [ ] DuckDB database exists: `data/nhlstats.duckdb`
- [ ] Elo classes available: `plugins/*.py`

---

## 🎯 Common Workflows

### Analyze NHL 2023 Season
1. Run: `streamlit run dashboard_app.py`
2. Select: League = NHL
3. Select: Season = 2023
4. Select: Up To Date = 2024-04-01
5. Explore: All 6 tabs

### Compare Two Leagues
1. Run dashboard
2. Analyze: NHL (season X)
3. Note: Key metrics
4. Switch: MLB (season X)
5. Compare: Metrics

### Export Data for Analysis
1. Run dashboard
2. Select: Your sport and season
3. Go to: Details tab
4. Click: "Download as CSV"
5. Analyze: In Excel/Python

### Extend with New Metric
1. Read: DASHBOARD_ARCHITECTURE.md (Extensibility)
2. Add: Metric calculation
3. Create: Visualization function
4. Add: UI tab
5. Test: Run dashboard

---

## 🚀 Next Steps

1. **First Time?**
   → Read DASHBOARD_QUICKSTART.md (5 min)
   → Run `streamlit run dashboard_app.py`

2. **Want Full Guide?**
   → Read DASHBOARD_README.md (15 min)

3. **Need Technical Details?**
   → Read DASHBOARD_ARCHITECTURE.md (30 min)

4. **Want to Extend?**
   → DASHBOARD_ARCHITECTURE.md → Extensibility section

---

## 📞 Quick Reference

| Need | File | Section |
|------|------|---------|
| Installation steps | README | Installation |
| First run guide | QUICKSTART | Installation |
| Feature descriptions | README | Dashboard Tabs |
| Metric definitions | QUICKSTART | Key Metrics Explained |
| Troubleshooting | README | Troubleshooting |
| Architecture | ARCHITECTURE | System Architecture |
| Adding new league | ARCHITECTURE | Extensibility Points |
| Data flow | ARCHITECTURE | Data Flow Example |
| Code comments | dashboard_app.py | N/A |

---

**Happy analyzing! 📊**

Start with **DASHBOARD_QUICKSTART.md** →
```bash
pip install -r requirements_dashboard.txt
streamlit run dashboard_app.py
```
