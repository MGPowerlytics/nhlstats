# Code Smell Report — ❌ F (Score: 43.9/100)

_Scanned: /mnt/data2/nhlstats_

_Generated: 2026-03-11T02:26:48.520030+00:00_

## Executive Summary

| Metric | Value |
|:-------|------:|
| **Overall Grade** | ❌ F |
| **Overall Score** | 43.9/100 |
| **Files Scanned** | 67 |
| **Total Lines (non-blank)** | 18,843 |
| **Total Smells** | 1082 |
| **Avg Maintainability Index** | 62.3 |
| **Avg Cyclomatic Complexity** | 0.0 |

### Smells by Severity

| Severity | Count |
|:---------|------:|
| low | 901 |
| medium | 174 |
| high | 7 |

### Smells by Category

| Category | Count |
|:---------|------:|
| Missing Type Hint | 584 |
| Magic Number | 141 |
| Long Method | 111 |
| Primitive Obsession | 73 |
| Feature Envy | 71 |
| Deep Nesting | 49 |
| Duplicate Code | 38 |
| Large Class | 15 |

## 🎯 Prioritised Refactoring Queue

These are the highest-impact smells to address first:

1. **dags/multi_sport_betting_workflow.py:603** — 🟠 HIGH — Deep Nesting
   Nesting depth 6 in '_load_sport_data_with_loader' (threshold: 4)
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

2. **plugins/csv_processors.py:72** — 🟠 HIGH — Duplicate Code
   Function '_extract_ncaab_game_data' is an exact duplicate of '_extract_wncaab_game_data' at plugins/csv_processors.py:355
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

3. **plugins/csv_processors.py:215** — 🟠 HIGH — Duplicate Code
   Function '_extract_epl_game_data' is an exact duplicate of '_extract_ligue1_game_data' at plugins/csv_processors.py:288
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

4. **plugins/elo/tennis_elo_rating.py:133** — 🟠 HIGH — Primitive Obsession
   Repeated primitive parameter group appears in: '_create_match_context' (line 133), '_create_legacy_match_result' (line 178), '_create_team_match_context' (line 202), 'predict' (line 242), 'predict_team' (line 528)
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

5. **plugins/elo/tennis_elo_rating.py:153** — 🟠 HIGH — Primitive Obsession
   Repeated primitive parameter group appears in: '_create_match_result' (line 153), '_create_team_match_result' (line 219), 'update_team' (line 546)
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

6. **plugins/kalshi_betting.py:480** — 🟠 HIGH — Primitive Obsession
   Repeated primitive parameter group appears in: '_create_signature' (line 480), '_fetch_from_kalshi_api' (line 668)
   → _Replace Data Value with Object — create a shared data structure for this recurring parameter group._

7. **plugins/kalshi_betting.py:688** — 🟠 HIGH — Duplicate Code
   Function 'get_open_positions' is an exact duplicate of 'get_open_orders' at plugins/kalshi_betting.py:696
   → _Once and Only Once — extract the shared logic into a single function and call it from both sites._

8. **dags/multi_sport_betting_workflow.py:597** — 🟡 MEDIUM — Deep Nesting
   Nesting depth 5 in '_load_sport_data_with_loader' (threshold: 4)
   → _Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return._

9. **plugins/csv_history_loader.py:315** — 🟡 MEDIUM — Long Method
   Function '_get_csv_load_config_for_sport' has 54 lines (threshold: 30)
   → _Extract Method — break this function into smaller, intention-revealing helper functions._

10. **plugins/csv_processors.py:47** — 🟡 MEDIUM — Duplicate Code
   Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:330
   → _Extract Shared Function — identify the common logic and parameterise the differences._

11. **plugins/csv_processors.py:47** — 🟡 MEDIUM — Duplicate Code
   Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:392
   → _Extract Shared Function — identify the common logic and parameterise the differences._

12. **plugins/csv_processors.py:47** — 🟡 MEDIUM — Duplicate Code
   Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:437
   → _Extract Shared Function — identify the common logic and parameterise the differences._

13. **plugins/csv_processors.py:184** — 🟡 MEDIUM — Duplicate Code
   Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:257
   → _Extract Shared Function — identify the common logic and parameterise the differences._

14. **plugins/csv_processors.py:330** — 🟡 MEDIUM — Duplicate Code
   Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:392
   → _Extract Shared Function — identify the common logic and parameterise the differences._

15. **plugins/csv_processors.py:330** — 🟡 MEDIUM — Duplicate Code
   Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:437
   → _Extract Shared Function — identify the common logic and parameterise the differences._


## 📊 Files Ranked by Quality

| Rank | File | Grade | Score | Smells | LOC | MI | Avg CC |
|-----:|:-----|:------|------:|-------:|----:|---:|-------:|
| 1 | plugins/portfolio_optimizer.py | ❌ F | 3.5 | 51 | 844 | 12 | 0.0 |
| 2 | plugins/kalshi_betting.py | ❌ F | 4.3 | 79 | 849 | 14 | 0.0 |
| 3 | plugins/kalshi_markets.py | ❌ F | 9.3 | 45 | 535 | 31 | 0.0 |
| 4 | plugins/db_loader.py | ❌ F | 13.0 | 50 | 458 | 43 | 0.0 |
| 5 | plugins/elo/tennis_elo_rating.py | ❌ F | 15.5 | 52 | 446 | 52 | 0.0 |
| 6 | plugins/csv_processors.py | ❌ F | 17.9 | 39 | 413 | 60 | 0.0 |
| 7 | plugins/nhl_game_events.py | ❌ F | 20.1 | 22 | 146 | 67 | 0.0 |
| 8 | plugins/portfolio_betting.py | ❌ F | 22.3 | 42 | 475 | 44 | 0.0 |
| 9 | plugins/the_odds_api.py | ❌ F | 25.8 | 34 | 419 | 46 | 0.0 |
| 10 | dashboard/dashboard_app.py | ❌ F | 27.1 | 33 | 1917 | 11 | 0.0 |

## 📁 Per-File Details

_Showing 20 worst files. 47 additional files omitted._

### plugins/portfolio_optimizer.py — ❌ F (3.5/100)

LOC: 844 | Classes: 7 | Functions: 4 | MI: 12 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 383 | 🟡 MEDIUM | Feature Envy | Method 'JsonFileParser._parse_teams' accesses 'data' 9 times but 'self' only 0 times | Move Method — consider moving '_parse_teams' to the class that owns 'data'. |
| 449 | 🟡 MEDIUM | Primitive Obsession | Function '_derive_market_prob_from_asks' has 4 primitive-typed parameters: yes_ask: Name(id='float', ctx=Load()), no_ask: Name(id='float', ctx=Load()), bet_direction: Name(id='str', ctx=Load()), fallback_prob: Name(id='float', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 478 | 🟡 MEDIUM | Large Class | Class 'PortfolioOptimizer' spans 552 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 608 | 🟡 MEDIUM | Long Method | Function 'load_opportunities_from_database' has 51 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 754 | 🟡 MEDIUM | Feature Envy | Method 'PortfolioOptimizer.filter_opportunities' accesses 'opp' 6 times but 'self' only 4 times | Move Method — consider moving 'filter_opportunities' to the class that owns 'opp'. |
| 965 | 🟡 MEDIUM | Long Method | Function 'generate_bet_report' has 58 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 965 | 🟡 MEDIUM | Feature Envy | Method 'PortfolioOptimizer.generate_bet_report' accesses 'lines' 7 times but 'self' only 4 times | Move Method — consider moving 'generate_bet_report' to the class that owns 'lines'. |
| 965 | 🟡 MEDIUM | Feature Envy | Method 'PortfolioOptimizer.generate_bet_report' accesses 'opp' 9 times but 'self' only 4 times | Move Method — consider moving 'generate_bet_report' to the class that owns 'opp'. |
| 154 | 🟢 LOW | Missing Type Hint | Function 'kelly_fraction' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 166 | 🟢 LOW | Missing Type Hint | Function 'expected_value' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 171 | 🟢 LOW | Missing Type Hint | Function 'blended_prob' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 179 | 🟢 LOW | Missing Type Hint | Function 'format_matchup' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 189 | 🟢 LOW | Missing Type Hint | Function 'format_rankings' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 238 | 🟢 LOW | Missing Type Hint | Function 'parse' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 242 | 🟢 LOW | Missing Type Hint | Function '_get_numeric' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |

_... and 36 more smells._

### plugins/kalshi_betting.py — ❌ F (4.3/100)

LOC: 849 | Classes: 7 | Functions: 0 | MI: 14 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 480 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_create_signature' (line 480), '_fetch_from_kalshi_api' (line 668) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 688 | 🟠 HIGH | Duplicate Code | Function 'get_open_positions' is an exact duplicate of 'get_open_orders' at plugins/kalshi_betting.py:696 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 125 | 🟡 MEDIUM | Primitive Obsession | Function '__init__' has 4 primitive-typed parameters: min_confidence: Name(id='float', ctx=Load()), min_edge: Name(id='float', ctx=Load()), dry_run: Name(id='bool', ctx=Load()), trade_date: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 242 | 🟡 MEDIUM | Large Class | Class 'KalshiBetting' spans 794 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 242 | 🟡 MEDIUM | Large Class | Class 'KalshiBetting' has 45 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 297 | 🟡 MEDIUM | Magic Number | Magic number 300 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 331 | 🟡 MEDIUM | Feature Envy | Method 'KalshiBetting._parse_positional_args' accesses 'kwargs' 7 times but 'self' only 0 times | Move Method — consider moving '_parse_positional_args' to the class that owns 'kwargs'. |
| 350 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 350 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 372 | 🟡 MEDIUM | Feature Envy | Method 'KalshiBetting._parse_legacy_keyword_args' accesses 'kwargs' 7 times but 'self' only 0 times | Move Method — consider moving '_parse_legacy_keyword_args' to the class that owns 'kwargs'. |
| 802 | 🟡 MEDIUM | Feature Envy | Method 'KalshiBetting._place_order' accesses 'market' 5 times but 'self' only 1 times | Move Method — consider moving '_place_order' to the class that owns 'market'. |
| 888 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 893 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 893 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 912 | 🟡 MEDIUM | Long Method | Function 'process_bet_recommendations' has 59 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 64 more smells._

### plugins/kalshi_markets.py — ❌ F (9.3/100)

LOC: 535 | Classes: 5 | Functions: 27 | MI: 31 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 88 | 🟡 MEDIUM | Missing Type Hint | Function '__init__' has incomplete type hints: fully untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟡 MEDIUM | Missing Type Hint | Function 'get_markets' has incomplete type hints: fully untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟡 MEDIUM | Feature Envy | Method 'KalshiAPI.get_markets' accesses 'logger' 5 times but 'self' only 1 times | Move Method — consider moving 'get_markets' to the class that owns 'logger'. |
| 169 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 209 | 🟡 MEDIUM | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 211 | 🟡 MEDIUM | Magic Number | Magic number 2000 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 212 | 🟡 MEDIUM | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 213 | 🟡 MEDIUM | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 213 | 🟡 MEDIUM | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 252 | 🟡 MEDIUM | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 304 | 🟡 MEDIUM | Missing Type Hint | Function '_generate_game_id' has incomplete type hints: fully untyped | Add Type Annotations for all parameters and return type. |
| 347 | 🟡 MEDIUM | Long Method | Function '_upsert_odds' has 53 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 347 | 🟡 MEDIUM | Primitive Obsession | Function '_upsert_odds' has 4 primitive-typed parameters: game_id: Name(id='str', ctx=Load()), home_team: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()), away_team: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()), ticker: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 380 | 🟡 MEDIUM | Magic Number | Magic number 100.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 384 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 30 more smells._

### plugins/db_loader.py — ❌ F (13.0/100)

LOC: 458 | Classes: 3 | Functions: 0 | MI: 43 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 67 | 🟡 MEDIUM | Duplicate Code | Function '__getattr__' is 100% similar to '_extract_raw_attribute' at plugins/elo/argument_parser.py:152 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 67 | 🟡 MEDIUM | Duplicate Code | Function '__getattr__' is 94% similar to '_create_team_match_context' at plugins/elo/tennis_elo_rating.py:202 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 363 | 🟡 MEDIUM | Duplicate Code | Function 'load_csv_history' is 95% similar to '_load_sport_csv_file' at plugins/db_loader.py:417 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 24 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 27 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 27 | 🟢 LOW | Feature Envy | Method 'LegacyConnWrapper.execute' accesses 'query' 3 times but 'self' only 2 times | Move Method — consider moving 'execute' to the class that owns 'query'. |
| 36 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 52 | 🟢 LOW | Missing Type Hint | Function 'commit' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 58 | 🟢 LOW | Missing Type Hint | Function 'fetchall' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 61 | 🟢 LOW | Missing Type Hint | Function 'fetchone' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 64 | 🟢 LOW | Missing Type Hint | Function 'close' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 67 | 🟢 LOW | Missing Type Hint | Function '__getattr__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 75 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 85 | 🟢 LOW | Missing Type Hint | Function 'conn' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 93 | 🟢 LOW | Missing Type Hint | Function '__enter__' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 35 more smells._

### plugins/elo/tennis_elo_rating.py — ❌ F (15.5/100)

LOC: 446 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 133 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_create_match_context' (line 133), '_create_legacy_match_result' (line 178), '_create_team_match_context' (line 202), 'predict' (line 242), 'predict_team' (line 528) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 153 | 🟠 HIGH | Primitive Obsession | Repeated primitive parameter group appears in: '_create_match_result' (line 153), '_create_team_match_result' (line 219), 'update_team' (line 546) | Replace Data Value with Object — create a shared data structure for this recurring parameter group. |
| 10 | 🟡 MEDIUM | Large Class | Class 'TennisEloRating' spans 560 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 133 | 🟡 MEDIUM | Primitive Obsession | Function '_create_match_context' has 4 primitive-typed parameters: player_a: Name(id='str', ctx=Load()), player_b: Name(id='str', ctx=Load()), tour: Name(id='str', ctx=Load()), is_neutral: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 153 | 🟡 MEDIUM | Primitive Obsession | Function '_create_match_result' has 5 primitive-typed parameters: player_a: Name(id='str', ctx=Load()), player_b: Name(id='str', ctx=Load()), home_won: Subscript(value=Name(id='Union', ctx=Load()), slice=Tuple(elts=[Name(id='bool', ctx=Load()), Name(id='float', ctx=Load())], ctx=Load()), ctx=Load()), tour: Name(id='str', ctx=Load()), is_neutral: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 153 | 🟡 MEDIUM | Duplicate Code | Function '_create_match_result' is 100% similar to '_create_team_match_result' at plugins/elo/tennis_elo_rating.py:219 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 178 | 🟡 MEDIUM | Primitive Obsession | Function '_create_legacy_match_result' has 4 primitive-typed parameters: winner: Name(id='str', ctx=Load()), loser: Name(id='str', ctx=Load()), tour: Name(id='str', ctx=Load()), is_neutral: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 219 | 🟡 MEDIUM | Primitive Obsession | Function '_create_team_match_result' has 4 primitive-typed parameters: home_team: Name(id='str', ctx=Load()), away_team: Name(id='str', ctx=Load()), home_win: Subscript(value=Name(id='Union', ctx=Load()), slice=Tuple(elts=[Name(id='bool', ctx=Load()), Name(id='float', ctx=Load())], ctx=Load()), ctx=Load()), is_neutral: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 242 | 🟡 MEDIUM | Primitive Obsession | Function 'predict' has 4 primitive-typed parameters: home_team: Name(id='str', ctx=Load()), away_team: Name(id='str', ctx=Load()), is_neutral: Name(id='bool', ctx=Load()), tour: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 316 | 🟡 MEDIUM | Primitive Obsession | Function '_calculate_update_change' has 4 primitive-typed parameters: rw: Name(id='float', ctx=Load()), rl: Name(id='float', ctx=Load()), mw: Name(id='int', ctx=Load()), ml: Name(id='int', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 481 | 🟡 MEDIUM | Duplicate Code | Function 'legacy_update' is 100% similar to 'predict_team' at plugins/elo/tennis_elo_rating.py:528 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 546 | 🟡 MEDIUM | Primitive Obsession | Function 'update_team' has 4 primitive-typed parameters: home_team: Name(id='str', ctx=Load()), away_team: Name(id='str', ctx=Load()), home_win: Subscript(value=Name(id='Union', ctx=Load()), slice=Tuple(elts=[Name(id='bool', ctx=Load()), Name(id='float', ctx=Load())], ctx=Load()), ctx=Load()), is_neutral: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 10 | 🟢 LOW | Large Class | Class 'TennisEloRating' has 24 methods (threshold: 20) | Split Class — group related methods into smaller collaborating classes. |
| 19 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 19 | 🟢 LOW | Primitive Obsession | Function '__init__' has 3 primitive-typed parameters: k_factor: Name(id='float', ctx=Load()), home_advantage: Name(id='float', ctx=Load()), initial_rating: Name(id='float', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

_... and 37 more smells._

### plugins/csv_processors.py — ❌ F (17.9/100)

LOC: 413 | Classes: 8 | Functions: 1 | MI: 60 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 72 | 🟠 HIGH | Duplicate Code | Function '_extract_ncaab_game_data' is an exact duplicate of '_extract_wncaab_game_data' at plugins/csv_processors.py:355 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 215 | 🟠 HIGH | Duplicate Code | Function '_extract_epl_game_data' is an exact duplicate of '_extract_ligue1_game_data' at plugins/csv_processors.py:288 | Once and Only Once — extract the shared logic into a single function and call it from both sites. |
| 47 | 🟡 MEDIUM | Duplicate Code | Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:330 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 47 | 🟡 MEDIUM | Duplicate Code | Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:392 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 47 | 🟡 MEDIUM | Duplicate Code | Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:437 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 184 | 🟡 MEDIUM | Duplicate Code | Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:257 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 330 | 🟡 MEDIUM | Duplicate Code | Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:392 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 330 | 🟡 MEDIUM | Duplicate Code | Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:437 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 392 | 🟡 MEDIUM | Duplicate Code | Function 'process_row' is 100% similar to 'process_row' at plugins/csv_processors.py:437 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 411 | 🟡 MEDIUM | Duplicate Code | Function '_extract_unrivaled_game_data' is 100% similar to '_extract_cba_game_data' at plugins/csv_processors.py:457 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 16 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 25 | 🟢 LOW | Missing Type Hint | Function 'process_row' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 35 | 🟢 LOW | Missing Type Hint | Function 'get_table_name' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 47 | 🟢 LOW | Missing Type Hint | Function 'process_row' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 72 | 🟢 LOW | Missing Type Hint | Function '_extract_ncaab_game_data' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 24 more smells._

### plugins/nhl_game_events.py — ❌ F (20.1/100)

LOC: 146 | Classes: 1 | Functions: 1 | MI: 67 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 18 | 🟡 MEDIUM | Missing Type Hint | Function 'get_schedule_by_date' has incomplete type hints: fully untyped | Add Type Annotations for all parameters and return type. |
| 18 | 🟡 MEDIUM | Duplicate Code | Function 'get_schedule_by_date' is 100% similar to 'get_season_schedule' at plugins/nhl_game_events.py:35 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 29 | 🟡 MEDIUM | Magic Number | Magic number 8 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 30 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 31 | 🟡 MEDIUM | Magic Number | Magic number 45 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 35 | 🟡 MEDIUM | Missing Type Hint | Function 'get_season_schedule' has incomplete type hints: fully untyped | Add Type Annotations for all parameters and return type. |
| 45 | 🟡 MEDIUM | Magic Number | Magic number 8 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 46 | 🟡 MEDIUM | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 47 | 🟡 MEDIUM | Magic Number | Magic number 45 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 51 | 🟡 MEDIUM | Missing Type Hint | Function 'get_game_data' has incomplete type hints: fully untyped | Add Type Annotations for all parameters and return type. |
| 61 | 🟡 MEDIUM | Missing Type Hint | Function 'get_game_boxscore' has incomplete type hints: fully untyped | Add Type Annotations for all parameters and return type. |
| 65 | 🟡 MEDIUM | Missing Type Hint | Function 'download_game' has incomplete type hints: fully untyped | Add Type Annotations for all parameters and return type. |
| 86 | 🟡 MEDIUM | Missing Type Hint | Function 'download_season' has incomplete type hints: fully untyped | Add Type Annotations for all parameters and return type. |
| 99 | 🟡 MEDIUM | Magic Number | Magic number 4 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 99 | 🟡 MEDIUM | Magic Number | Magic number 6 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |

_... and 7 more smells._

### plugins/portfolio_betting.py — ❌ F (22.3/100)

LOC: 475 | Classes: 2 | Functions: 3 | MI: 44 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 483 | 🟡 MEDIUM | Feature Envy | Method 'PortfolioBettingManager._format_allocation_row' accesses 'opp' 5 times but 'self' only 0 times | Move Method — consider moving '_format_allocation_row' to the class that owns 'opp'. |
| 31 | 🟢 LOW | Missing Type Hint | Function 'place_bet' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 38 | 🟢 LOW | Missing Type Hint | Function '_place_dry_run_bet' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 61 | 🟢 LOW | Long Method | Function '_place_real_bet' has 35 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 61 | 🟢 LOW | Missing Type Hint | Function '_place_real_bet' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 100 | 🟢 LOW | Large Class | Class 'PortfolioBettingManager' spans 446 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 108 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 129 | 🟢 LOW | Long Method | Function 'process_daily_bets' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 129 | 🟢 LOW | Missing Type Hint | Function 'process_daily_bets' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 184 | 🟢 LOW | Missing Type Hint | Function '_place_optimized_bets' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 210 | 🟢 LOW | Missing Type Hint | Function '_initialize_placement_results' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 228 | 🟢 LOW | Missing Type Hint | Function '_print_betting_header' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 234 | 🟢 LOW | Long Method | Function '_process_single_allocation' has 37 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 234 | 🟢 LOW | Missing Type Hint | Function '_process_single_allocation' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 283 | 🟢 LOW | Missing Type Hint | Function '_print_allocation_header' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |

_... and 27 more smells._

### plugins/the_odds_api.py — ❌ F (25.8/100)

LOC: 419 | Classes: 1 | Functions: 1 | MI: 46 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 55 | 🟡 MEDIUM | Feature Envy | Method 'TheOddsAPI._generate_game_id' accesses 'game' 6 times but 'self' only 0 times | Move Method — consider moving '_generate_game_id' to the class that owns 'game'. |
| 80 | 🟡 MEDIUM | Feature Envy | Method 'TheOddsAPI._upsert_team_mappings' accesses 'game' 6 times but 'self' only 0 times | Move Method — consider moving '_upsert_team_mappings' to the class that owns 'game'. |
| 91 | 🟡 MEDIUM | Feature Envy | Method 'TheOddsAPI._upsert_unified_game' accesses 'game' 9 times but 'self' only 1 times | Move Method — consider moving '_upsert_unified_game' to the class that owns 'game'. |
| 116 | 🟡 MEDIUM | Long Method | Function '_upsert_game_odds_for_bookmaker' has 61 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 116 | 🟡 MEDIUM | Feature Envy | Method 'TheOddsAPI._upsert_game_odds_for_bookmaker' accesses 'game' 7 times but 'self' only 2 times | Move Method — consider moving '_upsert_game_odds_for_bookmaker' to the class that owns 'game'. |
| 20 | 🟢 LOW | Large Class | Class 'TheOddsAPI' spans 450 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 36 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 55 | 🟢 LOW | Missing Type Hint | Function '_generate_game_id' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 73 | 🟢 LOW | Missing Type Hint | Function 'american_to_decimal' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 80 | 🟢 LOW | Missing Type Hint | Function '_upsert_team_mappings' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 91 | 🟢 LOW | Missing Type Hint | Function '_upsert_unified_game' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 116 | 🟢 LOW | Missing Type Hint | Function '_upsert_game_odds_for_bookmaker' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 185 | 🟢 LOW | Long Method | Function 'save_to_db' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 185 | 🟢 LOW | Missing Type Hint | Function 'save_to_db' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 238 | 🟢 LOW | Long Method | Function 'fetch_markets' has 47 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 19 more smells._

### dashboard/dashboard_app.py — ❌ F (27.1/100)

LOC: 1917 | Classes: 3 | Functions: 80 | MI: 11 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 111 | 🟢 LOW | Long Method | Function '_render_plotly_chart' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 320 | 🟢 LOW | Missing Type Hint | Function '_get_rating_class_for_league' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 372 | 🟢 LOW | Long Method | Function '_get_update_args' has 31 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 396 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_get_update_args' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 409 | 🟢 LOW | Long Method | Function 'run_elo_simulation' has 34 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 490 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_assign_deciles' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 496 | 🟢 LOW | Long Method | Function 'calculate_deciles' has 42 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 542 | 🟢 LOW | Long Method | Function 'calculate_decile_probability_roi_matrix' has 36 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 652 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_render_sync_button' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 753 | 🟢 LOW | Long Method | Function '_render_filters' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 840 | 🟢 LOW | Long Method | Function 'betting_performance_page_v2' has 40 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 840 | 🟢 LOW | Missing Type Hint | Function 'betting_performance_page_v2' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 884 | 🟢 LOW | Missing Type Hint | Function 'financial_performance_page' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 1014 | 🟢 LOW | Long Method | Function '_calculate_portfolio_value' has 41 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 1094 | 🟢 LOW | Long Method | Function '_display_pl_time_series' has 30 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 18 more smells._

### plugins/data_validation.py — ❌ F (28.5/100)

LOC: 1147 | Classes: 4 | Functions: 40 | MI: 20 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 52 | 🟢 LOW | Missing Type Hint | Function '__post_init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 63 | 🟢 LOW | Missing Type Hint | Function 'add_check' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 63 | 🟢 LOW | Primitive Obsession | Function 'add_check' has 3 primitive-typed parameters: passed: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='bool', ctx=Load()), ctx=Load()), message: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()), severity: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 97 | 🟢 LOW | Missing Type Hint | Function '_add_check_result' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 116 | 🟢 LOW | Missing Type Hint | Function '_format_check_message' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 130 | 🟢 LOW | Missing Type Hint | Function '_format_error_message' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 143 | 🟢 LOW | Missing Type Hint | Function '_format_warning_message' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 161 | 🟢 LOW | Missing Type Hint | Function 'add_stat' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 179 | 🟢 LOW | Missing Type Hint | Function 'print_report' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 498 | 🟢 LOW | Missing Type Hint | Function 'from_row' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 515 | 🟢 LOW | Missing Type Hint | Function '_format_error_message' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 526 | 🟢 LOW | Missing Type Hint | Function '_format_warning_message' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 537 | 🟢 LOW | Missing Type Hint | Function '_print_header' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 555 | 🟢 LOW | Missing Type Hint | Function '_print_passed_checks' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 565 | 🟢 LOW | Missing Type Hint | Function '_print_check_list' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |

_... and 19 more smells._

### plugins/odds_comparator.py — ❌ F (39.7/100)

LOC: 393 | Classes: 6 | Functions: 0 | MI: 37 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 437 | 🟡 MEDIUM | Feature Envy | Method 'OddsComparator.find_opportunities' accesses 'config' 5 times but 'self' only 2 times | Move Method — consider moving 'find_opportunities' to the class that owns 'config'. |
| 68 | 🟢 LOW | Missing Type Hint | Function 'expected_value' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 73 | 🟢 LOW | Missing Type Hint | Function 'kelly_fraction' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 83 | 🟢 LOW | Missing Type Hint | Function 'agreement_diff' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 87 | 🟢 LOW | Missing Type Hint | Function 'determine_confidence' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 102 | 🟢 LOW | Missing Type Hint | Function 'is_value_bet' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 125 | 🟢 LOW | Missing Type Hint | Function 'to_opportunity' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 173 | 🟢 LOW | Long Method | Function 'calculate_probabilities' has 34 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 173 | 🟢 LOW | Missing Type Hint | Function 'calculate_probabilities' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 184 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'calculate_probabilities' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 210 | 🟢 LOW | Missing Type Hint | Function 'evaluate' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 222 | 🟢 LOW | Missing Type Hint | Function '_prepare_outcomes' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 230 | 🟢 LOW | Missing Type Hint | Function '_evaluate_outcome' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 230 | 🟢 LOW | Primitive Obsession | Function '_evaluate_outcome' has 3 primitive-typed parameters: side: Name(id='str', ctx=Load()), team_name: Name(id='str', ctx=Load()), elo_prob: Name(id='float', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 262 | 🟢 LOW | Missing Type Hint | Function 'get_rating' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 13 more smells._

### dags/multi_sport_betting_workflow.py — ❌ F (40.6/100)

LOC: 1359 | Classes: 1 | Functions: 41 | MI: 30 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 603 | 🟠 HIGH | Deep Nesting | Nesting depth 6 in '_load_sport_data_with_loader' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 597 | 🟡 MEDIUM | Deep Nesting | Nesting depth 5 in '_load_sport_data_with_loader' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 53 | 🟢 LOW | Missing Type Hint | Function 'total_value' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 97 | 🟢 LOW | Long Method | Function 'send_sms' has 32 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 97 | 🟢 LOW | Primitive Obsession | Function 'send_sms' has 3 primitive-typed parameters: to_number: Name(id='str', ctx=Load()), subject: Name(id='str', ctx=Load()), body: Name(id='str', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 452 | 🟢 LOW | Long Method | Function 'download_games' has 44 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 491 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'download_games' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 593 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_load_sport_data_with_loader' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 608 | 🟢 LOW | Missing Type Hint | Function '_initialize_elo_system' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 634 | 🟢 LOW | Missing Type Hint | Function '_load_ligue1_ratings_from_csv' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 649 | 🟢 LOW | Missing Type Hint | Function '_load_games_from_unified_table' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 683 | 🟢 LOW | Missing Type Hint | Function '_load_epl_games' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 712 | 🟢 LOW | Long Method | Function 'update_elo_ratings' has 49 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 765 | 🟢 LOW | Missing Type Hint | Function '_load_games_from_sport_class' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 788 | 🟢 LOW | Long Method | Function 'fetch_prediction_markets' has 39 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |

_... and 7 more smells._

### plugins/elo/base_elo_rating.py — ❌ F (42.3/100)

LOC: 275 | Classes: 2 | Functions: 0 | MI: 64 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 306 | 🟡 MEDIUM | Duplicate Code | Function 'get_rating' is 94% similar to 'expected_score' at plugins/elo/base_elo_rating.py:318 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 306 | 🟡 MEDIUM | Duplicate Code | Function 'get_rating' is 94% similar to 'get_rating_or_default' at plugins/elo/rating_store.py:113 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 318 | 🟡 MEDIUM | Duplicate Code | Function 'expected_score' is 100% similar to 'get_rating_or_default' at plugins/elo/rating_store.py:113 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 30 | 🟢 LOW | Large Class | Class 'BaseEloRating' spans 309 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 43 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 43 | 🟢 LOW | Primitive Obsession | Function '__init__' has 3 primitive-typed parameters: k_factor: Name(id='float', ctx=Load()), home_advantage: Name(id='float', ctx=Load()), initial_rating: Name(id='float', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 80 | 🟢 LOW | Missing Type Hint | Function 'from_config' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 96 | 🟢 LOW | Missing Type Hint | Function 'k_factor' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 101 | 🟢 LOW | Missing Type Hint | Function 'home_advantage' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟢 LOW | Missing Type Hint | Function 'initial_rating' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 111 | 🟢 LOW | Missing Type Hint | Function 'ratings' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 116 | 🟢 LOW | Missing Type Hint | Function 'ratings' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 121 | 🟢 LOW | Missing Type Hint | Function 'set_rating' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 125 | 🟢 LOW | Missing Type Hint | Function 'predict' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 125 | 🟢 LOW | Primitive Obsession | Function 'predict' has 3 primitive-typed parameters: home_team: Name(id='str', ctx=Load()), away_team: Name(id='str', ctx=Load()), is_neutral: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |

_... and 14 more smells._

### plugins/bet_loader.py — ❌ F (43.4/100)

LOC: 369 | Classes: 4 | Functions: 4 | MI: 37 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 43 | 🟢 LOW | Missing Type Hint | Function 'computed_expected_value' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 51 | 🟢 LOW | Missing Type Hint | Function 'computed_kelly_fraction' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 63 | 🟢 LOW | Missing Type Hint | Function 'generate_id' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 69 | 🟢 LOW | Missing Type Hint | Function 'to_recommendation' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 92 | 🟢 LOW | Long Method | Function 'from_dict' has 38 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 92 | 🟢 LOW | Missing Type Hint | Function 'from_dict' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 92 | 🟢 LOW | Feature Envy | Method 'BetData.from_dict' accesses 'data' 4 times but 'self' only 0 times | Move Method — consider moving 'from_dict' to the class that owns 'data'. |
| 189 | 🟢 LOW | Missing Type Hint | Function 'to_sql_params' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 222 | 🟢 LOW | Missing Type Hint | Function 'from_dict' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 231 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 239 | 🟢 LOW | Missing Type Hint | Function '_lazy_initialize_table' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 261 | 🟢 LOW | Missing Type Hint | Function '_ensure_table' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 265 | 🟢 LOW | Magic Number | Magic number 3 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 275 | 🟢 LOW | Deep Nesting | Nesting depth 4 in '_ensure_table' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 282 | 🟢 LOW | Missing Type Hint | Function '_create_bet_recommendations_table' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |

_... and 12 more smells._

### plugins/csv_history_loader.py — ❌ F (44.1/100)

LOC: 356 | Classes: 2 | Functions: 0 | MI: 51 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 315 | 🟡 MEDIUM | Long Method | Function '_get_csv_load_config_for_sport' has 54 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 45 | 🟢 LOW | Large Class | Class 'CSVHistoryLoader' spans 393 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 48 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 56 | 🟢 LOW | Missing Type Hint | Function '_load_history_from_dir' has incomplete type hints: 1/6 params untyped | Add Type Annotations for all parameters and return type. |
| 56 | 🟢 LOW | Primitive Obsession | Function '_load_history_from_dir' has 3 primitive-typed parameters: pattern: Name(id='str', ctx=Load()), sport_name: Name(id='str', ctx=Load()), target_date: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 83 | 🟢 LOW | Missing Type Hint | Function '_get_csv_history_config' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 120 | 🟢 LOW | Missing Type Hint | Function 'load_csv_history' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 148 | 🟢 LOW | Missing Type Hint | Function '_process_csv_row' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 160 | 🟢 LOW | Missing Type Hint | Function '_load_csv_file' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 194 | 🟢 LOW | Missing Type Hint | Function '_extract_metadata' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 205 | 🟢 LOW | Missing Type Hint | Function '_read_csv_with_encoding' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 224 | 🟢 LOW | Missing Type Hint | Function '_try_read_csv_with_encoding' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 236 | 🟢 LOW | Missing Type Hint | Function '_try_read_csv_without_encoding' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 244 | 🟢 LOW | Missing Type Hint | Function '_process_date_column' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 244 | 🟢 LOW | Feature Envy | Method 'CSVHistoryLoader._process_date_column' accesses 'pd' 3 times but 'self' only 0 times | Move Method — consider moving '_process_date_column' to the class that owns 'pd'. |

_... and 13 more smells._

### plugins/elo/cba_elo_rating.py — ❌ F (45.4/100)

LOC: 213 | Classes: 3 | Functions: 0 | MI: 65 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 57 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at plugins/elo/mlb_elo_rating.py:23 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 57 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at plugins/elo/nba_elo_rating.py:24 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 57 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 95% similar to '__init__' at plugins/elo/nfl_elo_rating.py:15 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 57 | 🟡 MEDIUM | Duplicate Code | Function '__init__' is 100% similar to '__init__' at plugins/elo/unrivaled_elo_rating.py:25 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 77 | 🟡 MEDIUM | Primitive Obsession | Function 'update' has 4 primitive-typed parameters: home_team: Name(id='str', ctx=Load()), away_team: Name(id='str', ctx=Load()), home_won: Subscript(value=Name(id='Union', ctx=Load()), slice=Tuple(elts=[Name(id='bool', ctx=Load()), Name(id='float', ctx=Load())], ctx=Load()), ctx=Load()), is_neutral: Name(id='bool', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 161 | 🟡 MEDIUM | Feature Envy | Method 'CBAEloRating._calculate_elo_update' accesses 'params' 6 times but 'self' only 3 times | Move Method — consider moving '_calculate_elo_update' to the class that owns 'params'. |
| 185 | 🟡 MEDIUM | Feature Envy | Method 'CBAEloRating._record_game_history' accesses 'params' 9 times but 'self' only 1 times | Move Method — consider moving '_record_game_history' to the class that owns 'params'. |
| 57 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 57 | 🟢 LOW | Primitive Obsession | Function '__init__' has 3 primitive-typed parameters: k_factor: Name(id='float', ctx=Load()), home_advantage: Name(id='float', ctx=Load()), initial_rating: Name(id='float', ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 77 | 🟢 LOW | Long Method | Function 'update' has 45 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 77 | 🟢 LOW | Missing Type Hint | Function 'update' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 142 | 🟢 LOW | Missing Type Hint | Function '_validate_and_normalize_args' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 142 | 🟢 LOW | Primitive Obsession | Function '_validate_and_normalize_args' has 3 primitive-typed parameters: home_team: Name(id='str', ctx=Load()), away_team: Name(id='str', ctx=Load()), home_won: Subscript(value=Name(id='Union', ctx=Load()), slice=Tuple(elts=[Name(id='bool', ctx=Load()), Name(id='float', ctx=Load()), Constant(value=None)], ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 161 | 🟢 LOW | Missing Type Hint | Function '_calculate_elo_update' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 185 | 🟢 LOW | Missing Type Hint | Function '_record_game_history' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 6 more smells._

### plugins/base_games.py — ❌ F (46.7/100)

LOC: 324 | Classes: 4 | Functions: 0 | MI: 53 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 36 | 🟢 LOW | Missing Type Hint | Function 'execute' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 64 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'execute' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 71 | 🟢 LOW | Missing Type Hint | Function '_make_request_with_retry_logic' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function '_should_retry_after_exception' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 102 | 🟢 LOW | Missing Type Hint | Function '_handle_retry_after_exception' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟢 LOW | Magic Number | Magic number 60.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 113 | 🟢 LOW | Missing Type Hint | Function '_handle_rate_limit' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 125 | 🟢 LOW | Magic Number | Magic number 120.0 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 134 | 🟢 LOW | Missing Type Hint | Function '_handle_not_found' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 149 | 🟢 LOW | Missing Type Hint | Function '_calculate_wait_time' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 162 | 🟢 LOW | Magic Number | Magic number 0.8 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 162 | 🟢 LOW | Magic Number | Magic number 1.2 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 205 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 205 | 🟢 LOW | Primitive Obsession | Function '__init__' has 3 primitive-typed parameters: sport: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()), output_dir: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()), date_folder: Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(id='str', ctx=Load()), ctx=Load()) | Introduce Parameter Object — group related primitives into a dataclass or NamedTuple. |
| 234 | 🟢 LOW | Missing Type Hint | Function '_fetch_game_resource' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |

_... and 13 more smells._

### plugins/elo/argument_parser.py — ❌ F (47.3/100)

LOC: 311 | Classes: 2 | Functions: 0 | MI: 53 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 126 | 🟡 MEDIUM | Duplicate Code | Function '_extract_raw_matchup' is 100% similar to '_extract_raw_result' at plugins/elo/argument_parser.py:139 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 152 | 🟡 MEDIUM | Duplicate Code | Function '_extract_raw_attribute' is 94% similar to '_create_team_match_context' at plugins/elo/tennis_elo_rating.py:202 | Extract Shared Function — identify the common logic and parameterise the differences. |
| 368 | 🟡 MEDIUM | Feature Envy | Method 'ArgumentParser.parse_result' accesses 'kwargs' 5 times but 'self' only 2 times | Move Method — consider moving 'parse_result' to the class that owns 'kwargs'. |
| 23 | 🟢 LOW | Large Class | Class 'ArgumentParser' spans 376 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 31 | 🟢 LOW | Missing Type Hint | Function 'parse_update_args' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 54 | 🟢 LOW | Missing Type Hint | Function '_parse_update_args_from_object' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 79 | 🟢 LOW | Missing Type Hint | Function '_extract_attribute' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 98 | 🟢 LOW | Missing Type Hint | Function '_extract_attributes' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 126 | 🟢 LOW | Missing Type Hint | Function '_extract_raw_matchup' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 139 | 🟢 LOW | Missing Type Hint | Function '_extract_raw_result' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 152 | 🟢 LOW | Missing Type Hint | Function '_extract_raw_attribute' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |
| 163 | 🟢 LOW | Missing Type Hint | Function '_extract_home_won_status' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 177 | 🟢 LOW | Missing Type Hint | Function '_apply_legacy_score_hack' has incomplete type hints: 1/5 params untyped | Add Type Annotations for all parameters and return type. |
| 192 | 🟢 LOW | Missing Type Hint | Function '_validate_parsed_args' has incomplete type hints: 1/3 params untyped | Add Type Annotations for all parameters and return type. |
| 204 | 🟢 LOW | Missing Type Hint | Function '_parse_matchup_from_args' has incomplete type hints: 1/4 params untyped | Add Type Annotations for all parameters and return type. |

_... and 8 more smells._

### plugins/cba_games.py — ❌ F (47.9/100)

LOC: 322 | Classes: 1 | Functions: 0 | MI: 52 | Avg CC: 0.0

| Line | Severity | Type | Message | Suggested Refactoring |
|-----:|:---------|:-----|:--------|:----------------------|
| 20 | 🟢 LOW | Large Class | Class 'CBAGames' spans 430 lines (threshold: 300) | Extract Class — split into smaller, cohesive classes with single responsibilities. |
| 33 | 🟢 LOW | Missing Type Hint | Function '__init__' has incomplete type hints: missing return type | Add Type Annotations for all parameters and return type. |
| 48 | 🟢 LOW | Missing Type Hint | Function '_load_team_mapping' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 56 | 🟢 LOW | Missing Type Hint | Function 'normalize_team_name' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 87 | 🟢 LOW | Missing Type Hint | Function 'download_games' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 106 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'download_games' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 121 | 🟢 LOW | Missing Type Hint | Function '_fetch_season_events' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 134 | 🟢 LOW | Magic Number | Magic number 30 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 142 | 🟢 LOW | Missing Type Hint | Function 'download_games_for_date' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |
| 159 | 🟢 LOW | Magic Number | Magic number 30 — consider extracting to a named constant | Extract Constant / Introduce Named Constant. |
| 180 | 🟢 LOW | Long Method | Function 'load_games' has 44 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 180 | 🟢 LOW | Missing Type Hint | Function 'load_games' has incomplete type hints: 1/1 params untyped | Add Type Annotations for all parameters and return type. |
| 201 | 🟢 LOW | Deep Nesting | Nesting depth 4 in 'load_games' (threshold: 4) | Extract Method / Introduce Guard Clause / Replace Nested Conditional with Early Return. |
| 234 | 🟢 LOW | Long Method | Function '_parse_event' has 40 lines (threshold: 30) | Extract Method — break this function into smaller, intention-revealing helper functions. |
| 234 | 🟢 LOW | Missing Type Hint | Function '_parse_event' has incomplete type hints: 1/2 params untyped | Add Type Annotations for all parameters and return type. |

_... and 12 more smells._

## ✨ Clean Files (4 files with no smells)

<details><summary>Click to expand</summary>

- plugins/__init__.py — ✅ A
- plugins/constants.py — ✅ A
- plugins/elo/__init__.py — ✅ A
- plugins/elo/ncaab_elo_rating.py — ✅ A

</details>

---

_Report generated by XP Code Smell Detector. Smells are static heuristics — use judgement when prioritising fixes._
