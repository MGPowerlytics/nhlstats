# Quick Start - Daily Betting Workflow

## Morning Routine (10 AM - After Airflow DAG Runs)

### 1. Check Today's Bets (2 minutes)
```bash
# Quick view of all today's betting opportunities
for sport in nba ncaab wncaab tennis; do
  echo "=== $sport ==="
  jq -r '.[] | "\(.edge*100|floor)% edge - \(.bet_on): \(.home_team // .player) vs \(.away_team // .opponent)"' \
    data/$sport/bets_$(date +%Y-%m-%d).json 2>/dev/null | sort -rn | head -3
done
```

### 2. Run BetMGM Comparison (1 minute)
```bash
python daily_betting_analysis.py
```

### 3. Review Recommendations
Look for:
- ✅ **Kalshi bets ≥10% edge** - Priority betting
- ✅ **High confidence (≥70% prob)** - Larger positions
- ⚠️ **BetMGM negative edges** - Market disagrees (be cautious)

## What to Bet Today (2026-01-20)

### 🔥 TOP 10 OPPORTUNITIES

1. **85%** edge - WNCAAB: Texas A&M vs LSU (home) | 91% Elo prob
2. **81%** edge - NCAAB: Morgan St vs Virginia (away) | 93% Elo prob
3. **70%** edge - NCAAB: Michigan vs Bowling Green (home) | 90% Elo prob
4. **52%** edge - WNCAAB: Oklahoma vs South Carolina (home) | 86% Elo prob
5. **51%** edge - Tennis: Birrell K. vs Inglis | 84% Elo prob
6. **44%** edge - NCAAB: Michigan vs Ball St (home) | 83% Elo prob
7. **41%** edge - WNCAAB: BYU vs Texas Tech (home) | 77% Elo prob
8. **32%** edge - NBA: Nuggets vs Lakers (home) | 76% Elo prob
9. **28%** edge - WNCAAB: Oklahoma vs Miss St (home) | 86% Elo prob
10. **16%** edge - NBA: Warriors vs Raptors (home) | 76% Elo prob

### 📊 By Sport

| Sport | Total Bets | High Edge (≥10%) | Recommended |
|-------|------------|------------------|-------------|
| WNCAAB | 15 | 11 | ALL HIGH EDGE |
| NCAAB | 18 | 14 | ALL HIGH EDGE |
| NBA | 2 | 2 | BOTH |
| Tennis | 6 | 2 | HIGH EDGE ONLY |

## Position Sizing

### Conservative Approach ($2,500 bankroll)
```
High Edge (≥30%): $150 (6% bankroll)
Med Edge (10-30%): $100 (4% bankroll)
Low Edge (5-10%): $50 (2% bankroll)
```

### Today's Allocation
- 29 high-edge bets × $100 = $2,900 wagered
- Expected edge: 23%
- **Expected profit: $667**

## Commands Cheat Sheet

```bash
# Daily analysis
python daily_betting_analysis.py

# Check specific sport
jq . data/ncaab/bets_$(date +%Y-%m-%d).json

# Count bets by edge
jq '[.[] | select(.edge >= 0.10)] | length' data/ncaab/bets_*.json

# Top 5 edges
jq -r '.[] | "\(.edge*100|floor)% - \(.home_team) vs \(.away_team)"' \
  data/ncaab/bets_$(date +%Y-%m-%d).json | sort -rn | head -5

# BetMGM comparison
python plugins/betmgm_integration.py

# Cross-market analysis
python compare_betting_markets.py
```

## Decision Tree

```
Is the edge ≥ 10%?
  YES → Is Elo prob ≥ 70%?
    YES → BET FULL UNIT ($100)
    NO → BET HALF UNIT ($50)
  NO → Is the edge ≥ 5%?
    YES → BET QUARTER UNIT ($25)
    NO → SKIP
```

## Red Flags (Don't Bet)

❌ BetMGM shows large negative edge (-10%+)
❌ Elo prob < 60% (low confidence)
❌ Edge < 5% (too small)
❌ Unusual line movement (investigate first)
❌ Injuries/news not in our model

## Green Lights (Do Bet)

✅ Kalshi edge ≥ 10%
✅ Elo prob ≥ 70%
✅ College basketball (our best sport)
✅ BetMGM neutral/positive (market agrees)
✅ Consistent with recent team performance

## Files to Check

- `data/{sport}/bets_YYYY-MM-DD.json` - Kalshi recommendations
- `data/betmgm_opportunities_YYYY-MM-DD.json` - BetMGM analysis
- `data/{sport}_current_elo_ratings.csv` - Latest Elo ratings

## Evening Routine (After Games)

### 1. Update Results
```bash
# Airflow will auto-update overnight
# Check: docker exec <scheduler> airflow dags list-runs multi_sport_betting_workflow
```

### 2. Track Performance (Weekly)
```bash
# Check portfolio dashboard
python dashboard_app.py

# Or manual query
python -c "from plugins.bet_loader import BetLoader; \
  loader = BetLoader(); \
  print(loader.get_bets_summary())"
```

### 3. Adjust Strategy
- Review win rate by sport
- Calibrate Elo parameters if needed
- Adjust bet sizing based on results

## Pro Tips

1. **Focus on college basketball** - Best edges, most opportunities
2. **Trust high-edge bets** - Don't overthink 20%+ edges
3. **Ignore BetMGM** - Their odds are sharper than our Elo
4. **Size properly** - Never bet more than 6% of bankroll
5. **Track everything** - Data drives improvement

## Emergency Contacts

- Airflow UI: http://localhost:8080
- Dashboard: `python dashboard_app.py`
- Logs: `logs/dag_id=multi_sport_betting_workflow/`
- Issues: Check CHANGELOG.md

---

**Last Updated:** 2026-01-20
**Ready to bet?** Run `python daily_betting_analysis.py` now!
