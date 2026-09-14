#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-htp-power-htp-power-20260914T152014Z-03/control.sh

record_self watchdog
start=$(cat "$REMOTE/evidence/start.uptime")
case "$start" in ''|*[!0-9]*) exit 66;; esac
deadline=$((start + 90))
while [ ! -f "$REMOTE/evidence/exit-code.txt" ]; do
  read up rest < /proc/uptime
  now=${up%%.*}
  kb=$(du -sk "$REMOTE/evidence" | awk '{print $1}')
  case "$kb" in ''|*[!0-9]*) kb=16385;; esac
  if [ "$now" -ge "$deadline" ] || [ "$kb" -gt 16384 ]; then
    if [ "$kb" -gt 16384 ]; then reason=evidence_budget_or_unavailable; else reason=deadline90; fi
    printf '%s\n' "$reason" > "$REMOTE/evidence/watchdog-timeout.txt"
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
