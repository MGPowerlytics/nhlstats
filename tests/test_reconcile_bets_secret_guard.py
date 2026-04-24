"""Regression tests for reconcile_placed_bets secret handling."""

from pathlib import Path
from unittest.mock import patch


def test_run_reconcile_placed_bets_skips_without_kalshi_api_key(
    monkeypatch, tmp_path: Path
) -> None:
    """Reconcile should skip cleanly when Kalshi runtime secrets are absent."""
    from dags.multi_sport_betting_workflow import _run_reconcile_placed_bets

    monkeypatch.delenv("KALSHI_API_KEY_ID", raising=False)
    monkeypatch.setenv("KALSHI_PRIVATE_KEY_PATH", str(tmp_path / "kalshi.pem"))

    result = _run_reconcile_placed_bets()

    assert result["status"] == "skipped"
    assert result["reason"] == "KALSHI_API_KEY_ID environment variable is required"


def test_run_reconcile_placed_bets_accepts_legacy_kalshi_api_key_alias(
    monkeypatch,
) -> None:
    """Reconcile should proceed when only the legacy Kalshi API key env name is set."""
    from dags.multi_sport_betting_workflow import _run_reconcile_placed_bets

    monkeypatch.delenv("KALSHI_API_KEY_ID", raising=False)
    monkeypatch.setenv("KALSHI_API_KEY", "legacy-runtime-key")
    monkeypatch.setenv(
        "KALSHI_PRIVATE_KEY_PATH", "/run/secrets/kalshi_private_key.pem"
    )

    with patch(
        "dags.multi_sport_betting_workflow.Path.is_file",
        return_value=True,
    ), patch(
        "bet_reconciliation.reconcile_all",
        return_value={"status": "success"},
    ) as mock_reconcile:
        result = _run_reconcile_placed_bets()

    assert result == {"status": "success"}
    mock_reconcile.assert_called_once_with(cutoff_minutes=15)
