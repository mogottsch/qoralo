#!/usr/bin/env bash
# One invocation is exactly one globally gated, write-once full generation job.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACT_ROOT="${KITTEN_ARTIFACT_ROOT:-$ROOT/artifacts/kitten-tts-mini-0.8}"
VENV="${KITTEN_VENV:-$ARTIFACT_ROOT/venv}"
ATTEMPT="${1:-}"
RUN="${2:-primary}"
[[ $# -ge 1 && $# -le 2 ]] || { echo "BLOCKED: usage: generate-preview.sh <default|speed-0.95|speed-0.90> [primary|repeat-1]" >&2; exit 64; }
case "$ATTEMPT" in default|speed-0.95|speed-0.90) ;; *) echo "BLOCKED: attempt is not in the precommitted grid" >&2; exit 64 ;; esac
case "$RUN" in primary|repeat-1) ;; *) echo "BLOCKED: run must be primary or repeat-1" >&2; exit 64 ;; esac
[[ -x "$VENV/bin/python" ]] || { echo "BLOCKED: run setup.sh first" >&2; exit 69; }
exec "$ROOT/tools/with-resources.sh" --task task-8 --kind full-generation -- \
  env KITTEN_GATED_GENERATION=1 HF_HUB_OFFLINE=1 "$VENV/bin/python" "$HERE/generate_preview.py" --attempt "$ATTEMPT" --run "$RUN"
