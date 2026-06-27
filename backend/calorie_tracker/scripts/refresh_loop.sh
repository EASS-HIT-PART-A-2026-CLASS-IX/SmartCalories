#!/bin/sh
# Refresher worker loop (compose `refresher` service).
#
# Re-runs the idempotent daily-rollup refresher on a fixed interval. The Python script itself
# (calorie_tracker.scripts.refresh) is one-shot; this wrapper is the "worker" that keeps it ticking.
# `|| true` keeps the loop alive if a single run errors (e.g. a transient DB/Redis blip).
#
# Cadence comes from REFRESH_INTERVAL_SECONDS, which the compose `refresher` service injects from
# .env (single source of truth; default lives there, not here). `set -u` fails fast if it's unset.
set -u

echo "[refresher] starting loop; interval=${REFRESH_INTERVAL_SECONDS}s"
while true; do
  python -m calorie_tracker.scripts.refresh || true
  sleep "${REFRESH_INTERVAL_SECONDS}"
done
