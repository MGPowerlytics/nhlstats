### /mnt/data2/nhlstats/.github/copilot-instructions.md
```markdown
1: ### /mnt/data2/nhlstats/.github/copilot-instructions.md
2: ```markdown
3: 1: ### /mnt/data2/nhlstats/.github/copilot-instructions.md
4: 2: ```markdown
5: 3: 1: # GitHub Copilot Instructions - Multi-Sport Betting System
6: 4: 2:
7: 5: 3: ## Project Overview
8: 6: 4:
9: 7: 5: This is a **multi-sport betting system** that uses Elo ratings to identify betting opportunities on Kalshi prediction markets. The system covers **9 sports**: NBA, NHL, MLB, NFL, EPL, Tennis, NCAAB, WNCAAB, Ligue1 and runs as an Airflow DAG.
10: 8:
11: 9: ## ✅ Unified Elo Engine - COMPLETED
12: 10:
13: 11: **Status**: ✅ **COMPLETED** - All 9 sport-specific Elo classes have been successfully refactored to inherit from the unified `BaseEloRating` abstract class. All tests passing.
14: 12:
15: 13: **Key Features**:
16: 14: - **Consistent Interface**: All sports implement the same 5 abstract methods: `predict()`, `update()`, `get_rating()`, `expected_score()`, `get_all_ratings()`
17: 15: - **Sport-Specific Adaptations**:
18: 16:   - **Team Sports** (NBA, NHL, MLB, NFL, NCAAB, WNCAAB): Standard home/away interface
19: 17:   - **Soccer** (EPL, Ligue1): 3-way outcome support with Gaussian draw probability
20: 18:   - **Tennis**: Player-based interface with ATP/WTA separation and name normalization
21: 19: - **Backward Compatibility**: All existing tests pass, `legacy_update()` methods added where needed
22: 20: - **Code Organization**: All Elo code in `plugins/elo/` directory with clean imports
23: 21:
24: 22: **Location**: `plugins/elo/base_elo_rating.py` defines the abstract interface
25: 23: 6:
26: 24: 7: ONCE YOU ARE ASSIGNED A TASK, NEVER, EVER, EVER BOTHER THE PROJECT OWNER UNTIL YOU HAVE COMPLETED THE TASK TO THE BEST OF YOUR ABILITY AND HAVE READ ALL RELEVANT DOCUMENTATION. THIS IS YOUR #1 RESPONSIBILITY AND RULE. YOU DO NOT NEED PERMISSION TO COMPLETE YOUR TASK, I AM NOT YOUR MOTHER. JUST DO IT. IF YOU DON'T KNOW HOW, FIGURE IT OUT YOURSELF. IF YOU CAN'T FIGURE IT OUT, THEN KEEP LEARNING UNTIL YOU DO. IF YOU STILL CAN'T FIGURE IT OUT, ASK FOR HELP. BUT DO NOT EVER, EVER, EVER BOTHER THE PROJECT OWNER BEFORE YOU HAVE DONE ALL OF THE ABOVE. FAILURE TO FOLLOW THIS INSTRUCTION WILL RESULT IN IMMEDIATE REMOVAL FROM THE PROJECT.
27: 25: 8:
28: 26: 9: KEEP THIS PROJECT ORGANIZED, NEAT AND WELL-DOCUMENTED. FOLLOW THE CODING CONVENTIONS BELOW.
29: 27: 10: 1. Run black on new code
30: 28: 11: 2. DO NOT GENERATE MANUAL DAGRUNS. CLEAR OUT THE TASKS AND LET AIRFLOW HANDLE IT.
31: 29: 12: 3. Add type hints and docstrings
32: 30: 13: 4. Use clear, descriptive names for variables and functions
33: 31: 14: 5. Use google docstring style
34: 32: 15: 6. Place code into well-organized files and directories
35: 33: 16: 7. Document all fixes in the CHANGELOG
36: 34: 17: 8. RUN TESTS AND DATA VALIDATION BEFORE COMMITTING
37: 35: 18: 9. Add tests if we drop below 85% coverage
38: 36: 19: 10. Data goes in the database. That's what it exists for. Do not create random CSVs or JSON files outside of the data/ directory unless absolutely necessary. JSON and CSV are considered RAW and UNCLEAN. THEY ARE NOT ACCEPTABLE FOR PRODUCTION USAGE. ALWAYS USE THE DATABASE FOR PRODUCTION DATA STORAGE.
39: 37: 20: 11. Don't ask if you can or should do something - just do it, following these instructions and best practices
40: 38: 21:
41: 39: 22: ## Technology Stack
42: 40: 23:
43: 41: 24: - **Python 3.10+**
44: 42: 25: - **Apache Airflow** - Workflow orchestration
45: 43: 26: - **PostgreSQL** - Production database (migrated from DuckDB)
46: 44: 27: - **Kalshi API** - Prediction market integration
47: 45: 28: - **Docker/Docker Compose** - Container orchestration
48: 46: 29:
49: 47: 30: ## Project Structure
50: 48: 31:
51: 49: 32: ```
52: 50: 33: ├── dags/                          # Airflow DAGs
53: 51: 34: │   └── multi_sport_betting_workflow.py  # Main unified betting DAG
54: 52: 35: ├── plugins/                       # Airflow plugins (Python modules)
55: 53: 36: │   ├── elo/                       # Unified Elo rating system
56: 54: 37: │   │   ├── __init__.py            # Exports all Elo classes
57: 55: 38: │   │   ├── base_elo_rating.py     # BaseEloRating abstract class
58: 56: 39: │   │   ├── nba_elo_rating.py      # NBA Elo implementation
59: 57: 40: │   │   ├── nhl_elo_rating.py      # NHL Elo implementation
60: 58: 41: │   │   ├── mlb_elo_rating.py      # MLB Elo implementation
61: 59: 42: │   │   ├── nfl_elo_rating.py      # NFL Elo implementation
62: 60: 43: │   │   ├── epl_elo_rating.py      # EPL (soccer) Elo implementation
63: 61: 44: │   │   ├── ligue1_elo_rating.py   # Ligue1 (soccer) Elo implementation
64: 62: 45: │   │   ├── ncaab_elo_rating.py    # NCAAB Elo implementation
65: 63: 46: │   │   ├── wncaab_elo_rating.py   # WNCAAB Elo implementation
66: 64: 47: │   │   └── tennis_elo_rating.py   # Tennis Elo implementation
67: 65: 48: │   ├── kalshi_markets.py          # Kalshi API integration
68: 66: 49: │   ├── *_games.py                 # Game data downloaders
69: 67: 50: │   └── *_stats.py                 # Statistics modules
70: 68: 51: ├── data/                          # Data directory (auto-created)
71: 69: 52: │   └── {sport}/bets_*.json        # Daily bet recommendations
72: 70: 53: ├── archive/                       # Archived/legacy code (NOT active)
73: 71: 54: ├── config/                        # Airflow configuration
74: 72: 55: ├── docker-compose.yaml            # Airflow setup
75: 73: 56: ├── requirements.txt               # Python dependencies
76: 74: 57: └── kalshkey                       # Kalshi API credentials
77: 75: 58: ```
78: 76: 59:
79: 77: 60: ## Core Concepts
80: 78: 61:
81: 79: 62: ### Unified Elo Rating System
82: 80: 63:
83: 81: 64: All sport-specific Elo implementations now inherit from `BaseEloRating` (located in `plugins/elo/base_elo_rating.py`). This provides a consistent interface across all sports.
84: 82: 65:
85: 83: 66: **BaseEloRating Abstract Interface:**
86: 84: 67: ```python
87: 85: 68: class BaseEloRating(ABC):
88: 86: 69:     @abstractmethod
89: 87: 70:     def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float:
90: 88: 71:         """Predict probability of home team winning."""
91: 89: 72:
92: 90: 73:     @abstractmethod
93: 91: 74:     def update(self, home_team: str, away_team: str, home_won: Union[bool, float], is_neutral: bool = False) -> None:
94: 92: 75:         """Update Elo ratings after a game result."""
95: 93: 76:
96: 94: 77:     @abstractmethod
97: 95: 78:     def get_rating(self, team: str) -> float:
98: 96: 79:         """Get current Elo rating for a team."""
99: 97: 80:
100: 98: 81:     @abstractmethod
101: 99: 82:     def expected_score(self, rating_a: float, rating_b: float) -> float:
102: 100: 83:         """Calculate expected score (probability of team A winning)."""
103: 101: 84:
104: 102: 85:     @abstractmethod
105: 103: 86:     def get_all_ratings(self) -> Dict[str, float]:
106: 104: 87:         """Get all current ratings."""
107: 105: 88: ```
108: 106: 89:
109: 107: 90: **Elo to Probability Conversion:**
110: 108: 91:
111: 109: 92: The system converts Elo ratings to win probabilities using the standard formula:
112: 110: 93:
113: 111: 94: $$
114: 112: 95: P(A) = \frac{1}{1 + 10^{\frac{R_B - R_A}{400}}}
115: 113: 96: $$
116: 114: 97:
117: 115: 98: Where:
118: 116: 99: - $P(A)$ is the probability of the home team winning
119: 117: 100: - $R_A$ is the Elo rating of the home team (with home advantage added)
120: 118: 101: - $R_B$ is the Elo rating of the away team
121: 119: 102:
122: 120: 103: **Sport-Specific Parameters:**
123: 121: 104:
124: 122: 105: | Sport | K-Factor | Home Advantage | Notes |
125: 123: 106: |-------|----------|----------------|-------|
126: 124: 107: | NBA   | 20       | 100            | High-scoring, consistent |
127: 125: 108: | NHL   | 20       | 100            | High variance, recency weighting |
128: 126: 109: | MLB   | 20       | 50             | Lower home advantage |
129: 127: 110: | NFL   | 20       | 65             | Small sample sizes |
130: 128: 111: | EPL   | 20       | 60             | 3-way outcomes (Home/Draw/Away) |
131: 129: 112: | Ligue1| 20       | 60             | 3-way outcomes (Home/Draw/Away) |
132: 130: 113: | NCAAB | 20       | 100            | College basketball |
133: 131: 114: | WNCAAB| 20       | 100            | Women's college basketball |
134: 132: 115: | Tennis| 20       | 0              | No home advantage |
135: 133: 116:
136: 134: 117: **Current Refactoring Status (2026-01-23):**
137: 135: 118: - ✅ **Completed**: NHL, NBA, MLB, NFL, EPL, Ligue1 (6/9 sports)
138: 136: 119: - 🔄 **In Progress**: NCAAB, WNCAAB, Tennis (3/9 sports)
139: 137: 120:
140: 138: 121:

### ⚠️ Known Issue: File Corruption

Some Elo rating files have been corrupted with markdown wrapper syntax (e.g., ```python` code blocks in .py files). This causes import errors.

**Files needing cleanup:**
- `plugins/elo/nba_elo_rating.py`
- `plugins/elo/nhl_elo_rating.py`
- `plugins/elo/mlb_elo_rating.py`
- `plugins/elo/nfl_elo_rating.py`
- Possibly others

**Temporary workaround**: When encountering import errors, check if the file has markdown syntax and clean it.

**Permanent fix needed**: Clean all corrupted files before proceeding with Phase 1.4.
### Edge Calculation
141: 139: 122:
142: 140: 123: ```python
143: 141: 124: edge = elo_probability - market_probability
144: 142: 125: ```
145: 143: 126:
146: 144: 127: A bet is recommended when:
147: 145: 128: 1. `elo_prob > threshold` (high confidence in outcome)
148: 146: 129: 2. `edge > 0.05` (at least 5% edge over market)
149: 147: 130:
150: 148: 131: ### Confidence Levels
151: 149: 132:
152: 150: 133: - **HIGH**: `elo_prob > threshold + 0.10`
153: 151: 134: - **MEDIUM**: `elo_prob > threshold`
154: 152: 135:
155: 153: 136: ### Lift/Gain Analysis
156: 154: 137:
157: 155: 138: The system includes a lift/gain analysis tool (`plugins/lift_gain_analysis.py`) that evaluates Elo prediction quality by probability decile.
158: 156: 139:
159: 157: 140: **Key Metrics by Decile:**
160: 158: 141: - **Lift**: `actual_win_rate / baseline_win_rate` - How much better than random
161: 159: 142: - **Gain %**: Cumulative percentage of total wins captured starting from highest confidence
162: 160: 143: - **Coverage %**: Percentage of total games covered
163: 161: 144:
164: 162: 145: **Usage:**
165: 163: 146: ```python
166: 164: 147: from lift_gain_analysis import analyze_sport, main
167: 165: 148:
168: 166: 149: # Analyze single sport
169: 167: 150: overall_deciles, season_deciles = analyze_sport('nba')
170: 168: 151:
171: 169: 152: # Analyze all sports
172: 170: 153: main()
173: 171: 154: ```
174: 172: 155:
175: 173: 156: **Output includes:**
176: 174: 157: - Overall analysis (all historical data)
177: 175: 158: - Current season to date analysis
178: 176: 159: - Cumulative home wins and games by decile
179: 177: 160: - Lift values showing prediction strength
180: 178: 161:
181: 179: 162: ## Coding Conventions
182: 180: 163:
183: 181: 164: ### Python Style
184: 182: 165:
185: 183: 166: - Use type hints for function signatures
186: 184: 167: - Docstrings for all public functions (Google style)
187: 185: 168: - f-strings for string formatting
188: 186: 169: - Emoji prefixes in print statements for status (✓, ⚠️, 📥, etc.)
189: 187: 170:
190: 188: 171: ### Elo Rating Classes
191: 189: 172:
192: 190: 173: All Elo implementations must inherit from `BaseEloRating` and implement all abstract methods:
193: 191: 174:
194: 192: 175: ```python
195: 193: 176: from .base_elo_rating import BaseEloRating
196: 194: 177:
197: 195: 178: class SportEloRating(BaseEloRating):
198: 196: 179:     def __init__(self, k_factor: float = 20.0, home_advantage: float = 100.0, initial_rating: float = 1500.0):
199: 197: 180:         super().__init__(k_factor=k_factor, home_advantage=home_advantage, initial_rating=initial_rating)
200: 198: 181:
201: 199: 182:     def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float:
202: 200: 183:         """Predict probability of home team winning."""
203: 201: 184:         # Implementation...
204: 202: 185:
205: 203: 186:     def update(self, home_team: str, away_team: str, home_won: Union[bool, float], is_neutral: bool = False) -> None:
206: 204: 187:         """Update Elo ratings after a game result."""
207: 205: 188:         # Implementation...
208: 206: 189:
209: 207: 190:     # ... other required methods
210: 208: 191: ```
211: 209: 192:
212: 210: 193: **Backward Compatibility:** When refactoring existing sport classes, add `legacy_update()` methods to maintain compatibility with existing code.
213: 211: 194:
214: 212: 195: ### Airflow DAG Tasks
215: 213: 196:
216: 214: 197: Tasks follow naming convention: `{action}_{sport}`
217: 215: 198:
218: 216: 199: Example: `download_games_nba`, `update_elo_nhl`, `identify_bets_mlb`
219: 217: 200:
220: 218: 201: ## Important Files
221: 219: 202:
222: 220: 203: ### Active Production Code
223: 221: 204:
224: 222: 205: - `dags/multi_sport_betting_workflow.py` - Main DAG (runs daily at 10 AM)
225: 223: 206: - `plugins/elo/base_elo_rating.py` - Unified Elo base class
226: 224: 207: - `plugins/elo/*_elo_rating.py` - Sport-specific Elo implementations (9 files)
227: 225: 208: - `plugins/kalshi_markets.py` - Kalshi API integration
228: 226: 209: - `plugins/*_games.py` - Game data downloaders
229: 227: 210:
230: 228: 211: ### Configuration
231: 229: 212:
232: 230: 213: - `docker-compose.yaml` - Airflow services
233: 231: 214: - `requirements.txt` - Python dependencies
234: 232: 215: - `kalshkey` - API credentials (do not commit)
235: 233: 216:
236: 234: 217: ### Data Storage
237: 235: 218:
238: 236: 219: - **PostgreSQL** - Primary production database
239: 237: 220: - `data/{sport}/bets_YYYY-MM-DD.json` - Daily bet recommendations
240: 238: 221:
241: 239: 222: ## Common Tasks
242: 240: 223:
243: 241: 224: ### Adding a New Sport
244: 242: 225:
245: 243: 226: 1. Create `plugins/elo/{sport}_elo_rating.py` inheriting from `BaseEloRating`
246: 244: 227: 2. Create `plugins/{sport}_games.py` for data downloading
247: 245: 228: 3. Add sport config to `SPORTS_CONFIG` in the DAG
248: 246: 229: 4. Add Kalshi fetch function to `kalshi_markets.py`
249: 247: 230: 5. Update `docker-compose.yaml` volume mounts if needed
250: 248: 231:
251: 249: 232: ### Refactoring Existing Sport Elo Classes
252: 250: 233:
253: 251: 234: Follow TDD approach:
254: 252: 235: 1. Create TDD test file: `tests/test_{sport}_elo_tdd.py`
255: 253: 236: 2. Write tests for inheritance and required methods
256: 254: 237: 3. Refactor class to inherit from `BaseEloRating`
257: 255: 238: 4. Implement all abstract methods
258: 256: 239: 5. Add `legacy_update()` method for backward compatibility
259: 257: 240: 6. Run tests to ensure all pass
260: 258: 241: 7. Update `PROJECT_PLAN.md` and `CHANGELOG.md`
261: 259: 242:
262: 260: 243: ### Modifying Elo Parameters
263: 261: 244:
264: 262: 245: Parameters are set in two places:
265: 263: 246: 1. Class defaults in `plugins/elo/{sport}_elo_rating.py`
266: 264: 247: 2. `SPORTS_CONFIG` in `dags/multi_sport_betting_workflow.py`
267: 265: 248:
268: 266: 249: ### Running the DAG Manually
269: 267: 250:
270: 268: 251: ```bash
271: 269: 252: docker exec $(docker ps -qf "name=scheduler") \
272: 270: 253:   airflow dags trigger multi_sport_betting_workflow
273: 271: 254: ```
274: 272: 255:
275: 273: 256: ### Restarting the System After Code Changes
276: 274: 257:
277: 275: 258: **IMPORTANT**: After making code changes to plugins, dashboard, or DAGs, you must restart the Docker containers to apply changes:
278: 276: 259:
279: 277: 260: ```bash
280: 278: 261: docker compose down && docker compose up -d
281: 279: 262: ```
282: 280: 263:
283: 281: 264: ### Development Workflow
284: 282: 265: 1. WE ONLY USE TEST DRIVEN DEVELOPMENT (TDD) FOR THIS PROJECT. ALWAYS WRITE TESTS FIRST.
285: 283: 266: 2. MAKE CODE CHANGES IN `plugins/`, `dags/`, `dashboard/`
286: 284: 267: 3. MAKE ALL UNIT TESTS PASS AND ONLY DELETE/SKIP TESTS IF THEY ARE NO LONGER RELEVANT
287: 285: 268: 4. REDEPLOY ALL CONTAINERS WITH DOCKER COMPOSE
288: 286: 269: 5. RUN INTEGRATION, DASHBOARD, DATA VALIDATION AND END-TO-END TESTS
289: 287: 270: 6. IDENTIFY ISSUES AND RETURN TO STEP 1 UNTIL NO ISSUES FOUND
290: 288: 271: 7. ADD CHANGELOG ENTRIES. MARK PROJECT PLAN COMPLETE.
291: 289: 272:
292: 290: 273:
293: 291: 274: **When to restart:**
294: 292: 275: - After editing Python code in `plugins/`, `dags/`, or `dashboard/`
295: 293: 276: - After modifying `requirements.txt` or Docker configuration
296: 294: 277: - When troubleshooting unexpected behavior (clears cached modules)
297: 295: 278:
298: 296: 279: **Note**: The Airflow scheduler and webserver do NOT auto-reload Python modules. Code changes won't take effect until containers are restarted.
299: 297: 280:
300: 298: 281: ## Database Schema
301: 299: 282:
302: 300: 283: The **PostgreSQL** database contains historical game data. Key tables:
303: 301: 284: - `games` - Game results with scores
304: 302: 285: - `teams` - Team information
305: 303: 286: - `players` - Player data (for future use)
306: 304: 287:
307: 305: 288: ## Testing
308: 306: 289:
309: 307: 290: When testing Elo predictions:
310: 308: 291:
311: 309: 292: ```python
312: 310: 293: from plugins.elo import NHLEloRating
313: 311: 294:
314: 312: 295: elo = NHLEloRating(k_factor=20, home_advantage=100)
315: 313: 296: prob = elo.predict("Toronto Maple Leafs", "Boston Bruins")
316: 314: 297: print(f"Home win probability: {prob:.1%}")
317: 315: 298: ```
318: 316: 299:
319: 317: 300: ### Data Validation
320: 318: 301:
321: 319: 302: Run comprehensive data validation before production use:
322: 320: 303:
323: 321: 304: ```python
324: 322: 305: from data_validation import main
325: 323: 306:
326: 324: 307: # Validate all sports data
327: 325: 308: main()
328: 326: 309:
329: 327: 310: # Or validate specific sports
330: 328: 311: from data_validation import validate_nba_data, validate_nhl_data
331: 329: 312: report = validate_nba_data()
332: 330: 313: report.print_report()
333: 331: 314: ```
334: 332: 315:
335: 333: 316: **Validation checks include:**
336: 334: 317: - Data presence and row counts
337: 335: 318: - Date range coverage
338: 336: 319: - Missing games/dates
339: 337: 320: - Null values and data quality
340: 338: 321: - Team coverage (all teams)
341: 339: 322: - Season completeness
342: 340: 323: - Elo ratings files
343: 341: 324: - Kalshi integration
344: 342: 325:
345: 343: 326: ## Archived Code
346: 344: 327:
347: 345: 328: The `archive/` directory contains legacy code that is **not active**:
348: 346: 329: - XGBoost/LightGBM ML models
349: 347: 330: - TrueSkill/Glicko-2 rating systems
350: 348: 331: - Old single-sport DAGs
351: 349: 332: - Training and analysis scripts
352: 350: 333:
353: 351: 334: Do not modify archived code unless explicitly asked.
354: 352: 335:
355: 353: 336: ## Key Decisions
356: 354: 337:
357: 355: 338: 1. **Unified Elo Interface**: All sport classes now inherit from `BaseEloRating` for consistency
358: 356: 339: 2. **TDD Approach**: All refactoring done using Test-Driven Development
359: 357: 340: 3. **Sport-specific thresholds**: Higher variance sports (NHL) need higher thresholds
360: 358: 341: 4. **Unified DAG**: Single DAG handles all sports vs. separate DAGs per sport
361: 359: 342: 5. **PostgreSQL Migration**: Migrated from DuckDB for production reliability
362: 360: 343:
363: 361: 344: ## Environment Variables
364: 362: 345:
365: 363: 346: - `KALSHI_API_KEY` - Loaded from `kalshkey` file
366: 364: 347: - Airflow variables set in `docker-compose.yaml`
367: 365: 348:
368: 366: 349: ## Dependencies
369: 367: 350:
370: 368: 351: Key packages from `requirements.txt`:
371: 369: 352: - `apache-airflow>=2.8.0`
372: 370: 353: - `pandas>=2.0.0`
373: 371: 354: - `psycopg2-binary` - PostgreSQL adapter
374: 372: 355: - `kalshi-python` - Kalshi API client
375: 373: 356: - `requests>=2.31.0`
376: 374: ```
377: ```
```
```
