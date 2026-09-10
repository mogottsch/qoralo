#!/usr/bin/env bash
set -euo pipefail
OUT=$(cd "$(dirname "$0")" && pwd)
export TMPDIR="$OUT/tmp"
mkdir -p "$TMPDIR"
exec 9>/home/moritz/dev/vibevoice-android-spike/artifacts/locks/phone.lock
flock -n 9 || { echo LOCK_BUSY; exit 75; }
echo "UI_QA_LOCK_HELD serial=emulator-5556"
echo $$ > "$OUT/supervisor.pid"
child=''
cleanup() {
 trap - EXIT INT TERM
 if [[ -n "$child" ]] && kill -0 "$child" 2>/dev/null; then
  timeout 15s /home/moritz/Android/Sdk/platform-tools/adb -s emulator-5556 emu kill 9>&- >"$OUT/emulator-cleanup.log" 2>&1 || true
  kill -TERM "$child" 2>/dev/null || true
  for i in {1..20}; do kill -0 "$child" 2>/dev/null || break; sleep .5; done
  kill -KILL "$child" 2>/dev/null || true
  wait "$child" 2>/dev/null || true
 fi
 echo UI_QA_EMULATOR_STOPPED_LOCK_RELEASING
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
/home/moritz/Android/Sdk/emulator/emulator -avd fg-test -port 5556 -memory 2048 -cores 2 -read-only -no-snapshot-load -no-snapshot-save -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -accel on 9>&- >"$OUT/emulator.log" 2>&1 &
child=$!; echo "$child" > "$OUT/emulator.pid"
wait "$child"
