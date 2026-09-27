#!/usr/bin/env bash
# Rebuild everything from the raw sources: data -> tables -> figures -> dashboard data.
#   OFFLINE=1   use the files already in data/ without downloading anything
#   PY=...      Python to use (default .venv/bin/python)
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-.venv/bin/python}
PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")"

if [ -z "${OFFLINE:-}" ]; then
  "$PY" src/fetch.py --report
fi
(
  cd src
  "$PY" need.py
  "$PY" wage_screen.py
  "$PY" ladder.py
  "$PY" figures.py
  "$PY" export_dashboard.py
)
# The written report is distributed separately; render it only where it exists.
if [ -f report/report.md ]; then
  "$PY" src/render_report.py report/report.md "report/${REPORT_PDF:-report.pdf}"
fi
