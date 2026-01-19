"""
Pytest configuration for nhlstats tests.
Sets up paths and fixtures for testing.
"""
import sys
from pathlib import Path

# Add plugins directory to path for imports
plugins_dir = Path(__file__).parent.parent / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))
