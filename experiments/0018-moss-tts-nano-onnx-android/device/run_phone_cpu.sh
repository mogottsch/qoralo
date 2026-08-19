#!/usr/bin/env bash
set -euo pipefail
REPO="$(git rev-parse --show-toplevel)"
EXP="$REPO/experiments/0018-moss-tts-nano-onnx-android"
ADB="${ADB:-/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe}"
SERIAL=R5CW81PR8SY
PACKAGE=com.openmoss.ttsnano.onnxruntime
ACTIVITY="$PACKAGE/.MainActivity"
APK="$EXP/android/app/build/outputs/apk/debug/app-debug.apk"
RUN_ID="vibevoice-0018-$(date -u +%Y%m%dT%H%M%SZ)-$$"
REMOTE="/data/local/tmp/$RUN_ID"
OUT="${1:-$EXP/work/$RUN_ID}"
LOCK="$REPO/artifacts/locks/phone.lock"
mkdir -p "$OUT" "$(dirname "$LOCK")"
[[ -x "$ADB" && -f "$APK" ]] || { echo "missing adb or APK" >&2; exit 2; }
exec 9>"$LOCK"
flock -n 9 || { echo "phone lock busy" >&2; exit 3; }
export ADB_LIBUSB=1
adb_call() { 9>&- "$ADB" -s "$SERIAL" "$@" </dev/null; }
clean() { tr -d '\r'; }
cleanup_needed=0
cleanup() {
  local rc=$?
  if (( cleanup_needed )); then
    set +e
    adb_call shell am force-stop "$PACKAGE" >/dev/null 2>&1
    adb_call shell run-as "$PACKAGE" rm -rf "files/$RUN_ID" >/dev/null 2>&1
    adb_call shell rm -rf "$REMOTE" >/dev/null 2>&1
    adb_call uninstall "$PACKAGE" >/dev/null 2>&1
  fi
  return "$rc"
}
trap cleanup EXIT

mapfile -t devices < <(9>&- "$ADB" devices | clean | awk 'NR>1 && $2=="device" {print $1}')
[[ "${#devices[@]}" -eq 1 && "${devices[0]}" == "$SERIAL" ]] || {
  printf 'identity ambiguity: connected devices: %s\n' "${devices[*]:-none}" >&2; exit 4;
}
state="$(adb_call get-state | clean)"
model="$(adb_call shell getprop ro.product.model | clean)"
soc="$(adb_call shell getprop ro.soc.model | clean)"
manufacturer="$(adb_call shell getprop ro.product.manufacturer | clean)"
release="$(adb_call shell getprop ro.build.version.release | clean)"
sdk="$(adb_call shell getprop ro.build.version.sdk | clean)"
[[ "$state" == device && "$model" == SM-S918B && "$soc" == SM8550 ]] || {
  echo "identity gate failed: state=$state model=$model soc=$soc" >&2; exit 5;
}
printf 'serial=%s\nmodel=%s\nsoc=%s\nmanufacturer=%s\nandroid_release=%s\nsdk=%s\nrun_id=%s\n' \
  "$SERIAL" "$model" "$soc" "$manufacturer" "$release" "$sdk" "$RUN_ID" > "$OUT/device.txt"

adb_call install -r -t "$APK" | clean | tee "$OUT/install.txt"
cleanup_needed=1
adb_call shell mkdir "$REMOTE"
adb_call shell run-as "$PACKAGE" mkdir -p \
  "files/$RUN_ID/moss_tts_onnx/MOSS-TTS-Nano-100M-ONNX" \
  "files/$RUN_ID/moss_tts_onnx/MOSS-Audio-Tokenizer-Nano-ONNX"

stage_one() {
  local source="$1" app_remote="$2" upload
  upload="$REMOTE/$(basename "$source")"
  echo "staging $(basename "$source") ($(stat -c %s "$source") bytes)" >&2
  adb_call push "$source" "$upload" > "$OUT/push-$(basename "$source").log"
  local local_hash upload_hash app_hash
  local_hash="$(sha256sum "$source" | awk '{print $1}')"
  upload_hash="$(adb_call shell sha256sum "$upload" | clean | awk '{print $1}')"
  [[ "$local_hash" == "$upload_hash" ]] || { echo "upload hash mismatch: $source" >&2; exit 6; }
  # The shell UID reads the verified unique upload; run-as writes app-owned mode-0600 data internally.
  adb_call shell "cat '$upload' | run-as '$PACKAGE' sh -c 'umask 077; cat > \"$app_remote\"'"
  app_hash="$(adb_call shell run-as "$PACKAGE" sha256sum "$app_remote" | clean | awk '{print $1}')"
  [[ "$local_hash" == "$app_hash" ]] || { echo "app-internal hash mismatch: $source" >&2; exit 6; }
  adb_call shell rm "$upload"
  printf '%s  %s  %s\n' "$local_hash" "$(stat -c %s "$source")" "$app_remote" >> "$OUT/staged-files.txt"
}
TTS="$EXP/.local/tts"; CODEC="$EXP/.local/codec"
for name in browser_poc_manifest.json tts_browser_onnx_meta.json tokenizer.model \
  moss_tts_prefill.onnx moss_tts_decode_step.onnx moss_tts_local_fixed_sampled_frame.onnx \
  moss_tts_global_shared.data moss_tts_local_shared.data; do
  stage_one "$TTS/$name" "files/$RUN_ID/moss_tts_onnx/MOSS-TTS-Nano-100M-ONNX/$name"
done
for name in codec_browser_onnx_meta.json moss_audio_tokenizer_decode_full.onnx moss_audio_tokenizer_decode_shared.data; do
  stage_one "$CODEC/$name" "files/$RUN_ID/moss_tts_onnx/MOSS-Audio-Tokenizer-Nano-ONNX/$name"
done

run_mode() {
  local label="$1" profile="$2" runs="$3" timeout_seconds="$4"
  adb_call shell am force-stop "$PACKAGE"
  adb_call shell am start -W -n "$ACTIVITY" --es run_id "$RUN_ID" --es evidence_label "$label" \
    --ez profile "$profile" --ei runs "$runs" --ei threads 4 | clean > "$OUT/am-start-$label.txt"
  local status_path="files/$RUN_ID/evidence/$label/status.txt" start now status
  start="$(date +%s)"
  while true; do
    status="$(adb_call shell run-as "$PACKAGE" cat "$status_path" 2>/dev/null | clean || true)"
    [[ "$status" == passed ]] && break
    [[ "$status" == failed ]] && { echo "$label failed" >&2; exit 7; }
    now="$(date +%s)"; (( now - start < timeout_seconds )) || { echo "$label timed out" >&2; exit 8; }
    sleep 5
  done
  mkdir -p "$OUT/$label"
  for name in result.json status.txt; do
    adb_call exec-out run-as "$PACKAGE" cat "files/$RUN_ID/evidence/$label/$name" > "$OUT/$label/$name"
  done
  local wav
  wav=$([[ "$profile" == true ]] && echo profile-sample.wav || echo listening-sample.wav)
  adb_call exec-out run-as "$PACKAGE" cat "files/$RUN_ID/evidence/$label/$wav" > "$OUT/$label/$wav"
}

run_mode benchmark false 4 2400
run_mode profile true 1 2400
mkdir -p "$OUT/profile/profiles"
mapfile -t profile_files < <(python3 - "$OUT/profile/result.json" <<'PY'
import json,sys
for component,path in sorted(json.load(open(sys.argv[1]))['profile_prefixes'].items()):
 print(component+'\t'+path)
PY
)
[[ "${#profile_files[@]}" -eq 4 ]] || { printf 'expected 4 profile files, got %s: %s\n' "${#profile_files[@]}" "${profile_files[*]}" >&2; exit 9; }
for entry in "${profile_files[@]}"; do
  component="${entry%%$'\t'*}"; remote="${entry#*$'\t'}"
  adb_call exec-out run-as "$PACKAGE" cat "$remote" > "$OUT/profile/profiles/$component.json"
done
adb_call shell am force-stop "$PACKAGE"
adb_call shell run-as "$PACKAGE" rm -rf "files/$RUN_ID"
adb_call shell rm -rf "$REMOTE"
remaining="$(adb_call shell "run-as '$PACKAGE' sh -c \"test ! -e 'files/$RUN_ID' && echo absent\"" | clean)"
tmp_remaining="$(adb_call shell "test ! -e '$REMOTE' && echo absent" | clean)"
[[ "$remaining" == absent && "$tmp_remaining" == absent ]] || { echo "cleanup verification failed" >&2; exit 10; }
adb_call uninstall "$PACKAGE" | clean > "$OUT/uninstall.txt"
cleanup_needed=0
printf 'cleanup=passed\napp_internal_stage=absent\nremote_upload_stage=absent\n' > "$OUT/cleanup.txt"
echo "$OUT"
