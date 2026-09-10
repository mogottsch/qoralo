#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-fp16-fp16-long-20260910T171555Z-01/control.sh

record_self wrapper
cd "$REMOTE"
read up rest < /proc/uptime
printf '%s\n' "${up%%.*}" > evidence/start.uptime
/system/bin/sh "$REMOTE/model-entry.sh" > evidence/runner.stdout 2> evidence/runner.stderr &
child=$!
/system/bin/sh "$REMOTE/watchdog.sh" > evidence/watchdog.stdout 2> evidence/watchdog.stderr &
set +e
wait "$child"
rc=$?
printf '%s\n' "$rc" > evidence/exit-code.tmp
mv evidence/exit-code.tmp evidence/exit-code.txt
exit "$rc"
