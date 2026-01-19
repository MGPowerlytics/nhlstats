# Changelog

All notable changes to this project are documented in this file.

## 2026-01-19
- Added Markov Momentum overlay (`plugins/markov_momentum.py`) to provide a lightweight Markov-chain-based recent-form adjustment on top of Elo.
- Extended lift/gain analysis to support arbitrary probability columns and to compute `elo_markov_prob` (`plugins/lift_gain_analysis.py`).
- Added a current-season-only comparison runner for NBA/NHL Elo vs Elo+Markov (`plugins/compare_elo_markov_current_season.py`).
