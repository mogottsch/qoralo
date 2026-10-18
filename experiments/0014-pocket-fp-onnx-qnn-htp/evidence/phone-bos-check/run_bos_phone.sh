#!/usr/bin/env bash
# Bounded CPU-only phone check of the old Pocket runner's first-step BOS input.
# One 300 s run window, 40 s per run (retained run was ~7 s), 8 planned runs, no retries.
set -uo pipefail
[[ ${PHONE_USE_CONFIRMED:-} == yes ]] || { echo 'set PHONE_USE_CONFIRMED=yes' >&2; exit 2; }
[[ ${PHONE_SLOT_SCHEDULED:-no} == yes ]] || { echo 'Pi must schedule the shared-phone slot' >&2; exit 3; }
ROOT=/home/moritz/dev/vibevoice-android-spike; W=/tmp/qoralo-story-v3/phone; S=$W/stage
SERIAL=R5CW81PR8SY; ID=$(date -u +%Y%m%dT%H%M%SZ); OUT=$W/run-$ID; REMOTE=/data/local/tmp/pocket-bos-check-$ID-$$
WINDOW=300; RUN_NATIVE_TIMEOUT=40; RUN_HOST_TIMEOUT=75; PREFLIGHT_ONLY=${PREFLIGHT_ONLY:-no}
PKGS=(dev.qoralo.podcast.internal dev.vibevoice.podcast.internal)
mkdir -p "$OUT/raw"
exec 9>"$ROOT/artifacts/locks/phone.lock"
flock -n 9 || { echo 'phone.lock busy; do not race' >&2; exit 4; }
adb(){ timeout -k 5 "${ADB_T:-60}" /usr/bin/adb -s "$SERIAL" "$@" </dev/null 9>&-; }
log(){ echo "$(date -u +%H:%M:%S) $*" | tee -a "$OUT/controller.log"; }
STAGED=no; ABORT_RC=0
cleanup(){
  trap - EXIT INT TERM; local proof="$OUT/cleanup-proof.txt"
  if [[ $STAGED != yes ]]; then echo cleanup_not_needed_nothing_staged >"$proof"; return; fi
  local st; st=$(ADB_T=20 adb get-state 2>&1 | tr -d '\r')
  if [[ $st != device ]]; then echo "cleanup_unknown_device_unreachable($st) remote=$REMOTE" >"$proof"; log "CLEANUP INCOMPLETE: device unreachable"; return; fi
  ADB_T=30 adb shell "sh '$REMOTE/ctl/terminate_owned.sh' '$REMOTE'" >"$OUT/terminate.out" 2>&1; local trc=$?
  if [[ $trc != 0 ]]; then echo "cleanup_incomplete_owned_process_not_terminated rc=$trc remote=$REMOTE" >"$proof"; log "CLEANUP INCOMPLETE: owned process still present; stage kept"; return; fi
  local o rc; o=$(ADB_T=60 adb shell "rm -rf '$REMOTE'; if [ -e '$REMOTE' ]; then echo PRESENT; else echo ABSENT; fi" 2>&1 | tr -d '\r'); rc=${PIPESTATUS[0]}
  if [[ $o == ABSENT ]]; then echo cleanup_ok >"$proof"; log "cleanup ok (explicit ABSENT)"
  elif [[ $o == PRESENT ]]; then echo "cleanup_failed_present remote=$REMOTE" >"$proof"; log "CLEANUP FAILED: still present"
  else echo "cleanup_unknown($o) remote=$REMOTE" >"$proof"; log "CLEANUP UNKNOWN"; fi
}
trap 'ABORT_RC=130; log "signal: aborting"; exit 130' INT TERM
trap cleanup EXIT

# --- identity and pinned serial
L=$(/usr/bin/adb devices -l 9>&- | tr -d '\r'); printf '%s\n' "$L" >"$OUT/devices.txt"
mapfile -t D < <(printf '%s\n' "$L" | awk 'NR>1&&$2=="device"{print $1}')
[[ ${#D[@]} == 1 && ${D[0]} == "$SERIAL" ]] || { log "BLOCKED: expected exactly $SERIAL"; exit 5; }
{ echo model=$(adb shell getprop ro.product.model|tr -d '\r'); echo soc=$(adb shell getprop ro.soc.model|tr -d '\r'); echo abi=$(adb shell getprop ro.product.cpu.abi|tr -d '\r'); echo boot=$(adb shell getprop sys.boot_completed|tr -d '\r'); echo android=$(adb shell getprop ro.build.version.release|tr -d '\r'); } >"$OUT/identity.txt"

# --- fresh preflight: read-only. FAIL or UNPARSED blocks; nothing is stopped or changed.
BLOCK=0; pf(){ echo "$1 $2 $3" | tee -a "$OUT/preflight.txt" >>"$OUT/controller.log"; [[ $2 == PASS ]] || BLOCK=1; }
raw(){ adb shell "$1" 2>&1 | tr -d '\r' >"$OUT/raw/pf-$2.txt"; }
raw 'cat /proc/loadavg' load; raw 'grep -E "MemAvailable|MemTotal" /proc/meminfo' mem; raw 'df -k /data/local/tmp | tail -1' df
raw 'dumpsys battery' battery; raw 'dumpsys thermalservice' thermal; raw 'dumpsys audio' audio
raw 'dumpsys activity activities' activities; raw 'dumpsys power' power
LOAD=$(awk '{print $1}' "$OUT/raw/pf-load.txt" | head -1)
[[ $LOAD =~ ^[0-9.]+$ ]] && { awk -v l="$LOAD" 'BEGIN{exit !(l<=3.0)}' && pf load PASS "$LOAD<=3.0" || pf load FAIL "$LOAD>3.0"; } || pf load UNPARSED "$LOAD"
AV=$(awk '/MemAvailable/{print $2}' "$OUT/raw/pf-mem.txt"); [[ $AV =~ ^[0-9]+$ ]] && { [[ $AV -ge 1572864 ]] && pf mem PASS "${AV}KiB>=1.5GiB (retained peak 712312kB)" || pf mem FAIL "${AV}KiB<1.5GiB"; } || pf mem UNPARSED "$AV"
FREE=$(awk '{print $4}' "$OUT/raw/pf-df.txt"); [[ $FREE =~ ^[0-9]+$ ]] && { [[ $FREE -ge 1572864 ]] && pf disk PASS "${FREE}KiB" || pf disk FAIL "${FREE}KiB<1.5GiB"; } || pf disk UNPARSED "$FREE"
BT=$(awk -F: '/temperature/{gsub(/ /,"",$2);print $2;exit}' "$OUT/raw/pf-battery.txt"); [[ $BT =~ ^[0-9]+$ ]] && { [[ $BT -le 420 ]] && pf battery_temp PASS "${BT}x0.1C" || pf battery_temp FAIL "${BT}x0.1C>42C"; } || pf battery_temp UNPARSED "$BT"
TH=$(grep -m1 -oE 'Thermal Status: [0-9]+' "$OUT/raw/pf-thermal.txt" | awk '{print $3}'); [[ $TH =~ ^[0-9]+$ ]] && { [[ $TH -eq 0 ]] && pf thermal PASS "status=$TH" || pf thermal FAIL "status=$TH"; } || pf thermal UNPARSED "none"
NPB=$(grep -c 'AudioPlaybackConfiguration piid:' "$OUT/raw/pf-audio.txt"); if [[ $NPB -gt 0 || -n $(grep -m1 'Events log: playback activity' "$OUT/raw/pf-audio.txt") ]]; then AUD=$(grep 'AudioPlaybackConfiguration piid:' "$OUT/raw/pf-audio.txt" | grep -c 'state:started'); [[ $AUD == 0 ]] && pf audio_active PASS "players_listed=$NPB started=0" || pf audio_active FAIL "started_players=$AUD"; else pf audio_active UNPARSED "no playback section"; fi
if grep -q -E 'ResumedActivity|topResumedActivity' "$OUT/raw/pf-activities.txt"; then FG=$(grep -E 'ResumedActivity' "$OUT/raw/pf-activities.txt" | head -3 | tr '\n' ' '); if printf '%s' "$FG" | grep -q -E 'qoralo|vibevoice'; then pf foreground FAIL "app in foreground"; else pf foreground PASS "app not foreground"; fi; else pf foreground UNPARSED "no resumed activity line"; fi
for PKG in "${PKGS[@]}"; do
  PIDS=$(adb shell "pidof $PKG" 2>/dev/null | tr -d '\r')
  if [[ -z $PIDS ]]; then pf "app_cpu($PKG)" PASS "not running"; continue; fi
  P1=$(adb shell "cat /proc/${PIDS%% *}/stat" 2>/dev/null | tr -d '\r' | awk '{print $14+$15}'); sleep 2; P2=$(adb shell "cat /proc/${PIDS%% *}/stat" 2>/dev/null | tr -d '\r' | awk '{print $14+$15}')
  if [[ $P1 =~ ^[0-9]+$ && $P2 =~ ^[0-9]+$ ]]; then D=$((P2-P1)); [[ $D -le 20 ]] && pf "app_cpu($PKG)" PASS "idle delta=${D}ticks/2s" || pf "app_cpu($PKG)" FAIL "busy delta=${D}ticks/2s (possible user generation)"; else pf "app_cpu($PKG)" UNPARSED "$P1/$P2"; fi
done
grep -m2 -E 'mWakefulness=|Display Power: state=' "$OUT/raw/pf-power.txt" >"$OUT/screen-info.txt" 2>/dev/null
if [[ $BLOCK != 0 ]]; then log "BLOCKED by preflight (nothing pushed, nothing stopped)"; exit 8; fi
if [[ $PREFLIGHT_ONLY == yes ]]; then log "preflight-only: PASS (nothing pushed)"; exit 0; fi

# --- stage: push + verify
T0=$(date +%s); STAGED=yes
adb shell "mkdir -p '$REMOTE'" || { log "BLOCKED: mkdir failed"; exit 9; }
ADB_T=240 adb push "$S/." "$REMOTE/" >"$OUT/push.out" 2>&1 || { log "BLOCKED: push failed"; exit 9; }
ADB_T=120 adb shell "chmod 755 '$REMOTE'/bin/*; cd '$REMOTE'; find . -type f -exec sha256sum {} +|sort" | tr -d '\r' >"$OUT/remote.sha256"
diff <(awk '{print $1, $2}' "$W/stage.sha256") <(awk '{print $1, $2}' "$OUT/remote.sha256") >"$OUT/stage-diff.txt" && echo stage_verified >"$OUT/stage-proof.txt" || { log "BLOCKED: remote stage differs"; exit 7; }
log "stage verified; run window ${WINDOW}s, ${RUN_NATIVE_TIMEOUT}s/run"

# --- planned runs only: 4 variants x 2 rounds, raw pulled right after each run, no retries
PH0=$(date +%s)
for round in 1 2; do for v in runner_orig runner_dump runner_fixed runner_fixed_dump; do
  tag=$v-$round; EL=$(( $(date +%s) - PH0 ))
  if (( EL + RUN_NATIVE_TIMEOUT + 10 > WINDOW )); then echo skipped_window_exhausted >"$OUT/$tag.exit"; log "SKIP $tag: window exhausted at ${EL}s"; continue; fi
  ADB_T=$RUN_HOST_TIMEOUT adb shell "sh '$REMOTE/ctl/run_one.sh' '$REMOTE' $tag $v $RUN_NATIVE_TIMEOUT"; rc=$?; echo "$rc" >"$OUT/$tag.exit"; log "ran $tag rc=$rc"
  for f in $tag.json $tag.err $tag.wav $tag.pid; do ADB_T=60 adb pull "$REMOTE/$f" "$OUT/raw/$f" >/dev/null 2>&1 || log "pull missing $f"; done
done; done
log "runs finished in $(( $(date +%s) - PH0 ))s"; printf '%s\n' "$OUT"
