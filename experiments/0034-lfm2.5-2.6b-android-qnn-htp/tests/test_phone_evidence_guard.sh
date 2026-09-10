#!/usr/bin/env bash
set -euo pipefail
EXP=$(cd "$(dirname "$0")/.." && pwd)
source "$EXP/tools/phone_evidence_guard.sh"
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
FAKE="$ROOT/fake-adb"
cat >"$FAKE" <<'SH'
#!/usr/bin/env bash
args="$*"
case "${FAKE_ADB_MODE:?}" in
  cleanup-query-transport)
    [[ "$args" == *"rm -rf"* ]] && exit 0
    [[ "$args" == *"if test ! -e"* ]] && { echo "adb transport lost" >&2; exit 1; }
    ;;
  cleanup-present)
    [[ "$args" == *"rm -rf"* ]] && exit 0
    [[ "$args" == *"if test ! -e"* ]] && { printf 'present\r\n'; exit 0; }
    ;;
  cleanup-absent)
    [[ "$args" == *"rm -rf"* ]] && exit 0
    [[ "$args" == *"if test ! -e"* ]] && { printf 'absent\r\n'; exit 0; }
    ;;
  pid-transport)
    [[ "$args" == *"pidof"* ]] && { echo "adb transport lost" >&2; exit 1; }
    ;;
  pid-present)
    [[ "$args" == *"pidof"* ]] && { echo 1234; exit 0; }
    ;;
  pid-absent)
    [[ "$args" == *"pidof"* ]] && exit 0
    ;;
esac
exit 99
SH
chmod +x "$FAKE"
mkdir "$ROOT/query" "$ROOT/present" "$ROOT/absent" "$ROOT/pid"
if FAKE_ADB_MODE=cleanup-query-transport phone_cleanup_remote "$FAKE" serial /remote "$ROOT/query"; then exit 2; fi
grep -Fx unverified_transport_failure "$ROOT/query/cleanup-status.txt"
FAKE_ADB_MODE=cleanup-present phone_cleanup_remote "$FAKE" serial /remote "$ROOT/present"
grep -Fx present "$ROOT/present/cleanup-status.txt"
FAKE_ADB_MODE=cleanup-absent phone_cleanup_remote "$FAKE" serial /remote "$ROOT/absent"
grep -Fx absent "$ROOT/absent/cleanup-status.txt"
if FAKE_ADB_MODE=pid-transport phone_capture_process_after "$FAKE" serial runner "$ROOT/pid/transport.out" "$ROOT/pid/transport.err"; then exit 3; fi
grep -F "adb transport lost" "$ROOT/pid/transport.err"
if FAKE_ADB_MODE=pid-present phone_capture_process_after "$FAKE" serial runner "$ROOT/pid/present.out" "$ROOT/pid/present.err"; then exit 4; fi
grep -Fx 1234 "$ROOT/pid/present.out"
FAKE_ADB_MODE=pid-absent phone_capture_process_after "$FAKE" serial runner "$ROOT/pid/absent.out" "$ROOT/pid/absent.err"
[[ ! -s "$ROOT/pid/absent.out" ]]
# The supervisor must set retention before exiting on unknown/non-absent PID state.
grep -A4 -F 'if ! phone_capture_process_after' "$EXP/tools/run_integrated_qnn_phone_diagnostic.sh" | grep -F 'retain_remote=1'
echo "phone evidence guard fake-ADB checks passed"
