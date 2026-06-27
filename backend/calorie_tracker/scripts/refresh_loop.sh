#!/bin/sh
# Refresher worker loop (compose `refresher` service).
#
# Re-runs the idempotent daily-rollup refresher on a fixed interval. The Python script itself
# (calorie_tracker.scripts.refresh) is one-shot; this wrapper is the "worker" that keeps it ticking.
# `|| true` keeps the loop alive if a single run errors (e.g. a transient DB/Redis blip).
#
# Cadence: REFRESH_INTERVAL_SECONDS (default 3600s / 1h).
set -u

INTERVAL="${REFRESH_INTERVAL_SECONDS:-3600}"
echo "[refresher] starting loop; interval=${INTERVAL}s"
while true; do
  python -m calorie_tracker.scripts.refresh || true
  sleep "${INTERVAL}"
done
