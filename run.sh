#!/usr/bin/env bash
set -euo pipefail

app_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$app_dir"

venv_dir="${ADA_VIEWER_VENV:-$HOME/.virtualenvs/tofshield-hdf5-viewer}"
if [[ ! -f "$venv_dir/bin/activate" ]]; then
  mkdir -p "$(dirname "$venv_dir")"
  python3 -m venv "$venv_dir"
fi

source "$venv_dir/bin/activate"
python -m pip install --disable-pip-version-check -r requirements.txt
exec python server.py
