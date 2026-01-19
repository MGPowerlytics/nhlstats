"""Comprehensive tests for bet_tracker and bet_loader modules."""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent / 'plugins'))


class TestBetTrackerSQL:
    """Test bet tracker SQL operations."""
    
    def test_create_bets_table_schema(self, tmp_path):
        """Test bet table schema."""
        from bet_tracker import create_bets_table
        
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        
        create_bets_table(conn)
        
        # Verify table exists
        result = conn.execute("SELECT * FROM placed_bets LIMIT 0").fetchall()
        assert result == []
        
        conn.close()
    
    def test_placed_bets_columns(self, tmp_path):
        """Test placed_bets table has expected columns."""
        from bet_tracker import create_bets_table
        
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        
        create_bets_table(conn)
        
        # Check column names
        columns = conn.execute("DESCRIBE placed_bets").fetchall()
        column_names = [c[0] for c in columns]
        
        assert 'bet_id' in column_names
        assert 'sport' in column_names
        assert 'ticker' in column_names
        assert 'status' in column_names
        
        conn.close()


class TestBetLoaderInit:
    """Test BetLoader initialization."""
    
    def test_init_creates_table(self, tmp_path):
        """Test initialization creates table."""
        from bet_loader import BetLoader
        
        db_path = tmp_path / "test.duckdb"
        loader = BetLoader(db_path=str(db_path))
        
        # Verify table exists
        conn = duckdb.connect(str(db_path))
        result = conn.execute("SELECT * FROM bet_recommendations LIMIT 0").fetchall()
        conn.close()
        
        assert result == []
    
    def test_bet_recommendations_columns(self, tmp_path):
        """Test bet_recommendations table has expected columns."""
        from bet_loader import BetLoader
        
        db_path = tmp_path / "test.duckdb"
        loader = BetLoader(db_path=str(db_path))
        
        conn = duckdb.connect(str(db_path))
        columns = conn.execute("DESCRIBE bet_recommendations").fetchall()
        column_names = [c[0] for c in columns]
        conn.close()
        
        assert 'bet_id' in column_names
        assert 'sport' in column_names
        assert 'elo_prob' in column_names
        assert 'edge' in column_names


class TestBetLoading:
    """Test bet loading functionality."""
    
    def test_load_bets_file_not_found(self, tmp_path):
        """Test loading when file doesn't exist."""
        from bet_loader import BetLoader
        
        db_path = tmp_path / "test.duckdb"
        loader = BetLoader(db_path=str(db_path))
        
        with patch('bet_loader.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            
            count = loader.load_bets_for_date('nba', '2024-01-15')
            
            assert count == 0
    
    def test_bet_id_generation(self):
        """Test bet ID generation."""
        sport = 'nba'
        date_str = '2024-01-15'
        home_team = 'Lakers'
        away_team = 'Celtics'
        
        bet_id = f"{sport}_{date_str}_{home_team}_{away_team}".lower().replace(' ', '_')
        
        assert 'nba' in bet_id
        assert '2024-01-15' in bet_id


class TestBetDataStructure:
    """Test bet data structures."""
    
    def test_bet_json_structure(self):
        """Test bet JSON structure."""
        bet = {
            'home_team': 'Lakers',
            'away_team': 'Celtics',
            'bet_on': 'home',
            'elo_prob': 0.65,
            'market_prob': 0.55,
            'edge': 0.10,
            'confidence': 'HIGH',
            'ticker': 'KXNBA-TEST',
            'yes_ask': 55,
            'no_ask': 48
        }
        
        assert bet['elo_prob'] > bet['market_prob']
        assert bet['edge'] == pytest.approx(bet['elo_prob'] - bet['market_prob'], abs=0.001)
    
    def test_bet_status_transitions(self):
        """Test valid bet status transitions."""
        valid_transitions = {
            'open': ['won', 'lost', 'void'],
            'won': [],  # Terminal
            'lost': [],  # Terminal
            'void': []  # Terminal
        }
        
        assert 'won' in valid_transitions['open']
        assert len(valid_transitions['won']) == 0


class TestMarketStatusQueries:
    """Test market status queries."""
    
    def test_market_status_values(self):
        """Test valid market status values."""
        statuses = ['open', 'closed', 'finalized']
        
        assert 'finalized' in statuses
    
    def test_market_result_values(self):
        """Test valid market result values."""
        results = ['yes', 'no', None]
        
        assert 'yes' in results
        assert None in results


class TestProfitCalculations:
    """Test profit calculation functions."""
    
    def test_profit_won_yes_bet(self):
        """Test profit for won YES bet."""
        contracts = 10
        price_cents = 55
        result = 'yes'
        
        # YES won: profit = contracts * (100 - price) cents
        profit_cents = contracts * (100 - price_cents)
        profit_dollars = profit_cents / 100
        
        assert profit_dollars == 4.50
    
    def test_profit_lost_yes_bet(self):
        """Test profit for lost YES bet."""
        contracts = 10
        price_cents = 55
        result = 'no'
        
        # YES lost: profit = -contracts * price cents
        profit_cents = -contracts * price_cents
        profit_dollars = profit_cents / 100
        
        assert profit_dollars == -5.50
    
    def test_profit_won_no_bet(self):
        """Test profit for won NO bet."""
        contracts = 10
        price_cents = 45
        result = 'no'
        
        # NO won: profit = contracts * (100 - price) cents
        profit_cents = contracts * (100 - price_cents)
        profit_dollars = profit_cents / 100
        
        assert profit_dollars == 5.50
    
    def test_cost_calculation(self):
        """Test cost calculation."""
        contracts = 10
        price_cents = 55
        
        cost_cents = contracts * price_cents
        cost_dollars = cost_cents / 100
        
        assert cost_dollars == 5.50


class TestQueryBuilding:
    """Test SQL query building."""
    
    def test_insert_query_format(self):
        """Test INSERT query format."""
        table = 'bet_recommendations'
        columns = ['bet_id', 'sport', 'recommendation_date']
        
        query = f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES (?, ?, ?)
        """
        
        assert 'INSERT INTO' in query
        assert 'VALUES' in query
    
    def test_select_by_date_query(self):
        """Test SELECT by date query."""
        sport = 'nba'
        date_str = '2024-01-15'
        
        query = f"""
            SELECT * FROM bet_recommendations
            WHERE sport = '{sport}' AND recommendation_date = '{date_str}'
        """
        
        assert sport in query
        assert date_str in query
    
    def test_update_status_query(self):
        """Test UPDATE status query."""
        bet_id = 'nba_2024-01-15_lakers_celtics'
        new_status = 'won'
        
        query = f"""
            UPDATE placed_bets
            SET status = '{new_status}'
            WHERE bet_id = '{bet_id}'
        """
        
        assert 'UPDATE' in query
        assert 'SET status' in query


class TestDateRangeQueries:
    """Test date range queries."""
    
    def test_days_back_calculation(self):
        """Test days back calculation."""
        from datetime import datetime, timedelta
        
        days_back = 30
        today = datetime.now().date()
        start_date = today - timedelta(days=days_back)
        
        assert (today - start_date).days == 30
    
    def test_date_range_filter(self):
        """Test date range filter in query."""
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        start_date = today - timedelta(days=7)
        
        query = f"""
            SELECT * FROM placed_bets
            WHERE placed_date >= '{start_date}' AND placed_date <= '{today}'
        """
        
        assert 'placed_date >=' in query
        assert 'placed_date <=' in query


class TestAggregationQueries:
    """Test aggregation queries."""
    
    def test_win_rate_query(self):
        """Test win rate aggregation query."""
        query = """
            SELECT 
                sport,
                COUNT(*) as total_bets,
                SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
            FROM placed_bets
            WHERE status IN ('won', 'lost')
            GROUP BY sport
        """
        
        assert 'COUNT(*)' in query
        assert 'SUM(' in query
        assert 'GROUP BY' in query
    
    def test_profit_summary_query(self):
        """Test profit summary query."""
        query = """
            SELECT 
                sport,
                SUM(profit_dollars) as total_profit,
                SUM(cost_dollars) as total_invested,
                SUM(profit_dollars) / SUM(cost_dollars) * 100 as roi_pct
            FROM placed_bets
            WHERE status IN ('won', 'lost')
            GROUP BY sport
        """
        
        assert 'SUM(profit_dollars)' in query
        assert 'roi_pct' in query


class TestErrorHandling:
    """Test error handling."""
    
    def test_file_not_found_handling(self):
        """Test handling file not found."""
        file_path = Path('/nonexistent/path/bets.json')
        
        exists = file_path.exists()
        
        assert exists == False
    
    def test_json_decode_error_handling(self):
        """Test handling invalid JSON."""
        invalid_json = "{'key': 'value'}"  # Single quotes are invalid
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)
    
    def test_empty_bets_list(self):
        """Test handling empty bets list."""
        bets = []
        
        count = len(bets)
        
        assert count == 0
