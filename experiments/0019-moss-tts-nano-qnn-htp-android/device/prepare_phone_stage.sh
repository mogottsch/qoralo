#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"; EXP="$ROOT/experiments/0019-moss-tts-nano-qnn-htp-android"; D="$EXP/.local/specialized"; STAGE="$EXP/.local/phone-stage"
rm -rf "$STAGE";mkdir -p "$STAGE/models" "$STAGE/models-cpu"
copy_source_models(){
  local dest=$1
  cp --reflink=auto "$D/prefill-s226-qnn.onnx" "$dest/prefill.onnx"
  cp --reflink=auto "$D/decode-fixed-cap600-attention-qnn.onnx" "$dest/decode.onnx"
  cp --reflink=auto "$D/local-fixed-b1.onnx" "$dest/local.onnx"
  cp --reflink=auto "$D/codec-full-cap375-qnn.onnx" "$dest/codec.onnx"
  cp --reflink=auto "$D/moss_tts_global_shared.data" "$D/moss_tts_local_shared.data" "$D/moss_audio_tokenizer_decode_shared.data" "$dest/"
}
CTX="$EXP/.local/contexts"
if [[ ${USE_CONTEXTS:-1} == 1 && -f "$CTX/context-manifest.sha256" ]];then
  cp "$CTX"/* "$STAGE/models/"
  cp "$CTX/prefill_ctx.onnx" "$STAGE/models/prefill.onnx"
  cp "$CTX/decode_ctx.onnx" "$STAGE/models/decode.onnx"
  cp "$CTX/local_ctx.onnx" "$STAGE/models/local.onnx"
  cp "$CTX/codec_ctx.onnx" "$STAGE/models/codec.onnx"
  copy_source_models "$STAGE/models-cpu"
  echo context-binaries-plus-matched-cpu-source >"$STAGE/stage-mode.txt"
else
  copy_source_models "$STAGE/models"
  # Kept as a second explicit root so route commands and manifests remain identical.
  cp -al "$STAGE/models/." "$STAGE/models-cpu/"
  echo source-onnx-both-routes >"$STAGE/stage-mode.txt"
fi
(
 cd "$STAGE"
 find models models-cpu -type f -print0 | sort -z | xargs -0 sha256sum > stage-manifest.sha256
)
APK=$("$EXP/device/build_carrier_apk.sh" | tail -1)
cp "$APK" "$STAGE/carrier.apk"
sha256sum "$STAGE/carrier.apk" > "$STAGE/carrier.apk.sha256"
python3 - "$STAGE/carrier.apk" "$STAGE/carrier-native-manifest.sha256" <<'PY'
import hashlib,sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
 rows=[f"{hashlib.sha256(z.read(n)).hexdigest()}  {n.split('/')[-1]}" for n in sorted(x for x in z.namelist() if x.startswith('lib/arm64-v8a/'))]
open(sys.argv[2],'w').write('\n'.join(rows)+'\n')
PY
echo "$STAGE"
