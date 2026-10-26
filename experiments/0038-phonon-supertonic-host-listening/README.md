# 0038 — Phonon 31m vs Qoralo Supertonic 3: host listening samples

**Prepared, not listening-reviewed.** [Open the comparison](index.html): three identical English inputs, two different stock voices. All speech is synthetic. No subjective acceptance, quality ranking, ASR accuracy result, phone measurement or S23/NPU speed claim is made. This is not Pocket TTS.

## Delivered samples

Each row has a native, unprocessed **FLOAT WAV** (`*.native.wav`) preserving the exact array returned by the supported runtime, and a browser-friendly **PCM16 WAV** (`*.wav`). Players use the latter. Only float-to-PCM16 encoding at unity gain is applied; no normalization, level matching, trimming, dither, resampling, padding-to-length or time stretching. Native model/frontend chunking remains part of each recipe. Durations below are actual emitted frames/rate, not the SDK’s predicted duration.

| Input | Phonon 31m duration / native peak | Supertonic 3 duration / native peak |
|---|---:|---:|
| Canonical-v2 benchmark | 14.400000 s / 0.673220 | 15.116190 s / 0.447112 |
| Original conversational podcast excerpt | 19.680000 s / 0.695808 | 21.128299 s / 0.525655 |
| Original numbers/dates/abbreviations | 27.520000 s / 0.673604 | 25.565170 s / 0.513303 |

Paths are `samples/{phonon,supertonic}/{canonical,conversation,structured}{.native,}.wav`. All twelve WAVs are committed; weights and environments are not. The two new texts are fictional, nonprivate, original material. The canonical input is copied byte-for-byte from `podcast-app/app/src/debug/assets/tts-only/canonical.txt`: **226 bytes**, SHA-256 `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`, including its original final newline. Neither model receives a manually expanded numbers variant. Exact strings/hashes: [protocol/inputs.json](protocol/inputs.json).

## Actual current Qoralo baseline, not a generic SDK default

Inspected main **`07b197580a73411019fbb291eb16b4ffafacbca8`** before selection:

- [`trusted-supertonic-provider.json`](../../podcast-app/config/trusted-supertonic-provider.json) selects `supertonic-3-provider`, M1/SID5, English, target 300 code points, speed 1.05, 13,230 gap frames, seed 20260911, NumPy legacy MT19937 and `FULL_NATIVE_VOCODER`.
- [`provider_math.h`](../../podcast-app/app/src/main/cpp/provider_math.h) fixes eight steps, speed 1.05, seed 20260911, 44.1 kHz, 3,072-hop full native output; [`ProviderAudioPlan.kt`](../../podcast-app/app/src/main/java/dev/qoralo/podcast/runtime/ProviderAudioPlan.kt) admits text extent <=320 and native latent extent <=512.
- [Experiment 0037](../0037-supertonic-provider-pipeline/README.md) and its pinned source manifest establish original FP32 Supertonic-3 weights **`724fb5abbf5502583fb520898d45929e62f02c0b`**, official Python **1.3.1**, source commit `908a56486e821e833a80530ff0cae3ad0b046fce`. The generator verifies all six SDK source file hashes and all downloaded model/voice bytes against these authorities.

This experiment uses that **same M1/SID5, language, segmentation/normalization order, eight steps, 1.05 model speed, per-case seed and full-native-wave recipe**, with the upstream SDK’s original dynamic FP32 CPU ONNX graphs. Supertonic makes one/two/one segments for canonical/conversation/structured respectively; the conversation contains one prescribed 0.3 s zero gap. Gaussian state resets at each case, like a chapter, and continues across its segments.

### Explicit deviations and fairness boundaries

- **Host CPU SDK, not Qoralo’s Android C++/QNN path.** No QNN graph rewriting, static T320/L512 edge gathers, quantized HTP contexts, phone transport or on-device inference is exercised. It is not bit-identical to a previously accepted app WAV and inherits no earlier listening verdict.
- ONNX Runtime **1.27.0**, one intra-op and one inter-op thread, versus experiment 0037 Android CPU ORT 1.27.1/four intra-op threads. Python **3.11.17**, NumPy **2.3.5** and the provider SDK preserve the Unicode 14 frontend and RNG recipe. All four loaded sessions report only `CPUExecutionProvider`.
- Phonon uses **ptts 0.4.2**, native Rust CPU q8_0, model revision **`92741c5b07d085ff840e26fea8ce43110b87852f`**, and the stock checkpoint `default-voice.safetensors` registered as `default`. No external voice catalog, voice cloning, reference recording or paid service is used. Its speaker identity is not claimed to be Easton or the same as M1.
- Phonon settings: temperature **0.3** (runtime API default, not config `temp=0.8`), seed **4242424242424242** reset per case, CFG disabled, EOS threshold **4.0**, one decode step from checkpoint, no condition overrides, English `rewrites="default"`, native 50-token sentence/chunk planner, no runtime post-processing modules, one tensor-op thread. Source **`cc0c32bcad4e79121e98cb16d9a1b19f87772e82`** (tag v0.4.2) pins defaults not exposed by its Python API.
- Different stock speakers, native sample rates, quantization and native frontends are deliberate end-to-end configuration differences, not a controlled architecture-only or same-speaker test. Phonon normalization expands e.g. currency and month abbreviations; Supertonic retains these strings with its own tagged Unicode frontend. Effective frontend strings are in provenance. No hidden shared pre-normalization is applied.
- Host wall measurements in provenance are **single-run diagnostics only**, including normal frontend work and chunk assembly. They are not warm distributions, controlled throughput benchmarks, or evidence about Galaxy S23 Ultra/SM8550 compatibility. No Phonon phone/QNN bundle is deployed.

## Evidence and reproduction

- [models.json](protocol/models.json): exact revisions, asset byte sizes and SHA-256, including stock voices/tokenizers.
- [Phonon provenance](results/phonon.json), [Supertonic provenance](results/supertonic.json): exact runtime versions/build/source hashes, settings, frontend strings, returned arrays’ PCM hashes, file hashes, measured frames/durations/peaks and finite checks. `human_listening_accepted` remains false.
- [Independent verification](results/verification.json): separate FFmpeg decoder/prober, no imports from the generator/export helper; verifies all twelve WAVs, exact native PCM hashes, finite/non-silent/no-full-scale samples, playable frame identity, <=1 PCM16 LSB conversion error, FFmpeg true peak and all six HTML players/local links. This does **not** certify pronunciation or content completeness.
- [Browser verification](results/browser-verification.json): actual local-file Chromium 156.0.8078.4 / Playwright 1.56.0 decoded and started all six labeled players without media/page errors; 390 px layout had no horizontal overflow. Screenshots remain ignored under `.local/`. This is browser transport/playback evidence, not audible human review.
- [Repeat-inference check](results/reproducibility.json): all six PCM16 WAVs were byte-identical on one fresh-process repeat. Five native float arrays were identical; Phonon canonical differed by at most **8.940697e-08** with identical frames and identical playable encoding. An initial strict all-native-PCM equality assertion failed and was investigated, not hidden. Both complete runs passed the independent decoder checks; the first-run originals remain the delivered samples. This demonstrates this repeat's bounded result, not universal bitwise determinism.
- `tools/test_comparison.py`, `tools/test_verify.py`: native-array preservation, overwrite refusal, invalid-array rejection, safe HTML rendering, unity-gain PCM16/clipping refusal and independent hash/frame mismatch rejection. Tests use clearly synthetic small fixtures, never substituted for inference outputs.

From this experiment directory, with `uv` and FFmpeg/ffprobe on PATH:

```sh
# No system Python or shared environment changes. Use this override if /opt/python is read-only.
export UV_PYTHON_INSTALL_DIR="${TMPDIR:-$HOME/.cache}/qoralo-uv-python"
uv venv --python 3.11.17 .local/venv
uv pip sync --python .local/venv/bin/python --require-hashes requirements.lock
.local/venv/bin/python -m pytest tools -q
.local/venv/bin/python tools/verify.py
# Existing delivered outputs are immutable: regenerate into a NEW output root.
.local/venv/bin/python tools/generate.py --model phonon --output .local/repro-01
.local/venv/bin/python tools/generate.py --model supertonic --output .local/repro-01
cp README.md .local/repro-01/README.md
.local/venv/bin/python tools/verify.py --output .local/repro-01 --report .local/repro-01/results/verification.json
```

`generate.py` sequentially downloads only pinned, SHA-verified assets under ignored `.local/models/`. It enforces the dependency versions and Python 3.11, bounds each invocation by a 30-minute alarm, keeps CPU tensor/ORT threads at one and refuses existing sample directories. Run models in separate sequential processes. No PyTorch/GPU dependency was necessary. Versions and hashes pin the recipe, but cross-machine bit-for-bit model inference is not promised; compare actual new PCM/file hashes rather than assuming equal seeds prove equality. FLOAT WAV metadata may also vary independently of identical PCM.

Open `index.html` directly, or serve the experiment locally with `python3 -m http.server 8765 --bind 127.0.0.1` and visit `http://127.0.0.1:8765/`. Nothing is pushed, hosted publicly, deployed or changed in the app backend by this experiment.

## Source/output licensing

See [LICENSES.md](LICENSES.md). Phonon **31m** weights/tokenizer/default voice are Apache-2.0 (not the NC 40m model); its separate runtime is MIT OR Apache-2.0. Supertonic-3 weights/preset voice are OpenRAIL-M; its Python SDK is MIT. The pinned OpenRAIL-M license’s **section 6** says the licensor claims no rights in generated output except the license’s conditions; output use cannot contravene the license. Its Attachment A(e) requires an intelligible machine-generated disclosure, present on this page and audition. These benign original text-to-speech listening samples may be distributed with those notices; they are outputs, not weights or a derivative model. No claim that all audio/model rights become Apache-2.0 merely because the Qoralo app is Apache-2.0, no voice impersonation, and no endorsement by either provider.

**Remaining review:** human listening to these exact hashes and independent code/artifact review before any publication. Numerical checks and browser playback are not human acceptance.
