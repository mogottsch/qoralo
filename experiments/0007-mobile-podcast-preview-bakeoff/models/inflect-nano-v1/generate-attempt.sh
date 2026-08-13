#!/usr/bin/env bash
# One invocation = one globally exclusive, write-once full-generation attempt/repeat.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
VENV="${INFLECT_NANO_VENV:-$EXPERIMENT/artifacts/inflect-nano-v1/venv}"
test -x "$VENV/bin/python" || { echo "BLOCKED: run setup.sh first" >&2; exit 69; }
if [[ $# -lt 1 || $# -gt 2 || ! "$1" =~ ^[0-9]+$ || ( $# -eq 2 && "$2" != "--repeat" ) ]]; then
  echo "usage: $0 ATTEMPT_INDEX [--repeat]" >&2
  exit 64
fi
export CUDA_VISIBLE_DEVICES=""
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
args=(--attempt-index "$1")
[[ $# -eq 2 ]] && args+=(--repeat)
exec "$EXPERIMENT/tools/with-resources.sh" \
  --task task-7-inflect-generation --kind full-generation -- \
  "$VENV/bin/python" "$HERE/generate_attempt.py" "${args[@]}"
