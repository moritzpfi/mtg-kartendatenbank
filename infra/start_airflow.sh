#!/usr/bin/env bash
set -euo pipefail
airflow scheduler &
scheduler=$!
airflow webserver --port 8080 &
webserver=$!
trap 'kill "$scheduler" "$webserver" 2>/dev/null || true; wait || true' EXIT
trap 'exit 0' TERM INT
wait -n "$scheduler" "$webserver"
exit 1
