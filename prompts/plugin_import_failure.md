# Plugin Import Failure: Missing `lazy_imports` and `appdirs`

## Context
Airflow plugin manager fails to import plugins `kalshi_markets.py` and `nfl_games.py` during DAG parsing, causing tasks like `epl_fetch_markets`, `nhl_fetch_markets` to fail with `ImportError: cannot import name 'fetch_nba_markets'`.

### Error Logs
```
{"timestamp":"2026-01-26T05:00:18.472382Z","level":"error","event":"Failed to import plugin /opt/airflow/plugins/kalshi_markets.py","logger":"airflow.plugins_manager","filename":"plugins_manager.py","lineno":298,"error_detail":[{"exc_type":"ModuleNotFoundError","exc_value":"No module named 'lazy_imports'","exc_notes":[],"syntax_error":null,"is_cause":false,"frames":[{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/plugins_manager.py","lineno":291,"name":"load_plugins_from_plugin_directory"},{"filename":"<frozen importlib._bootstrap_external>","lineno":999,"name":"exec_module"},{"filename":"<frozen importlib._bootstrap>","lineno":488,"name":"_call_with_frames_removed"},{"filename":"/opt/airflow/plugins/kalshi_markets.py","lineno":6,"name":"<module>"},{"filename":"/home/airflow/.local/lib/python3.12/site-packages/kalshi_python/__init__.py","lineno":20,"name":"<module>"},{"filename":"/home/airflow/.local/lib/python3.12/site-packages/kalshi_python/api/__init__.py","lineno":17,"name":"<module>"}],"is_group":false,"exceptions":[]}]}
```

Similarly for `nfl_games.py`:
```
{"timestamp":"2026-01-26T05:00:19.014740Z","level":"error","event":"Failed to import plugin /opt/airflow/plugins/nfl_games.py","logger":"airflow.plugins_manager","filename":"plugins_manager.py","lineno":298,"error_detail":[{"exc_type":"ModuleNotFoundError","exc_value":"No module named 'appdirs'","exc_notes":[],"syntax_error":null,"is_cause":false,"frames":[{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/plugins_manager.py","lineno":291,"name":"load_plugins_from_plugin_directory"},{"filename":"<frozen importlib._bootstrap_external>","lineno":999,"name":"exec_module"},{"filename":"<frozen importlib._bootstrap>","lineno":488,"name":"_call_with_frames_removed"},{"filename":"/opt/airflow/plugins/nfl_games.py","lineno":6,"name":"<module>"},{"filename":"/home/airflow/.local/lib/python3.12/site-packages/nfl_data_py/__init__.py","lineno":12,"name":"<module>"}],"is_group":false,"exceptions":[]}]}
```

### Root Cause
The `kalshi_python` package (version 2.1.0) uses `lazy_imports` for lazy loading of API modules. The `nfl_data_py` package depends on `appdirs`. These dependencies are not installed in the Airflow environment at plugin load time, causing import failures.

Despite `lazy_imports` and `appdirs` being present in the user site-packages (`/home/airflow/.local/lib/python3.12/site-packages`), the plugin manager may not have the same `sys.path` or may load plugins before the user site-packages are added.

## Viewing Instructions
1. **Check installed packages** in the scheduler container:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 pip3 list | grep -E "lazy_imports|appdirs"
   ```
2. **Test import manually**:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 python -c "import lazy_imports; import appdirs; print('OK')"
   ```
3. **Examine plugin manager's sys.path** by adding debug to `plugins_manager.py` or checking logs.
4. **View full error logs** for the failed tasks:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 cat /opt/airflow/logs/dag_id=multi_sport_betting_workflow/run_id=scheduled__2026-01-26T05:00:00+00:00/task_id=epl_fetch_markets/attempt=1.log | jq -r '.error_detail[].exc_value' 2>/dev/null
   ```

## Possible Solutions

### 1. Install missing dependencies
Add `lazy_imports` and `appdirs` to `requirements.txt` and rebuild containers:
```bash
echo "lazy_imports>=1.2.0" >> requirements.txt
echo "appdirs>=1.4.4" >> requirements.txt
docker compose down && docker compose up -d
```

### 2. Install directly into running container (temporary)
```bash
docker exec nhlstats-airflow-scheduler-1 pip3 install lazy_imports appdirs
docker compose restart airflow-scheduler
```

### 3. Verify Python path
Ensure the plugin manager's `sys.path` includes user site-packages. The plugin manager runs within the same Python process as the scheduler, so the path should be correct. If not, consider setting `PYTHONPATH` in `docker-compose.yaml`.

### 4. Use try-except in plugin imports
Modify `kalshi_markets.py` and `nfl_games.py` to catch `ImportError` and provide a fallback or install missing packages dynamically (not recommended for production).

### 5. Check package version compatibility
Ensure `kalshi_python==2.1.0` is compatible with `lazy_imports`. If not, consider downgrading `kalshi_python` or upgrading `lazy_imports`.

### 6. Restart containers after any changes
As per project guidelines, after modifying plugins or dependencies, restart all containers:
```bash
docker compose down && docker compose up -d
```

## Expected Outcome
After resolving the missing dependencies, the plugin import should succeed, and the tasks `epl_fetch_markets`, `nhl_fetch_markets`, `nba_fetch_markets`, etc. should run without `ImportError`.

## Additional Notes
- The `fetch_nba_markets` function exists in `kalshi_markets.py` at line 278, but the module is not fully loaded due to the import failure.
- The same issue may affect other plugins that depend on external packages not listed in `requirements.txt`.
- Consider running `pip freeze` inside the container to generate a complete dependency list and update `requirements.txt` accordingly.
