#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes ]] || { echo 'set PHONE_USE_CONFIRMED=yes' >&2; exit 2; }
ROOT="$(git rev-parse --show-toplevel)";EXP="$ROOT/experiments/0019-moss-tts-nano-qnn-htp-android";STAGE="$EXP/.local/phone-stage"
ADB="${ADB:-/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe}";SERIAL=R5CW81PR8SY;PKG=com.openmoss.ttsnano.onnxruntime
RUN_ID="moss-0019-$(date -u +%Y%m%dT%H%M%SZ)-$$";TMP="/data/local/tmp/$RUN_ID";INTERNAL="files/$RUN_ID";OUT="$EXP/work/$RUN_ID"
[[ -f "$EXP/results/fixed-capacity-cpu-equivalence.json" ]] && python3 -c "import json;assert json.load(open('$EXP/results/fixed-capacity-cpu-equivalence.json'))['passed']"
[[ -f "$STAGE/stage-manifest.sha256" && -f "$STAGE/carrier.apk" ]] || { echo 'prepare phone stage first' >&2; exit 2; }
mkdir -p "$OUT" "$ROOT/artifacts/locks";exec 9>"$ROOT/artifacts/locks/phone.lock";flock -n 9 || { echo 'phone lock busy' >&2;exit 3; };export ADB_LIBUSB=1
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup(){ set +e;adb shell "run-as '$PKG' rm -rf '$INTERNAL'" >"$OUT/cleanup-internal.log" 2>&1;adb shell "rm -rf '$TMP'" >"$OUT/cleanup-tmp.log" 2>&1;adb uninstall "$PKG" >"$OUT/uninstall.log" 2>&1; }
trap cleanup EXIT
mapfile -t devs < <("$ADB" devices 9>&- | tr -d '\r' | awk 'NR>1&&$2=="device"{print $1}');[[ ${#devs[@]} == 1 && ${devs[0]} == "$SERIAL" ]] || exit 4
{ echo "serial=$(adb get-serialno|tr -d '\r')";echo "model=$(adb shell getprop ro.product.model|tr -d '\r')";echo "soc=$(adb shell getprop ro.soc.model|tr -d '\r')";echo "abi=$(adb shell getprop ro.product.cpu.abi|tr -d '\r')";echo "release=$(adb shell getprop ro.build.version.release|tr -d '\r')";echo "sdk=$(adb shell getprop ro.build.version.sdk|tr -d '\r')";echo "boot=$(adb shell getprop sys.boot_completed|tr -d '\r')";} >"$OUT/identity.txt"
grep -Fxq serial=$SERIAL "$OUT/identity.txt";grep -Fxq model=SM-S918B "$OUT/identity.txt";grep -Fxq soc=SM8550 "$OUT/identity.txt";grep -Fxq abi=arm64-v8a "$OUT/identity.txt";grep -Fxq boot=1 "$OUT/identity.txt"
cp "$STAGE/stage-manifest.sha256" "$STAGE/carrier.apk.sha256" "$STAGE/carrier-native-manifest.sha256" "$STAGE/stage-mode.txt" "$OUT/";adb install -r "$STAGE/carrier.apk" >"$OUT/install.log";LIB_ROOT=$(adb shell dumpsys package "$PKG" | tr -d '\r' | sed -n 's/^[[:space:]]*legacyNativeLibraryDir=//p' | head -1);[[ -n $LIB_ROOT ]];NATIVE_DIR="$LIB_ROOT/arm64";printf '%s\n' "$NATIVE_DIR" >"$OUT/native-library-dir.txt";adb shell "test -x '$NATIVE_DIR/libmossrunner.so'";adb shell dumpsys package "$PKG" >"$OUT/package-dumpsys.txt";grep -Fq 'libcdsprpc.so' "$OUT/package-dumpsys.txt";adb shell "cd '$NATIVE_DIR' && sha256sum *.so" | tr -d '\r' >"$OUT/remote-native-manifest.sha256";python3 - "$OUT/carrier-native-manifest.sha256" "$OUT/remote-native-manifest.sha256" <<'PY'
import sys
parse=lambda p:{line.split()[1].split('/')[-1]:line.split()[0] for line in open(p) if line.strip()}
a,b=parse(sys.argv[1]),parse(sys.argv[2]);assert a==b,(a,b)
PY
adb shell "rm -rf '$TMP'; mkdir -p '$TMP/upload' '$TMP/pull' '$TMP/dsp'; cp '$NATIVE_DIR/libQnnHtpV73Skel.so' '$TMP/dsp/'; chmod 755 '$TMP' '$TMP/upload' '$TMP/pull' '$TMP/dsp'; chmod 644 '$TMP/dsp/libQnnHtpV73Skel.so'"
adb shell "sha256sum '$TMP/dsp/libQnnHtpV73Skel.so'; stat -c '%a %n' '$TMP/dsp' '$TMP/dsp/libQnnHtpV73Skel.so'" | tr -d '\r' >"$OUT/remote-dsp-stage.txt";grep -Fq "$(grep 'libQnnHtpV73Skel.so' "$OUT/carrier-native-manifest.sha256" | awk '{print $1}')" "$OUT/remote-dsp-stage.txt";grep -Fq "755 $TMP/dsp" "$OUT/remote-dsp-stage.txt";grep -Fq "644 $TMP/dsp/libQnnHtpV73Skel.so" "$OUT/remote-dsp-stage.txt"
adb push "$STAGE/models" "$STAGE/models-cpu" "$STAGE/stage-manifest.sha256" "$TMP/upload/" >"$OUT/push.log" 2>&1
adb shell "cd '$TMP/upload' && sha256sum -c stage-manifest.sha256" >"$OUT/upload-sha256-check.txt"
adb shell "run-as '$PKG' sh -c \"mkdir -p '$INTERNAL/models' '$INTERNAL/models-cpu' '$INTERNAL/evidence/benchmark-profiles' '$INTERNAL/evidence/profile-profiles'; cp -r '$TMP/upload/models/.' '$INTERNAL/models/'; cp -r '$TMP/upload/models-cpu/.' '$INTERNAL/models-cpu/'; chmod -R u=rwX,go= '$INTERNAL'\""
adb shell "run-as '$PKG' sh -c \"cd '$INTERNAL' && sha256sum -c '$TMP/upload/stage-manifest.sha256'\"" >"$OUT/internal-sha256-check.txt"
run_route(){
  local label=$1 mode=$2 model_root=$3 runs=$4 profiling=$5 wav=$6
  local profile_dir="evidence/${label}-profiles" extra=""
  [[ $mode == qnn ]] && extra="--backend '$NATIVE_DIR/libQnnHtp.so'"
  adb shell dumpsys thermalservice >"$OUT/thermal-$label-before.txt"
  adb shell dumpsys battery >"$OUT/battery-$label-before.txt"
  local cmd="run-as '$PKG' sh -c \"cd '$INTERNAL' && export LD_LIBRARY_PATH='$NATIVE_DIR' ADSP_LIBRARY_PATH='$TMP/dsp;/vendor/dsp;/system/lib/rfsa/adsp;/vendor/lib/rfsa/adsp;/dsp' && '$NATIVE_DIR/libmossrunner.so' --mode '$mode' --model-root '$model_root' --output 'evidence/$wav' --result-json 'evidence/${label}-result.json' --setup-log 'evidence/${label}-setup.tsv' --profile-dir '$profile_dir' $extra --runs '$runs' --profiling '$profiling'\""
  printf '%s\n' "$cmd" >"$OUT/$label-command.txt";date -u +%FT%TZ >"$OUT/$label-wall-start.txt";local start end rc monitor_pid;start=$(date +%s.%N)
  (while true;do date -u +%FT%TZ;"$ADB" -s "$SERIAL" shell dumpsys thermalservice </dev/null 9>&-;sleep 30;done) >"$OUT/thermal-$label-during.txt" 2>&1 & monitor_pid=$!
  set +e;timeout --signal=TERM --kill-after=60 7200 "$ADB" -s "$SERIAL" shell "$cmd" </dev/null 9>&- >"$OUT/$label-stdout.log" 2>"$OUT/$label-stderr.log";rc=$?;kill "$monitor_pid" 2>/dev/null;wait "$monitor_pid" 2>/dev/null;set -e;end=$(date +%s.%N);echo "$rc" >"$OUT/$label-exit-code.txt";python3 -c "print(float('$end')-float('$start'))" >"$OUT/$label-process-wall-seconds.txt";date -u +%FT%TZ >"$OUT/$label-wall-end.txt";adb shell dumpsys thermalservice >"$OUT/thermal-$label-after.txt";adb shell dumpsys battery >"$OUT/battery-$label-after.txt";set +e;adb shell "run-as '$PKG' sh -c \"test -f '$INTERNAL/evidence/${label}-setup.tsv' && cat '$INTERNAL/evidence/${label}-setup.tsv'\"" | tr -d '\r' >"$OUT/$label-setup.tsv";set -e;[[ $rc == 0 ]];adb shell "run-as '$PKG' cat '$INTERNAL/evidence/${label}-result.json'" | tr -d '\r' >"$OUT/$label-result.json";python3 -c "import json;d=json.load(open('$OUT/$label-result.json'));assert d['result']=='passed' and d['profiling']=='$profiling'"
}
adb shell dumpsys thermalservice >"$OUT/thermal-before-cooldown.txt";sleep 120
run_route htp-benchmark qnn models 6 off moss-fixed-all-htp.wav
sleep 60
run_route htp-profile qnn models 1 detailed moss-fixed-all-htp-profile.wav
sleep 120
run_route cpu-benchmark cpu models-cpu 6 off moss-fixed-cpu.wav
sleep 60
run_route cpu-profile cpu models-cpu 1 detailed moss-fixed-cpu-profile.wav
adb shell "run-as '$PKG' sh -c \"cd '$INTERNAL' && find evidence -type f -exec sha256sum {} +\"" >"$OUT/remote-evidence-sha256.txt"
adb shell "rm -rf '$TMP/pull'; mkdir '$TMP/pull'; chmod 777 '$TMP/pull'; run-as '$PKG' cp -r '$INTERNAL/evidence/.' '$TMP/pull/'; chmod -R a+rX '$TMP/pull'"
adb pull "$TMP/pull/." "$OUT/evidence/" >"$OUT/pull.log" 2>&1
find "$OUT/evidence" -type f -print0 | sort -z | xargs -0 sha256sum >"$OUT/local-evidence-sha256.txt"
# Explicit cleanup and verification; disable trap only after success.
cleanup;trap - EXIT
[[ -z $(adb shell "find /data/local/tmp -maxdepth 1 -name '$RUN_ID' -print" | tr -d '\r') ]]
[[ -z $(adb shell pm list packages "$PKG" | tr -d '\r') ]]
printf 'cleanup=passed\nremote_tmp=absent\npackage=absent\napp_internal=removed_by_uninstall\n' >"$OUT/cleanup.txt"
echo "$OUT"
