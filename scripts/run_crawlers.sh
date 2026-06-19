#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

PY="python"
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

echo "🚀 PIPELINE START: $TS"

echo "=== Running LinkedIn crawler ==="
$PY -m backend.crawler.linkedin \
  --keywords "Data Engineer" \
  --location "Armenia" \
  --date-posted week \
  --max-pages 2 \
  --delay 0.5 \
  || echo "LinkedIn crawler failed"

echo "=== Running staff.am crawler ==="
$PY -m backend.crawler.staff_am \
  --max-pages 5 \
  --delay 0.5 \
  || echo "staff.am crawler failed"

echo "🏁 PIPELINE END"