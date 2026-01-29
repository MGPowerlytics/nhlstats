# ImportError: cannot import name 'fetch_nba_markets' from 'kalshi_markets'

## Context
Tasks such as `epl_fetch_markets`, `nhl_fetch_markets` fail with the following error:

```
{"timestamp":"2026-01-26T05:00:19.102864Z","level":"error","event":"Task failed with exception","logger":"task","filename":"task_runner.py","lineno":1078,"error_detail":[{"exc_type":"ImportError","exc_value":"cannot import name 'fetch_nba_markets' from 'kalshi_markets' (/opt/airflow/plugins/kalshi_markets.py)","exc_notes":[],"syntax_error":null,"is_cause":false,"frames":[{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/sdk/execution_time/task_runner.py","lineno":1004,"name":"run"},{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/sdk/execution_time/task_runner.py","lineno":1405,"name":"_execute_task"},{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/sdk/bases/operator.py","lineno":417,"name":"wrapper"},{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/providers/standard/operators/python.py","lineno":214,"name":"execute"},{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/providers/standard/operators/python.py","lineno":237,"name":"execute_callable"},{"filename":"/home/airflow/.local/lib/python3.12/site-packages/airflow/sdk/execution_time/callback_runner.py","lineno":82,"name":"run"},{"filename":"/opt/airflow/dags/multi_sport_betting_workflow.py","lineno":668,"name":"fetch_prediction_markets"}],"is_group":false,"exceptions":[]}]}
```

### Root Cause
The `kalshi_markets` plugin fails to import due to missing dependencies (`lazy_imports`). This causes the plugin module to be only partially loaded, and the function `fetch_nba_markets` (which is defined later in the file) is not registered in the module's namespace. The import error is a symptom of the earlier plugin import failure.

The function `fetch_nba_markets` exists at line 278 of `/opt/airflow/plugins/kalshi_markets.py`. However, because the import of `kalshi_python` fails at line 6, the module execution stops, and the function definition is never executed.

## Viewing Instructions
1. **Check plugin import logs** for `kalshi_markets.py`:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 grep -A5 -B5 "Failed to import plugin.*kalshi_markets" /opt/airflow/logs/dag_id=multi_sport_betting_workflow/run_id=scheduled__2026-01-26T05:00:00+00:00/task_id=epl_fetch_markets/attempt=1.log
   ```
2. **Verify the function exists**:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 grep -n "def fetch_nba_markets" /opt/airflow/plugins/kalshi_markets.py
   ```
3. **Test manual import** of the plugin:
   ```bash
   docker exec nhlstats-airflow-scheduler-1 python -c "import sys; sys.path.insert(0, '/opt/airflow/plugins'); import kalshi_markets; print(kalshi_markets.fetch_nba_markets)"
   ```
   If this fails with `ImportError` (missing `lazy_imports`), you'll see the underlying cause.

## Possible Solutions

### 1. Fix the plugin import failure
Resolve the missing `lazy_imports` dependency as described in the [plugin_import_failure.md](plugin_import_failure.md) prompt.

### 2. Ensure plugin loads completely
After installing missing dependencies, restart the Airflow containers to reload plugins:
```bash
docker compose down && docker compose up -d
```

### 3. Verify plugin loading
Check that the plugin is now loaded correctly by looking for successful import messages in the scheduler logs:
```bash
docker logs nhlstats-airflow-scheduler-1 2>&1 | grep -i "kalshi_markets" | head -5
```

### 4. Test the task manually
Trigger the task manually after fixing dependencies:
```bash
docker exec nhlstats-airflow-scheduler-1 airflow tasks test multi_sport_betting_workflow epl_fetch_markets 2026-01-26
```

### 5. Consider refactoring plugin imports
If the dependency issue persists, consider modifying `kalshi_markets.py` to catch `ImportError` and provide a graceful fallback (e.g., log warning and skip Kalshi integration). However, this is a workaround and not recommended for production.

## Expected Outcome
Once the plugin import succeeds, the `fetch_nba_markets` function will be available, and the tasks will execute without `ImportError`.

## Additional Notes
- The same issue may affect other functions in `kalshi_markets.py` such as `fetch_nhl_markets`, `fetch_mlb_markets`, etc.
- Ensure all dependent packages (`kalshi_python`, `lazy_imports`, `appdirs`) are listed in `requirements.txt` and installed in the Docker image.
- After making changes to `requirements.txt`, rebuild the Docker images with `docker compose build` and restart containers.
