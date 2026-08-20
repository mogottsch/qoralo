#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes ]]||{ echo set_PHONE_USE_CONFIRMED >&2;exit 2; }
SERIAL=R5CW81PR8SY;ROOT=$(cd "$(dirname "$0")/../../.."&&pwd);EXP="$ROOT/experiments/0014-pocket-fp-onnx-qnn-htp";STAGE="$EXP/.local/alba-cpu-stage";ADB=${ADB:-/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe};ID="$(date -u +%Y%m%dT%H%M%SZ)-$$";REMOTE="/data/local/tmp/experiment-0014-pocket-alba-cpu-$ID";OUT="$EXP/work/quality-recovery/phone-alba-cpu-$ID";mkdir -p "$OUT" "$ROOT/artifacts/locks";exec 9>>"$ROOT/artifacts/locks/phone.lock";flock -n 9||{ echo phone_lock_busy >&2;exit 3;};export ADB_LIBUSB=1
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup(){ set +e;adb shell "rm -rf '$REMOTE'" >"$OUT/cleanup.stdout" 2>"$OUT/cleanup.stderr";echo $? >"$OUT/cleanup.exit"; }
trap cleanup EXIT
L=$("$ADB" devices -l 9>&-|tr -d '\r');printf '%s\n' "$L">"$OUT/devices.txt";mapfile -t D < <(printf '%s\n' "$L"|awk 'NR>1&&$2=="device"{print $1}');[[ ${#D[@]} == 1 && ${D[0]} == "$SERIAL" ]]||exit 4
{ echo serial=$(adb get-serialno|tr -d '\r');echo model=$(adb shell getprop ro.product.model|tr -d '\r');echo soc=$(adb shell getprop ro.soc.model|tr -d '\r');echo abi=$(adb shell getprop ro.product.cpu.abi|tr -d '\r');echo boot=$(adb shell getprop sys.boot_completed|tr -d '\r');}>"$OUT/identity.txt";grep -Fxq serial=$SERIAL "$OUT/identity.txt";grep -Fxq model=SM-S918B "$OUT/identity.txt";grep -Fxq soc=SM8550 "$OUT/identity.txt";grep -Fxq abi=arm64-v8a "$OUT/identity.txt";grep -Fxq boot=1 "$OUT/identity.txt"
adb shell "mkdir -p '$REMOTE'";adb push "$STAGE/." "$REMOTE/" >"$OUT/push.stdout" 2>"$OUT/push.stderr";adb shell "chmod 755 '$REMOTE/pocket_alba_cpu_runner';cd '$REMOTE';find . -type f -exec sha256sum {} +|sort"|tr -d '\r'>"$OUT/remote-stage-sha256.txt"
set +e
timeout 900 "$ADB" -s "$SERIAL" shell "cd '$REMOTE' && export LD_LIBRARY_PATH='$REMOTE/lib' && ./pocket_alba_cpu_runner '$REMOTE/model' '$REMOTE/assets/alba-flow-cache-v1.f32' '$REMOTE/assets/numpy-randomstate-seed0-temp0p3-134x32.f32' '$REMOTE/alba-cpu.wav' 0.3 134 >'$REMOTE/result.json' 2>'$REMOTE/result.stderr'" </dev/null 9>&-
run_rc=$?;set -e;printf '%s\n' "$run_rc">"$OUT/runner.exit"
adb shell "cd '$REMOTE';find . -maxdepth 1 -type f \( -name 'alba-cpu.wav' -o -name 'result.*' \) -exec sha256sum {} +|sort"|tr -d '\r'>"$OUT/remote-output-sha256.txt"||true
for f in result.json result.stderr alba-cpu.wav;do adb pull "$REMOTE/$f" "$OUT/$f" >/dev/null 2>&1||true;done
cleanup;trap - EXIT
if adb shell test -e "$REMOTE";then echo cleanup_failed >&2;exit 5;else echo cleanup_ok>"$OUT/cleanup-proof.txt";fi
printf '%s\n' "$OUT"
[[ $run_rc == 0 ]]||exit "$run_rc"
