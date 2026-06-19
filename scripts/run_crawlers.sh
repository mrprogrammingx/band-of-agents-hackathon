#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

VENV="$REPO_DIR/.venv"
PY="$VENV/bin/python"
LOGDIR="$REPO_DIR/data/logs"
mkdir -p "$LOGDIR"

LOCKDIR="/tmp/band-of-agents-crawlers.lock"
if mkdir "$LOCKDIR" 2>/dev/null; then
  trap 'rm -rf "$LOCKDIR"' EXIT
else
  echo "Runner already in progress; exiting." >&2
  exit 0
fi

TS="$(date -u +%Y-%m-%dT%H%M%SZ)"

# Run LinkedIn crawler (adjust args as needed)
if [ -x "$PY" ]; then
  echo "=== [$TS] Running LinkedIn crawler ===" | tee -a "$LOGDIR/linkedin-$TS.log"
  "$PY" backend/crawler/linkedin.py \
    --keywords "Data Engineer" \
    --location "Armenia" \
    --date-posted week \
    --max-pages 2 \
    --delay 0.5 \
    2>&1 | tee -a "$LOGDIR/linkedin-$TS.log" || true
else
  echo "Python not found at $PY; activate your venv or adjust VENV path" | tee -a "$LOGDIR/run-error-$TS.log" >&2
fi

# Run staff.am crawler
if [ -x "$PY" ]; then
  echo "=== [$TS] Running staff.am crawler ===" | tee -a "$LOGDIR/staff_am-$TS.log"
  "$PY" backend/crawler/staff_am.py \
    --max-pages 5 \
    --delay 0.5 \
    2>&1 | tee -a "$LOGDIR/staff_am-$TS.log" || true
fi