#!/usr/bin/env bash
# Acquire one atomic globally exclusive RAM+generation grant before model loading.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACTS="${VIBEVOICE_REALTIME_ARTIFACTS:-$HERE/artifacts}"
test -x "$ARTIFACTS/venv/bin/python" || { echo "run setup.sh first" >&2; exit 2; }
exec "$ROOT/tools/with-resources.sh" --task task-6 --kind generation-realtime -- \
  env VIBEVOICE_PREVIEW_GATE=task-6:generation-realtime VIBEVOICE_REALTIME_ARTIFACTS="$ARTIFACTS" \
  "$ARTIFACTS/venv/bin/python" "$HERE/generate_preview.py"
