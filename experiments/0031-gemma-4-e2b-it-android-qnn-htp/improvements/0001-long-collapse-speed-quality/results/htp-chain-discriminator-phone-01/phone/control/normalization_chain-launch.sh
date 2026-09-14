#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-htp-chain-htp-chains-20260914T160058Z-01/normalization_chain-control.sh

record_self wrapper
cd "$REMOTE"
read up rest < /proc/uptime
printf '%s\n' "${up%%.*}" > evidence/normalization_chain.start.uptime
/system/bin/sh "$REMOTE/normalization_chain-model-entry.sh" > evidence/normalization_chain.runner.stdout 2> evidence/normalization_chain.runner.stderr &
child=$!
/system/bin/sh "$REMOTE/normalization_chain-watchdog.sh" > evidence/normalization_chain.watchdog.stdout 2> evidence/normalization_chain.watchdog.stderr &
set +e
wait "$child"
rc=$?
printf '%s\n' "$rc" > evidence/normalization_chain.exit-code.tmp
mv evidence/normalization_chain.exit-code.tmp evidence/normalization_chain.exit-code.txt
exit "$rc"
