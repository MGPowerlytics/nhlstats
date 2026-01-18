# NHL Prediction Features - 100 Feature Task List

## Overview
Comprehensive task list of 100+ features that can be added to improve NHL game outcome predictions. All features are marked incomplete and ready for implementation.

---

## 🗓️ Schedule & Fatigue Features (15 features)

- [x] 1. Calculate days of rest since last game (per team) ✅ Implemented
- [x] 2. Detect back-to-back games (2nd night flag) ✅ Implemented
- [x] 3. Detect 3-in-4 nights schedule compression ✅ Implemented
- [x] 4. Detect 4-in-6 nights schedule compression ✅ Implemented
- [x] 5. Count consecutive home games (home stand length) ✅ Implemented
- [x] 6. Count consecutive away games (road trip length) ✅ Implemented
- [x] 7. Calculate days since last home game ✅ Implemented
- [x] 8. Calculate days since last away game ✅ Implemented
- [x] 9. Detect if returning home after long road trip (5+ games) ✅ Implemented
- [x] 10. Count back-to-backs in last 10 games ✅ Implemented
- [ ] 11. Calculate average rest days over last 10 games
- [ ] 12. Flag if team has 3+ days rest (well-rested) ✅ Implemented as bonus
- [ ] 13. Flag if team has 1 day rest after travel
- [ ] 14. Calculate cumulative fatigue index (weighted recent games)
- [ ] 15. Detect schedule advantage (rest days difference between teams) ✅ Implemented as bonus

---

## ✈️ Travel & Geography Features (15 features)

- [ ] 16. Build NHL venue latitude/longitude database (32 arenas)
- [ ] 17. Calculate travel distance since last game (miles)
- [ ] 18. Calculate time zones crossed since last game
- [ ] 19. Detect East-to-West travel (jet lag advantage)
- [ ] 20. Detect West-to-East travel (jet lag disadvantage)
- [ ] 21. Calculate total miles traveled in last week
- [ ] 22. Calculate total miles traveled in last month
- [ ] 23. Count time zone crossings in last 5 games
- [ ] 24. Flag long-distance travel (>1500 miles)
- [ ] 25. Flag cross-country travel (>2000 miles)
- [ ] 26. Calculate travel disadvantage index
- [ ] 27. Detect Canadian team playing in USA
- [ ] 28. Detect USA team playing in Canada (border crossing)
- [ ] 29. Calculate elevation change (Denver altitude advantage)
- [ ] 30. Flag if team is on West Coast road trip (for East teams)

---

## 🥅 Goaltender Features (15 features)

- [ ] 31. Scrape confirmed starting goalie (1-3 hours before game)
- [ ] 32. Flag if backup goalie is starting
- [ ] 33. Calculate goalie's days rest since last start
- [ ] 34. Calculate goalie's save % in last 3 starts
- [ ] 35. Calculate goalie's save % in last 5 starts
- [ ] 36. Calculate goalie's save % in last 10 starts
- [ ] 37. Calculate goalie's GAA (goals against average) last 5 starts
- [ ] 38. Calculate goalie's quality start percentage (QS%)
- [ ] 39. Get goalie's career save % vs opponent
- [ ] 40. Get goalie's save % at specific venue
- [ ] 41. Flag if goalie playing back-to-back
- [ ] 42. Calculate goalie's performance after rest vs no rest
- [ ] 43. Get goalie's high danger save % (HDSV%)
- [ ] 44. Calculate goalie's goals saved above expected (GSAx)
- [ ] 45. Flag if goalie is on hot/cold streak (3+ game trend)

---

## 🏒 Advanced Shot Metrics (15 features)

- [ ] 46. Calculate expected goals (xG) per game
- [ ] 47. Calculate expected goals against (xGA) per game
- [ ] 48. Calculate xG differential (xGF - xGA)
- [ ] 49. Calculate xG% (team xG / total xG)
- [ ] 50. Get shots from slot (inner slot vs outer slot)
- [ ] 51. Calculate shot quality score (weighted by location)
- [ ] 52. Get shots off rush vs controlled entry
- [ ] 53. Calculate rebound shot percentage
- [ ] 54. Calculate shot location heatmap density
- [ ] 55. Get shooting percentage by zone (offensive/neutral/defensive)
- [ ] 56. Calculate dangerous scoring chances (DSC)
- [ ] 57. Get shot attempts while trailing/leading/tied
- [ ] 58. Calculate Corsi-For% when score is close (within 1 goal)
- [ ] 59. Get unblocked shot attempt percentage (Fenwick%)
- [ ] 60. Calculate shot differential per 60 minutes

---

## 🧑‍🤝‍🧑 Player & Roster Features (15 features)

- [ ] 61. Scrape daily injury reports
- [ ] 62. Flag if star player (top-6 forward) is out
- [ ] 63. Flag if top-2 defenseman is out
- [ ] 64. Flag if starting goalie is injured
- [ ] 65. Calculate roster continuity index (lineup stability)
- [ ] 66. Get average team age
- [ ] 67. Get average team experience (NHL games played)
- [ ] 68. Calculate top-line production (goals by top line)
- [ ] 69. Get depth scoring (goals by 3rd/4th lines)
- [ ] 70. Calculate power play personnel quality
- [ ] 71. Calculate penalty kill personnel quality
- [ ] 72. Flag recent trades/acquisitions (within 5 games)
- [ ] 73. Get player chemistry index (time together on ice)
- [ ] 74. Calculate star player utilization rate (% of ice time)
- [ ] 75. Flag if backup goalie has extensive recent play

---

## 📈 Situational & Context Features (10 features)

- [ ] 76. Calculate team's points percentage (standings position)
- [ ] 77. Flag if team is in playoff position
- [ ] 78. Flag if team is fighting for playoff spot (bubble team)
- [ ] 79. Flag if team is mathematically eliminated
- [ ] 80. Flag if playoff matchup preview (likely opponent)
- [ ] 81. Detect revenge game (lost to opponent recently)
- [ ] 82. Flag division rival matchup
- [ ] 83. Flag conference matchup
- [ ] 84. Calculate win streak length
- [ ] 85. Calculate losing streak length

---

## 💰 Betting Market Features (10 features)

- [ ] 86. Fetch opening moneyline odds
- [ ] 87. Fetch closing moneyline odds (game time)
- [ ] 88. Calculate line movement (opening to closing)
- [ ] 89. Fetch opening puck line (spread)
- [ ] 90. Fetch closing puck line
- [ ] 91. Fetch opening total (over/under)
- [ ] 92. Fetch closing total
- [ ] 93. Get public betting percentage (% of bets on each side)
- [ ] 94. Get money percentage (% of money on each side)
- [ ] 95. Flag reverse line movement (sharp money indicator)

---

## 🎯 Historical Matchup Features (5 features)

- [ ] 96. Calculate head-to-head win percentage (all-time)
- [ ] 97. Calculate head-to-head win percentage (last season)
- [ ] 98. Calculate head-to-head win percentage (last 5 games)
- [ ] 99. Get average goals scored in H2H matchups
- [ ] 100. Get home/away split in H2H matchups

---

## 🔬 Advanced Analytics Features (Bonus 20)

- [ ] 101. Calculate zone entry efficiency (controlled entries %)
- [ ] 102. Calculate zone exit efficiency (clean exits %)
- [ ] 103. Get 5v5 Corsi percentage
- [ ] 104. Get 5v4 shot attempt differential
- [ ] 105. Calculate offensive zone faceoff win percentage
- [ ] 106. Calculate defensive zone faceoff win percentage
- [ ] 107. Get neutral zone faceoff win percentage
- [ ] 108. Calculate penalties drawn vs penalties taken
- [ ] 109. Get short-handed chances against per PK
- [ ] 110. Calculate first goal scored percentage
- [ ] 111. Get win percentage when scoring first
- [ ] 112. Get win percentage when trailing after 1st period
- [ ] 113. Calculate comeback win percentage (trailing after 2)
- [ ] 114. Get regulation win percentage (no OT/SO)
- [ ] 115. Calculate one-goal game record
- [ ] 116. Get empty net goals for/against rate
- [ ] 117. Calculate line matching efficiency (vs opponent top line)
- [ ] 118. Get ice time distribution (top-6 vs bottom-6)
- [ ] 119. Calculate penalty differential per game
- [ ] 120. Get goalie pull timing and success rate

---

## 🌦️ Environmental Features (Bonus 10)

- [ ] 121. Get arena temperature (if available)
- [ ] 122. Get ice quality rating
- [ ] 123. Flag outdoor game (Winter Classic, Stadium Series)
- [ ] 124. Get attendance percentage (crowd energy)
- [ ] 125. Flag matinee game (afternoon start)
- [ ] 126. Flag late night game (10pm+ ET start)
- [ ] 127. Get days since last game at venue (ice familiarity)
- [ ] 128. Flag if arena has different ice dimensions
- [ ] 129. Get referee assignment (if impacts penalties)
- [ ] 130. Flag nationally televised game (pressure)

---

## 📊 Feature Engineering Tasks (Bonus 10)

- [ ] 131. Create interaction features (rest × travel)
- [ ] 132. Calculate momentum index (weighted recent performance)
- [ ] 133. Create fatigue-adjusted Corsi
- [ ] 134. Calculate rest-adjusted save percentage
- [ ] 135. Create travel-adjusted xG
- [ ] 136. Calculate situation-specific metrics (leading/trailing/tied)
- [ ] 137. Create goalie quality adjustment factor
- [ ] 138. Calculate roster strength index
- [ ] 139. Create opponent-adjusted metrics
- [ ] 140. Build ensemble feature importance ranking

---

## 🏗️ Infrastructure Tasks (Bonus 10)

- [ ] 141. Build automated venue location database updater
- [ ] 142. Create real-time goalie starter scraper
- [ ] 143. Build injury report scraper (daily updates)
- [ ] 144. Integrate Odds API for betting lines
- [ ] 145. Create feature calculation pipeline (orchestration)
- [ ] 146. Build feature store (cache computed features)
- [ ] 147. Create feature validation tests
- [ ] 148. Build feature monitoring dashboard
- [ ] 149. Implement feature versioning system
- [ ] 150. Create feature documentation generator

---

## Priority Levels (for Reference)

### 🔴 Critical (Highest Impact)
- Tasks 1-15: Schedule & Fatigue
- Tasks 16-30: Travel & Geography
- Tasks 31-45: Goaltender
- Tasks 86-95: Betting Markets

### 🟠 High Priority (Significant Impact)
- Tasks 46-60: Advanced Shot Metrics
- Tasks 61-75: Player & Roster
- Tasks 96-100: Historical Matchups

### 🟡 Medium Priority (Measurable Impact)
- Tasks 76-85: Situational Context
- Tasks 101-120: Advanced Analytics

### 🟢 Low Priority (Nice to Have)
- Tasks 121-130: Environmental
- Tasks 131-150: Engineering & Infrastructure

---

## Implementation Notes

### Quick Wins (Can Calculate from Existing Data)
- Tasks 96-100: H2H features (2-3 hours)
- Tasks 76-85: Situational features (1-2 hours)
- Tasks 131-140: Feature engineering (4-6 hours)

### Medium Effort (Need External Data)
- Tasks 1-15: Schedule analysis (4-6 hours)
- Tasks 16-30: Travel distance (6-8 hours with venue database)
- Tasks 46-60: Advanced shot metrics (8-12 hours)

### High Effort (Scraping/APIs Required)
- Tasks 31-45: Goalie starters (12-20 hours)
- Tasks 61-75: Injury tracking (12-20 hours)
- Tasks 86-95: Betting market integration (8-12 hours)

### Infrastructure (Long-term Projects)
- Tasks 141-150: Platform improvements (40-80 hours)

---

## Expected Accuracy Improvements

| Features Added | Baseline | Expected Accuracy | Gain |
|----------------|----------|------------------|------|
| **None (current)** | 55-57% | 55-57% | - |
| **+ Tasks 1-30 (Schedule/Travel)** | 55-57% | 58-60% | +3-4% |
| **+ Tasks 31-45 (Goalies)** | 58-60% | 60-62% | +2% |
| **+ Tasks 46-60 (Advanced Shots)** | 60-62% | 61-63% | +1% |
| **+ Tasks 86-95 (Betting Lines)** | 61-63% | 63-66% | +2-3% |
| **+ Tasks 61-75 (Injuries)** | 63-66% | 64-67% | +1% |
| **+ All Critical Features** | 55-57% | 64-67% | +9-12% |

---

## Completion Tracking

- **Total Features**: 155 (added 5 special teams)
- **Completed**: 30 (+ 2 bonus)
- **In Progress**: 0
- **Not Started**: 123
- **Completion %**: 19%

**Last Completed**: 
- Tasks 1-10 (Schedule & Fatigue) - 2026-01-17
- Tasks 76-85 (Situational & Context - ALL 10) - 2026-01-17
- Tasks 96-100 (Head-to-Head history) - 2026-01-17
- Special Teams (5 features) - 2026-01-17
---

## How to Use This List

1. **Pick a feature** from the list above
2. **Check the box** when starting work: `- [x]`
3. **Implement** the feature in appropriate file
4. **Test** the feature with historical data
5. **Document** any assumptions or data sources
6. **Commit** with message: `feat: Add feature #N - Description`
7. **Update** this document and push

---

## Related Documentation

- `nhl_prediction_features.md` - Detailed feature descriptions
- `build_training_dataset.py` - Current feature implementation
- `nhl_db_schema.sql` - Database schema
- `ML_TRAINING_DATASET.md` - ML dataset documentation

---

**Last Updated**: 2026-01-17  
**Branch**: brainstorming  
**Status**: All tasks pending implementation

## 🔵 Special Teams & Season Stats (5 features)

- [x] Team Season Shooting Percentage ✅ Implemented
- [x] Team Season Save Percentage (approximation) ✅ Implemented
- [x] Team Season Power Play Percentage ✅ Implemented
- [x] Team Season Penalty Kill Percentage ✅ Implemented
- [x] Team Season Faceoff Win Percentage ✅ Implemented
