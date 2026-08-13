#!/usr/bin/env bash
# User/project-local setup only: no sudo, system package manager, credentials, or acceptance prompt.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
VENV="${SUPERTONIC_VENV:-$EXPERIMENT/artifacts/supertonic-3/venv}"
command -v uv >/dev/null || { echo "BLOCKED: install uv in user or project scope" >&2; exit 69; }
[[ -z "${HF_TOKEN:-}${HUGGING_FACE_HUB_TOKEN:-}" ]] || { echo "BLOCKED: this public track refuses credentials" >&2; exit 69; }
uv venv --clear --python 3.11 --no-python-downloads "$VENV"
UV_PROJECT_ENVIRONMENT="$VENV" uv sync --project "$HERE" --locked --no-dev
"$VENV/bin/python" "$HERE/verify_pins.py"
printf 'isolated CPU environment: %s\n' "$VENV"
