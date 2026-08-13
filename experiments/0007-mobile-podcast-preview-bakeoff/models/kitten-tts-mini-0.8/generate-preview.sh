#!/usr/bin/env bash
# One invocation is exactly one globally gated, write-once full generation job.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACT_ROOT="${KITTEN_ARTIFACT_ROOT:-$ROOT/artifacts/kitten-tts-mini-0.8}"
VENV="${KITTEN_VENV:-$ARTIFACT_ROOT/venv}"
RUN="${1:-primary}"
[[ "$RUN" =~ ^[a-z0-9-]+$ ]] || { echo "BLOCKED: run label must be lowercase alphanumeric/hyphen" >&2; exit 64; }
[[ -x "$VENV/bin/python" ]] || { echo "BLOCKED: run setup.sh first" >&2; exit 69; }
OUTPUT="$ARTIFACT_ROOT/generation/attempt-01-default-$RUN.f32le"
exec "$ROOT/tools/with-resources.sh" --task task-8 --kind full-generation -- \
  env KITTEN_GATED_GENERATION=1 HF_HUB_OFFLINE=1 "$VENV/bin/python" "$HERE/generate_preview.py" --attempt default --output "$OUTPUT"
