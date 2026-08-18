#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes ]] || { echo "set PHONE_USE_CONFIRMED=yes" >&2; exit 2; }
SERIAL=R5CW81PR8SY
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
EXP="$REPO/experiments/0011-supertonic-official-fp32-phone-comparison"
STAGE="$EXP/.local/htp-stage"
ADB="${ADB:-/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe}"
RUN_ID="fp32-htp-components-$(date -u +%Y%m%dT%H%M%SZ)-$$"
REMOTE="/data/local/tmp/vibevoice-0011-$RUN_ID"
OUT="$EXP/work/phone-$RUN_ID"
mkdir -p "$OUT" "$REPO/artifacts/locks"
exec 9>"$REPO/artifacts/locks/phone.lock"
flock -n 9 || { echo "phone lock is held" >&2; exit 3; }
export ADB_LIBUSB=1
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup(){ set +e; adb shell "rm -rf '$REMOTE'" >"$OUT/cleanup.stdout.log" 2>"$OUT/cleanup.stderr.log"; echo $? >"$OUT/cleanup.exit-code.txt"; }
trap cleanup EXIT
"$ADB" devices -l 9>&- >"$OUT/devices.txt"
mapfile -t devices < <("$ADB" devices 9>&- | tr -d '\r' | awk 'NR>1&&$2=="device"{print $1}')
[[ ${#devices[@]} == 1 && ${devices[0]} == "$SERIAL" ]] || exit 4
{
 echo "serial=$(adb get-serialno|tr -d '\r')"; echo "model=$(adb shell getprop ro.product.model|tr -d '\r')"; echo "soc=$(adb shell getprop ro.soc.model|tr -d '\r')"; echo "abi=$(adb shell getprop ro.product.cpu.abi|tr -d '\r')"; echo "boot=$(adb shell getprop sys.boot_completed|tr -d '\r')";
} >"$OUT/identity.txt"
grep -Fxq "serial=$SERIAL" "$OUT/identity.txt"; grep -Fxq model=SM-S918B "$OUT/identity.txt"; grep -Fxq soc=SM8550 "$OUT/identity.txt"; grep -Fxq abi=arm64-v8a "$OUT/identity.txt"; grep -Fxq boot=1 "$OUT/identity.txt"
cp "$STAGE/stage-manifest.sha256" "$STAGE/htp-probe-policy.json" "$OUT/"
adb shell "mkdir '$REMOTE'"; adb push "$STAGE/." "$REMOTE/" >"$OUT/push.stdout.log" 2>"$OUT/push.stderr.log"
adb shell "chmod 755 '$REMOTE/component-runner' '$REMOTE'/*.so; cd '$REMOTE'; find . -type f ! -name stage-manifest.sha256 -exec sha256sum {} + | sort" >"$OUT/remote-stage-sha256.txt"
failed=0
for component in duration_predictor text_encoder vocoder; do
  mkdir "$OUT/$component"
  command="cd '$REMOTE' && mkdir -p '$component' && export LD_LIBRARY_PATH='$REMOTE' ADSP_LIBRARY_PATH='$REMOTE' && ./component-runner --component '$component' --model '$REMOTE/models/$component.onnx' --inputs '$REMOTE/inputs' --output '$REMOTE/$component/output.raw' --backend '$REMOTE/libQnnHtp.so' --profile-prefix '$REMOTE/$component/profile' --runs 2"
  printf '%s\n' "$command" >"$OUT/$component/command.txt"
  set +e; timeout 1800 "$ADB" -s "$SERIAL" shell "$command" </dev/null 9>&- >"$OUT/$component/stdout.json" 2>"$OUT/$component/stderr.log"; rc=$?; set -e
  echo "$rc" >"$OUT/$component/exit-code.txt"
  if [[ $rc != 0 ]]; then failed=1; continue; fi
  grep -Fq '"result": "passed"' "$OUT/$component/stdout.json" || { failed=1; continue; }
  adb shell "cd '$REMOTE/$component'; sha256sum output.raw profile*" >"$OUT/$component/remote-sha256.txt"
  adb pull "$REMOTE/$component/." "$OUT/$component/" >/dev/null
  profile=$(find "$OUT/$component" -name '*.qnn.csv' -type f | head -1)
  [[ -n $profile ]] || { failed=1; continue; }
  for term in 'RPC (execute) time' 'QNN accelerator (execute) time' 'Accelerator (execute) time (cycles)' 'Number of HVX threads used'; do grep -Fq "$term" "$profile" || failed=1; done
  sha256sum "$OUT/$component/output.raw" >"$OUT/$component/local-output-sha256.txt"
done
echo "$failed" >"$OUT/any-failure.txt"
[[ $failed == 0 ]]
printf 'passed: %s\n' "$OUT"
