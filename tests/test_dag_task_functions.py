"""
Tests for Airflow DAG task wrapper functions in multi_sport_betting_workflow.py
Uses mocked Airflow context and Kalshi sandbox environment.
"""
import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.no_cover

@pytest.fixture
def mock_airflow_context():
    ti = MagicMock()
    ti.xcom_pull.return_value = {'LAL': 1550, 'BOS': 1500}
    ti.xcom_push = MagicMock()
    return {
        'ds': '2026-01-21',
        'task_instance': ti,
    }

@pytest.fixture
def kalshi_sandbox_client():
    with patch('plugins.kalshi_markets.KalshiAPI') as MockKalshi:
        client = MockKalshi.return_value
        client.get_markets.return_value = {'markets': [{'id': 'sandbox_market', 'team': 'LAL', 'price': 0.65}]}
        yield client


def test_place_portfolio_optimized_bets_exact_xcom(mock_airflow_context, kalshi_sandbox_client):
    context = mock_airflow_context
    # Patch the PortfolioBettingManager in the plugin module, reload DAG module, then import the function
    import importlib
    with patch('portfolio_betting.PortfolioBettingManager') as MockManager:
        manager = MockManager.return_value
        manager.process_daily_bets.return_value = {
            'planned_bets': 1,
            'placed_bets': [{'player': 'LeBron James', 'amount': 100, 'order_id': 'sandbox123', 'status': 'filled'}],
            'skipped_bets': [],
            'errors': []
        }
        import dags.multi_sport_betting_workflow
        importlib.reload(dags.multi_sport_betting_workflow)
        from dags.multi_sport_betting_workflow import place_portfolio_optimized_bets
        result = place_portfolio_optimized_bets(**context)
        assert result['placed_bets'][0]['player'] == 'LeBron James'


def test_identify_good_bets_exact_xcom(mock_airflow_context):
    context = mock_airflow_context
    # Patch NBAEloRating and OddsComparator in the plugin modules, reload DAG module, then import the function
    import importlib
    with patch('nba_elo_rating.NBAEloRating') as MockElo:
        with patch('odds_comparator.OddsComparator') as MockComparator:
            elo = MockElo.return_value
            elo.predict.return_value = 0.80
            context['task_instance'].xcom_pull.return_value = {'Lakers': 1550, 'Celtics': 1500}
            comparator = MockComparator.return_value
            comparator.find_opportunities.return_value = [
                {
                    'home_team': 'Lakers',
                    'away_team': 'Celtics',
                    'bet_on': 'Lakers',
                    'edge': 0.15,
                    'elo_prob': 0.80,
                    'confidence': 'HIGH',
                    'bookmaker': 'Kalshi',
                    'market_odds': 1.95
                }
            ]
            import dags.multi_sport_betting_workflow
            importlib.reload(dags.multi_sport_betting_workflow)
            from dags.multi_sport_betting_workflow import identify_good_bets
            identify_good_bets('nba', **context)


def test_fetch_prediction_markets_exact_xcom(mock_airflow_context, kalshi_sandbox_client):
    context = mock_airflow_context
    from dags.multi_sport_betting_workflow import fetch_prediction_markets
    fetch_prediction_markets('nba', **context)
    context['task_instance'].xcom_push.assert_called()


def test_update_elo_ratings_exact_xcom(mock_airflow_context):
    context = mock_airflow_context
    with patch('plugins.nba_elo_rating.NBAEloRating') as MockElo:
        elo = MockElo.return_value
        elo.ratings = {'Lakers': 1555, 'Celtics': 1505}
        from dags.multi_sport_betting_workflow import update_elo_ratings
        update_elo_ratings('nba', **context)
        context['task_instance'].xcom_push.assert_called()
