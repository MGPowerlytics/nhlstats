# Missing `plugins` Module Error

## Context
Airflow plugin manager fails to import plugins that attempt to import the `plugins` module (e.g., `from plugins.db_manager import DBManager`). The error is `ModuleNotFoundError: No module named 'plugins'`. This affects plugins such as `backtest_kalshi_nhl.py`, `deposit_tracking.py`, `compare_elo_trueskill_nhl.py`, and possibly others.

### Error Logs
```
{"timestamp":"2026-01-25T13:49:48.078709Z","level":"error","event":"Failed to import plugin /opt/airflow/plugins/backtest_kalshi_nhl.py","logger":"airflow.plugins_manager","filename":"plugins_manager.py","lineno":298,"error_detail":[{"exc_type":"ModuleNotFoundError","exc_value":"No module named 'plugins'","exc_notes":[],"syntax_error":null,"is_cause":false,"frames":[{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/plugins_manager.py","lineno":291,"name":"load_plugins_from_plugin_directory"},{"filename":"<frozen importlib._bootstrap_external>","lineno":999,"name":"exec_module"},{"filename":"<frozen importlib._bootstrap>","lineno":488,"name":"_call_with_frames_removed"},{"filename":"/opt/airflow/plugins/backtest_kalshi_nhl.py","lineno":31,"name":"<module>"}],"is_group":false,"exceptions":[]}]}
```

Similarly for `deposit_tracking.py` line 7 and `compare_elo_trueskill_nhl.py` line 33.

### Root Cause
The plugin manager loads each plugin file individually, adding the plugin directory (`/opt/airflow/plugins`) to `sys.path`. However, for a module `plugins` to be importable, the directory must be recognized as a Python package (i.e., contain an `__init__.py` file) and the parent directory (`/opt/airflow`) must be in `sys.path`. The plugin manager may not add the parent directory, causing `import plugins` to fail.

Alternatively, the plugin manager may change the current working directory, causing relative imports to break.

The `plugins` directory does have an `__init__.py` file (present in the local copy). However, the plugin manager may be loading the plugin file with a different `__name__` (e.g., `__main__`) which disrupts package-relative imports.

## Viewing Instructions
1. **Check if `plugins` is a package**:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 ls -la /opt/airflow/plugins/__init__.py
   ```
2. **Examine the import statements** in the failing files:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 grep -n "import plugins" /opt/airflow/plugins/backtest_kalshi_nhl.py
   docker exec nhlstats-airflow-scheduler-1 grep -n "from plugins" /opt/airflow/plugins/deposit_tracking.py
   ```
3. **Test import manually** from the plugin directory:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 cd /opt/airflow && python -c "import sys; sys.path.insert(0, '.'); import plugins; print('success')"
   ```
4. **Check `sys.path` during plugin loading** by adding a debug print in `plugins_manager.py` or inspecting logs.

## Possible Solutions

### 1. Ensure `plugins` is a proper package
Make sure `plugins/__init__.py` exists and is readable. If missing, create it.

### 2. Add parent directory to `sys.path`
Modify the plugin manager or the plugin files to add `/opt/airflow` to `sys.path` before importing `plugins`. This can be done by inserting:
```python
import sys
sys.path.insert(0, '/opt/airflow')
```
at the top of each plugin file that imports `plugins`.

### 3. Use relative imports within the plugin directory
Change `from plugins.db_manager import DBManager` to `from .db_manager import DBManager`. However, this may break other imports if the plugin is not loaded as a submodule.

### 4. Adjust plugin manager configuration
Airflow's plugin manager can be configured to treat the plugin directory as a package. This may involve setting `PLUGINS_FOLDER` or modifying the plugin loading logic in `plugins_manager.py`.

### 5. Restructure plugin imports
Move common modules out of the `plugins` package and into a separate package that is installed via `pip`. This is a larger refactor but ensures imports are independent of the plugin loading mechanism.

### 6. Use absolute imports with `airflow.plugins` namespace
If Airflow provides a namespace for plugins, use `from airflow.plugins.db_manager import DBManager`. However, this may not be applicable.

## Recommended Approach
The simplest fix is to ensure the parent directory (`/opt/airflow`) is in `sys.path` when the plugin is loaded. This can be done by adding the following lines at the top of each affected plugin file:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
```

Alternatively, modify the plugin manager to add the parent directory globally.

**Steps**:
1. Identify all plugin files that import `plugins` (grep for `from plugins` or `import plugins`).
2. Add the sys.path insertion at the top of each file.
3. Restart Airflow containers to reload plugins.

## Expected Outcome
After fixing the import path, the `plugins` module will be found, and the plugin import will succeed. This will resolve the `ModuleNotFoundError` for those plugins.

## Additional Notes
- The same issue may affect other plugins that rely on intra-package imports.
- Consider adding a test to verify plugin imports in the CI/CD pipeline.
- After making changes, run `python -m pytest tests/test_plugin_imports.py` (if such a test exists) to ensure all plugins can be imported.
