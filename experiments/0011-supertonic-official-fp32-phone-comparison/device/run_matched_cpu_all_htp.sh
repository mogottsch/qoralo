#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes ]] || exit 2
SERIAL=R5CW81PR8SY
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"; EXP="$REPO/experiments/0011-supertonic-official-fp32-phone-comparison"; STAGE="$EXP/.local/softplus-phase-stage"
ADB="${ADB:-/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe}"
RUN_ID="matched-cpu-all-htp-$(date -u +%Y%m%dT%H%M%SZ)-$$"; REMOTE="/data/local/tmp/vibevoice-0011-$RUN_ID"; OUT="$EXP/work/phone-$RUN_ID"
mkdir -p "$OUT" "$REPO/artifacts/locks"; exec 9>"$REPO/artifacts/locks/phone.lock"; flock -n 9 || exit 3; export ADB_LIBUSB=1
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup(){ set +e; adb shell "rm -rf '$REMOTE'" >"$OUT/cleanup.stdout.log" 2>"$OUT/cleanup.stderr.log"; echo $? >"$OUT/cleanup.exit-code.txt"; }; trap cleanup EXIT
"$ADB" devices -l 9>&- >"$OUT/devices.txt"; mapfile -t ds < <("$ADB" devices 9>&-|tr -d '\r'|awk 'NR>1&&$2=="device"{print $1}'); [[ ${#ds[@]} == 1 && ${ds[0]} == "$SERIAL" ]] || exit 4
{ echo serial=$(adb get-serialno|tr -d '\r'); echo model=$(adb shell getprop ro.product.model|tr -d '\r'); echo soc=$(adb shell getprop ro.soc.model|tr -d '\r'); echo abi=$(adb shell getprop ro.product.cpu.abi|tr -d '\r'); echo boot=$(adb shell getprop sys.boot_completed|tr -d '\r'); } >"$OUT/identity.txt"
grep -Fxq serial=$SERIAL "$OUT/identity.txt"; grep -Fxq model=SM-S918B "$OUT/identity.txt"; grep -Fxq soc=SM8550 "$OUT/identity.txt"; grep -Fxq abi=arm64-v8a "$OUT/identity.txt"; grep -Fxq boot=1 "$OUT/identity.txt"
cp "$STAGE/stage-manifest.sha256" "$STAGE/matched-e2e-protocol.json" "$STAGE/softplus-phase-policy.json" "$OUT/"
adb shell "mkdir '$REMOTE'"; adb push "$STAGE/." "$REMOTE/" >"$OUT/push.stdout.log" 2>"$OUT/push.stderr.log"
adb shell "chmod 755 '$REMOTE/e2e-runner' '$REMOTE'/*.so; cd '$REMOTE'; find . -type f ! -name stage-manifest.sha256 -exec sha256sum {} +|sort" >"$OUT/remote-stage-sha256.txt"
run_route(){
  local route=$1 mode vector wav raw extra
  if [[ $route == all-htp ]]; then mode=qnn; vector=vector_estimator-stable-softplus.onnx; wav=official-fp32-all-htp.wav; raw=official-fp32-all-htp.raw; extra="--backend '$REMOTE/libQnnHtp.so'"; else mode=cpu; vector=vector_estimator-original.onnx; wav=official-fp32-phone-cpu.wav; raw=official-fp32-phone-cpu.raw; extra=""; fi
  mkdir -p "$OUT/$route/profiles"
  sleep 120
  adb shell dumpsys thermalservice >"$OUT/$route/thermal-before.txt"
  local cmd="cd '$REMOTE' && rm -rf 'profiles-$route' && mkdir 'profiles-$route' && export LD_LIBRARY_PATH='$REMOTE' ADSP_LIBRARY_PATH='$REMOTE' && ./e2e-runner --mode '$mode' --model-root '$REMOTE/models' --vector-model '$REMOTE/models/$vector' --vocoder-model '$REMOTE/models/vocoder.onnx' --transcript '$REMOTE/transcript.txt' --output-wav '$REMOTE/$wav' --output-raw '$REMOTE/$raw' --profile-dir '$REMOTE/profiles-$route' --runs 6 $extra"
  echo "$cmd" >"$OUT/$route/command.txt"; date -u +%Y-%m-%dT%H:%M:%S.%NZ >"$OUT/$route/wall-start.txt"; start=$(date +%s.%N)
  set +e; timeout 2400 "$ADB" -s "$SERIAL" shell "$cmd" </dev/null 9>&- >"$OUT/$route/stdout.json" 2>"$OUT/$route/stderr.log"; rc=$?; set -e
  end=$(date +%s.%N); date -u +%Y-%m-%dT%H:%M:%S.%NZ >"$OUT/$route/wall-end.txt"; python3 -c "print(float('$end')-float('$start'))" >"$OUT/$route/process-wall-seconds.txt"; echo $rc >"$OUT/$route/exit-code.txt"; [[ $rc == 0 ]]; grep -Fq '"result": "passed"' "$OUT/$route/stdout.json"
  adb shell dumpsys thermalservice >"$OUT/$route/thermal-after.txt"
  adb shell "cd '$REMOTE'; sha256sum '$wav' '$raw' profiles-$route/*" >"$OUT/$route/remote-evidence-sha256.txt"
  adb pull "$REMOTE/$wav" "$OUT/$route/$wav" >/dev/null; adb pull "$REMOTE/$raw" "$OUT/$route/$raw" >/dev/null; adb pull "$REMOTE/profiles-$route/." "$OUT/$route/profiles/" >/dev/null
  sha256sum "$OUT/$route/$wav" "$OUT/$route/$raw" >"$OUT/$route/output-sha256.txt"
}
run_route all-htp
# Do not start the CPU route unless every all-HTP profile is unambiguous.
python3 - "$OUT/all-htp/profiles" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); ort=list(root.glob('*.json')); qnn=list(root.glob('*.qnn.csv'))
assert len(ort)==4,(len(ort),ort); assert len(qnn)==4,(len(qnn),qnn)
for p in ort:
 d=json.load(open(p)); ev=d if isinstance(d,list) else d.get('traceEvents',[])
 providers={e.get('args',{}).get('provider') for e in ev if e.get('args',{}).get('provider')}
 assert providers=={'QNNExecutionProvider'},(p,providers)
 assert not any('CPUExecutionProvider' in json.dumps(e) for e in ev),p
for p in qnn:
 text=p.read_text()
 for term in ('RPC (execute) time','QNN accelerator (execute) time','Accelerator (execute) time (cycles)','Number of HVX threads used'): assert term in text,(p,term)
 counts=[line.split(',')[2] for line in text.splitlines() if line.endswith('Number of HVX threads used')]
 assert counts and set(counts)=={'4'},(p,counts)
PY
run_route cpu
python3 - "$OUT/cpu/profiles" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); ort=list(root.glob('*.json')); assert len(ort)==4
for p in ort:
 d=json.load(open(p));ev=d if isinstance(d,list) else d.get('traceEvents',[])
 providers={e.get('args',{}).get('provider') for e in ev if e.get('args',{}).get('provider')}
 assert providers=={'CPUExecutionProvider'},(p,providers)
 assert not any('QNNExecutionProvider' in json.dumps(e) for e in ev),p
assert not list(root.glob('*.qnn.csv'))
PY
echo "passed: $OUT"
