#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PROJECT="$ROOT/podcast-app"
LOCK="$ROOT/artifacts/locks/phone.lock"
APP_ID=dev.qoralo.podcast.internal
SERIAL=${ANDROID_SERIAL:-R5CW81PR8SY}
ADB=${ADB:-adb}
APK="$PROJECT/app/build/outputs/apk/debug/app-debug.apk"
PACKS="$PROJECT/.local/model-packs"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE="$PROJECT/.local/phone-install/$STAMP"
REMOTE="/data/local/tmp/qoralo-podcast-$STAMP-$$"

if [[ ${PODCAST_PHONE_PRIORITY:-} != approved ]]; then
  echo "PODCAST_PHONE_PRIORITY=approved is required after explicit Pi priority" >&2
  exit 64
fi
[[ -f "$APK" ]] || { echo "missing debug APK: $APK" >&2; exit 66; }
[[ -f "$PACKS/gemma-4-e2b/current/manifest.json" ]] || { echo "missing prepared Gemma pack" >&2; exit 66; }
[[ -f "$PACKS/supertonic-3/current/manifest.json" ]] || { echo "missing prepared Supertonic pack" >&2; exit 66; }
mkdir -p "$EVIDENCE"
"$PROJECT/tools/verify_apk_runtime.py" --apk "$APK" --output "$EVIDENCE/apk-runtime-provenance.json" | tee "$EVIDENCE/apk-preflight.txt"

exec 9>"$LOCK"
flock -n 9 || { echo "phone lock busy: $LOCK" >&2; exit 75; }
cleanup() {
  "$ADB" -s "$SERIAL" shell rm -rf "$REMOTE" 9>&- >"$EVIDENCE/cleanup.stdout" 2>"$EVIDENCE/cleanup.stderr" || true
}
trap cleanup EXIT

"$ADB" -s "$SERIAL" get-state 9>&- | tee "$EVIDENCE/device-state.txt"
MODEL=$("$ADB" -s "$SERIAL" shell getprop ro.product.model 9>&- | tr -d '\r')
SOC=$("$ADB" -s "$SERIAL" shell getprop ro.soc.model 9>&- | tr -d '\r')
printf 'serial=%s\nmodel=%s\nsoc=%s\n' "$SERIAL" "$MODEL" "$SOC" | tee "$EVIDENCE/identity.txt"
[[ "$MODEL" == "SM-S918B" && "$SOC" == "SM8550" ]] || { echo "unexpected phone identity" >&2; exit 65; }
sha256sum "$APK" "$PACKS/gemma-4-e2b/current/manifest.json" "$PACKS/supertonic-3/current/manifest.json" >"$EVIDENCE/local-sha256.txt"

# Personal user only: never install into the work profile.
"$ADB" -s "$SERIAL" install -r -t --user 0 "$APK" 9>&- | tee "$EVIDENCE/install.txt"
"$ADB" -s "$SERIAL" shell mkdir -p "$REMOTE" 9>&-
"$ADB" -s "$SERIAL" push "$PACKS/gemma-4-e2b/current" "$REMOTE/gemma-current" 9>&- | tee "$EVIDENCE/push-gemma.txt"
"$ADB" -s "$SERIAL" push "$PACKS/supertonic-3/current" "$REMOTE/supertonic-current" 9>&- | tee "$EVIDENCE/push-supertonic.txt"
"$ADB" -s "$SERIAL" shell "chmod -R a+rX '$REMOTE'" 9>&-

"$ADB" -s "$SERIAL" shell "run-as '$APP_ID' sh -c 'rm -rf no_backup/model-packs/gemma-4-e2b/current no_backup/model-packs/supertonic-3/current; mkdir -p no_backup/model-packs/gemma-4-e2b no_backup/model-packs/supertonic-3; cp -R $REMOTE/gemma-current no_backup/model-packs/gemma-4-e2b/current; cp -R $REMOTE/supertonic-current no_backup/model-packs/supertonic-3/current'" 9>&- | tee "$EVIDENCE/install-packs.txt"
"$ADB" -s "$SERIAL" shell "run-as '$APP_ID' sha256sum no_backup/model-packs/gemma-4-e2b/current/manifest.json no_backup/model-packs/supertonic-3/current/manifest.json" 9>&- | tee "$EVIDENCE/remote-manifest-sha256.txt"

printf 'result=installed\nevidence=%s\n' "$EVIDENCE"
