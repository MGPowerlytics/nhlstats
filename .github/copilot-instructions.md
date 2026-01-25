### /mnt/data2/nhlstats/.github/copilot-instructions.md
```markdown
1: ### /mnt/data2/nhlstats/.github/copilot-instructions.md
2: ```markdown
3: 1: ### /mnt/data2/nhlstats/./.github/copilot-instructions.md
4: 2: ```markdown
5: 3: 1:  # GitHub Copilot Instructions - Multi-Sport Betting System
6: 4: 2:
7: 5: 3:  ## Project Overview
8: 6: 4:
9: 7: 5:  This is a **multi-sport betting system** that uses Elo ratings to identify betting opportunities on Kalshi prediction markets. The system covers **9 sports**: NBA, NHL, MLB, NFL, EPL, Tennis, NCAAB, WNCAAB, Ligue1 and runs as an Airflow DAG.
10: 8: 6:
11: 9: 7:  ## ✅ Unified Elo Engine - COMPLETED
12: 10: 8:
13: 11: 9:  **Status**: ✅ **COMPLETED** - All 9 sport-specific Elo classes have been successfully refactored to inherit from the unified `BaseEloRating` abstract class. All tests passing.
14: 12: 10:
15: 13: 11:  **Key Features**:
16: 14: 12:  - **Consistent Interface**: All sports implement the same 5 abstract methods: `predict()`, `update()`, `get_rating()`, `expected_score()`, `get_all_ratings()`
17: 15: 13:  - **Sport-Specific Adaptations**:
18: 16: 14:  - **Team Sports** (NBA, NHL, MLB, NFL, NCAAB, WNCAAB): Standard home/away interface
19: 17: 15:  - **Soccer** (EPL, Ligue1): 3-way outcome support with Gaussian draw probability
20: 18: 16:  - **Tennis**: Player-based interface with ATP/WTA separation and name normalization
21: 19: 17:  - **Backward Compatibility**: All existing tests pass, `legacy_update()` methods added where needed
22: 20: 18:  - **Code Organization**: All Elo code in `plugins/elo/` directory with clean imports
23: 21: 19:
24: 22: 20:  **Location**: `plugins/elo/base_elo_rating.py` defines the abstract interface
25: 23: 21:
26: 24: 22:  ONCE YOU ARE ASSIGNED A TASK, NEVER, EVER, EVER BOTHER THE PROJECT OWNER UNTIL YOU HAVE COMPLETED THE TASK TO THE BEST OF YOUR ABILITY AND HAVE READ ALL RELEVANT DOCUMENTATION. THIS IS YOUR #1 RESPONSIBILITY AND RULE. YOU DO NOT NEED PERMISSION TO COMPLETE YOUR TASK, I AM NOT YOUR MOTHER. JUST DO IT. IF YOU DON'T KNOW HOW, FIGURE IT OUT YOURSELF. IF YOU CAN'T FIGURE IT OUT, THEN KEEP LEARNING UNTIL YOU DO. IF YOU STILL CAN'T FIGURE IT OUT, ASK FOR HELP. BUT DO NOT EVER, EVER, EVER BOTHER THE PROJECT OWNER BEFORE YOU HAVE DONE ALL OF THE ABOVE. FAILURE TO FOLLOW THIS INSTRUCTION WILL RESULT IN IMMEDIATE REMOVAL FROM THE PROJECT.
27: 25: 23:
28: 26: 24:  KEEP THIS PROJECT ORGANIZED, NEAT AND WELL-DOCUMENTED. FOLLOW THE CODING CONVENTIONS BELOW.
29: 27: 25:  1. Run black on new code
30: 28: 26:  2. DO NOT GENERATE MANUAL DAGRUNS. CLEAR OUT THE TASKS AND LET AIRFLOW HANDLE IT.
31: 29: 27:  3. Add type hints and docstrings
32: 30: 28:  4. Use clear, descriptive names for variables and functions
33: 31: 29:  5. Use google docstring style
34: 32: 30:  6. Place code into well-organized files and directories
35: 33: 31:  7. Document all fixes in the CHANGELOG
36: 34: 32:  8. RUN TESTS AND DATA VALIDATION BEFORE COMMITTING
37: 35: 33:  9. Add tests if we drop below 85% coverage
38: 36: 34:  10. Data goes in the database. That's what it exists for. Do not create random CSVs or JSON files outside of the data/ directory unless absolutely necessary. JSON and CSV are considered RAW and UNCLEAN. THEY ARE NOT ACCEPTABLE FOR PRODUCTION USAGE. ALWAYS USE THE DATABASE FOR PRODUCTION DATA STORAGE.
39: 37: 35:  11. Don't ask if you can or should do something - just do it, following these instructions and best practices
40: 38: 36:
41: 39: 37:  ## Technology Stack
42: 40: 38:
43: 41: 39:  - **Python 3.10+**
44: 42: 40:  - **Apache Airflow** - Workflow orchestration
45: 43: 41:  - **PostgreSQL** - Production database (migrated from DuckDB)
46: 44: 42:  - **Kalshi API** - Prediction market integration
47: 45: 43:  - **Docker/Docker Compose** - Container orchestration
48: 46: 44:
49: 47: 45:  ## Project Structure
50: 48: 46:
51: 49: 47:  ```
52: 50: 48:  ├── dags/                          # Airflow DAGs
53: 51: 49:  │   └── multi_sport_betting_workflow.py  # Main unified betting DAG
54: 52: 50:  ├── plugins/                       # Airflow plugins (Python modules)
55: 53: 51:  │   ├── elo/                       # Unified Elo rating system
56: 54: 52:  │   │   ├── __init__.py            # Exports all Elo classes
57: 55: 53:  │   │   ├── base_elo_rating.py     # BaseEloRating abstract class
58: 56: 54:  │   │   ├── nba_elo_rating.py      # NBA Elo implementation
59: 57: 55:  │   │   ├── nhl_elo_rating.py      # NHL Elo implementation
60: 58: 56:  │   │   ├── mlb_elo_rating.py      # MLB Elo implementation
61: 59: 57:  │   │   ├── nfl_elo_rating.py      # NFL Elo implementation
62: 60: 58:  │   │   ├── epl_elo_rating.py      # EPL (soccer) Elo implementation
63: 61: 59:  │   │   ├── ligue1_elo_rating.py   # Ligue1 (soccer) Elo implementation
64: 62: 60:  │   │   ├── ncaab_elo_rating.py    # NCAAB Elo implementation
65: 63: 61:  │   │   ├── wncaab_elo_rating.py   # WNCAAB Elo implementation
66: 64: 62:  │   │   └── tennis_elo_rating.py   # Tennis Elo implementation
67: 65: 63:  │   ├── kalshi_markets.py          # Kalshi API integration
68: 66: 64:  │   ├── *_games.py                 # Game data downloaders
69: 67: 65:  │   └── *_stats.py                 # Statistics modules
70: 68: 66:  ├── data/                          # Data directory (auto-created)
71: 69: 67:  │   └── {sport}/bets_*.json        # Daily bet recommendations
72: 70: 68:  ├── archive/                       # Archived/legacy code (NOT active)
73: 71: 69:  ├── config/                        # Airflow configuration
74: 72: 70:  ├── docker-compose.yaml            # Airflow setup
75: 73: 71:  ├── requirements.txt               # Python dependencies
76: 74: 72:  └── kalshkey                       # Kalshi API credentials
77: 75: 73:  ```
78: 76: 74:
79: 77: 75:  ## Core Concepts
80: 78: 76:
81: 79: 77:  ### Unified Elo Rating System
82: 80: 78:
83: 81: 79:  All sport-specific Elo implementations now inherit from `BaseEloRating` (located in `plugins/elo/base_elo_rating.py`). This provides a consistent interface across all sports.
84: 82: 80:
85: 83: 81:  **BaseEloRating Abstract Interface:**
86: 84: 82:  ```python
87: 85: 83:  class BaseEloRating(ABC):
88: 86: 84:  @abstractmethod
89: 87: 85:  def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float:
90: 88: 86:  """Predict probability of home team winning."""
91: 89: 87:
92: 90: 88:  @abstractmethod
93: 91: 89:  def update(self, home_team: str, away_team: str, home_won: Union[bool, float], is_neutral: bool = False) -> None:
94: 92: 90:  """Update Elo ratings after a game result."""
95: 93: 91:
96: 94: 92:  @abstractmethod
97: 95: 93:  def get_rating(self, team: str) -> float:
98: 96: 94:  """Get current Elo rating for a team."""
99: 97: 95:
100: 98: 96:  @abstractmethod
101: 99: 97:  def expected_score(self, rating_a: float, rating_b: float) -> float:
102: 100: 98:  """Calculate expected score (probability of team A winning)."""
103: 101: 99:
104: 102: 100:  @abstractmethod
105: 103: 101:  def get_all_ratings(self) -> Dict[str, float]:
106: 104: 102:  """Get all current ratings."""
107: 105: 103:  ```
108: 106: 104:
109: 107: 105:  **Elo to Probability Conversion:**
110: 108: 106:
111: 109: 107:  The system converts Elo ratings to win probabilities using the standard formula:
112: 110: 108:
113: 111: 109:  $$
114: 112: 110:  P(A) = \frac{1}{1 + 10^{\frac{R_B - R_A}{400}}}
115: 113: 111:  $$
116: 114: 112:
117: 115: 113:  Where:
118: 116: 114:  - $P(A)$ is the probability of the home team winning
119: 117: 115:  - $R_A$ is the Elo rating of the home team (with home advantage added)
120: 118: 116:  - $R_B$ is the Elo rating of the away team
121: 119: 117:
122: 120: 118:  **Sport-Specific Parameters:**
123: 121: 119:
124: 122: 120:  | Sport | K-Factor | Home Advantage | Notes |
125: 123: 121:  |-------|----------|----------------|-------|
126: 124: 122:  | NBA   | 20       | 100            | High-scoring, consistent |
127: 125: 123:  | NHL   | 20       | 100            | High variance, recency weighting |
128: 126: 124:  | MLB   | 20       | 50             | Lower home advantage |
129: 127: 125:  | NFL   | 20       | 65             | Small sample sizes |
130: 128: 126:  | EPL   | 20       | 60             | 3-way outcomes (Home/Draw/Away) |
131: 129: 127:  | Ligue1| 20       | 60             | 3-way outcomes (Home/Draw/Away) |
132: 130: 128:  | NCAAB | 20       | 100            | College basketball |
133: 131: 129:  | WNCAAB| 20       | 100            | Women's college basketball |
134: 132: 130:  | Tennis| 20       | 0              | No home advantage |
135: 133: 131:
136: 134: 132:  **Current Refactoring Status (2026-01-23):**
137: 135: 133:
138: 136: 134:  - ✅ **Completed**: All 9 sports (NHL, NBA, MLB, NFL, EPL, Ligue1, NCAAB, WNCAAB, Tennis)
139: 137: 135:
140: 138: 136:  - 🔄 **In Progress**: None (Phase 1.2 Completed)
141: 139: 137:
142: 140: 138:
143: 141: 139:
144: 142: 140:  ### Edge Calculation
145: 143: 141:
146: 144: 142:  ```python
147: 145: 143:  edge = elo_probability - market_probability
148: 146: 144:  ```
149: 147: 145:
150: 148: 146:  A bet is recommended when:
151: 149: 147:  1. `elo_prob > threshold` (high confidence in outcome)
152: 150: 148:  2. `edge > 0.05` (at least 5% edge over market)
153: 151: 149:
154: 152: 150:  ### Confidence Levels
155: 153: 151:
156: 154: 152:  - **HIGH**: `elo_prob > threshold + 0.10`
157: 155: 153:  - **MEDIUM**: `elo_prob > threshold`
158: 156: 154:
159: 157: 155:  ### Lift/Gain Analysis
160: 158: 156:
161: 159: 157:  The system includes a lift/gain analysis tool (`plugins/lift_gain_analysis.py`) that evaluates Elo prediction quality by probability decile.
162: 160: 158:
163: 161: 159:  **Key Metrics by Decile:**
164: 162: 160:  - **Lift**: `actual_win_rate / baseline_win_rate` - How much better than random
165: 163: 161:  - **Gain %**: Cumulative percentage of total wins captured starting from highest confidence
166: 164: 162:  - **Coverage %**: Percentage of total games covered
167: 165: 163:
168: 166: 164:  **Usage:**
169: 167: 165:  ```python
170: 168: 166:  from lift_gain_analysis import analyze_sport, main
171: 169: 167:
172: 170: 168:  # Analyze single sport
173: 171: 169:  overall_deciles, season_deciles = analyze_sport('nba')
174: 172: 170:
175: 173: 171:  # Analyze all sports
176: 174: 172:  main()
177: 175: 173:  ```
178: 176: 174:
179: 177: 175:  **Output includes:**
180: 178: 176:  - Overall analysis (all historical data)
181: 179: 177:  - Current season to date analysis
182: 180: 178:  - Cumulative home wins and games by decile
183: 181: 179:  - Lift values showing prediction strength
184: 182: 180:
185: 183: 181:  ## Coding Conventions
186: 184: 182:
187: 185: 183:  ### Python Style
188: 186: 184:
189: 187: 185:  - Use type hints for function signatures
190: 188: 186:  - Docstrings for all public functions (Google style)
191: 189: 187:  - f-strings for string formatting
192: 190: 188:  - Emoji prefixes in print statements for status (✓, ⚠️, 📥, etc.)
193: 191: 189:
194: 192: 190:  ### Elo Rating Classes
195: 193: 191:
196: 194: 192:  All Elo implementations must inherit from `BaseEloRating` and implement all abstract methods:
197: 195: 193:
198: 196: 194:  ```python
199: 197: 195:  from .base_elo_rating import BaseEloRating
200: 198: 196:
201: 199: 197:  class SportEloRating(BaseEloRating):
202: 200: 198:  def __init__(self, k_factor: float = 20.0, home_advantage: float = 100.0, initial_rating: float = 1500.0):
203: 201: 199:  super().__init__(k_factor=k_factor, home_advantage=home_advantage, initial_rating=initial_rating)
204: 202: 200:
205: 203: 201:  def predict(self, home_team: str, away_team: str, is_neutral: bool = False) -> float:
206: 204: 202:  """Predict probability of home team winning."""
207: 205: 203:  # Implementation...
208: 206: 204:
209: 207: 205:  def update(self, home_team: str, away_team: str, home_won: Union[bool, float], is_neutral: bool = False) -> None:
210: 208: 206:  """Update Elo ratings after a game result."""
211: 209: 207:  # Implementation...
212: 210: 208:
213: 211: 209:  # ... other required methods
214: 212: 210:  ```
215: 213: 211:
216: 214: 212:  **Backward Compatibility:** When refactoring existing sport classes, add `legacy_update()` methods to maintain compatibility with existing code.
217: 215: 213:
218: 216: 214:  ### Airflow DAG Tasks
219: 217: 215:
220: 218: 216:  Tasks follow naming convention: `{action}_{sport}`
221: 219: 217:
222: 220: 218:  Example: `download_games_nba`, `update_elo_nhl`, `identify_bets_mlb`
223: 221: 219:
224: 222: 220:  ## Important Files
225: 223: 221:
226: 224: 222:  ### Active Production Code
227: 225: 223:
228: 226: 224:  - `dags/multi_sport_betting_workflow.py` - Main DAG (runs daily at 10 AM)
229: 227: 225:  - `plugins/elo/base_elo_rating.py` - Unified Elo base class
230: 228: 226:  - `plugins/elo/*_elo_rating.py` - Sport-specific Elo implementations (9 files)
231: 229: 227:  - `plugins/kalshi_markets.py` - Kalshi API integration
232: 230: 228:  - `plugins/*_games.py` - Game data downloaders
233: 231: 229:
234: 232: 230:  ### Configuration
235: 233: 231:
236: 234: 232:  - `docker-compose.yaml` - Airflow services
237: 235: 233:  - `requirements.txt` - Python dependencies
238: 236: 234:  - `kalshkey` - API credentials (do not commit)
239: 237: 235:
240: 238: 236:  ### Data Storage
241: 239: 237:
242: 240: 238:  - **PostgreSQL** - Primary production database
243: 241: 239:  - `data/{sport}/bets_YYYY-MM-DD.json` - Daily bet recommendations
244: 242: 240:
245: 243: 241:  ## Common Tasks
246: 244: 242:
247: 245: 243:  ### Adding a New Sport
248: 246: 244:
249: 247: 245:  1. Create `plugins/elo/{sport}_elo_rating.py` inheriting from `BaseEloRating`
250: 248: 246:  2. Create `plugins/{sport}_games.py` for data downloading
251: 249: 247:  3. Add sport config to `SPORTS_CONFIG` in the DAG
252: 250: 248:  4. Add Kalshi fetch function to `kalshi_markets.py`
253: 251: 249:  5. Update `docker-compose.yaml` volume mounts if needed
254: 252: 250:
255: 253: 251:  ### Refactoring Existing Sport Elo Classes
256: 254: 252:
257: 255: 253:  Follow TDD approach:
258: 256: 254:  1. Create TDD test file: `tests/test_{sport}_elo_tdd.py`
259: 257: 255:  2. Write tests for inheritance and required methods
260: 258: 256:  3. Refactor class to inherit from `BaseEloRating`
261: 259: 257:  4. Implement all abstract methods
262: 260: 258:  5. Add `legacy_update()` method for backward compatibility
263: 261: 259:  6. Run tests to ensure all pass
264: 262: 260:  7. Update `PROJECT_PLAN.md` and `CHANGELOG.md`
265: 263: 261:
266: 264: 262:  ### Modifying Elo Parameters
267: 265: 263:
268: 266: 264:  Parameters are set in two places:
269: 267: 265:  1. Class defaults in `plugins/elo/{sport}_elo_rating.py`
270: 268: 266:  2. `SPORTS_CONFIG` in `dags/multi_sport_betting_workflow.py`
271: 269: 267:
272: 270: 268:  ### Running the DAG Manually
273: 271: 269:
274: 272: 270:  ```bash
275: 273: 271:  docker exec $(docker ps -qf "name=scheduler") \
276: 274: 272:  airflow dags trigger multi_sport_betting_workflow
277: 275: 273:  ```
278: 276: 274:
279: 277: 275:  ### Restarting the System After Code Changes
280: 278: 276:
281: 279: 277:  **IMPORTANT**: After making code changes to plugins, dashboard, or DAGs, you must restart the Docker containers to apply changes:
282: 280: 278:
283: 281: 279:  ```bash
284: 282: 280:  docker compose down && docker compose up -d
285: 283: 281:  ```
286: 284: 282:
287: 285: 283:  ### Development Workflow
288: 286: 284:  1. WE ONLY USE TEST DRIVEN DEVELOPMENT (TDD) FOR THIS PROJECT. ALWAYS WRITE TESTS FIRST.
289: 287: 285:  2. MAKE CODE CHANGES IN `plugins/`, `dags/`, `dashboard/`
290: 288: 286:  3. MAKE ALL UNIT TESTS PASS AND ONLY DELETE/SKIP TESTS IF THEY ARE NO LONGER RELEVANT
291: 289: 287:  4. REDEPLOY ALL CONTAINERS WITH DOCKER COMPOSE
292: 290: 288:  5. RUN INTEGRATION, DASHBOARD, DATA VALIDATION AND END-TO-END TESTS
293: 291: 289:  6. IDENTIFY ISSUES AND RETURN TO STEP 1 UNTIL NO ISSUES FOUND
294: 292: 290:  7. ADD CHANGELOG ENTRIES. MARK PROJECT PLAN COMPLETE.
295: 293: 291:
296: 294: 292:
297: 295: 293:  **When to restart:**
298: 296: 294:  - After editing Python code in `plugins/`, `dags/`, or `dashboard/`
299: 297: 295:  - After modifying `requirements.txt` or Docker configuration
300: 298: 296:  - When troubleshooting unexpected behavior (clears cached modules)
301: 299: 297:
302: 300: 298:  **Note**: The Airflow scheduler and webserver do NOT auto-reload Python modules. Code changes won't take effect until containers are restarted.
303: 301: 299:
304: 302: 300:  ## Database Schema
305: 303: 301:
306: 304: 302:  The **PostgreSQL** database contains historical game data. Key tables:
307: 305: 303:  - `games` - Game results with scores
308: 306: 304:  - `teams` - Team information
309: 307: 305:  - `players` - Player data (for future use)
310: 308: 306:
311: 309: 307:  ## Testing
312: 310: 308:
313: 311: 309:  When testing Elo predictions:
314: 312: 310:
315: 313: 311:  ```python
316: 314: 312:  from plugins.elo import NHLEloRating
317: 315: 313:
318: 316: 314:  elo = NHLEloRating(k_factor=20, home_advantage=100)
319: 317: 315:  prob = elo.predict("Toronto Maple Leafs", "Boston Bruins")
320: 318: 316:  print(f"Home win probability: {prob:.1%}")
321: 319: 317:  ```
322: 320: 318:
323: 321: 319:  ### Data Validation
324: 322: 320:
325: 323: 321:  Run comprehensive data validation before production use:
326: 324: 322:
327: 325: 323:  ```python
328: 326: 324:  from data_validation import main
329: 327: 325:
330: 328: 326:  # Validate all sports data
331: 329: 327:  main()
332: 330: 328:
333: 331: 329:  # Or validate specific sports
334: 332: 330:  from data_validation import validate_nba_data, validate_nhl_data
335: 333: 331:  report = validate_nba_data()
336: 334: 332:  report.print_report()
337: 335: 333:  ```
338: 336: 334:
339: 337: 335:  **Validation checks include:**
340: 338: 336:  - Data presence and row counts
341: 339: 337:  - Date range coverage
342: 340: 338:  - Missing games/dates
343: 341: 339:  - Null values and data quality
344: 342: 340:  - Team coverage (all teams)
345: 343: 341:  - Season completeness
346: 344: 342:  - Elo ratings files
347: 345: 343:  - Kalshi integration
348: 346: 344:
349: 347: 345:  ## Archived Code
350: 348: 346:
351: 349: 347:  The `archive/` directory contains legacy code that is **not active**:
352: 350: 348:  - XGBoost/LightGBM ML models
353: 351: 349:  - TrueSkill/Glicko-2 rating systems
354: 352: 350:  - Old single-sport DAGs
355: 353: 351:  - Training and analysis scripts
356: 354: 352:
357: 355: 353:  Do not modify archived code unless explicitly asked.
358: 356: 354:
359: 357: 355:  ## Key Decisions
360: 358: 356:
361: 359: 357:  1. **Unified Elo Interface**: All sport classes now inherit from `BaseEloRating` for consistency
362: 360: 358:  2. **TDD Approach**: All refactoring done using Test-Driven Development
363: 361: 359:  3. **Sport-specific thresholds**: Higher variance sports (NHL) need higher thresholds
364: 362: 360:  4. **Unified DAG**: Single DAG handles all sports vs. separate DAGs per sport
365: 363: 361:  5. **PostgreSQL Migration**: Migrated from DuckDB for production reliability
366: 364: 362:
367: 365: 363:  ## Environment Variables
368: 366: 364:
369: 367: 365:  - `KALSHI_API_KEY` - Loaded from `kalshkey` file
370: 368: 366:  - Airflow variables set in `docker-compose.yaml`
371: 369: 367:
372: 370: 368:  ## Dependencies
373: 371: 369:
374: 372: 370:  Key packages from `requirements.txt`:
375: 373: 371:  - `apache-airflow>=2.8.0`
376: 374: 372:  - `pandas>=2.0.0`
377: 375: 373:  - `psycopg2-binary` - PostgreSQL adapter
378: 376: 374:  - `kalshi-python` - Kalshi API client
379: 377: 375:  - `requests>=2.31.0`
380: 378: ```
381: 379:
382: 380:
383: 381: ## Markdown Formatting Guidelines
384: 382:
385: 383: When displaying file contents or writing Markdown:
386: 384:
387: 385: 1. **DO NOT add line numbers** to Markdown output
388: 386: 2. Use clean code blocks without line number prefixes
389: 387: 3. Format code blocks with language identifiers:
390: 388:    ```python
391: 389:    # Code here
392: 390:    ```
393: 391: 4. For file paths, use plain text without special formatting
394: 392: 5. Ensure all Markdown is properly formatted and readable
395: 393:
396: 394: Example of **CORRECT** formatting:
397: 395: ```python
398: 396: def example_function():
399: 397:     """This is a properly formatted code block."""
400: 398:     return "Hello World"
401: 399: ```
402: 400:
403: 401: Example of **INCORRECT** formatting:
404: 402: ```
405: 403: 1: def example_function():
406: 404: 2:     """Line numbers should NOT be included."""
407: 405: 3:     return "Hello World"
408: 406: ```
409: ```
410:
411:
412: ## ✅ Unified Elo Interface Verification - COMPLETED
413:
414: **Status**: ✅ **COMPLETED** - All 9 sport-specific Elo classes have been verified to properly inherit from `BaseEloRating` and implement all required abstract methods.
415:
416: **Verification Tests**:
417: - `tests/test_unified_elo_interface.py`: Comprehensive test suite verifying inheritance and method implementations
418: - All 9 tests passing, confirming unified interface compliance
419: - Tests verify: inheritance, required methods, method signatures, sport-specific parameters, backward compatibility
420:
421: **Key Verification Points**:
422: 1. **Inheritance**: All sport classes (`NBAEloRating`, `NHLEloRating`, etc.) inherit from `BaseEloRating`
423: 2. **Abstract Methods**: All implement `predict()`, `update()`, `get_rating()`, `expected_score()`, `get_all_ratings()`
424: 3. **Type Consistency**: All methods have correct type signatures and return types
425: 4. **Backward Compatibility**: `legacy_update()` methods preserved where needed
426: 5. **Sport-Specific Features**: NHL recency weighting, soccer 3-way outcomes, tennis player normalization all maintained
427:
428: ## ✅ Database Schema Documentation - COMPLETED
429:
430: **Status**: ✅ **COMPLETED** - Comprehensive database schema documentation created.
431:
432: **Documentation Location**: `docs/database_schema.md`
433:
434: **Contents**:
435: 1. **Table Summary**: All database tables with descriptions, primary keys, and DAG producers
436: 2. **Table Details**: Complete column definitions, indexes, foreign keys for each table
437: 3. **Data Flow**: How DAG tasks populate each table in daily/hourly pipelines
438: 4. **Schema Validation**: Instructions for validating schema integrity
439: 5. **Migration Notes**: History and maintenance procedures
440:
441: **Tables Documented**:
442: - `unified_games`: Centralized game schedule for all sports
443: - `game_odds`: Betting odds from various bookmakers
444: - `placed_bets`: Tracked bets placed on prediction markets
445: - `portfolio_snapshots`: Hourly portfolio value tracking
446: - `elo_ratings`: Historical Elo ratings for teams/players
447: - `bet_recommendations`: Daily bet recommendations
448:
449: **DAG Task Mapping**:
450: Each table includes mapping to DAG tasks that produce/update its data, enabling traceability from data to pipeline.
451:
452: ## Updated Development Guidelines
453:
454: ### When Modifying Elo Classes
455: 1. Always run `tests/test_unified_elo_interface.py` to ensure continued compliance
456: 2. Maintain inheritance from `BaseEloRating`
457: 3. Implement all 5 abstract methods with correct signatures
458: 4. Preserve backward compatibility with `legacy_update()` if needed
459: 5. Add sport-specific parameters in `__init__` method
460:
461: ### When Modifying Database Schema
462: 1. Update `plugins/database_schema_manager.py` with schema changes
463: 2. Run `scripts/check_schema.py` to validate
464: 3. Update `docs/database_schema.md` documentation
465: 4. Add migration script if altering existing tables
466: 5. Test with existing data before deployment
467:
468: ### CI/CD Pipeline Updates
469: The CI/CD pipeline (`ci_cd_pipeline.sh`) now includes:
470: 1. Unified Elo interface verification tests
471: 2. Database schema validation
472: 3. Documentation consistency checks
```


## 🔗 Phase 1.4: Integration Testing Guidance

### Integration Testing Philosophy
1. **Test Interactions, Not Just Units**: Focus on how components work together
2. **Realistic Data Flow**: Test complete pipelines, not isolated functions
3. **Failure Scenarios**: Test error propagation and recovery
4. **Performance Under Load**: Test integrated system performance

### Critical Integration Points to Test

#### 1. DAG-Elo System Integration
- Verify DAG tasks correctly instantiate Elo classes using SPORTS_CONFIG
- Test Elo predictions within DAG execution context
- Validate sport-specific parameters (K-factor, home advantage) are applied
- Ensure backward compatibility methods work from DAGs

#### 2. Database Integration
- Test complete CRUD operations from DAG tasks
- Verify foreign key constraints are enforced
- Validate data consistency across related tables
- Test transaction rollback on failures

#### 3. End-to-End Pipeline
- Test complete data flow for at least one sport
- Verify data consistency across pipeline stages
- Test error recovery and retry logic
- Validate timing and scheduling dependencies

#### 4. Dashboard Integration
- Test dashboard with real Elo data and database queries
- Verify visualizations render correctly
- Test sport switching with unified interface
- Validate user interactions work as expected

### Integration Test Implementation Patterns

#### Test Data Management
```python
# Use fixtures for test data
@pytest.fixture
def test_game_data():
    return {
        "game_id": "NBA_20240120_LAL_BOS",
        "sport": "NBA",
        "home_team": "Lakers",
        "away_team": "Celtics"
    }
```

#### Database Transaction Management
```python
# Use transaction rollback for isolation
def test_database_write(db_session):
    # Test code here
    db_session.rollback()  # Clean up after test
```

#### External API Mocking
```python
# Mock external API calls
@patch('plugins.kalshi_markets.fetch_nba_markets')
def test_market_fetch(mock_fetch):
    mock_fetch.return_value = test_market_data
    # Test code here
```

### CI/CD Integration
- Add integration test stage to ci_cd_pipeline.sh
- Run integration tests after unit tests
- Fail build on integration test failures
- Generate integration test coverage reports

### Success Criteria for Integration Tests
- **Coverage**: 85%+ of integration points tested
- **Reliability**: Tests consistently catch integration issues
- **Performance**: Full suite runs in < 10 minutes
- **Maintainability**: Clear, documented test patterns
