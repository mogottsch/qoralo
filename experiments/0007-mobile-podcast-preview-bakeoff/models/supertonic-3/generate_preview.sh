#!/usr/bin/env bash
# Run exactly one precommitted attempt under the global exclusive gate.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
VENV="${SUPERTONIC_VENV:-$EXPERIMENT/artifacts/supertonic-3/venv}"
[[ $# -ge 1 && $# -le 2 && "$1" =~ ^[0-7]$ && ( $# -eq 1 || "$2" == "--repeat" ) ]] || { echo "usage: $0 ATTEMPT_INDEX (0..7) [--repeat]" >&2; exit 64; }
[[ -x "$VENV/bin/python" ]] || { echo "BLOCKED: run setup.sh first" >&2; exit 69; }
args=(--attempt-index "$1")
[[ $# -eq 2 ]] && args+=(--repeat)
exec "$EXPERIMENT/tools/with-resources.sh" --task task-6 --kind full-generation -- \
  env -u HF_TOKEN -u HUGGING_FACE_HUB_TOKEN SUPERTONIC_ATTEMPT_GRANT=1 "$VENV/bin/python" "$HERE/generate_preview.py" "${args[@]}"
