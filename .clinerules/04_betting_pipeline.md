# Betting Pipeline

## Overview

The Multi-Sport Betting Pipeline is an Apache Airflow DAG that orchestrates daily data collection, Elo rating updates, market price fetching, and bet identification across 9 sports. The pipeline runs daily at 10 AM UTC (5 AM Eastern) and follows a unified workflow for all sports.

## DAG Structure

### Main DAG File
**Location**: `dags/multi_sport_betting_workflow.py`

**Schedule**: Daily at 10 AM UTC (5 AM Eastern)

**Sports Covered**: NBA, NHL, MLB, NFL, EPL, Tennis, NCAAB, WNCAAB, Ligue1

### Task Flow
```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Multi-Sport Betting Workflow                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  For each sport:                                                        │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐ │
│  │ Download    │ → │ Load to DB  │ → │ Update Elo  │ → │ Fetch       │ │
│  │ Games       │   │             │   │ Ratings     │   │ Markets     │ │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘ │
│                                          │                              │
│                                          ▼                              │
│                                   ┌─────────────┐                       │
│                                   │ Identify    │                       │
│                                   │ Good Bets   │                       │
│                                   └─────────────┘                       │
│                                          │                              │
│                                          ▼                              │
│                                   ┌─────────────┐                       │
│                                   │ Load Bets   │                       │
│                                   │ to DB       │                       │
│                                   └─────────────┘                       │
│                                                                         │
│  After all sports:                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Portfolio-Optimized Betting (Unified across all sports)        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                          │                              │
│                                          ▼                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Update CLV Data (Closed markets)                              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                          │                              │
│                                          ▼                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Send Daily Summary (SMS)                                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Sport Configurations

### Threshold Optimization
Each sport has optimized Elo thresholds based on historical lift/gain analysis:

| Sport | Elo Threshold | Lift Analysis | Notes |
|-------|---------------|---------------|-------|
| **NBA** | 0.73 | 1.39x lift in top 20% | Focuses on highest lift deciles |
| **NHL** | 0.66 | 1.28x lift at 66% | Lowered from 0.77 (too conservative) |
| **MLB** | 0.67 | 1.18x lift in top deciles | Consistent lift in high deciles |
| **NFL** | 0.70 | 1.34x lift in top deciles | Strong discrimination |
| **EPL** | 0.45 | 3-way markets | Draw probability included |
| **Ligue1** | 0.45 | 3-way markets | Similar to EPL |
| **NCAAB** | 0.72 | Aligns with NBA pattern | Optimized from 0.65 |
| **WNCAAB** | 0.72 | Aligns with basketball | Same as NCAAB |
| **Tennis** | 0.60 | Binary markets | Surface adjustments |

### Team Mappings
Each sport has team abbreviation mappings for Kalshi market ticker generation:

```python
SPORTS_CONFIG = {
    "nba": {
        "elo_module": "elo",
        "games_module": "nba_games",
        "kalshi_function": "fetch_nba_markets",
        "elo_threshold": 0.73,
        "series_ticker": "KXNBAGAME",
        "team_mapping": {
            "ATL": "Hawks",
            "BOS": "Celtics",
            # ... full mapping
        }
    },
    # ... other sports
}
```

## Core Tasks

### 1. Download Games
**Task**: `{sport}_download_games`

**Purpose**: Download latest game data from external APIs

**Implementation**: Sport-specific downloaders in `plugins/*_games.py`

```python
def download_games(sport, **context):
    if sport == "nba":
        from nba_games import NBAGames
        games = NBAGames(date_folder=date_str)
        games.download_games_for_date(date_str)
    # ... other sports
```

### 2. Load to Database
**Task**: `{sport}_load_db`

**Purpose**: Load downloaded games into PostgreSQL

**Implementation**: Uses `db_loader.py` with unified interface

```python
def load_data_to_db(sport, **context):
    from db_loader import NHLDatabaseLoader
    with NHLDatabaseLoader() as loader:
        count = loader.load_date(date_str)
```

### 3. Update Elo Ratings
**Task**: `{sport}_update_elo`

**Purpose**: Calculate current Elo ratings for the sport

**Implementation**: Sport-specific Elo classes from `plugins/elo/`

```python
def update_elo_ratings(sport, **context):
    from elo import get_elo_class
    EloClass = get_elo_class(sport)
    elo = EloClass(k_factor=20, home_advantage=100)
    # ... update with historical games
```

### 4. Fetch Prediction Markets
**Task**: `{sport}_fetch_markets`

**Purpose**: Fetch current Kalshi market prices

**Implementation**: Sport-specific market fetchers in `kalshi_markets.py`

```python
def fetch_prediction_markets(sport, **context):
    from kalshi_markets import fetch_nba_markets, fetch_nhl_markets, ...
    fetch_function = {
        "nba": fetch_nba_markets,
        "nhl": fetch_nhl_markets,
        # ... other sports
    }[sport]
    markets = fetch_function(date_str)
```

### 5. Identify Good Bets
**Task**: `{sport}_identify_bets`

**Purpose**: Compare Elo probabilities with market prices to find edges

**Implementation**: Uses `OddsComparator` from `odds_comparator.py`

```python
def identify_good_bets(sport, **context):
    from odds_comparator import OddsComparator
    comparator = OddsComparator()
    good_bets = comparator.find_opportunities(
        sport=sport,
        elo_ratings=elo_ratings,
        elo_system=elo_system,
        threshold=elo_threshold,
        min_edge=0.05,
        use_sharp_confirmation=(sport in ["tennis", "nhl", "ligue1"])
    )
```

### 6. Load Bets to Database
**Task**: `{sport}_load_bets_db`

**Purpose**: Save bet recommendations to PostgreSQL

**Implementation**: Uses `BetLoader` from `bet_loader.py`

```python
def load_bets_to_db(sport, **context):
    from bet_loader import BetLoader
    loader = BetLoader()
    count = loader.load_bets_for_date(sport, date_str)
```

## Portfolio-Optimized Betting

### Unified Betting Task
**Task**: `portfolio_optimized_betting`

**Purpose**: Place portfolio-optimized bets across all sports using Kelly Criterion

**Key Features**:
- Unified portfolio management across all sports
- Kelly Criterion with conservative fraction (0.20)
- Risk management with daily limits
- Diversification across sports and games

```python
def place_portfolio_optimized_bets(**context):
    from portfolio_betting import PortfolioBettingManager
    from kalshi_betting import KalshiBetting

    manager = PortfolioBettingManager(
        kalshi_client=kalshi_client,
        max_daily_risk_pct=0.25,      # 25% max daily risk
        kelly_fraction=0.20,          # Conservative Kelly
        min_bet_size=2.0,
        max_bet_size=10.0,            # Lower max for diversification
        max_single_bet_pct=0.03,      # Lower single bet limit
        min_edge=0.05,
        min_confidence=0.68,
        dry_run=False                  # LIVE BETTING
    )
```

### Risk Management Parameters
| Parameter | Value | Purpose |
|-----------|-------|---------|
| Max Daily Risk | 25% | Total risk exposure per day |
| Kelly Fraction | 0.20 | Conservative fraction of full Kelly |
| Min Bet Size | $2.00 | Minimum bet amount |
| Max Bet Size | $10.00 | Maximum bet amount |
| Max Single Bet | 3% | Maximum of portfolio per bet |
| Min Edge | 5% | Minimum edge required |
| Min Confidence | 68% | Minimum model confidence |

## CLV Data Updates

### Task: `update_clv_data`
**Purpose**: Update Closing Line Value (CLV) data for closed markets

**Implementation**: Uses `update_clv_data.py` module

```python
def update_clv_wrapper(**context):
    from update_clv_data import update_clv_for_closed_markets
    return update_clv_for_closed_markets()
```

**Key Functions**:
- Track price movements before market close
- Calculate CLV for settled bets
- Update `kalshi_decision_prices` table

## Daily Summary

### Task: `send_daily_summary`
**Purpose**: Send SMS summary with balance, winnings, and today's bets

**Implementation**: Uses Verizon SMS gateway via Gmail SMTP

```python
def send_daily_summary(**context):
    # Get current balance and portfolio value
    balance, portfolio_value = client.get_balance()

    # Calculate yesterday's winnings
    winnings = portfolio_value - yesterday_portfolio

    # Send SMS in multiple messages (160 char limit)
    send_sms("7244959219", "Daily Summary", message_body)
```

**SMS Content**:
1. **Message 1**: Summary stats (balance, portfolio, P/L)
2. **Message 2**: Bet summary (number placed, total amount, top bets)
3. **Message 3**: Additional bets or available balance

## Data Flow

### 1. Game Data Collection
```
External APIs → Sport-specific downloaders → PostgreSQL tables
```

### 2. Elo Rating Updates
```
PostgreSQL games → Elo engine → Updated ratings (CSV + XCom)
```

### 3. Market Price Fetching
```
Kalshi API → Market prices → JSON files + XCom
```

### 4. Bet Identification
```
Elo ratings + Market prices → Edge calculation → Bet recommendations
```

### 5. Portfolio Optimization
```
All bet recommendations → Kelly Criterion → Portfolio-optimized bets
```

### 6. Bet Execution
```
Portfolio bets → Kalshi API → Placed bets → PostgreSQL
```

### 7. CLV Tracking
```
Closed markets → Price analysis → CLV metrics → PostgreSQL
```

## Error Handling

### Retry Logic
- **Retries**: 1 retry on failure
- **Retry Delay**: 5 minutes
- **Email on Failure**: Yes (to SMS gateway)

### Common Issues
1. **API Rate Limits**: Implemented exponential backoff in API clients
2. **Missing Data**: Skip sports with no games/markets
3. **Network Issues**: Retry logic with increasing delays
4. **Kalshi Authentication**: Credential validation at startup

## Monitoring

### Airflow Metrics
- **DAG Runs**: Daily success/failure tracking
- **Task Duration**: Performance monitoring
- **XCom Data**: Verify data flow between tasks

### Custom Monitoring
- **Balance Tracking**: Daily portfolio value snapshots
- **Bet Performance**: Win/loss tracking in `placed_bets` table
- **Edge Distribution**: Historical edge analysis in dashboard

## Extending the Pipeline

### Adding a New Sport
1. **Create Game Downloader**: `plugins/{sport}_games.py`
2. **Create Elo Implementation**: `plugins/elo/{sport}_elo_rating.py`
3. **Create Market Fetcher**: Add to `kalshi_markets.py`
4. **Update SPORTS_CONFIG**: Add sport configuration in DAG
5. **Update Team Mapping**: Add abbreviation mappings if needed

### Modifying Thresholds
1. **Analyze Historical Data**: Use lift/gain analysis
2. **Test New Threshold**: Backtest with historical games
3. **Update SPORTS_CONFIG**: Modify `elo_threshold` value
4. **Monitor Performance**: Track new threshold in dashboard

## Performance Considerations

### Parallel Execution
- Sports run in parallel where possible
- Database operations optimized with indexes
- API calls with rate limiting and caching

### Memory Management
- Elo ratings stored in memory during pipeline execution
- Large datasets processed in chunks
- Database connections pooled and reused

### Scalability
- **Current**: 9 sports, ~100 daily games
- **Future**: Can add more sports with same architecture
- **Database**: PostgreSQL handles concurrent writes from multiple sports

---

*Last Updated: 2026-01-26*
