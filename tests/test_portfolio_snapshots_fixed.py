from unittest.mock import patch
import pandas as pd


def test_load_snapshots_since():
    """Test loading portfolio snapshots with mocked database."""
    # Mock the database response
    mock_data = pd.DataFrame(
        {
            "snapshot_hour_utc": ["2026-01-22 12:00:00"],
            "balance_dollars": [73.35],
            "portfolio_value_dollars": [80.69],
        }
    )

    with patch("plugins.portfolio_snapshots.default_db") as mock_db:
        mock_db.fetch_df.return_value = mock_data
        mock_db.table_exists.return_value = True

        from plugins.portfolio_snapshots import load_snapshots_since

        # Pass db=mock_db explicitly because default arg is bound at definition time
        result = load_snapshots_since(
            since_utc=pd.to_datetime("2026-01-20"), db=mock_db
        )

        # Verify result matches mock data
        assert len(result) == 1
        assert result.iloc[0]["balance_dollars"] == 73.35
    assert len(result) == 1
    assert result.iloc[0]["balance_dollars"] == 73.35
    print("Portfolio snapshots test passed with mock")
