# Reproducing experiment 0017

This is the durable clean-machine reconstruction and execution guide for experiment 0017. Committed protocols, tools, hashes, and result summaries are authoritative; ignored `work/` and `.local/` artifacts are not evidence or unique sources of decisions. Large generated models, tensors, compiler logs, profiles, Qualcomm libraries, binaries, and WAVs remain intentionally ignored and must be regenerated or restored only after their hashes are verified.

## Current execution boundary

No phone access has occurred for the canonical-v2 Kokoro route.

The current canonical host attempt was externally interrupted by a WSL shutdown/restart:

- canonical stages **1–15** finalized and executed successfully in separate fallback-disabled QNN host processes;
- each of those 15 ORT profiles contains one `QNNExecutionProvider` node event and zero CPU-provider events;
- stage 16, `generator_1_resblock_5`, reached `Graph Sequencing for Target` **12%** but did not finalize or execute;
- stages 17 (`generator_1_merge`) and 18 (`waveform_istft`) were not attempted;
- no canonical QNN final audio exists;
- this is an **external infrastructure interruption**, not a stage-16 technical failure or OOM;
- phone eligibility is false.

The complete durable record, including per-stage model/output/profile hashes, QNN metrics, CPU comparisons, resource samples, the partial stage-16 compiler times, and claim boundaries, is [`results/canonical-v2-host-qnn-interrupted-checkpoint.json`](results/canonical-v2-host-qnn-interrupted-checkpoint.json).

## Canonical-v2 route contract

Canonical means the exact committed 226-byte transcript [`../../protocols/android-tts-benchmark/transcript.txt`](../../protocols/android-tts-benchmark/transcript.txt), no trailing newline, SHA-256:

```text
424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67
```

The old experiment-0013 sherpa lexicon frontend fails closed on this text with:

```text
selected text is not fully covered by lexicon: 'makes'
```

The new route therefore uses the pinned official frontend, separate from all old experiment-0013/0017 metrics and verdicts:

- `kokoro==0.9.4`, `KPipeline(lang_code="a", model=False, trf=False)`;
- `misaki==0.9.4`, `phonemizer-fork==3.3.2`, `espeakng-loader==0.2.4`;
- one American-English chunk;
- 233 phoneme code points / 323 UTF-8 bytes, SHA `7c7299c2d19943162b5bc85cebe116d16e534f336ac5bcb4fce40fe126a8b3a0`;
- tokens `[1,235]`, little-endian int64 SHA `9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280`;
- `af_heart` style row 232, `[1,256]` float32 SHA `8acaca07623d98a1085f6b182fb997d715dd1d67862e350567e6d9b1bc8ec71b`;
- speed `1.0`, SHA `e00e5eb9444182f352323374ef4e08ebcb784725fdd4fd612d7730540b3e0c8c`;
- seed `20260818`;
- duration `[235]`, sum `602`, SHA `99494f78e82ad3d8b506d5b0a5c4edde6292c6a52ca54a47b50f109fa534480c`;
- audio `[361200]` at 24 kHz = `15.05 s`.

The frozen machine contract is [`protocol-canonical-v2-stage-decomposition.json`](protocol-canonical-v2-stage-decomposition.json). It contains all 18 model hashes and fixed I/O contracts.

## Durable evidence already complete

| Evidence | Result |
|---|---|
| Official-frontend proof | [`results/canonical-v2-frontend-provenance.json`](results/canonical-v2-frontend-provenance.json) |
| Controlled-eager CPU oracle | valid audio SHA `b7cc6d6c719bd0151c35aa6ae4ef8bcec0b3b99acb7a6423e4c6e42e2edee536`; [`results/canonical-v2-eager-oracle.json`](results/canonical-v2-eager-oracle.json) |
| FP32 ONNX export | `26120b192f2ad7567c6c1215ccbcf374d1946460c4589c1098941ab15e43aa73`; 4,352 nodes, no quantization/random ops; [`results/canonical-v2-onnx-export-provenance.json`](results/canonical-v2-onnx-export-provenance.json) |
| Patched ORT 1.27.1 source-ONNX CPU | exact duration, structurally valid audio SHA `1f7eb49ca903a3eed8cdb36049041a48540bd08027b38b4a6cee52e27cb9f624`; phase-tolerant pass but separate `.999/.01` waveform failure; [`results/canonical-v2-source-onnx-cpu-equivalence.json`](results/canonical-v2-source-onnx-cpu-equivalence.json) |
| Metadata-shaped graph | `d81053acc21a9fa42a7ff09bae17abad1ef7499aa2252f70bda27f9ac89194a3`; [`results/canonical-v2-profile-shape-provenance.json`](results/canonical-v2-profile-shape-provenance.json) |
| QNN compatibility graph | `0c7ce33eac4c6664819a61e48469a9cf43ad403d852b01af5517a13c7ed2a066`; 1,685 nodes, 809 initializers, no quantization or retained initializer changes; bit-exact to shaped CPU source; [`results/canonical-v2-qnn-compat-rewrite-provenance.json`](results/canonical-v2-qnn-compat-rewrite-provenance.json) |
| Stage decomposition | 18 stages, all 1,685 source nodes covered, five named support nodes recomputed at boundaries; deterministic model hashes/interfaces; [`results/canonical-v2-stage-decomposition-provenance.json`](results/canonical-v2-stage-decomposition-provenance.json) |
| Stage CPU recomposition | bit-exact audio/duration; audio SHA `fb8895f6bb9c2ee94dd18f8b9bfdc6f1b36f99e01c40f5806bdd71076acd6d36`; [`results/canonical-v2-stage-cpu-equivalence.json`](results/canonical-v2-stage-cpu-equivalence.json) |
| Interrupted canonical QNN attempt | 15 completed, stage 16 partial, 17–18 unattempted; [`results/canonical-v2-host-qnn-interrupted-checkpoint.json`](results/canonical-v2-host-qnn-interrupted-checkpoint.json) |

The completed **noncanonical** 116-byte historical stage experiment is separately preserved in [`results/staged-host-qnn-feasibility.json`](results/staged-host-qnn-feasibility.json): all 18 host stages ran with QNN assignment, but duration changed from 304 to 305 and the final float audio was invalid (`peak 94848`, 182,236 samples with `abs >= 1`). It is feasibility/debug evidence only, never canonical, phone-eligible, or listening material.

## Regenerating ignored canonical artifacts

All commands run from repository root. The official model/config and lossless voice tensor are expected under the ignored experiment-0013 paths and are hash-gated by the tools.

```bash
EXP13=experiments/0013-kokoro-onnx-vs-executorch-android
EXP17=experiments/0017-kokoro-onnx-qnn-htp-android
PY="$EXP13/.local/venv/bin/python"
SHERPA="$EXP13/.local/source/sherpa/extracted/kokoro-multi-lang-v1_0"
FRONT="$EXP17/work/canonical-v2/frontend-official-v1"

"$PY" "$EXP17/tools/prepare_canonical_v2_frontend.py" \
  --canonical-text protocols/android-tts-benchmark/transcript.txt \
  --official-config "$EXP13/.local/source/official/config.json" \
  --voice-f32 "$EXP13/.local/derived/af_heart.f32" \
  --sherpa-contract-tool "$EXP13/tools/kokoro_contract.py" \
  --sherpa-tokens "$SHERPA/tokens.txt" --sherpa-lexicon "$SHERPA/lexicon-us-en.txt" \
  --output-dir "$FRONT" \
  --provenance "$EXP17/results/canonical-v2-frontend-provenance.json"

"$PY" "$EXP17/tools/run_canonical_v2_eager_oracle.py" \
  --model "$EXP13/.local/source/official/kokoro-v1_0.pth" \
  --config "$EXP13/.local/source/official/config.json" \
  --tokens "$FRONT/tokens.raw" --style "$FRONT/style.raw" --speed "$FRONT/speed.raw" \
  --experiment-0013-tools "$EXP13/tools" \
  --output-dir "$EXP17/work/canonical-v2/eager-oracle-v1" \
  --provenance "$EXP17/results/canonical-v2-eager-oracle.json"

"$PY" "$EXP17/tools/export_canonical_v2_onnx_fp.py" \
  --model "$EXP13/.local/source/official/kokoro-v1_0.pth" \
  --config "$EXP13/.local/source/official/config.json" \
  --tokens "$FRONT/tokens.raw" --style "$FRONT/style.raw" --speed "$FRONT/speed.raw" \
  --oracle "$EXP17/results/canonical-v2-eager-oracle.json" \
  --experiment-0013-tools "$EXP13/tools" \
  --output "$EXP17/work/canonical-v2/export-v2/kokoro-canonical-v2-fp32-controlled-t235.onnx" \
  --provenance "$EXP17/results/canonical-v2-onnx-export-provenance.json"

"$PY" "$EXP17/tools/prepare_canonical_v2_optimized_graph.py" \
  --model "$EXP17/work/canonical-v2/export-v2/kokoro-canonical-v2-fp32-controlled-t235.onnx" \
  --tokens "$FRONT/tokens.raw" --style "$FRONT/style.raw" --speed "$FRONT/speed.raw" \
  --optimized-model "$EXP17/work/canonical-v2/ort123-basic-v1/optimized-basic.onnx" \
  --profile-prefix "$EXP17/work/canonical-v2/ort123-basic-v1/profile" \
  --audio-output "$EXP17/work/canonical-v2/ort123-basic-v1/audio.f32" \
  --duration-output "$EXP17/work/canonical-v2/ort123-basic-v1/duration.i64" \
  --provenance "$EXP17/results/canonical-v2-basic-optimized-provenance.json"

PROFILE=$(find "$EXP17/work/canonical-v2/ort123-basic-v1" -maxdepth 1 -name 'profile_*.json' -print -quit)
"$PY" "$EXP17/tools/annotate_canonical_v2_profile_shapes.py" \
  --model "$EXP17/work/canonical-v2/ort123-basic-v1/optimized-basic.onnx" \
  --profile "$PROFILE" \
  --output "$EXP17/work/canonical-v2/shaped-v1/optimized-basic-shaped.onnx" \
  --provenance "$EXP17/results/canonical-v2-profile-shape-provenance.json"

"$PY" "$EXP17/tools/rewrite_canonical_v2_qnn_compat.py" \
  --source "$EXP17/work/canonical-v2/shaped-v1/optimized-basic-shaped.onnx" \
  --output "$EXP17/work/canonical-v2/rewrite-v1/kokoro-canonical-v2-qnn-compat.onnx" \
  --provenance "$EXP17/results/canonical-v2-qnn-compat-rewrite-provenance.json"

"$PY" "$EXP17/tools/extract_canonical_v2_staged_graphs.py" \
  --source "$EXP17/work/canonical-v2/rewrite-v1/kokoro-canonical-v2-qnn-compat.onnx" \
  --output-dir "$EXP17/work/canonical-v2/stages-v1/models" \
  --manifest "$EXP17/work/canonical-v2/stages-v1/manifest.json"
```

Rebuild the ignored Ubuntu 22 runner against the existing patched ORT build:

```bash
ROOT=$PWD
EXP="$ROOT/experiments/0017-kokoro-onnx-qnn-htp-android"
SRC="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source"
BUILD="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/Release"
docker run --rm -v "$SRC:/src:ro" -v "$BUILD:/build:ro" -v "$EXP:/exp" \
  vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04 \
  bash -lc 'g++ -std=c++17 -O2 -Wall -Wextra -Werror \
    -I/src/include/onnxruntime/core/session \
    /exp/host/kokoro_canonical_stage_runner.cc -L/build -lonnxruntime \
    -Wl,-rpath,/build -o /exp/.local/bin/kokoro-canonical-stage-host-docker'
sha256sum "$EXP/.local/bin/kokoro-canonical-stage-host-docker"
# Must be 938480879497262461dcc4632a0ebeebb92f721c9192441c17b406af8ac0e023
```

The committed contract tests and hash gates must pass before QNN:

```bash
python3 -m unittest experiments/0017-kokoro-onnx-qnn-htp-android/tests/test_contract.py -v
```

## Exact next action

Do **not** resume from stage 16. Restart the complete canonical host record from stage 1:

```bash
RUN_ID=canonical-v2-rerun \
  experiments/0017-kokoro-onnx-qnn-htp-android/host/run_canonical_v2_staged_host_qnn.sh
```

The script verifies the manifest, all 18 model hashes, runner, and inputs; defaults to refusing a concurrent QNN compiler; runs one stage process at a time; records memory every five seconds; and never accesses the phone. `QAIRT_ROOT` defaults to `/home/moritz/opt/qairt/2.49.0.260730`.

After an 18/18 pass, create the durable host execution summary (replace `$RUN`):

```bash
EXP=experiments/0017-kokoro-onnx-qnn-htp-android
RUN="$EXP/work/canonical-v2/stages-v1/qnn-host-canonical-v2-rerun"
python3 "$EXP/tools/summarize_staged_qnn_run.py" \
  --manifest "$EXP/work/canonical-v2/stages-v1/manifest.json" \
  --checkpoint "$RUN/pipeline-checkpoint.json" \
  --cpu-checkpoint "$EXP/work/canonical-v2/stages-v1/cpu127/pipeline-checkpoint.json" \
  --route canonical_v2_official_frontend_fixed_fp32_staged_qnn_host \
  --transcript-sha256 424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67 \
  --comparability canonical_v2 \
  --expected-audio-elements 361200 --expected-duration-elements 235 \
  --expected-duration-sum 602 \
  --output "$EXP/results/canonical-v2-host-qnn-gate.json"
```

Then inspect structural validity and numerical/acoustic metrics. Numerical or EOS divergence is descriptive, not a listening rejection. **Do not touch the phone** unless all 18 fallback-disabled stages ran, provider proof has zero CPU events, and the canonical host output is structurally valid. Physical RPC/accelerator/cycle/HVX evidence, first and five warm RTFs using actual emitted duration, thermal context, memory semantics, a fresh valid WAV, and Moritz's exact-sample verdict remain outstanding.

## Claim boundaries

- Host QNN execution is not physical phone HTP proof.
- Capability/partition counts are not session finalization or inference.
- CPU orchestration, tensor transport, frontend work, and WAV encoding must be disclosed separately from neural HTP execution.
- `ru_maxrss`/`VmHWM` are process-lifetime high-water marks, not steady PSS or component-isolated memory.
- The canonical source ONNX passed the named phase-tolerant policy but failed the separate strict waveform screen; neither decides listening quality.
- The accepted experiment-0013 CPU WAV and every historical metric/verdict remain scoped to their old noncanonical route and do not transfer to canonical v2.
- Canonical QNN listening status is `not_reviewed`; only Moritz may accept or reject an exact WAV hash.
- No quantization is authorized.
