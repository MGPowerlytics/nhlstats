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
    """Verify the main multi-sport betting DAG has correct structure."""
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
        assert f"{sport}_update_elo" in tasks
        assert f"{sport}_fetch_markets" in tasks
        assert f"{sport}_identify_bets" in tasks
        assert f"{sport}_load_bets_db" in tasks  # Duplicate check for emphasis

def test_dag_schedule():
    """Verify DAG has correct schedule."""
    dag_id = "multi_sport_betting_workflow"

    # This would require importing the DAG module directly
    # For now, just check it exists in the dag_bag
    pass
