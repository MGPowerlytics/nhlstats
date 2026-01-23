import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from plugins.db_manager import DBManager, default_db
# Note: backfill_bet_metrics will be implemented later, so this import might fail if run before implementation
# But for TDD we write the test first.
from plugins.bet_tracker import sync_bets_to_database, create_bets_table

# We'll expect this to become available
try:
    from plugins.bet_tracker import backfill_bet_metrics
except ImportError:
    backfill_bet_metrics = None

# Data fixtures
RECOMMENDATION_DATA = {
    'bet_id': 'TEST_REC_1',
    'sport': 'TENNIS',
    'recommendation_date': '2026-01-22',
    'ticker': 'KXATPMATCH-26JAN22-TEST',
    'home_team': 'Player A',
    'away_team': 'Player B',
    'bet_on': 'Player A',
    'elo_prob': 0.75,
    'market_prob': 0.55,
    'edge': 0.20,
    'confidence': 'HIGH'
}

FILL_DATA = {
    'ticker': 'KXATPMATCH-26JAN22-TEST',
    'trade_id': 'TRADE_1',
    'side': 'yes',
    'count': 10,
    'yes_price': 55,
    'created_time': '2026-01-22T12:00:00Z'
}

@pytest.fixture
def setup_recommendations(mock_db_manager_to_test_engine):
    """Setup bet_recommendations table and insert test data."""
    db = DBManager()
    try:
        db.execute("DROP TABLE IF EXISTS bet_recommendations CASCADE")
    except:
        pass

    db.execute("""
        CREATE TABLE bet_recommendations (
            bet_id VARCHAR PRIMARY KEY,
            sport VARCHAR,
            recommendation_date DATE,
            home_team VARCHAR,
            away_team VARCHAR,
            bet_on VARCHAR,
            elo_prob DOUBLE PRECISION,
            market_prob DOUBLE PRECISION,
            edge DOUBLE PRECISION,
            confidence VARCHAR,
            ticker VARCHAR,
            yes_ask DOUBLE PRECISION,
            no_ask DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test recommendation
    db.execute("""
        INSERT INTO bet_recommendations (
            bet_id, sport, recommendation_date, ticker,
            elo_prob, market_prob, edge, confidence
        ) VALUES (
            :bet_id, :sport, :recommendation_date, :ticker,
            :elo_prob, :market_prob, :edge, :confidence
        )
    """, RECOMMENDATION_DATA)
    return db

@pytest.fixture
def mock_kalshi_client():
    with patch('plugins.bet_tracker.KalshiBetting') as MockClass:
        client = MockClass.return_value
        client.get_market_details.return_value = {
            'status': 'active', 'result': None, 'close_time': '2026-01-23T00:00:00Z', 'title': 'Test Market'
        }
        client._get.return_value = {'fills': []} # Default empty
        yield client

def test_sync_new_bets_captures_metrics(setup_recommendations, mock_kalshi_client):
    """Test that sync_bets_to_database captures metrics from recommendations for NEW bets."""
    # Mock load_fills to return our fill
    with patch('plugins.bet_tracker.load_fills_from_kalshi', return_value=[FILL_DATA]):
        with patch('plugins.bet_tracker._read_kalshkey', return_value=('key', 'path')):
            sync_bets_to_database()

    # Verify metrics were captured
    db = DBManager()
    df = db.fetch_df("SELECT * FROM placed_bets WHERE ticker = 'KXATPMATCH-26JAN22-TEST'")

    assert len(df) == 1
    row = df.iloc[0]
    # Check close enough floats
    assert abs(row['elo_prob'] - 0.75) < 0.001
    assert abs(row['market_prob'] - 0.55) < 0.001
    assert abs(row['edge'] - 0.20) < 0.001
    assert row['confidence'] == 'HIGH'

def test_backfill_existing_bets(setup_recommendations):
    """Test that backfill_bet_metrics updates existing bets with NULL metrics."""
    if not backfill_bet_metrics:
        pytest.fail("backfill_bet_metrics function not implemented yet")

    db = DBManager()
    create_bets_table(db)

    # Insert bet with NULL metrics
    # Need minimal cols to satisfy not nulls if any (bet_tracker uses only PK constraints mostly)
    db.execute("""
        INSERT INTO placed_bets (
            bet_id, sport, placed_date, ticker,
            elo_prob, market_prob, edge, confidence
        ) VALUES (
            'EXISTING_BET', 'TENNIS', '2026-01-22', 'KXATPMATCH-26JAN22-TEST',
            NULL, NULL, NULL, NULL
        )
    """)

    # Run backfill
    backfill_bet_metrics(db)

    # Verify update
    df = db.fetch_df("SELECT * FROM placed_bets WHERE bet_id = 'EXISTING_BET'")
    row = df.iloc[0]
    assert abs(row['elo_prob'] - 0.75) < 0.001
    assert abs(row['edge'] - 0.20) < 0.001

def test_metrics_not_overwritten(setup_recommendations):
    """Test that valid existing metrics are NOT overwritten by backfill."""
    if not backfill_bet_metrics:
        pytest.fail("backfill_bet_metrics function not implemented yet")

    db = DBManager()
    create_bets_table(db)

    # Insert bet with EXISTING valid metrics (different from rec)
    db.execute("""
        INSERT INTO placed_bets (
            bet_id, sport, placed_date, ticker,
            elo_prob, market_prob, edge, confidence
        ) VALUES (
            'VALID_BET', 'TENNIS', '2026-01-22', 'KXATPMATCH-26JAN22-TEST',
            0.99, 0.10, 0.89, 'SUPER_HIGH'
        )
    """)

    backfill_bet_metrics(db)

    df = db.fetch_df("SELECT * FROM placed_bets WHERE bet_id = 'VALID_BET'")
    row = df.iloc[0]
    assert abs(row['elo_prob'] - 0.99) < 0.001
    assert row['confidence'] == 'SUPER_HIGH'

def test_no_match_leaves_null(setup_recommendations, mock_kalshi_client):
    """Test that bets without matching recommendation remain NULL."""
    unmatched_fill = FILL_DATA.copy()
    unmatched_fill['ticker'] = 'KX-NO-MATCH'

    with patch('plugins.bet_tracker.load_fills_from_kalshi', return_value=[unmatched_fill]):
        with patch('plugins.bet_tracker._read_kalshkey', return_value=('key', 'path')):
            sync_bets_to_database()

    db = DBManager()
    df = db.fetch_df("SELECT * FROM placed_bets WHERE ticker = 'KX-NO-MATCH'")
    assert len(df) == 1
    # Check for NaN (pandas) or None
    assert pd.isna(df.iloc[0]['elo_prob']) or df.iloc[0]['elo_prob'] is None
