#!/usr/bin/env bash
# Isolated, unprivileged setup. Weights, caches, and the venv remain ignored.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
VENV="${INFLECT_NANO_VENV:-$EXPERIMENT/artifacts/inflect-nano-v1/venv}"
command -v uv >/dev/null || {
  echo "BLOCKED: uv is required in user/project scope; this track never uses sudo or system pip." >&2
  exit 69
}
python3 "$HERE/verify_pins.py"
uv venv --clear --python 3.11 --no-python-downloads "$VENV"
UV_PROJECT_ENVIRONMENT="$VENV" uv sync --project "$HERE" --locked --no-dev
"$VENV/bin/python" "$HERE/prepare_snapshot.py"
"$VENV/bin/python" "$HERE/prepare_frontend.py"
printf 'Inflect-Nano-v1 isolated environment: %s\n' "$VENV"
