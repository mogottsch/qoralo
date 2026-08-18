#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes ]] || exit 2
SERIAL=R5CW81PR8SY
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"; EXP="$REPO/experiments/0011-supertonic-official-fp32-phone-comparison"; STAGE="$EXP/.local/softplus-phase-stage"
ADB="${ADB:-/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe}"
RUN_ID="stable-softplus-vector-$(date -u +%Y%m%dT%H%M%SZ)-$$"; REMOTE="/data/local/tmp/vibevoice-0011-$RUN_ID"; OUT="$EXP/work/phone-$RUN_ID"
mkdir -p "$OUT" "$REPO/artifacts/locks"; exec 9>"$REPO/artifacts/locks/phone.lock"; flock -n 9 || exit 3; export ADB_LIBUSB=1
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup(){ set +e; adb shell "rm -rf '$REMOTE'" >"$OUT/cleanup.stdout.log" 2>"$OUT/cleanup.stderr.log"; echo $? >"$OUT/cleanup.exit-code.txt"; }; trap cleanup EXIT
"$ADB" devices -l 9>&- >"$OUT/devices.txt"; mapfile -t ds < <("$ADB" devices 9>&-|tr -d '\r'|awk 'NR>1&&$2=="device"{print $1}'); [[ ${#ds[@]} == 1 && ${ds[0]} == "$SERIAL" ]] || exit 4
{ echo serial=$(adb get-serialno|tr -d '\r'); echo model=$(adb shell getprop ro.product.model|tr -d '\r'); echo soc=$(adb shell getprop ro.soc.model|tr -d '\r'); echo abi=$(adb shell getprop ro.product.cpu.abi|tr -d '\r'); echo boot=$(adb shell getprop sys.boot_completed|tr -d '\r'); } >"$OUT/identity.txt"
grep -Fxq serial=$SERIAL "$OUT/identity.txt"; grep -Fxq model=SM-S918B "$OUT/identity.txt"; grep -Fxq soc=SM8550 "$OUT/identity.txt"; grep -Fxq abi=arm64-v8a "$OUT/identity.txt"; grep -Fxq boot=1 "$OUT/identity.txt"
cp "$STAGE/stage-manifest.sha256" "$STAGE/softplus-phase-policy.json" "$OUT/"; adb shell "mkdir '$REMOTE'"; adb push "$STAGE/." "$REMOTE/" >"$OUT/push.stdout.log" 2>"$OUT/push.stderr.log"
adb shell "chmod 755 '$REMOTE/component-runner' '$REMOTE'/*.so; cd '$REMOTE'; find . -type f ! -name stage-manifest.sha256 -exec sha256sum {} +|sort" >"$OUT/remote-stage-sha256.txt"
cmd="cd '$REMOTE' && mkdir vector && export LD_LIBRARY_PATH='$REMOTE' ADSP_LIBRARY_PATH='$REMOTE' && ./component-runner --component vector_estimator --model '$REMOTE/models/vector_estimator-stable-softplus.onnx' --inputs '$REMOTE/inputs' --output '$REMOTE/vector/output.raw' --backend '$REMOTE/libQnnHtp.so' --profile-prefix '$REMOTE/vector/profile' --runs 3"
echo "$cmd" >"$OUT/command.txt"; set +e; timeout 1800 "$ADB" -s "$SERIAL" shell "$cmd" </dev/null 9>&- >"$OUT/stdout.json" 2>"$OUT/stderr.log"; rc=$?; set -e; echo $rc >"$OUT/exit-code.txt"; [[ $rc == 0 ]]; grep -Fq '"result": "passed"' "$OUT/stdout.json"
adb pull "$REMOTE/vector/." "$OUT/vector/" >/dev/null
qnn=$(find "$OUT/vector" -name '*.qnn.csv' -type f|head -1); ort=$(find "$OUT/vector" -name 'profile_*.json' -type f|head -1); [[ -n $qnn && -n $ort ]]
for term in 'RPC (execute) time' 'QNN accelerator (execute) time' 'Accelerator (execute) time (cycles)' 'Number of HVX threads used'; do grep -Fq "$term" "$qnn"; done
grep -Fq ',4,COUNT,' "$qnn"
python3 - "$ort" <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); events=x if isinstance(x,list) else x.get('traceEvents',[])
p={e.get('args',{}).get('provider') for e in events if e.get('args',{}).get('provider')}
assert p=={'QNNExecutionProvider'},p
assert not any('CPUExecutionProvider' in json.dumps(e) for e in events)
PY
sha256sum "$OUT/vector/output.raw" "$qnn" "$ort" >"$OUT/evidence-sha256.txt"
echo "passed: $OUT"
