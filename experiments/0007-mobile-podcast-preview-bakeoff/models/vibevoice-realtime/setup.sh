#!/usr/bin/env bash
# Create an isolated, pinned environment and fetch immutable official inputs.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACTS="${VIBEVOICE_REALTIME_ARTIFACTS:-$HERE/artifacts}"
SOURCE="$ARTIFACTS/source/microsoft-vibevoice"
MODEL="$ARTIFACTS/model/microsoft-VibeVoice-Realtime-0.5B"
TOKENIZER="$ARTIFACTS/model/Qwen2.5-0.5B-tokenizer"
VENV="$ARTIFACTS/venv"
SOURCE_REV=94da20d98b2fa7688e9cbfaf7692ddb4954f7600
MODEL_REV=6bce5f06044837fe6d2c5d7a71a84f0416bd57e4
TOKENIZER_REV=060db6499f32faf8b98477b0a26969ef7d8b9987

command -v uv >/dev/null || { echo "uv is required; system Python will not be modified" >&2; exit 2; }
mkdir -p "$ARTIFACTS"
if [[ ! -x "$VENV/bin/python" ]]; then uv venv --python 3.11 "$VENV"; fi
"$VENV/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 11)'
uv pip sync --python "$VENV/bin/python" "$HERE/requirements.lock" \
  --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match

if [[ ! -d "$SOURCE/.git" ]]; then
  git clone --filter=blob:none https://github.com/microsoft/VibeVoice.git "$SOURCE"
fi
git -C "$SOURCE" fetch --no-tags origin "$SOURCE_REV"
git -C "$SOURCE" checkout --detach "$SOURCE_REV"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$SOURCE_REV"
uv pip install --python "$VENV/bin/python" --no-deps -e "$SOURCE"

# --local-dir is isolated from the shared HF cache; the revision is never a branch name.
HF_HUB_DISABLE_TELEMETRY=1 MODEL_DIR="$MODEL" MODEL_REV="$MODEL_REV" "$VENV/bin/python" - <<'PY'
import os
from huggingface_hub import snapshot_download
resolved = snapshot_download(
    "microsoft/VibeVoice-Realtime-0.5B", revision=os.environ["MODEL_REV"],
    local_dir=os.environ["MODEL_DIR"], ignore_patterns=["figures/*"],
)
print(resolved)
PY
printf '%s\n' "$MODEL_REV" > "$MODEL/.model-revision"
HF_HUB_DISABLE_TELEMETRY=1 TOKENIZER_DIR="$TOKENIZER" TOKENIZER_REV="$TOKENIZER_REV" "$VENV/bin/python" - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(
    "Qwen/Qwen2.5-0.5B", revision=os.environ["TOKENIZER_REV"],
    local_dir=os.environ["TOKENIZER_DIR"],
    allow_patterns=["config.json", "merges.txt", "tokenizer.json", "tokenizer_config.json", "vocab.json"],
)
PY
printf '%s\n' "$TOKENIZER_REV" > "$TOKENIZER/.model-revision"
"$VENV/bin/python" "$HERE/verify_pins.py" --source "$SOURCE" --model "$MODEL" --tokenizer "$TOKENIZER" --environment "$VENV"
