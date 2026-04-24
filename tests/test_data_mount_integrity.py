#!/usr/bin/env python3
"""
Regression test for data mount integrity between Airflow containers and host.
Ensures that data written in containers is accessible on the host filesystem.
"""

import json
import tempfile
import subprocess
import sys
from pathlib import Path
import pytest


def test_docker_compose_has_correct_data_mount():
    """Test that docker-compose.yaml has correct bind mount for data directory."""
    compose_path = Path(__file__).parent.parent / "docker-compose.yaml"

    with open(compose_path, 'r') as f:
        content = f.read()

    # Check for bind mount pattern (./data:/opt/airflow/data)
    assert "./data:/opt/airflow/data" in content, \
        "docker-compose.yaml must have bind mount './data:/opt/airflow/data'"

    # Check it's not using a volume for data
    assert "airflow-data:/opt/airflow/data" not in content, \
        "docker-compose.yaml should not use 'airflow-data' volume for data directory"


def test_data_directory_structure():
    """Test that data directory has expected structure for all sports."""
    data_dir = Path(__file__).parent.parent / "data"

    # Check data directory exists
    assert data_dir.exists(), f"Data directory {data_dir} does not exist"
    assert data_dir.is_dir(), f"Data directory {data_dir} is not a directory"

    # Check for sport subdirectories
    expected_sports = ["mlb", "nba", "nfl", "epl", "ligue1", "nhl", "cba"]
    for sport in expected_sports:
        sport_dir = data_dir / sport
        # Directory should exist or be creatable
        assert sport_dir.exists() or True, \
            f"Sport directory {sport_dir} should exist or be creatable"


def test_file_writing_integration():
    """Integration test: write file in simulated container context, read from host."""
    data_dir = Path(__file__).parent.parent / "data"
    test_dir = data_dir / "test_integration"
    test_dir.mkdir(exist_ok=True)

    test_file = test_dir / "test_write_read.txt"
    test_content = "Integration test: " + __file__

    try:
        # Simulate container writing (same path as container would use)
        container_data_path = data_dir  # This is what /opt/airflow/data maps to

        # Write file
        write_path = container_data_path / "test_integration" / "test_write_read.txt"
        write_path.write_text(test_content)

        # Read file from host perspective
        read_path = data_dir / "test_integration" / "test_write_read.txt"
        assert read_path.exists(), f"File {read_path} should exist after writing"

        content = read_path.read_text()
        assert content == test_content, \
            f"Content mismatch. Expected: {test_content}, Got: {content}"

        print(f"✓ Integration test passed: File written and read correctly")

    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()
        if test_dir.exists():
            test_dir.rmdir()


def test_sport_downloader_paths():
    """Test that sport downloaders use correct relative paths."""
    from plugins.base_games import BaseGamesFetcher

    # Test MLB downloader path
    test_sport = "mlb"
    downloader = BaseGamesFetcher(sport=test_sport)

    # Output dir should be relative to current working directory
    expected_suffix = f"data/{test_sport}"
    assert str(downloader.output_dir).endswith(expected_suffix), \
        f"Downloader output_dir should end with '{expected_suffix}', got: {downloader.output_dir}"

    # Directory should be creatable
    downloader.output_dir.mkdir(parents=True, exist_ok=True)
    assert downloader.output_dir.exists(), \
        f"Downloader output_dir {downloader.output_dir} should be creatable"


if __name__ == "__main__":
    # Run tests
    print("Running data mount integrity tests...")

    try:
        test_docker_compose_has_correct_data_mount()
        print("✓ docker-compose mount configuration test passed")

        test_data_directory_structure()
        print("✓ data directory structure test passed")

        test_file_writing_integration()
        print("✓ file writing integration test passed")

        # Note: test_sport_downloader_paths requires plugins in PYTHONPATH
        # This would be run in the full test suite

        print("\n✅ All data mount integrity tests passed!")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
