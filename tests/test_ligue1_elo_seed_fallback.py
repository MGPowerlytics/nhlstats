"""Regression tests for Ligue 1 Elo seed loading."""

from types import SimpleNamespace


def test_load_ligue1_ratings_from_csv_missing_file(monkeypatch, tmp_path):
    """Missing Ligue 1 seed file should not fail the DAG task."""
    from dags.multi_sport_betting_workflow import _load_ligue1_ratings_from_csv

    monkeypatch.chdir(tmp_path)
    elo = SimpleNamespace(ratings={})

    _load_ligue1_ratings_from_csv(elo)

    assert elo.ratings == {}
