"""
Comprehensive integrity tests for Airflow DAGs.
Validates structure, dependencies, and configuration.
"""
import pytest
from airflow.models import DagBag

@pytest.fixture(scope="module")
def dag_bag():
    return DagBag(dag_folder="dags", include_examples=False)

def test_no_import_errors(dag_bag):
    """Verify that all DAGs can be imported without errors."""
    assert len(dag_bag.import_errors) == 0, f"DAG import errors: {dag_bag.import_errors}"

def test_multi_sport_betting_workflow_structure(dag_bag):
    """Validate specific structure of the main betting workflow DAG."""
    dag_id = "multi_sport_betting_workflow"
    # Access from dags dict to avoid DB query
    dag = dag_bag.dags.get(dag_id)
    assert dag is not None, f"DAG {dag_id} not found"

    # Verify required tasks exist for all enabled sports
    # Including newly enabled NHL and Ligue 1
    sports = ["nba", "nhl", "mlb", "nfl", "epl", "tennis", "ncaab", "wncaab", "ligue1"]
    tasks = dag.task_ids

            for sport in sports:
                assert f"{sport}_download_games" in tasks
                assert f"{sport}_load_bets_db" in tasks
                assert f"{sport}_update_elo" in tasks        assert f"{sport}_fetch_markets" in tasks
        assert f"{sport}_identify_bets" in tasks
        assert f"{sport}_load_bets_db" in tasks

    # Verify betting tasks exist for enabled betting sports
    betting_sports = ["nba", "nhl", "ncaab", "wncaab", "tennis", "ligue1"]
    for sport in betting_sports:
        assert f"{sport}_place_bets" in tasks

    # Verify unified portfolio task
    assert "portfolio_optimized_betting" in tasks
    assert "send_daily_summary" in tasks

def test_dag_tags(dag_bag):
    """Ensure proper tagging for filtering."""
    # Access from dags dict to avoid DB query
    dag = dag_bag.dags.get("multi_sport_betting_workflow")
    assert dag is not None
    assert "betting" in dag.tags
    assert "multi-sport" in dag.tags
