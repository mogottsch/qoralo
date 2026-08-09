#!/usr/bin/env bash
# Create only an ignored, project-local environment; never invokes apt/sudo or system pip.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
VENV="${KOKORO_VENV:-$ROOT/artifacts/kokoro/venv}"

command -v uv >/dev/null || {
  echo "BLOCKED: uv is required to create the isolated Python environment; install uv in user/project scope." >&2
  exit 69
}
command -v espeak-ng >/dev/null || {
  echo "BLOCKED: executable 'espeak-ng' is required by misaki's English OOD fallback. Provide it as a permitted project-local artifact and prepend its directory to PATH; this script will not run apt/sudo." >&2
  exit 69
}

uv venv --clear --python 3.11 --no-python-downloads "$VENV"
UV_PROJECT_ENVIRONMENT="$VENV" uv sync --project "$HERE" --locked --no-dev
"$VENV/bin/python" - <<'PY'
import kokoro, sys
assert kokoro.__version__ == "0.9.4", kokoro.__version__
assert sys.version_info[:2] == (3, 11), sys.version
print(f"kokoro={kokoro.__version__} python={sys.version.split()[0]}")
PY
printf 'isolated environment: %s\n' "$VENV"
