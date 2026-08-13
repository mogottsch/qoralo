#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
VENV="${INFLECT_NANO_VENV:-$EXPERIMENT/artifacts/inflect-nano-v1/venv}"
test -x "$VENV/bin/python" || { echo "BLOCKED: run setup.sh first" >&2; exit 69; }
export CUDA_VISIBLE_DEVICES=""
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
exec "$EXPERIMENT/tools/with-resources.sh" \
  --task task-3-inflect-smoke --kind model-load -- \
  "$VENV/bin/python" "$HERE/smoke_load.py"
