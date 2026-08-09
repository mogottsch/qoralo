#!/usr/bin/env bash
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
BUILD="$REPO/experiments/0007-mobile-podcast-preview-bakeoff/artifacts/publication-build"
SLUG=${1:-vibevoice-android}
PORT=${PREVIEW_API_PORT:-18000}

python3 "$HERE/build_publication.py" --output "$BUILD"
# The WAVs stay ignored: curl reads them directly from the build directory.
test -z "$(git -C "$REPO" diff --cached --name-only -- '*.wav' '*.flac' '*.mp3' '*.m4a')"
RAW=$(kubectl -n static-preview get secret static-preview-api-tokens -o jsonpath='{.data.SHARE_API_TOKENS}' | base64 -d)
TOKEN=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["moritz"])' "$RAW")
kubectl -n static-preview port-forward svc/static-preview-api "$PORT:8000" >"$BUILD/port-forward.log" 2>&1 &
PF=$!
trap 'kill "$PF" 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep .25; done
ETAG=$(curl -fsS -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$PORT/api/previews/$SLUG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["etag"])')
FORM=(
  -F "files=@$BUILD/index.html;filename=index.html;type=text/html"
  -F "files=@$BUILD/bakeoff-manifest.json;filename=bakeoff-manifest.json;type=application/json"
  -F "files=@$BUILD/crew-tasks.json;filename=crew-tasks.json;type=application/json"
)
while IFS= read -r -d '' wav; do
  relative=${wav#"$BUILD/"}
  FORM+=( -F "files=@$wav;filename=$relative;type=audio/wav" )
done < <(find "$BUILD/audio" -type f -name '*.wav' -print0 | sort -z)
RESPONSE=$(curl -fsS -X PUT -H "Authorization: Bearer $TOKEN" -H "If-Match: $ETAG" "${FORM[@]}" "http://127.0.0.1:$PORT/api/previews/$SLUG")
printf '%s\n' "$RESPONSE"
# Audit after upload: publication must not have staged ignored evidence.
test -z "$(git -C "$REPO" diff --cached --name-only | grep -E '(^|/)(artifacts/|.*\\.(wav|flac|mp3|m4a)$)' || true)"
