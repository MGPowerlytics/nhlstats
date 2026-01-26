from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Set


def _extract_sports_config_keys(dag_path: Path) -> Set[str]:
    tree = ast.parse(dag_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(t, ast.Name) and t.id == "SPORTS_CONFIG"
                for t in node.targets
            ):
                if not isinstance(node.value, ast.Dict):
                    raise AssertionError("SPORTS_CONFIG is not a dict literal")
                keys: Set[str] = set()
                for k in node.value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
                    else:
                        raise AssertionError("SPORTS_CONFIG contains a non-string key")
                return keys
    raise AssertionError("Could not find SPORTS_CONFIG assignment")


def _extract_dashboard_leagues(dashboard_path: Path) -> List[str]:
    """Extract the dashboard league list from the sidebar selectbox.

    We intentionally parse the file AST (not import it) to avoid
    executing Streamlit at import time.
    """

    tree = ast.parse(dashboard_path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # Match calls like: st.sidebar.selectbox("Select League", [...])
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "selectbox":
            continue

        # Try to detect first arg "Select League"
        if not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and first.value == "Select League"):
            continue

        if len(node.args) < 2:
            raise AssertionError("Select League selectbox missing options list")

        second = node.args[1]
        if not isinstance(second, ast.List):
            raise AssertionError("Select League options are not a list literal")

        leagues: List[str] = []
        for elt in second.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                leagues.append(elt.value)
            else:
                raise AssertionError("Select League options contain a non-string")

        return leagues

    raise AssertionError("Could not find the dashboard Select League selectbox")


def test_dag_and_dashboard_sports_aligned() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    dag_path = repo_root / "dags" / "multi_sport_betting_workflow.py"
    dashboard_path = repo_root / "dashboard" / "dashboard_app.py"

    dag_sports = _extract_sports_config_keys(dag_path)
    dashboard_leagues = _extract_dashboard_leagues(dashboard_path)

    dashboard_sports = {x.strip().lower() for x in dashboard_leagues}

    missing_in_dashboard = sorted(dag_sports - dashboard_sports)
    extra_in_dashboard = sorted(dashboard_sports - dag_sports)

    assert missing_in_dashboard == [], (
        f"Dashboard missing leagues for: {missing_in_dashboard}"
    )
    assert extra_in_dashboard == [], (
        f"Dashboard has leagues not in DAG: {extra_in_dashboard}"
    )
