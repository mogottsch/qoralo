#!/usr/bin/env bash
# One invocation is exactly one globally gated, write-once full generation job.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACT_ROOT="${KITTEN_ARTIFACT_ROOT:-$ROOT/artifacts/kitten-tts-mini-0.8}"
VENV="${KITTEN_VENV:-$ARTIFACT_ROOT/venv}"
RUN="${1:-primary}"
[[ $# -le 1 ]] || { echo "BLOCKED: usage: generate-preview.sh [primary|repeat-1]" >&2; exit 64; }
case "$RUN" in
  primary|repeat-1) ;;
  *) echo "BLOCKED: run must be primary or repeat-1" >&2; exit 64 ;;
esac
[[ -x "$VENV/bin/python" ]] || { echo "BLOCKED: run setup.sh first" >&2; exit 69; }
exec "$ROOT/tools/with-resources.sh" --task task-8 --kind full-generation -- \
  env KITTEN_GATED_GENERATION=1 HF_HUB_OFFLINE=1 "$VENV/bin/python" "$HERE/generate_preview.py" --run "$RUN"
