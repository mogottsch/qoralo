#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-htp-mean-add-mean-add-20260914T164350Z-01/mean_edge-control.sh

record_self wrapper
cd "$REMOTE"
read up rest < /proc/uptime
printf '%s\n' "${up%%.*}" > evidence/mean_edge.start.uptime
/system/bin/sh "$REMOTE/mean_edge-model-entry.sh" > evidence/mean_edge.runner.stdout 2> evidence/mean_edge.runner.stderr &
child=$!
/system/bin/sh "$REMOTE/mean_edge-watchdog.sh" > evidence/mean_edge.watchdog.stdout 2> evidence/mean_edge.watchdog.stderr &
set +e
wait "$child"
rc=$?
printf '%s\n' "$rc" > evidence/mean_edge.exit-code.tmp
mv evidence/mean_edge.exit-code.tmp evidence/mean_edge.exit-code.txt
exit "$rc"
