#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

PY="python3"
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

echo "======================================"
echo "🚀 PIPELINE START: $TS"
echo "======================================"

echo "=== Running LinkedIn crawler ===" | tee -a "$LOGDIR/linkedin-$TS.log"
python3 backend/crawler/linkedin.py \
  --keywords "Data Engineer" \
  --location "Armenia" \
  --date-posted week \
  --max-pages 2 \
  --delay 0.5 \
  2>&1 | tee -a "$LOGDIR/linkedin-$TS.log" || true

echo "=== Running staff.am crawler ===" | tee -a "$LOGDIR/staff_am-$TS.log"
python3 backend/crawler/staff_am.py \
  --max-pages 5 \
  --delay 0.5 \
  2>&1 | tee -a "$LOGDIR/staff_am-$TS.log" || true

echo "======================================"
echo "🏁 PIPELINE END"
echo "======================================"