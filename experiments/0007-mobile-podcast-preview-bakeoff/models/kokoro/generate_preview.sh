#!/usr/bin/env bash
# Acquire exactly one policy-defined grant around both fresh-process renders.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACT_ROOT="${KOKORO_ARTIFACT_ROOT:-$EXPERIMENT/artifacts/kokoro}"
[[ -x "$ARTIFACT_ROOT/venv/bin/python" ]] || {
  echo "run $HERE/setup.sh first" >&2
  exit 65
}
command -v espeak-ng >/dev/null || {
  echo "BLOCKED: provide a user/project-local espeak-ng executable on PATH; no privileged installation is performed" >&2
  exit 69
}
exec "$EXPERIMENT/tools/with-resources.sh" \
  --task task-8 --kind generation-kokoro -- \
  env PREVIEW_RESOURCE_GRANT_KIND=generation-kokoro \
  KOKORO_ARTIFACT_ROOT="$ARTIFACT_ROOT" \
  python3 "$HERE/generate_preview.py"
