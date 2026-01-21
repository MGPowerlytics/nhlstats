"""
Test script to validate that the Airflow DAG parses successfully and contains no import errors.
"""

import pytest
from airflow.models import DagBag

def test_dag_parsing():
    """Ensure that the DAG parses successfully."""
    dag_bag = DagBag(dag_folder="dags", include_examples=False)
    assert len(dag_bag.import_errors) == 0, f"DAG import errors: {dag_bag.import_errors}"
    assert len(dag_bag.dags) > 0, "No DAGs were found in the specified folder."
