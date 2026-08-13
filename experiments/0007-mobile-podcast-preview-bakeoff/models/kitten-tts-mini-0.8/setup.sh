#!/usr/bin/env bash
# Build only an ignored project-local environment; never use sudo or system pip.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
ARTIFACT_ROOT="${KITTEN_ARTIFACT_ROOT:-$ROOT/artifacts/kitten-tts-mini-0.8}"
VENV="${KITTEN_VENV:-$ARTIFACT_ROOT/venv}"
WHEEL="$ARTIFACT_ROOT/downloads/kittentts-0.8.0-py3-none-any.whl"

command -v python3 >/dev/null || { echo "BLOCKED: python3 is required to validate committed provenance" >&2; exit 69; }
# Fail closed on model/package/voice/plan/lock drift before creating an
# environment or downloading anything. The pins file is the sole wheel authority.
python3 "$HERE/verify_pins.py"
mapfile -t RELEASE_PIN < <(python3 - "$HERE/pins.json" <<'PY'
import json, sys
implementation = json.load(open(sys.argv[1], encoding="utf-8"))["implementation"]
print(implementation["release_asset_url"])
print(implementation["release_asset_sha256"])
PY
)
[[ ${#RELEASE_PIN[@]} -eq 2 ]] || { echo "BLOCKED: invalid committed wheel authority" >&2; exit 65; }
WHEEL_URL="${RELEASE_PIN[0]}"
WHEEL_SHA256="${RELEASE_PIN[1]}"

command -v uv >/dev/null || { echo "BLOCKED: uv is required in user/project scope" >&2; exit 69; }
command -v curl >/dev/null || { echo "BLOCKED: curl is required to retrieve the exact official release asset" >&2; exit 69; }
command -v espeak-ng >/dev/null || { echo "BLOCKED: espeak-ng is required; provide a permitted user/project-local copy on PATH" >&2; exit 69; }
[[ -f "${KITTEN_ESPEAK_LIBRARY:-/usr/lib/libespeak-ng.so}" ]] || { echo "BLOCKED: set KITTEN_ESPEAK_LIBRARY to an available permitted libespeak-ng" >&2; exit 69; }
[[ -d "${KITTEN_ESPEAK_DATA:-/usr/share/espeak-ng-data}" ]] || { echo "BLOCKED: set KITTEN_ESPEAK_DATA to an available permitted espeak-ng-data directory" >&2; exit 69; }
mkdir -p "$(dirname -- "$WHEEL")"
if [[ ! -f "$WHEEL" ]]; then curl --fail --location --proto '=https' --tlsv1.2 --output "$WHEEL" "$WHEEL_URL"; fi
printf '%s  %s\n' "$WHEEL_SHA256" "$WHEEL" | sha256sum --check --status || { echo "BLOCKED: official 0.8.0 wheel hash mismatch" >&2; exit 65; }
uv venv --clear --python 3.11 --no-python-downloads "$VENV"
# Upstream's exact 0.8.0 asset has stale 0.1.0 METADATA; uv requires this
# narrowly scoped acknowledgement of that verified filename/metadata mismatch.
UV_SKIP_WHEEL_FILENAME_CHECK=1 UV_PROJECT_ENVIRONMENT="$VENV" uv sync --project "$HERE" --locked --no-dev
"$VENV/bin/python" - <<'PY'
import kittentts, onnxruntime
# The official 0.8 release asset is mislabelled internally as 0.1.0. Identity is
# therefore established by release URL/name/hash, not this stale metadata field.
assert kittentts.__version__ == "0.1.0", kittentts.__version__
assert "CPUExecutionProvider" in onnxruntime.get_available_providers()
assert not {"CUDAExecutionProvider", "TensorrtExecutionProvider"} & set(onnxruntime.get_available_providers())
print("official-release-asset=0.8.0 runtime-metadata=0.1.0 provider=CPUExecutionProvider")
PY
printf 'isolated environment: %s\n' "$VENV"
