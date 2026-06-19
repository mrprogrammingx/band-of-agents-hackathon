#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

PY="$(which python3)"
LOGDIR="$REPO_DIR/data/logs"
mkdir -p "$LOGDIR"

LOCKDIR="/tmp/band-of-agents-crawlers.lock"
if mkdir "$LOCKDIR" 2>/dev/null; then
  trap 'rm -rf "$LOCKDIR"' EXIT
else
  echo "Runner already in progress; exiting."
  exit 0
fi

TS="$(date -u +%Y-%m-%dT%H%M%SZ)"

echo "======================================"
echo "🚀 PIPELINE START: $TS"
echo "======================================"

# -------------------------
# LinkedIn crawler
# -------------------------
echo "=== Running LinkedIn crawler ==="

"$PY" "$REPO_DIR/backend/crawler/linkedin.py" \
  --keywords "Data Engineer" \
  --location "Armenia" \
  --date-posted week \
  --max-pages 2 \
  --delay 0.5 \
  2>&1 | tee "$LOGDIR/linkedin-$TS.log"

echo "LinkedIn crawler finished"

# -------------------------
# staff.am crawler
# -------------------------
echo "=== Running staff.am crawler ==="

"$PY" "$REPO_DIR/backend/crawler/staff_am.py" \
  --max-pages 5 \
  --delay 0.5 \
  2>&1 | tee "$LOGDIR/staff_am-$TS.log"

echo "staff.am crawler finished"

echo "======================================"
echo "🏁 PIPELINE COMPLETE"
echo "======================================"