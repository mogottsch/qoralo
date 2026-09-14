#!/system/bin/sh
set -eu
. /data/local/tmp/SYNTHETIC_ONLY/epsilon_add-control.sh

record_self wrapper
cd "$REMOTE"
read up rest < /proc/uptime
printf '%s\n' "${up%%.*}" > evidence/epsilon_add.start.uptime
/system/bin/sh "$REMOTE/epsilon_add-model-entry.sh" > evidence/epsilon_add.runner.stdout 2> evidence/epsilon_add.runner.stderr &
child=$!
/system/bin/sh "$REMOTE/epsilon_add-watchdog.sh" > evidence/epsilon_add.watchdog.stdout 2> evidence/epsilon_add.watchdog.stderr &
set +e
wait "$child"
rc=$?
printf '%s\n' "$rc" > evidence/epsilon_add.exit-code.tmp
mv evidence/epsilon_add.exit-code.tmp evidence/epsilon_add.exit-code.txt
exit "$rc"
