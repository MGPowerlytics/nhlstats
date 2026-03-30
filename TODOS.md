# TODOS

Deferred work items from engineering review. Each item includes context for pickup.

## QA Deferred Issues (2026-03-30)

### ISSUE-005 (Low): `inf` Elo divergence displayed raw in Diagnostic Report
- **Page**: Diagnostic Report → Elo Divergence metric
- **Repro**: Navigate to Diagnostic Report; Tennis shows `inf` divergence
- **Fix**: Handle `math.isinf()` in dashboard — display "∞" or "N/A" instead of raw `inf`
- **File**: `dashboard/dashboard_app.py` — diagnostic_report_page() function

### ISSUE-006 (Low): Last Run date truncated in Diagnostic Report header
- **Page**: Diagnostic Report → header subtitle
- **Repro**: "Last Run" timestamp is cut off mid-string
- **Fix**: Either widen the metric column or truncate cleanly at a word boundary
- **File**: `dashboard/dashboard_app.py` — diagnostic_report_page() function

### ISSUE-004 (Upstream): Streamlit sidebar theme color warnings
- **Console**: `Invalid color passed for widgetBackgroundColor/widgetBorderColor/skeletonBackgroundColor in theme.sidebar: ""`
- **Root cause**: Streamlit 1.54 upstream bug — these JS-frontend properties are not in the Python config schema
- **Status**: Cannot fix without Streamlit upstream fix; `.streamlit/config.toml` has been updated with all configurable values
