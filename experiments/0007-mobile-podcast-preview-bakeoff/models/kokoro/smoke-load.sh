#!/usr/bin/env bash
# The only supported smoke entry point: download and load happen inside one grant.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
VENV="${KOKORO_VENV:-$ROOT/artifacts/kokoro/venv}"
[[ -x "$VENV/bin/python" ]] || {
  echo "BLOCKED: isolated environment missing at $VENV; run $HERE/setup.sh first." >&2
  exit 69
}
exec "$ROOT/tools/with-resources.sh" \
  --task task-4 --kind smoke-load -- \
  env KOKORO_GATED_SMOKE=1 "$VENV/bin/python" "$HERE/smoke_load.py"
