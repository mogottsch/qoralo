#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel); BASE="$ROOT/experiments/0002-vibevoice-1.5b-executorch-android"; ANDROID="$BASE/android"; EXPORT="$BASE/export"
INPUT=${INPUT:-$ROOT/artifacts/0002/generation-multi-chunk-input}; HOST=${HOST:-$ROOT/artifacts/0002/generation-multi-chunk-host}; OUT=${ARTIFACT_DIR:-$ROOT/artifacts/0002/generation-multi-chunk-android}
PY=${PYTHON:-$ROOT/.venv/bin/python}; ETPY=${EXECUTORCH_PYTHON:-$ROOT/artifacts/venv-executorch-1.2/bin/python}; GRADLE=${GRADLE:-$ROOT/artifacts/tools/gradle-8.10.2/bin/gradle}
Q=$ROOT/artifacts/0002/lane-c/qwen2-int8-package; D=$ROOT/artifacts/0002/lane-b/diffusion-head/diffusion-step-xnnpack.pte; FIRST=$ROOT/artifacts/0002/acoustic-decoder-streaming-first-segments-1.2; CACHED=$ROOT/artifacts/0002/acoustic-decoder-streaming-cached-segments-1.2; SEM=$ROOT/artifacts/0002/lane-b/semantic-encoder; CON=$ROOT/artifacts/0002/lane-b/connectors/connectors-xnnpack.pte
export ANDROID_HOME=${ANDROID_HOME:-/home/moritz/Android/Sdk};export ANDROID_SDK_ROOT=$ANDROID_HOME;PKG=dev.moket.vibevoiceprobe;mkdir -p "$OUT"
mapfile -t DEV < <(adb devices|awk 'NR>1&&NF{print $1" "$2}');[[ ${#DEV[@]} == 1 && ${DEV[0]} == *' device' ]]||{ echo 'expected one authorized phone' >&2;exit 2;};[[ $(adb shell getprop ro.product.model|tr -d '\r') == SM-S918B ]]||exit 2
"$PY" "$EXPORT/generation_multi_chunk_io.py" prepare "$INPUT" | tee "$OUT/prepare.log"
if [[ ${SKIP_HOST:-0} != 1 || ! -f "$HOST/host-result.json" ]];then PYTHONPATH="$EXPORT" "$ETPY" "$EXPORT/generation_multi_chunk_io.py" host "$INPUT" "$HOST" | tee "$OUT/host.log";fi
(cd "$ANDROID"&&"$GRADLE" --no-daemon :app:assembleDebug)|tee "$OUT/build.log";adb install -r -t "$ANDROID/app/build/outputs/apk/debug/app-debug.apk"|tee "$OUT/install.log"
adb shell run-as "$PKG" rm -f files/generation-result.json 'files/generation-run-*';adb shell run-as "$PKG" mkdir -p files/models/qwen files/models/decoder/first files/models/decoder/cached
push(){ local src=$1 dst=$2 tag=${3:-$(basename "$src")};adb push "$src" "/data/local/tmp/$tag">"$OUT/push-$tag.log";adb shell chmod 0644 "/data/local/tmp/$tag";adb shell run-as "$PKG" cp "/data/local/tmp/$tag" "files/$dst";adb shell rm -f "/data/local/tmp/$tag";}
# Reuse the dependency run's Qwen/diffusion/connectors files when present; push only missing files.
has(){ adb shell run-as "$PKG" test -s "files/$1"; }
for f in prepare.pte layer-{00..27}.pte final.pte decode-prepare.pte decode-layer-{00..27}.pte decode-final.pte;do has "models/qwen/$f"||push "$Q/$f" "models/qwen/$f" "q-$f";done
has models/diffusion.pte||push "$D" models/diffusion.pte diffusion.pte;has models/connectors.pte||push "$CON" models/connectors.pte connectors.pte
for i in {0..7};do has "models/decoder/first/segment-$i.pte"||push "$FIRST/segment-$i.pte" "models/decoder/first/segment-$i.pte" "decoder-first-$i.pte";has "models/decoder/cached/segment-$i.pte"||push "$CACHED/segment-$i.pte" "models/decoder/cached/segment-$i.pte" "decoder-cached-$i.pte";done
has models/semantic-first.pte||push "$SEM/semantic-encoder-first-xnnpack.pte" models/semantic-first.pte semantic-first.pte;has models/semantic-cached.pte||push "$SEM/semantic-encoder-cached-xnnpack.pte" models/semantic-cached.pte semantic-cached.pte
for f in prompt.txt prompt-embeddings.f32le initial-noises.f32le negative-condition.f32le timesteps.f32le sigmas.f32le;do push "$INPUT/$f" "$f" "input-$f";done
"$PY" - <<'PY' >"$OUT/device-properties.json"
import json,subprocess
def p(x):return subprocess.check_output(['adb','shell','getprop',x],text=True).strip()
print(json.dumps({'manufacturer':p('ro.product.manufacturer'),'model':p('ro.product.model'),'device':p('ro.product.device'),'soc':p('ro.soc.model'),'android_release':p('ro.build.version.release'),'api_level':int(p('ro.build.version.sdk')),'abi':p('ro.product.cpu.abi'),'build_fingerprint':p('ro.build.fingerprint')},indent=2))
PY
adb logcat -c;adb shell am force-stop "$PKG";adb shell am start -W -n "$PKG/.GenerationProbeActivity"|tee "$OUT/activity-start.log";done=false
for _ in $(seq 1 5400);do adb shell run-as "$PKG" test -f files/generation-result.json&&{ done=true;break;};sleep 1;done
adb logcat -d -s VibeVoiceGeneration:V ExecuTorch:V '*:S'>"$OUT/logcat.txt"||true;[[ $done == true ]]||{ echo timeout >&2;exit 3;}
adb exec-out run-as "$PKG" cat files/generation-result.json >"$OUT/device-result.json";cat "$OUT/device-result.json";[[ $("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["status"])' "$OUT/device-result.json") == passed ]]||exit 4
chunks=$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["runs"][0]["audio_chunks"])' "$OUT/device-result.json")
for r in 0 1;do for ext in pcm wav;do adb exec-out run-as "$PKG" cat "files/generation-run-$r.$ext">"$OUT/generation-run-$r.$ext";done;for ci in $(seq 0 $((chunks-1)));do c=$(printf %02d "$ci");for n in diffusion decoder_pcm semantic_features connector_embedding qwen_hidden qwen_logits;do adb exec-out run-as "$PKG" cat "files/generation-run-$r-chunk-$c-$n.f32le">"$OUT/generation-run-$r-chunk-$c-$n.f32le";done;done;done
"$PY" "$EXPORT/generation_multi_chunk_io.py" compare "$HOST" "$OUT" "$OUT/device-result.json" "$OUT/device-properties.json" "$BASE/results/generation-3-to-5s-android.json" --commit "$(git rev-parse HEAD)"|tee "$OUT/comparison.log"
