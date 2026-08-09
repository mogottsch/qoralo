#!/usr/bin/env bash
# Acquire task 1's single atomic grant before importing/loading Pocket TTS.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACT_ROOT="${POCKET_TTS_ARTIFACT_ROOT:-$EXPERIMENT/artifacts/setup/pocket-tts}"
PYTHON="$ARTIFACT_ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || { echo "run $HERE/setup.sh first" >&2; exit 65; }
exec "$EXPERIMENT/tools/with-resources.sh" \
  --task task-3 --kind smoke-load -- \
  env PREVIEW_RESOURCE_GRANT_KIND=smoke-load POCKET_TTS_ARTIFACT_ROOT="$ARTIFACT_ROOT" \
  "$PYTHON" "$HERE/smoke_load.py"
