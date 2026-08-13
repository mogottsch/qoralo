#!/usr/bin/env bash
# Only supported model-load entry point; download, verification, and load share one grant.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
VENV="${SUPERTONIC_VENV:-$EXPERIMENT/artifacts/supertonic-3/venv}"
[[ -x "$VENV/bin/python" ]] || { echo "BLOCKED: run $HERE/setup.sh first" >&2; exit 69; }
exec "$EXPERIMENT/tools/with-resources.sh" --task task-2 --kind smoke-load -- \
  env SUPERTONIC_GATED_SMOKE=1 "$VENV/bin/python" "$HERE/smoke_load.py"
