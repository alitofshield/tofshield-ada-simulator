#!/usr/bin/env bash
set -euo pipefail

app_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
viewer_url="http://127.0.0.1:${ADA_VIEWER_PORT:-8081}"

(
  sleep 2
  xdg-open "$viewer_url" >/dev/null 2>&1 || true
) &

exec "$app_dir/run.sh"
