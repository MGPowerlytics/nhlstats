# TODOS

Deferred work items from engineering review. Each item includes context for pickup.

---

## TODO-001: CLV Calculation Audit — ⚠️ RESOLVED: CLV IS BROKEN
**Priority:** HIGH → **PROMOTED TO PHASE 0** (blocking prerequisite for diagnostic)
**Status:** AUDIT COMPLETE — CLV uses binary game outcomes (1.0/0.0), NOT market closing prices. `fetch_closing_lines_from_kalshi()` and `fetch_closing_lines_from_sbr()` are unimplemented TODO stubs. "Positive CLV" across all sports is a mathematical artifact.
**What:** Fix `plugins/clv_tracker.py` to compute real closing prices from `game_odds` snapshots (last snapshot before `market_close_time_utc`, matched on `game_id`). Add `update_real_closing_lines()` to hourly DAG for ongoing tracking.
**Why:** Without real CLV, the diagnostic's qualification gate is measuring nothing. This is the highest-leverage fix in the entire plan.
**Where to start:** `plugins/clv_tracker.py` — replace binary outcome CLV with real closing price CLV. `plugins/bet_tracker.py:165-205` — `_calculate_closing_probability()` needs rewrite.
**Depends on:** Nothing — this IS Phase 0
**Added:** 2026-03-30 (eng review) | **Updated:** 2026-03-30 (CEO review — audit complete, promoted)

---

## TODO-002: Automate Diagnostic as Weekly DAG Task
**Priority:** LOW — only after Phase 1 proves edge
**What:** Wrap `pnl_diagnostic.py` as a weekly DAG task storing results in `diagnostic_reports` table.
**Why:** Edge decays as markets adapt. Ongoing monitoring catches degradation early.
**Where to start:** `pnl_diagnostic.py` will expose `run_diagnostic()` — wrap in a DAG task following existing patterns in `dags/`.
**Depends on:** `pnl_diagnostic.py` complete + Phase 1 showing qualifying sports
**Added:** 2026-03-30 (eng review)

---

## TODO-003: Replay/Reality Gap Verification
**Priority:** MEDIUM — validates Elo replay integrity
**What:** Verify `unified_games` data hasn't been retroactively corrected since bets were placed. Compare `loaded_at` timestamps against bet placement dates.
**Why:** If game data was backfilled or corrected after betting decisions, the Elo replay uses "future knowledge" the production bot didn't have — a form of look-ahead bias that invalidates the backfill.
**Where to start:** SQL query comparing `unified_games.loaded_at` against `placed_bets.placed_date` for games used in Elo calculations.
**Depends on:** Nothing — can be a preliminary check
**Added:** 2026-03-30 (eng review, outside voice)

---

## TODO-004: CLV Tracker Test Coverage
**Priority:** MEDIUM — untested critical module
**What:** Write tests for `plugins/clv_tracker.py` (currently zero test coverage).
**Why:** CLV tracker computes values the diagnostic relies on. If calculations are wrong, qualification gates are unreliable. Only critical module with zero tests.
**Where to start:** Test `record_bet_line()`, `update_closing_line()`, `analyze_clv()`. Focus on how `closing_line_prob` is derived from market prices.
**Depends on:** TODO-001 (CLV audit) — understand semantics before testing
**Added:** 2026-03-30 (eng review)

---

## TODO-005: Dashboard Integration for Diagnostic Results
**Priority:** LOW — deferred from Phase 1
**What:** Add "Diagnostic Report" page to Streamlit dashboard showing qualification gates, per-sport analysis, Elo replay comparison.
**Why:** Makes diagnostic output persistent and accessible without re-running the script.
**Where to start:** `dashboard/dashboard_app.py` — follow existing page patterns (Financial Performance, CLV Analysis).
**Depends on:** `pnl_diagnostic.py` complete + Phase 1 results
**Added:** 2026-03-30 (eng review)

---

## TODO-006: Kalshi Order Book Depth Analysis
**Priority:** LOW — likely non-issue at current bet sizes
**What:** Analyze whether $10 max bets move Kalshi order book prices (market impact check).
**Why:** If system's own orders move thin books, CLV is self-generated. At $10 max with $1K-$50K typical OI, almost certainly negligible — but worth confirming.
**Where to start:** Compare pre-placement and post-placement prices for a sample of bets using Kalshi API order book data.
**Depends on:** Nothing
**Added:** 2026-03-30 (eng review, outside voice)

---

## TODO-007: Timing Heatmap Visualization
**Priority:** P3
**What:** Build an hour × sport colored grid (heatmap) showing ROI by time bucket and sport.
**Why:** The timing analysis produces tabular data; a heatmap makes patterns instantly visible. Could reveal sport-specific optimal betting windows (e.g., NHL fine at 5 AM, Tennis needs near-game).
**Where to start:** After `pnl_diagnostic.py` timing analysis runs, add matplotlib heatmap output. Follow existing visualization patterns in dashboard.
**Depends on:** P&L diagnostic timing analysis complete
**Added:** 2026-03-30 (CEO review)

---

## TODO-008: Kalshi-Specific Closing Line Tracking
**Priority:** P2
**What:** Capture Kalshi order book prices near market close (last 30 min before game) for precise CLV measurement. Currently using cross-bookmaker closing prices (SBR fallback).
**Why:** GPT-5.4 outside voice correctly identified that cross-bookmaker CLV measures market drift, not Kalshi execution quality. For true CLV, need Kalshi-specific closing prices.
**Where to start:** Add a DAG task that fetches Kalshi prices 30 min before each game's market close. Store in `game_odds` with bookmaker='Kalshi_close'. May require DAG schedule changes.
**Depends on:** Kalshi API stability, potentially DAG schedule refactor
**Added:** 2026-03-30 (CEO review, outside voice — GPT-5.4)

---

## TODO-009: Fill Time / Resting Duration Analysis
**Priority:** P2
**What:** Investigate whether Kalshi fill timestamps are available in the API. If so, compute resting duration (fill_time - placed_time) and analyze ROI by how long orders sat on the book.
**Why:** Adverse selection depends on resting duration, not just hours-before-game. An order placed 8hr before game that fills in 5 min has different risk than one sitting 6 hours.
**Where to start:** Check Kalshi API docs for fill timestamp fields. Inspect `bet_sync_hourly` DAG — does `_process_fill()` in `bet_tracker.py:532` capture fill timestamps? If yes, add resting duration column to timing analysis.
**Depends on:** Kalshi API documentation review
**Added:** 2026-03-30 (CEO review, outside voice — GPT-5.4)

---

## TODO-010: Bootstrap Confidence Intervals for ROI
**Priority:** P2
**What:** Add bootstrap 95% CI around each sport's ROI estimate in diagnostic output. Show [-8%, +2%] instead of just "-3%".
**Why:** Point estimates are ambiguous. CI of [-8%, +2%] means "could be profitable." CI of [-5%, -1%] means "definitely losing." Directly feeds auto-pause logic.
**Where to start:** Bootstrap infrastructure already being added for P&L significance test. Extend to produce CIs — ~5 extra lines in `pnl_diagnostic.py`.
**Depends on:** Bootstrap P&L test (in scope for diagnostic)
**Added:** 2026-03-30 (CEO review)
