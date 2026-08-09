#!/usr/bin/env bash
# Materialize the official pinned source and its frozen uv environment under ignored artifacts/.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACT_ROOT="${POCKET_TTS_ARTIFACT_ROOT:-$EXPERIMENT/artifacts/setup/pocket-tts}"
SOURCE="$ARTIFACT_ROOT/source"
REVISION=d108410d23eef7e01db282f9442891162dbc3db6
REPOSITORY=https://github.com/kyutai-labs/pocket-tts.git

mkdir -p "$ARTIFACT_ROOT"
if [[ ! -d "$SOURCE/.git" ]]; then
  [[ ! -e "$SOURCE" ]] || { echo "refusing non-git source path: $SOURCE" >&2; exit 65; }
  git clone --filter=blob:none --no-checkout "$REPOSITORY" "$SOURCE"
fi
ORIGIN="$(git -C "$SOURCE" remote get-url origin)"
case "$ORIGIN" in
  "$REPOSITORY"|git@github.com:kyutai-labs/pocket-tts.git) ;;
  *) echo "Pocket TTS origin drift: $ORIGIN" >&2; exit 65 ;;
esac
git -C "$SOURCE" fetch --depth=1 origin "$REVISION"
git -C "$SOURCE" checkout --detach "$REVISION"
[[ "$(git -C "$SOURCE" rev-parse HEAD)" == "$REVISION" ]] || {
  echo "Pocket TTS revision drift" >&2; exit 65;
}
[[ -z "$(git -C "$SOURCE" status --porcelain --untracked-files=no)" ]] || {
  echo "Pocket TTS tracked source is dirty" >&2; exit 65;
}

# The upstream uv.lock is part of the pinned source commit. --frozen fails rather
# than resolving newer dependencies, and the venv remains model-local.
# Do not use upstream's .python-version (3.10): its NumPy 2.2.6 conflicts
# with the source's explicit warning that generation before NumPy 2.5 is
# incorrect. The frozen lock currently selects 2.4.3 on 3.14 too, so apply the
# shared protocol's exact 2.5.1 corrective pin after syncing every other lock.
(cd "$SOURCE" && UV_PROJECT_ENVIRONMENT="$ARTIFACT_ROOT/.venv" uv sync --python 3.14 --frozen --no-dev)
uv pip install --python "$ARTIFACT_ROOT/.venv/bin/python" 'numpy==2.5.1'
"$ARTIFACT_ROOT/.venv/bin/python" - <<'PY'
import numpy
assert numpy.__version__ == "2.5.1", f"refusing NumPy drift: {numpy.__version__}"
PY
printf 'Pocket TTS %s ready at %s\n' "$REVISION" "$SOURCE"
