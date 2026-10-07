#!/usr/bin/env bash
set -euo pipefail
app_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ADA_VIEWER_PORT="${ADA_VIEWER_PORT:-8083}"
export ADA_HDF5_ROOTS="${ADA_HDF5_ROOTS:-/media/sali/ADA/TOFshield_Team_Share/HDF5}"
exec bash "$app_dir/start-viewer.sh"
