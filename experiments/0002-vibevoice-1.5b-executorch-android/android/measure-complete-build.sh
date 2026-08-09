#!/usr/bin/env bash
# Reproducible cold/warm measurement of the accepted locked-reference build.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
BASE="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android"
OUT=${ARTIFACT_DIR:-$ROOT/artifacts/0002/lane-d/complete-build-measurement}
RESULT=${RESULT:-$BASE/results/complete-build-xnnpack.json}
PREFLIGHT=${PREFLIGHT:-$ROOT/artifacts/0002/lane-d/locked-reference/preflight.json}
APK=${APK:-$BASE/android/app/build/outputs/apk/debug/app-debug.apk}
PY=${PYTHON:-python3}
PKG=dev.moket.vibevoiceprobe
mkdir -p "$OUT" "$ROOT/artifacts/locks"
exec 9>"$ROOT/artifacts/locks/phone.lock"
flock 9

mapfile -t DEVICES < <(adb devices | awk 'NR>1 && NF {print $1" "$2}')
[[ ${#DEVICES[@]} == 1 && ${DEVICES[0]} == *' device' ]] || { echo 'expected one authorized phone' >&2; exit 2; }
[[ $(adb shell getprop ro.product.model | tr -d '\r') == SM-S918B ]] || { echo 'measurement requires SM-S918B' >&2; exit 2; }
[[ -s "$PREFLIGHT" && -s "$APK" ]] || { echo 'run android/run-locked-reference-generation.sh first (preflight and APK required)' >&2; exit 2; }
adb shell run-as "$PKG" test -s files/models/qwen/final.pte || { echo 'accepted model package is not deployed' >&2; exit 2; }

capture_thermal() {
  local label=$1
  adb shell dumpsys thermalservice >"$OUT/thermal-$label.txt"
  adb shell dumpsys battery >"$OUT/battery-$label.txt"
}
run_process() {
  local label=$1
  adb shell am force-stop "$PKG"
  adb shell run-as "$PKG" rm -f files/generation-result.json
  local start end done=false
  start=$($PY -c 'import time; print(time.monotonic_ns())')
  adb shell am start -W -n "$PKG/.GenerationProbeActivity" >"$OUT/activity-$label.txt"
  for _ in $(seq 1 900); do
    if adb shell run-as "$PKG" test -f files/generation-result.json; then done=true; break; fi
    sleep 1
  done
  end=$($PY -c 'import time; print(time.monotonic_ns())')
  [[ $done == true ]] || { echo "$label run timed out" >&2; exit 3; }
  adb exec-out run-as "$PKG" cat files/generation-result.json >"$OUT/device-$label.json"
  printf '%s\n' "$($PY -c "print(($end-$start)/1e9)")" >"$OUT/wall-$label.txt"
}

capture_thermal before
run_process cold
sleep 15
run_process warm
capture_thermal after

# Device/runtime and thermal observations are kept raw alongside a compact JSON record.
DEPLOYED=$(adb shell run-as "$PKG" du -sb files/models 2>/dev/null | awk '{print $1}' | tr -d '\r' || true)
export ROOT BASE OUT PREFLIGHT APK RESULT DEPLOYED
"$PY" - <<'PY'
import hashlib,json,os,re,subprocess
from pathlib import Path
out=Path(os.environ['OUT']); root=Path(os.environ['ROOT'])
def prop(name): return subprocess.check_output(['adb','shell','getprop',name],text=True).strip()
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def battery(path):
    text=path.read_text(errors='replace')
    m=re.search(r'^\s*temperature:\s*(\d+)',text,re.M)
    return None if not m else int(m.group(1))/10
def thermal_values(path):
    text=path.read_text(errors='replace')
    status=re.search(r'^Thermal Status:\s*(\d+)',text,re.M)
    values={name:float(value) for value,name in re.findall(r'Temperature\{mValue=([0-9.]+).*?mName=([^,}]+)',text)}
    return {'status':None if not status else int(status.group(1)),'status_scale':'Android THERMAL_STATUS_* (0=NONE)',
            'ap_temperature_c':values.get('AP'),'skin_temperature_c':values.get('SKIN')}
thermal={}
for label in ('before','after'):
    t=out/f'thermal-{label}.txt'; b=out/f'battery-{label}.txt'
    thermal[label]={**thermal_values(t),'battery_temperature_c':battery(b),'thermalservice_sha256':digest(t),'thermalservice_path':str(t.relative_to(root)),'battery_path':str(b.relative_to(root))}
raw={
 'schema_version':1,
 'runs':[{'label':label,'wall_seconds':float((out/f'wall-{label}.txt').read_text()),'device_result':json.loads((out/f'device-{label}.json').read_text())} for label in ('cold','warm')],
 'deployed_module_bytes':int(os.environ['DEPLOYED']) if os.environ['DEPLOYED'].isdigit() else None,
 'device':{'manufacturer':prop('ro.product.manufacturer'),'model':prop('ro.product.model'),'device':prop('ro.product.device'),'soc':prop('ro.soc.model'),'android_release':prop('ro.build.version.release'),'api_level':int(prop('ro.build.version.sdk')),'abi':prop('ro.product.cpu.abi'),'build_fingerprint':prop('ro.build.fingerprint'),'kernel':prop('ro.kernel.version') or subprocess.check_output(['adb','shell','uname','-r'],text=True).strip()},
 'thermal':thermal,
 'commands':['flock artifacts/locks/phone.lock experiments/0002-vibevoice-1.5b-executorch-android/android/measure-complete-build.sh','python3 -m unittest discover -s experiments/0002-vibevoice-1.5b-executorch-android/tests -p test_complete_build_measurement.py','python3 -m json.tool experiments/0002-vibevoice-1.5b-executorch-android/results/complete-build-xnnpack.json >/dev/null']}
(out/'raw.json').write_text(json.dumps(raw,indent=2)+'\n')
PY
"$PY" "$BASE/export/complete_build_measurement.py" "$OUT/raw.json" "$PREFLIGHT" "$APK" "$RESULT" --commit "$(git rev-parse HEAD)"
