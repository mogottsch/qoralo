#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-htp-chain-htp-chains-20260914T160058Z-01/normalization_chain-control.sh

record_self watchdog
start=$(cat "$REMOTE/evidence/normalization_chain.start.uptime")
case "$start" in ''|*[!0-9]*) exit 66;; esac
deadline=$((start + 90))
while [ ! -f "$REMOTE/evidence/normalization_chain.exit-code.txt" ]; do
  read up rest < /proc/uptime
  now=${up%%.*}
  kb=$(du -sk "$REMOTE/evidence" | awk '{print $1}')
  case "$kb" in ''|*[!0-9]*) kb=16385;; esac
  if [ "$now" -ge "$deadline" ] || [ "$kb" -gt 16384 ]; then
    if [ "$kb" -gt 16384 ]; then reason=evidence_budget_or_unavailable; else reason=deadline90; fi
    printf '%s\n' "$reason" > "$REMOTE/evidence/normalization_chain.watchdog-timeout.txt"
    pid=$(cat "$REMOTE/evidence/normalization_chain.model.pid") || exit 66
    born=$(cat "$REMOTE/evidence/normalization_chain.model.start") || exit 66
    signal_owned model "$pid" "$born" TERM || exit 67
    # Bounded grace; never escalate without a fresh identity check.
    sleep 5
    signal_owned model "$pid" "$born" KILL || exit 67
    exit 124
  fi
  sleep 1
done
