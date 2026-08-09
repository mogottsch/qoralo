#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel); BASE="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android"; ANDROID="$BASE/android"; EXPORT="$BASE/export"
INPUT=${INPUT:-$ROOT/artifacts/0002/generation-one-chunk-input}; HOST=${HOST:-$ROOT/artifacts/0002/generation-one-chunk-host}; OUT=${ARTIFACT_DIR:-$ROOT/artifacts/0002/generation-one-chunk-android}
PY=${PYTHON:-$ROOT/.venv/bin/python}; ETPY=${EXECUTORCH_PYTHON:-$ROOT/artifacts/venv-executorch-1.2/bin/python}; GRADLE=${GRADLE:-$ROOT/artifacts/tools/gradle-8.10.2/bin/gradle}
Q=$ROOT/artifacts/0002/lane-c/qwen2-int8-package; D=$ROOT/artifacts/0002/lane-b/diffusion-head/diffusion-step-xnnpack.pte; DEC=$ROOT/artifacts/0002/acoustic-decoder-streaming-first-segments-1.2; SEM=$ROOT/artifacts/0002/lane-b/semantic-encoder/semantic-encoder-first-xnnpack.pte; CON=$ROOT/artifacts/0002/lane-b/connectors/connectors-xnnpack.pte
export ANDROID_HOME=${ANDROID_HOME:-/home/moritz/Android/Sdk}; export ANDROID_SDK_ROOT=$ANDROID_HOME; PKG=dev.moket.vibevoiceprobe; mkdir -p "$OUT"
mapfile -t DEV < <(adb devices | awk 'NR>1&&NF{print $1" "$2}'); [[ ${#DEV[@]} == 1 && ${DEV[0]} == *' device' ]] || { echo 'expected one authorized phone' >&2; exit 2; }; [[ $(adb shell getprop ro.product.model|tr -d '\r') == SM-S918B ]] || exit 2
"$PY" "$EXPORT/generation_android_io.py" prepare "$INPUT" | tee "$OUT/prepare.log"
if [[ ${SKIP_HOST:-0} != 1 || ! -f "$HOST/host-result.json" ]]; then PYTHONPATH="$EXPORT" "$ETPY" "$EXPORT/generation_android_io.py" host "$INPUT" "$HOST" | tee "$OUT/host.log"; fi
(cd "$ANDROID" && "$GRADLE" --no-daemon :app:assembleDebug) | tee "$OUT/build.log"; adb install -r -t "$ANDROID/app/build/outputs/apk/debug/app-debug.apk" | tee "$OUT/install.log"
adb shell run-as "$PKG" rm -rf files/models files/generation-result.json 'files/generation-run-*'; adb shell run-as "$PKG" mkdir -p files/models/qwen files/models/decoder
push(){ local src=$1 dst=$2 tag=${3:-$(basename "$src")}; adb push "$src" "/data/local/tmp/$tag" >"$OUT/push-$tag.log"; adb shell chmod 0644 "/data/local/tmp/$tag"; adb shell run-as "$PKG" cp "/data/local/tmp/$tag" "files/$dst"; adb shell rm -f "/data/local/tmp/$tag"; }
for f in prepare.pte layer-{00..27}.pte final.pte decode-prepare.pte decode-layer-{00..27}.pte decode-final.pte; do push "$Q/$f" "models/qwen/$f" "q-$f"; done
push "$D" models/diffusion.pte diffusion.pte; for i in {0..7}; do push "$DEC/segment-$i.pte" "models/decoder/segment-$i.pte" "decoder-$i.pte"; done; push "$SEM" models/semantic.pte semantic.pte; push "$CON" models/connectors.pte connectors.pte
for f in prompt.txt prompt-embeddings.f32le speech-start-embedding.f32le initial-noise.f32le negative-condition.f32le timesteps.f32le sigmas.f32le; do push "$INPUT/$f" "$f" "input-$f"; done
"$PY" - <<'PY' >"$OUT/device-properties.json"
import json,subprocess
def p(x):return subprocess.check_output(['adb','shell','getprop',x],text=True).strip()
print(json.dumps({'manufacturer':p('ro.product.manufacturer'),'model':p('ro.product.model'),'device':p('ro.product.device'),'soc':p('ro.soc.model'),'android_release':p('ro.build.version.release'),'api_level':int(p('ro.build.version.sdk')),'abi':p('ro.product.cpu.abi'),'build_fingerprint':p('ro.build.fingerprint')},indent=2))
PY
adb logcat -c; adb shell am force-stop "$PKG"; adb shell am start -W -n "$PKG/.GenerationProbeActivity" | tee "$OUT/activity-start.log"; done=false
for _ in $(seq 1 5400); do adb shell run-as "$PKG" test -f files/generation-result.json && { done=true; break; }; sleep 1; done
adb logcat -d -s VibeVoiceGeneration:V ExecuTorch:V '*:S' >"$OUT/logcat.txt" || true; [[ $done == true ]] || { echo timeout >&2; exit 3; }
adb exec-out run-as "$PKG" cat files/generation-result.json >"$OUT/device-result.json"; cat "$OUT/device-result.json"; [[ $("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["status"])' "$OUT/device-result.json") == passed ]] || exit 4
for r in 0 1; do adb exec-out run-as "$PKG" cat "files/generation-run-$r.pcm" >"$OUT/generation-run-$r.pcm"; for n in qwen_prefill_hidden qwen_prefill_logits qwen_decode_503_hidden qwen_decode_503_logits diffusion decoder_pcm semantic_features connector_embedding; do adb exec-out run-as "$PKG" cat "files/generation-run-$r-$n.f32le" >"$OUT/generation-run-$r-$n.f32le"; done; done
"$PY" "$EXPORT/generation_android_io.py" compare "$HOST" "$OUT" "$OUT/device-result.json" "$OUT/device-properties.json" "$BASE/results/generation-one-chunk-android.json" --commit "$(git rev-parse HEAD)" | tee "$OUT/comparison.log"
