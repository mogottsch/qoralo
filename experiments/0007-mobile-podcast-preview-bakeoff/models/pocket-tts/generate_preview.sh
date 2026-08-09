#!/usr/bin/env bash
# Acquire exactly one policy-defined atomic grant for the complete load/generation.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACT_ROOT="${POCKET_TTS_ARTIFACT_ROOT:-$EXPERIMENT/artifacts/setup/pocket-tts}"
PYTHON="$ARTIFACT_ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || { echo "run $HERE/setup.sh first" >&2; exit 65; }
exec "$EXPERIMENT/tools/with-resources.sh" \
  --task task-7 --kind generation-pocket -- \
  env PREVIEW_RESOURCE_GRANT_KIND=generation-pocket \
  POCKET_TTS_ARTIFACT_ROOT="$ARTIFACT_ROOT" \
  "$PYTHON" "$HERE/generate_preview.py"
