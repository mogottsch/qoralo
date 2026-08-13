#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
VENV="${KITTEN_VENV:-${KITTEN_ARTIFACT_ROOT:-$ROOT/artifacts/kitten-tts-mini-0.8}/venv}"
[[ -x "$VENV/bin/python" ]] || { echo "BLOCKED: run models/kitten-tts-mini-0.8/setup.sh first" >&2; exit 69; }
exec "$ROOT/tools/with-resources.sh" --task task-4 --kind model-load -- env KITTEN_GATED_SMOKE=1 "$VENV/bin/python" "$HERE/smoke_load.py"
