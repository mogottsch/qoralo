#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes ]] || { echo 'set PHONE_USE_CONFIRMED=yes' >&2; exit 2; }
SERIAL=R5CW81PR8SY
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
EXP="$REPO/experiments/0016-pocket-onnx-qnn-hybrid-android";STAGE="$EXP/.local/stage"
ADB=${ADB:-/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe}
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$";REMOTE="/data/local/tmp/experiment-0016-pocket-hybrid-$RUN_ID";OUT="$EXP/work/phone-$RUN_ID";mkdir -p "$OUT" "$REPO/artifacts/locks"
exec 9>>"$REPO/artifacts/locks/phone.lock";flock -n 9||{ echo phone_lock_busy >&2;exit 3; };export ADB_LIBUSB=1
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
cleanup(){ set +e;adb shell "rm -rf '$REMOTE'" >"$OUT/cleanup.stdout" 2>"$OUT/cleanup.stderr";echo $? >"$OUT/cleanup.exit"; }
trap cleanup EXIT
LIST=$("$ADB" devices -l 9>&-|tr -d '\r');printf '%s\n' "$LIST">"$OUT/devices.txt";mapfile -t D < <(printf '%s\n' "$LIST"|awk 'NR>1&&$2=="device"{print $1}');[[ ${#D[@]} == 1 && ${D[0]} == "$SERIAL" ]]||exit 4
{ echo serial=$(adb get-serialno|tr -d '\r');echo model=$(adb shell getprop ro.product.model|tr -d '\r');echo soc=$(adb shell getprop ro.soc.model|tr -d '\r');echo abi=$(adb shell getprop ro.product.cpu.abi|tr -d '\r');echo boot=$(adb shell getprop sys.boot_completed|tr -d '\r');}>"$OUT/identity.txt"
grep -Fxq serial=$SERIAL "$OUT/identity.txt";grep -Fxq model=SM-S918B "$OUT/identity.txt";grep -Fxq soc=SM8550 "$OUT/identity.txt";grep -Fxq abi=arm64-v8a "$OUT/identity.txt";grep -Fxq boot=1 "$OUT/identity.txt"
adb shell "mkdir -p '$REMOTE/output-proof' '$REMOTE/output-perf' '$REMOTE/profiles' '$REMOTE/lib' '$REMOTE/model'";adb push "$STAGE/." "$REMOTE/" >"$OUT/push.stdout" 2>"$OUT/push.stderr"
cat >"$OUT/qnn-proof.config" <<EOF
DEBUG=1
GraphOptimizationLevel=99
LogSeverityLevel=0
ProfilingFilePrefix=$REMOTE/profiles/ort
SessionConfig.session.disable_cpu_ep_fallback=0
backend_path=$REMOTE/lib/libQnnHtp.so
profiling_level=detailed
profiling_file_path=$REMOTE/profiles/qnn.csv
offload_graph_io_quantization=0
htp_performance_mode=burst
soc_model=43
EOF
cat >"$OUT/qnn-perf.config" <<EOF
GraphOptimizationLevel=99
LogSeverityLevel=2
SessionConfig.session.disable_cpu_ep_fallback=0
backend_path=$REMOTE/lib/libQnnHtp.so
offload_graph_io_quantization=0
htp_performance_mode=burst
soc_model=43
EOF
adb push "$OUT/qnn-proof.config" "$REMOTE/qnn-proof.config" >/dev/null;adb push "$OUT/qnn-perf.config" "$REMOTE/qnn-perf.config" >/dev/null
adb shell "chmod 755 '$REMOTE/pocket_hybrid_bench';cd '$REMOTE';find . -type f ! -path './output-*/*' -exec sha256sum {} +|sort"|tr -d '\r'>"$OUT/remote-stage-sha256.txt"
ENV="export LD_LIBRARY_PATH='$REMOTE/lib' ADSP_LIBRARY_PATH='$REMOTE/lib;/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp;/vendor/dsp'"
# One instrumented generation establishes provider assignment and physical activity.
timeout 3600 "$ADB" -s "$SERIAL" shell "cd '$REMOTE' && $ENV && ./pocket_hybrid_bench '$REMOTE/model' '$REMOTE/output-proof' '$REMOTE/qnn-proof.config' 1 >'$REMOTE/proof.json' 2>'$REMOTE/proof.stderr'" </dev/null 9>&-
# Fresh process without profiling overhead supplies benchmark timings.
timeout 3600 "$ADB" -s "$SERIAL" shell "cd '$REMOTE' && $ENV && ./pocket_hybrid_bench '$REMOTE/model' '$REMOTE/output-perf' '$REMOTE/qnn-perf.config' 6 >'$REMOTE/perf.json' 2>'$REMOTE/perf.stderr'" </dev/null 9>&-
adb shell "cd '$REMOTE';sha256sum output-proof/*.wav output-perf/*.wav proof.json perf.json profiles/*"|tr -d '\r'>"$OUT/remote-output-sha256.txt"
adb pull "$REMOTE/proof.json" "$OUT/proof.json" >/dev/null;adb pull "$REMOTE/proof.stderr" "$OUT/proof.stderr" >/dev/null;adb pull "$REMOTE/perf.json" "$OUT/perf.json" >/dev/null;adb pull "$REMOTE/perf.stderr" "$OUT/perf.stderr" >/dev/null;adb pull "$REMOTE/output-proof" "$OUT/" >/dev/null;adb pull "$REMOTE/output-perf" "$OUT/" >/dev/null;adb pull "$REMOTE/profiles" "$OUT/" >/dev/null
cleanup;trap - EXIT
if adb shell test -e "$REMOTE";then echo cleanup_failed >&2;exit 5;else echo cleanup_ok>"$OUT/cleanup-proof.txt";fi
printf '%s\n' "$OUT"
