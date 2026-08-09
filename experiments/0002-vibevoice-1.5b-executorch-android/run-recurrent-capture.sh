#!/usr/bin/env bash
# The resource gate owns the complete model process, including cleanup on signals.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:?usage: $0 OUTPUT_DIR [REPEAT_OF]}"
REPEAT_OF="${2:-}"
ARGS=(--output "$OUT")
if [[ -n "$REPEAT_OF" ]]; then ARGS+=(--repeat-of "$REPEAT_OF"); fi
exec python3 "$ROOT/experiments/0007-mobile-podcast-preview-bakeoff/tools/resource_lock.py" run \
  --task task-9 --kind capture -- \
  "$ROOT/artifacts/venv-executorch-1.2/bin/python" "$ROOT/experiments/0002-vibevoice-1.5b-executorch-android/export/capture_recurrent_trace.py" "${ARGS[@]}"
