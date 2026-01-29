# Relative Import Failure in Elo Plugin Subdirectory

## Context
Airflow plugin manager fails to import plugins located in the `elo/` subdirectory (`/opt/airflow/plugins/elo/`). The error indicates `attempted relative import with no known parent package`. This affects all Elo rating modules (`nba_elo_rating.py`, `nfl_elo_rating.py`, etc.) and the `__init__.py` within the `elo/` directory.

### Error Logs
```
{"timestamp":"2026-01-25T13:49:49.450096Z","level":"error","event":"Failed to import plugin /opt/airflow/plugins/elo/mlb_elo_rating.py","logger":"airflow.plugins_manager","filename":"plugins_manager.py","lineno":298,"error_detail":[{"exc_type":"ImportError","exc_value":"attempted relative import with no known parent package","exc_notes":[],"syntax_error":null,"is_cause":false,"frames":[{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/plugins_manager.py","lineno":291,"name":"load_plugins_from_plugin_directory"},{"filename":"<frozen importlib._bootstrap_external>","lineno":999,"name":"exec_module"},{"filename":"<frozen importlib._bootstrap>","lineno":488,"name":"_call_with_frames_removed"},{"filename":"/opt/airflow/plugins/elo/mlb_elo_rating.py","lineno":8,"name":"<module>"}],"is_group":false,"exceptions":[]}]}
```

Similar errors for `wncaab_elo_rating.py`, `__init__.py`, `tennis_elo_rating.py`, `nba_elo_rating.py`, `nfl_elo_rating.py`, `ncaab_elo_rating.py`, `ligue1_elo_rating.py`, `epl_elo_rating.py`, `nhl_elo_rating.py`.

### Root Cause
The plugin manager loads each plugin file individually, treating the plugin directory as a flat list of modules. When a plugin file contains relative imports (e.g., `from .base_elo_rating import BaseEloRating`), the Python interpreter cannot resolve the parent package because the file is not being executed as part of a package.

The `elo/` directory is a subpackage under `plugins`, but the plugin manager may not add `plugins` to `sys.path` as a package root, causing relative imports to fail.

Additionally, the `__init__.py` file in `elo/` may also contain relative imports that fail.

## Viewing Instructions
1. **Check the import statements** in the affected files:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 grep -n "from \." /opt/airflow/plugins/elo/*.py
   ```
2. **Examine the plugin manager's sys.path** by adding a debug print in `plugins_manager.py` or checking the logs for `sys.path` entries.
3. **Test import manually** from the plugin directory:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 cd /opt/airflow/plugins && python -c "import sys; sys.path.insert(0, '.'); from elo.nba_elo_rating import NBAEloRating; print('success')"
   ```
4. **Verify package structure**:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 ls -la /opt/airflow/plugins/elo/
   ```

## Possible Solutions

### 1. Convert relative imports to absolute imports
Change imports like `from .base_elo_rating import BaseEloRating` to `from plugins.elo.base_elo_rating import BaseEloRating`. This ensures the import works regardless of how the module is loaded.

**Pros**: Simple, works with Airflow plugin manager.
**Cons**: Requires modifying multiple files.

### 2. Ensure `plugins` is a proper Python package
Add an `__init__.py` file in `/opt/airflow/plugins/` (if not present) and ensure `plugins` is in `sys.path`. The plugin manager already adds the plugin directory to `sys.path`, but the subpackage `elo` may not be recognized.

### 3. Modify plugin loading to treat subdirectories as packages
Airflow's plugin manager may need configuration to treat subdirectories as packages. This can be done by setting `PLUGINS_FOLDER` or adjusting the plugin discovery logic.

### 4. Use `importlib` to dynamically import
Modify the plugin files to use `importlib.import_module` for relative imports, but this is complex.

### 5. Restructure the plugin directory
Move all Elo rating files out of the `elo/` subdirectory and into the main `plugins/` directory, flattening the structure. This eliminates relative import issues.

### 6. Add `__init__.py` with proper exports
Ensure `elo/__init__.py` does not contain relative imports. Instead, use absolute imports or re-export after importing.

## Recommended Approach
Given the project's current structure, the simplest fix is to convert relative imports to absolute imports within the `elo/` subdirectory.

**Steps**:
1. For each `*_elo_rating.py` file, replace `from .base_elo_rating import BaseEloRating` with `from plugins.elo.base_elo_rating import BaseEloRating`.
2. Similarly update any other relative imports (e.g., `from . import some_module`).
3. Ensure `plugins/__init__.py` exists (even if empty).
4. Restart Airflow containers after changes.

## Expected Outcome
After fixing the relative imports, the plugin manager should successfully import all Elo rating modules, and tasks like `nfl_update_elo` will no longer fail with `ImportError: cannot import name 'calculate_current_elo_ratings'`.

## Additional Notes
- The same issue may affect other subdirectories under `plugins/` (e.g., `data/`, `elo/`).
- Consider adding a test to verify plugin imports in the CI/CD pipeline.
- After making changes, run `python -m pytest tests/test_unified_elo_interface.py` to ensure Elo classes still work correctly.
