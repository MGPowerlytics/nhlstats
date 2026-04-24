# Elo Rating Fix - Complete Solution

## Problem Identified
The Elo rating system has been using incomplete data:
- **NHL**: Using `games` table (30 games) instead of `unified_games` (9,177 games)
- **NBA**: Same issue - narrow rating range (58 points vs expected 300)
- Other sports likely have similar issues

## Root Cause
In `dags/multi_sport_betting_workflow.py`, the `update_elo_ratings()` function queries from sport-specific tables (`games`, `nba_games`, etc.) instead of the comprehensive `unified_games` table.

## Immediate Fix (Already Done)
✅ **NHL Elo ratings have been regenerated** using all historical data from `unified_games`:
- 9,177 games processed (vs 30 previously)
- Rating range: 257.5 points (vs 24 previously)
- Probability range: 37.6% to 85.4% (vs ~5% previously)

## Next Steps Required

### 1. Fix Other Sports
Run the comprehensive fix script:
```bash
cd /mnt/data2/nhlstats
POSTGRES_HOST=localhost python scripts/fix_all_sports_elo.py
```

This will fix:
- NBA (critical - 58 point range vs expected 300)
- MLB
- NFL
- NCAAB
- WNCAAB
- Tennis

### 2. Update Airflow DAG
The DAG needs to be updated to use `unified_games`. Key changes needed in `update_elo_ratings()`:

**For NHL (example):**
```python
# OLD (line ~502):
query = """
    WITH ranked_games AS (
        SELECT game_date, home_team_abbrev, away_team_abbrev,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win,
               ROW_NUMBER() OVER (
                   PARTITION BY game_date, home_team_abbrev, away_team_abbrev
                   ORDER BY game_id
               ) as rn
        FROM games  # <-- PROBLEM: Uses games table
        WHERE game_state IN ('OFF', 'FINAL', 'Final')
          AND home_team_abbrev NOT IN :ex_teams
          AND away_team_abbrev NOT IN :ex_teams
    )
    SELECT game_date, home_team_abbrev as home_team,
           away_team_abbrev as away_team, home_win
    FROM ranked_games
    WHERE rn = 1
    ORDER BY game_date, home_team
"""

# NEW:
query = """
    SELECT
        game_date,
        home_team_name,
        away_team_name,
        CASE WHEN home_score > away_score THEN 1 ELSE 0 END as home_win
    FROM unified_games  # <-- FIX: Use unified_games
    WHERE sport = 'NHL'
      AND home_score IS NOT NULL
      AND away_score IS NOT NULL
      AND home_team_name IS NOT NULL
      AND away_team_name IS NOT NULL
    ORDER BY game_date
"""
```

**Add team name mapping for NHL:**
```python
# Add this mapping in the NHL section
team_mapping = {
    'Anaheim Ducks': 'ANA', 'Arizona Coyotes': 'ARI', 'Boston Bruins': 'BOS',
    # ... full mapping for all NHL teams
}

# Use mapping when processing games
home_team = team_mapping.get(game["home_team_name"], game["home_team_name"])
away_team = team_mapping.get(game["away_team_name"], game["away_team_name"])
```

### 3. Add Logging to DAG
Add logging to show rating changes:

```python
# After calculating new ratings, add:
if previous_ratings:  # Loaded from current CSV file
    print(f"\n📊 {sport.upper()} Elo Rating Changes:")
    print("=" * 50)

    common_teams = set(new_ratings.keys()) & set(previous_ratings.keys())
    print(f"  Teams: {len(new_ratings)} total ({len(common_teams)} updated)")

    if common_teams:
        changes = []
        for team in common_teams:
            old = previous_ratings[team]
            new = new_ratings[team]
            change = new - old
            changes.append((team, old, new, change))

        changes.sort(key=lambda x: abs(x[3]), reverse=True)

        print(f"\n  Top 3 increases:")
        for team, old, new, change in changes[:3]:
            if change > 0:
                print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")

        print(f"\n  Top 3 decreases:")
        for team, old, new, change in changes[:3]:
            if change < 0:
                print(f"    {team}: {old:.1f} → {new:.1f} ({change:+.1f})")
```

### 4. Implement Monitoring
Run daily monitoring:
```bash
cd /mnt/data2/nhlstats
POSTGRES_HOST=localhost python scripts/elo_monitoring_and_fix.py
```

This will:
- Check all sports' Elo ratings
- Backup current ratings
- Log changes
- Alert if issues found
- Generate reports in `data/elo_reports/`

### 5. Verify Bet Recommendations
After fixing Elo ratings:
1. Run the DAG or wait for next scheduled run
2. Check new bet recommendations have proper probability ranges
3. Monitor betting performance
4. Re-run predictiveness analysis

## Expected Improvements

### For NHL:
- **Before**: 5% probability range → All bets had similar confidence
- **After**: 48% probability range → Proper differentiation between matchups

### For NBA:
- **Before**: ~58 point range → ~5% probability range
- **After**: ~300 point range → ~40% probability range (expected)

### Impact on Betting:
1. **Better edge identification**: Strong teams vs weak teams properly identified
2. **Improved bankroll management**: Can bet more on high-confidence games
3. **Reduced false positives**: Fewer bets on "coin flip" games
4. **Increased ROI**: Proper probability estimates lead to better betting decisions

## Files Created

1. `scripts/simple_regenerate_nhl_elo.py` - Fixed NHL Elo ratings
2. `scripts/fix_elo_for_all_sports.py` - Check and fix all sports
3. `scripts/elo_monitoring_and_fix.py` - Daily monitoring script
4. `scripts/dag_elo_fix_patch.py` - DAG patch instructions
5. `data/nhl_current_elo_ratings.csv` - Fixed NHL ratings
6. `data/elo_backups/` - Backup directory
7. `data/elo_reports/` - Monitoring reports

## Immediate Action Items

1. **Run NBA fix**: `python scripts/fix_nba_elo.py` (to be created)
2. **Update DAG**: Apply the patch to `update_elo_ratings()` function
3. **Schedule monitoring**: Add `elo_monitoring_and_fix.py` to daily cron
4. **Verify**: Check next day's bet recommendations

## Long-term Solution

1. **Fix DAG permanently**: Update `update_elo_ratings()` to use `unified_games`
2. **Add validation**: Check rating ranges after each update
3. **Implement alerts**: Email/Slack alerts for Elo issues
4. **Documentation**: Add to runbook for future maintenance

## Verification

After fixes, verify by:
1. Checking probability ranges in bet recommendations
2. Monitoring betting performance
3. Running predictiveness analysis
4. Checking Elo monitoring reports

The fix should significantly improve the betting system's performance by providing accurate probability estimates based on complete historical data.
