#!/usr/bin/env bash
set -euo pipefail

[[ ${PHONE_USE_CONFIRMED:-} == yes ]] || { echo "set PHONE_USE_CONFIRMED=yes" >&2; exit 2; }
SERIAL=R5CW81PR8SY
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
EXP="$REPO/experiments/0011-supertonic-official-fp32-phone-comparison"
STAGE="$EXP/.local/cpu-stage"
ADB="${ADB:-/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe}"
RUN_ID="fp32-cpu-$(date -u +%Y%m%dT%H%M%SZ)-$$"
REMOTE="/data/local/tmp/vibevoice-0011-$RUN_ID"
OUT="$EXP/work/phone-$RUN_ID"
mkdir -p "$OUT" "$REPO/artifacts/locks"

exec 9>"$REPO/artifacts/locks/phone.lock"
flock -n 9 || { echo "phone lock is held" >&2; exit 3; }
export ADB_LIBUSB=1
adb() { "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup() {
  set +e
  adb shell "rm -rf '$REMOTE'" >"$OUT/cleanup.stdout.log" 2>"$OUT/cleanup.stderr.log"
  echo $? >"$OUT/cleanup.exit-code.txt"
}
trap cleanup EXIT

"$ADB" devices -l 9>&- >"$OUT/devices.txt"
mapfile -t devices < <("$ADB" devices 9>&- | tr -d '\r' | awk 'NR>1 && $2=="device" {print $1}')
[[ ${#devices[@]} == 1 && ${devices[0]} == "$SERIAL" ]] || { echo "device identity gate failed" >&2; exit 4; }
{
  echo "serial=$(adb get-serialno | tr -d '\r')"
  echo "model=$(adb shell getprop ro.product.model | tr -d '\r')"
  echo "soc=$(adb shell getprop ro.soc.model | tr -d '\r')"
  echo "abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')"
  echo "boot=$(adb shell getprop sys.boot_completed | tr -d '\r')"
} >"$OUT/identity.txt"
grep -Fxq "serial=$SERIAL" "$OUT/identity.txt"
grep -Fxq 'model=SM-S918B' "$OUT/identity.txt"
grep -Fxq 'soc=SM8550' "$OUT/identity.txt"
grep -Fxq 'abi=arm64-v8a' "$OUT/identity.txt"
grep -Fxq 'boot=1' "$OUT/identity.txt"

cp "$STAGE/stage-manifest.sha256" "$OUT/"
adb shell "mkdir '$REMOTE'"
adb push "$STAGE/." "$REMOTE/" >"$OUT/push.stdout.log" 2>"$OUT/push.stderr.log"
adb shell "chmod 755 '$REMOTE/e2e-runner' '$REMOTE'/*.so; cd '$REMOTE'; find . -type f ! -name stage-manifest.sha256 -exec sha256sum {} + | sort" >"$OUT/remote-stage-sha256.txt"

COMMAND="cd '$REMOTE' && mkdir profiles-cpu && export LD_LIBRARY_PATH='$REMOTE' && ./e2e-runner --mode cpu --model-root '$REMOTE/models' --vector-model '$REMOTE/models/vector_estimator.onnx' --vocoder-model '$REMOTE/models/vocoder.onnx' --transcript '$REMOTE/transcript.txt' --output-wav '$REMOTE/cpu.wav' --output-raw '$REMOTE/cpu.raw' --profile-dir '$REMOTE/profiles-cpu' --runs 4"
printf '%s\n' "$COMMAND" >"$OUT/cpu.command.txt"
set +e
timeout 1800 "$ADB" -s "$SERIAL" shell "$COMMAND" </dev/null 9>&- >"$OUT/cpu.stdout.json" 2>"$OUT/cpu.stderr.log"
rc=$?
set -e
printf '%s\n' "$rc" >"$OUT/cpu.exit-code.txt"
[[ $rc == 0 ]]
grep -Fq '"result": "passed"' "$OUT/cpu.stdout.json"
adb shell "cd '$REMOTE'; sha256sum cpu.wav cpu.raw profiles-cpu/*" >"$OUT/remote-output-sha256.txt"
adb pull "$REMOTE/cpu.wav" "$OUT/cpu.wav" >/dev/null
adb pull "$REMOTE/cpu.raw" "$OUT/cpu.raw" >/dev/null
mkdir "$OUT/profiles-cpu"
adb pull "$REMOTE/profiles-cpu/." "$OUT/profiles-cpu/" >/dev/null
if grep -Rni 'QNNExecutionProvider\|QNN_' "$OUT/profiles-cpu" >"$OUT/qnn-profile-events.txt"; then
  echo "unexpected QNN profile event in CPU-only run" >&2
  exit 5
fi
printf 'zero QNN events across CPU-only ORT profiles\n' >"$OUT/qnn-profile-events.txt"
sha256sum "$OUT/cpu.wav" "$OUT/cpu.raw" >"$OUT/local-output-sha256.txt"
printf 'passed: %s\n' "$OUT"
