#!/usr/bin/env bash
# The only supported smoke entry point: one atomic conservative model-resource grant.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACTS="${VIBEVOICE_REALTIME_ARTIFACTS:-$HERE/artifacts}"
test -x "$ARTIFACTS/venv/bin/python" || { echo "run setup.sh first" >&2; exit 2; }
exec "$ROOT/tools/with-resources.sh" --task task-2 --kind smoke-load -- \
  env VIBEVOICE_SMOKE_GATE=task-2 VIBEVOICE_REALTIME_ARTIFACTS="$ARTIFACTS" \
  "$ARTIFACTS/venv/bin/python" "$HERE/_smoke_load.py"
