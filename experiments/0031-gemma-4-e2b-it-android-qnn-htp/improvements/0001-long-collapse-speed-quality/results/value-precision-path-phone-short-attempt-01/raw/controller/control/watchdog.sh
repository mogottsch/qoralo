#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-value-value-short-20260911T124722Z-01/control.sh

record_self watchdog
start=$(cat "$REMOTE/evidence/start.uptime")
case "$start" in ''|*[!0-9]*) exit 66;; esac
deadline=$((start + 1800))
while [ ! -f "$REMOTE/evidence/exit-code.txt" ]; do
  read up rest < /proc/uptime
  now=${up%%.*}
  if [ "$now" -ge "$deadline" ]; then
    printf 'deadline1800\n' > "$REMOTE/evidence/watchdog-timeout.txt"
    pid=$(cat "$REMOTE/evidence/model.pid") || exit 66
    born=$(cat "$REMOTE/evidence/model.start") || exit 66
    signal_owned model "$pid" "$born" TERM || exit 67
    # Bounded grace; never escalate without a fresh identity check.
    sleep 5
    signal_owned model "$pid" "$born" KILL || exit 67
    exit 124
  fi
  sleep 1
done
