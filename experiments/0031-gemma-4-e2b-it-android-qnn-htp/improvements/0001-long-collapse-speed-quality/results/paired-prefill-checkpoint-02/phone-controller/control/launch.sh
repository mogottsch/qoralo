#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-paired-paired-prefill-20260912T140747Z-02/control.sh

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
