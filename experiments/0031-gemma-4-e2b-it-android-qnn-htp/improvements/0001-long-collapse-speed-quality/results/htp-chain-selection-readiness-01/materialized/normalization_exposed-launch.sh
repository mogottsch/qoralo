#!/system/bin/sh
set -eu
. /data/local/tmp/SYNTHETIC_ONLY/normalization_exposed-control.sh

record_self wrapper
cd "$REMOTE"
read up rest < /proc/uptime
printf '%s\n' "${up%%.*}" > evidence/normalization_exposed.start.uptime
/system/bin/sh "$REMOTE/normalization_exposed-model-entry.sh" > evidence/normalization_exposed.runner.stdout 2> evidence/normalization_exposed.runner.stderr &
child=$!
/system/bin/sh "$REMOTE/normalization_exposed-watchdog.sh" > evidence/normalization_exposed.watchdog.stdout 2> evidence/normalization_exposed.watchdog.stderr &
set +e
wait "$child"
rc=$?
printf '%s\n' "$rc" > evidence/normalization_exposed.exit-code.tmp
mv evidence/normalization_exposed.exit-code.tmp evidence/normalization_exposed.exit-code.txt
exit "$rc"
