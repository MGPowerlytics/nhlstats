# Project Architecture

## System Overview

The Multi-Sport Betting System is a Python-based platform that uses Elo ratings to identify betting opportunities on Kalshi prediction markets. The system covers 9 sports (NBA, NHL, MLB, NFL, EPL, Tennis, NCAAB, WNCAAB, Ligue1) and runs as an Apache Airflow DAG that executes daily.

## Core Components

### 1. Unified Elo Engine
- **Location**: `plugins/elo/`
- **Purpose**: Sport-specific Elo rating implementations for win probability prediction
- **Key File**: `base_elo_rating.py` - Abstract base class defining unified interface
- **Sport Implementations**: 9 sport-specific classes inheriting from `BaseEloRating`

### 2. Data Pipeline (Airflow DAG)
- **Location**: `dags/multi_sport_betting_workflow.py`
- **Purpose**: Orchestrates daily data collection, Elo updates, and bet identification
- **Schedule**: Runs daily at 10 AM UTC
- **Key Tasks**:
  - Download game data for each sport
  - Update Elo ratings with latest results
  - Fetch Kalshi market prices
  - Identify betting opportunities (edge > threshold)
  - Generate bet recommendations

### 3. Database Layer
- **Primary Database**: PostgreSQL (production), DuckDB (development)
- **Schema**: Comprehensive schema covering games, teams, odds, bets, portfolio
- **Key Tables**: `unified_games`, `game_odds`, `placed_bets`, `portfolio_value_snapshots`
- **Data Flow**: DAG tasks populate tables; dashboard queries for visualization

### 4. Kalshi Integration
- **Location**: `plugins/kalshi_markets.py`
- **Purpose**: Interface with Kalshi prediction market API
- **Functions**: Fetch market prices, place bets, track positions
- **Authentication**: Uses `kalshkey` file with API credentials

### 5. Dashboard
- **Location**: `dashboard/dashboard_app.py`
- **Technology**: Streamlit web application
- **Purpose**: Visualize betting performance, portfolio value, and model metrics
- **Features**: Sport switching, real-time data, performance charts

### 6. Plugin System
- **Location**: `plugins/`
- **Structure**: Modular Python modules for each sport and functionality
- **Game Data**: `*_games.py` modules for each sport data collection
- **Utilities**: `db_manager.py`, `data_validation.py`, `portfolio_optimizer.py`

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Orchestration** | Apache Airflow 2.8+ | Workflow scheduling and execution |
| **Database** | PostgreSQL 14+ | Production data storage |
| **Development DB** | DuckDB | Lightweight analytics database |
| **Web Framework** | Streamlit | Interactive dashboard |
| **API Client** | Kalshi Python SDK | Prediction market integration |
| **Containerization** | Docker & Docker Compose | Environment consistency |
| **Language** | Python 3.10+ | Core implementation language |
| **Testing** | pytest | Unit and integration tests |

## Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                    Airflow DAG (Scheduler)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │Game Data    │  │Elo Updates  │  │Bet Identification   │  │
│  │Download     │  │             │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                 │                    │             │
│         ▼                 ▼                    ▼             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  Database (PostgreSQL)                  │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │ │
│  │  │Games     │  │Odds      │  │Bets & Portfolio      │  │ │
│  │  │Tables    │  │Tables    │  │Tables                │  │ │
│  │  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │ │
│  └───────┼─────────────┼───────────────────┼──────────────┘ │
│          │             │                   │                 │
│          ▼             ▼                   ▼                 │
│  ┌──────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │Kalshi API    │ │Odds APIs    │ │Streamlit Dashboard  │   │
│  │Integration   │ │(SBR, etc.)  │ │                     │   │
│  └──────────────┘ └─────────────┘ └─────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Daily Schedule** (10 AM UTC):
   - Airflow DAG triggers
   - Sport-specific game data downloaders fetch latest results
   - Elo ratings updated with new game outcomes
   - Kalshi API queried for current market prices

2. **Bet Identification**:
   - Compare Elo probabilities with market probabilities
   - Calculate edge: `edge = elo_probability - market_probability`
   - Filter for edges > threshold (typically 5%)
   - Generate bet recommendations with confidence levels

3. **Portfolio Management**:
   - Track open positions on Kalshi
   - Calculate portfolio value hourly
   - Update bet status (open, won, lost)

4. **Dashboard Updates**:
   - Streamlit app queries database for latest data
   - Visualize performance metrics, edge distribution, portfolio value

## Key Design Decisions

### 1. Unified Elo Interface
- All sport-specific Elo implementations inherit from `BaseEloRating`
- Consistent interface: `predict()`, `update()`, `get_rating()`, `expected_score()`, `get_all_ratings()`
- Enables generic code to work with any sport

### 2. Single DAG Architecture
- One DAG handles all sports vs. separate DAGs per sport
- Simplifies monitoring and reduces Airflow overhead
- Sport-specific logic encapsulated in plugins

### 3. PostgreSQL Migration
- Migrated from DuckDB for production reliability
- Better concurrency, persistence, and tooling support
- DuckDB retained for development and analytics

### 4. Modular Plugin System
- Each sport has dedicated modules for data collection and Elo logic
- Easy to add new sports by implementing standard interfaces
- Clear separation of concerns

## Directory Structure

```
├── dags/                          # Airflow DAGs
│   └── multi_sport_betting_workflow.py  # Main unified betting DAG
├── plugins/                       # Airflow plugins (Python modules)
│   ├── elo/                       # Unified Elo rating system
│   │   ├── __init__.py            # Exports all Elo classes
│   │   ├── base_elo_rating.py     # BaseEloRating abstract class
│   │   ├── nba_elo_rating.py      # NBA Elo implementation
│   │   ├── nhl_elo_rating.py      # NHL Elo implementation
│   │   ├── mlb_elo_rating.py      # MLB Elo implementation
│   │   ├── nfl_elo_rating.py      # NFL Elo implementation
│   │   ├── epl_elo_rating.py      # EPL (soccer) Elo implementation
│   │   ├── ligue1_elo_rating.py   # Ligue1 (soccer) Elo implementation
│   │   ├── ncaab_elo_rating.py    # NCAAB Elo implementation
│   │   ├── wncaab_elo_rating.py   # WNCAAB Elo implementation
│   │   └── tennis_elo_rating.py   # Tennis Elo implementation
│   ├── kalshi_markets.py          # Kalshi API integration
│   ├── *_games.py                 # Game data downloaders
│   └── *_stats.py                 # Statistics modules
├── dashboard/                     # Streamlit dashboard
│   └── dashboard_app.py           # Main dashboard application
├── data/                          # Data directory
│   └── {sport}/bets_*.json        # Daily bet recommendations
├── config/                        # Airflow configuration
├── tests/                         # Test suite
└── docs/                          # Documentation
```

## Integration Points

### External APIs
- **Kalshi**: Prediction market prices and trading
- **Sports Data APIs**: Game results and schedules
- **Odds APIs**: Market odds for edge calculation

### Internal Interfaces
- **Database**: All components read/write to PostgreSQL
- **Airflow**: DAG tasks call plugin functions
- **Dashboard**: Streamlit queries database via SQLAlchemy

## Scaling Considerations

### Current Scale
- 9 sports with historical data back to 2010+ for some sports
- ~85,000 games in unified_games table
- ~11 million Kalshi trades tracked
- Daily processing of ~100-500 new games

### Future Scaling
- Horizontal scaling: Add more sports by implementing new plugin modules
- Performance: Database indexing and query optimization
- Monitoring: Enhanced logging and alerting for pipeline failures

---

*Last Updated: 2026-01-26*
