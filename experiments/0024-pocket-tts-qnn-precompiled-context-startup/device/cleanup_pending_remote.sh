#!/usr/bin/env bash
set -euo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes && ${PHONE_COORDINATION_CLEARED:-} == yes ]] || exit 2
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
EXP="$ROOT/experiments/0024-pocket-tts-qnn-precompiled-context-startup"
ADB=/usr/bin/adb
SERIAL=R5CW81PR8SY
REMOTE=/data/local/tmp/experiment-0024-pocket-context-context-20260823T085809Z-225310
EXPECTED_ADB_SHA256=506163fd859265bc895b64eeba28252fb0f7864decf8b42dac3cbf9711240f9f
OUT="$EXP/work/pending-cleanup-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$OUT" "$ROOT/artifacts/locks"
[[ -f $ADB && -x $ADB && ! -L $ADB && $(realpath "$ADB") == "$ADB" ]] || exit 2
[[ $(sha256sum "$ADB"|awk '{print $1}') == "$EXPECTED_ADB_SHA256" ]] || exit 2
unset ADB_LIBUSB
exec 9>>"$ROOT/artifacts/locks/phone.lock"
flock -n 9 || exit 3
adb(){ "$ADB" -s "$SERIAL" "$@" </dev/null 9>&-; }
"$ADB" version </dev/null 9>&- >"$OUT/adb-version.txt"
grep -Fxq 'Version 37.0.0-android-tools' "$OUT/adb-version.txt"
LIST=$("$ADB" devices -l 9>&-); printf '%s\n' "$LIST" >"$OUT/devices.txt"
mapfile -t D < <(printf '%s\n' "$LIST"|awk 'NR>1&&$2=="device"{print $1}')
[[ ${#D[@]} == 1 && ${D[0]} == "$SERIAL" ]] || exit 4
{
 echo serial=$(adb get-serialno); echo manufacturer=$(adb shell getprop ro.product.manufacturer)
 echo model=$(adb shell getprop ro.product.model); echo device=$(adb shell getprop ro.product.device)
 echo soc=$(adb shell getprop ro.soc.model); echo abi=$(adb shell getprop ro.product.cpu.abi)
 echo boot=$(adb shell getprop sys.boot_completed); echo verified_boot=$(adb shell getprop ro.boot.verifiedbootstate)
 echo flash_locked=$(adb shell getprop ro.boot.flash.locked)
} >"$OUT/identity.txt"
for v in serial=$SERIAL manufacturer=samsung model=SM-S918B device=dm3q soc=SM8550 abi=arm64-v8a boot=1 verified_boot=green flash_locked=1; do grep -Fxq "$v" "$OUT/identity.txt"; done
if adb shell "rm -rf '$REMOTE'" >"$OUT/remove.stdout" 2>"$OUT/remove.stderr"; then remove_rc=0; else remove_rc=$?; fi
printf '%s\n' "$remove_rc" >"$OUT/remove.exit"
if adb get-state >"$OUT/transport.stdout" 2>"$OUT/transport.stderr"; then trc=0; else trc=$?; fi
if [[ $trc == 0 ]]; then if adb shell test -e "$REMOTE" >"$OUT/exists.stdout" 2>"$OUT/exists.stderr"; then erc=0; else erc=$?; fi; else erc=99; fi
printf '%s\n' "$trc" >"$OUT/transport.exit"; printf '%s\n' "$erc" >"$OUT/exists.exit"
set +e; status=$(python3 "$EXP/tools/classify_cleanup_status.py" "$trc" "$erc"); src=$?; set -e
printf '%s\n' "$status" >"$OUT/status.txt"
[[ $remove_rc == 0 && $src == 0 && $status == verified_absent ]] || exit 5
printf '%s\n' "$REMOTE" >"$OUT/remote-root.txt"
echo "$OUT"
