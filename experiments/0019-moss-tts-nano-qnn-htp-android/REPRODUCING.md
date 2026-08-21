# Reproducing experiment 0019

## Read this first

This file is the durable clean-machine reconstruction and rerun guide. No ignored `.local/` or `work/` file is required as evidence or as the sole copy of a decision. The tracked sources of truth are:

1. [`results/fixed-capacity-phone-blocker.json`](results/fixed-capacity-phone-blocker.json) — final old-device boundary and all nine attempt classifications;
2. [`results/fixed-capacity-cpu-equivalence.json`](results/fixed-capacity-cpu-equivalence.json) — passing canonical-v2 CPU equivalence;
3. [`results/fixed-capacity-derivative-provenance.json`](results/fixed-capacity-derivative-provenance.json) — every fixed-shape/operator derivative;
4. [`results/fixed-capacity-context-provenance.json`](results/fixed-capacity-context-provenance.json) — host QNN context hashes, shapes, and reload gates;
5. [`results/source-lock.json`](results/source-lock.json) and experiment 0018's [`source-inventory.json`](../0018-moss-tts-nano-onnx-android/results/source-inventory.json) — official revisions, file sizes, and hashes;
6. [`protocol/fixed-capacity-equivalence-policy.json`](protocol/fixed-capacity-equivalence-policy.json) and [`protocol/fixed-capacity-phone-policy.json`](protocol/fixed-capacity-phone-policy.json) — frozen semantics;
7. [`README.md`](README.md) — concise result narrative.

Relevant commits:

- canonical transcript v2: `2de8b80be3a85341bee89ff6a5363e415e4f4d02`;
- experiment 0018 CPU source baseline: `f38c8aa76120e7540fffd09dccf47902bb463fbb`;
- experiment 0019 original dynamic/static map: `1a20d1f`;
- experiment 0019 fixed-capacity result: `de8d22cdcc1f4953219b5c23842ad3087ed5a26f`;
- exhaustive-only dashboard blocker: `fa7e96b477a26096871a77a5d90978d8fd152621`.

Read `.agents/skills/android-tts-benchmark/SKILL.md` and `protocols/android-tts-benchmark/contract.json` before collecting new evidence.

## What is established

### Reusable neural topology

The correct decode ABI is:

- 226 prefill positions;
- 375 maximum generated frames;
- 600-position pre-step decode input view;
- 601-position decode output and retained logical state;
- the physical graph output appends new K/V at index 600;
- CPU state orchestration copies that index into logical slot `past_valid_lengths`;
- attention consumes a derivative that inserts current K/V at the logical valid-length position;
- final call reads valid length 600, writes/retains slot 600, and has no following decode call.

Simple zero padding is invalid at step 0. Do not revive it. The accepted attention-insertion derivative passes all 375 recursive CPU calls, boundary steps `0/104/208/209/373/374`, final 601-state equality, and codec equivalence.

### Host QNN eligibility

All four final graphs compile as one fail-closed QNN partition:

- `prefill-s226-qnn.onnx`;
- `decode-fixed-cap600-attention-qnn.onnx`;
- `local-fixed-b1.onnx`;
- `codec-full-cap375-qnn.onnx`.

Four external QNN 2.49 contexts were generated and reloaded as one EPContext/QNN partition each. These artifacts are ignored and must be regenerated; their expected hashes and sizes are tracked in `results/fixed-capacity-context-provenance.json`.

### Old phone boundary

The old authorized phone was `R5CW81PR8SY / SM-S918B / SM8550`, Android 15/API 35, HTP V73. In the final minimal reproduction:

- carrier native hashes matched;
- `libcdsprpc.so` existed in `/vendor/lib64`, was listed in Samsung's `public.libraries.txt`, and was required by the APK manifest;
- the exact V73 skel was exposed at a unique world-readable tmp DSP path followed by standard RFSA paths;
- models/contexts were app-internal and hash-verified;
- CPU fallback was disabled;
- graph-I/O quantization was off;
- runtime SoC auto-detection was used;
- no burst/performance option or other optional device config was supplied.

QNN loaded backend interface 2.38, then `CreateDevice` failed with `QNN_DEVICE_ERROR_INVALID_CONFIG` before `GetCapability`, session assignment, or inference. This is bounded to that exact carrier/app UID/device/runtime path. It is not a general statement about QNN, Android, or host-context portability.

No physical HTP, phone RTF, phone memory, WAV, or listening evidence exists for 0019.

## Files intentionally not in Git

Do not look for these in Git history:

- official downloaded ONNX/external-data/tokenizer assets;
- Qualcomm QAIRT SDK contents;
- patched ONNX Runtime source/build outputs;
- specialized ONNX files and QNN contexts;
- host/Android binaries and carrier APKs;
- raw profiles, phone logs, tensors, and WAVs.

They are ignored because of size, licensing, or reproducibility policy. Their identities and reconstruction procedures are tracked here and in JSON results.

If a new model/SDK download presents authentication, gating, click-through terms, consent, or export attestation, stop and ask Moritz. Do not accept it automatically.

## Clean-machine reconstruction

Commands below assume repository root and may use different absolute installation roots through the documented environment variables.

### 1. Restore official assets

The Hugging Face repositories were public, anonymous, ungated, and Apache-2.0 when checked. Pin exact revisions:

```bash
EXP=experiments/0018-moss-tts-nano-onnx-android
mkdir -p "$EXP/.local"
git clone https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX "$EXP/.local/tts"
git -C "$EXP/.local/tts" checkout f52645cb467506d8e18e746ddd59482685b74e58
git -C "$EXP/.local/tts" lfs pull

git clone https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX "$EXP/.local/codec"
git -C "$EXP/.local/codec" checkout ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae
git -C "$EXP/.local/codec" lfs pull
```

The reconstruction script rejects any byte/size mismatch against `results/source-lock.json`.

### 2. Create the Python environment

The recorded deterministic stack was Python 3.12 with:

```bash
python3 -m venv experiments/0019-moss-tts-nano-qnn-htp-android/.local/venv
experiments/0019-moss-tts-nano-qnn-htp-android/.local/venv/bin/pip install \
  onnx==1.17.0 onnxruntime==1.20.0 numpy==1.26.4 \
  sentencepiece==0.2.1 pytest==8.3.5
```

### 3. Recreate exact ONNX derivatives

```bash
PY=experiments/0019-moss-tts-nano-qnn-htp-android/.local/venv/bin/python
$PY experiments/0019-moss-tts-nano-qnn-htp-android/tools/prepare_fixed_capacity_derivatives.py
```

The command writes `.local/specialized/fixed-capacity-manifest.json` and fails unless all eight derivative hashes equal the tracked expected values. The final hashes include:

```text
prefill-s226-qnn.onnx                     a974e163f7d17ab5b880992e4b1bbeb36e31d087110adfd24f660266b4597bbc
decode-fixed-cap600-attention-qnn.onnx    e9f87f69d1ead5d32746872d7ae462a337ddbb5f6a80eedaa08f1c14789567b9
local-fixed-b1.onnx                       f475a116f028f832606d4ca5f0bee5697bca2d0923a3a0a6cb28bd81585eaf02
codec-full-cap375-qnn.onnx                a7a5e97d5949bf6dff839745ba7a01c241b030c7b39d8987b5c9d529c467b7b9
```

### 4. Re-run canonical-v2 CPU equivalence

```bash
/usr/bin/time -v "$PY" \
  experiments/0019-moss-tts-nano-qnn-htp-android/tools/compare_fixed_capacity_cpu.py
```

This is memory-heavy. The recorded successful run peaked at `22,739,692 KiB` RSS and took 2:36.44. Start with at least about 25 GiB `MemAvailable` and do not overlap it with a QNN compiler. It must write a passing `results/fixed-capacity-cpu-equivalence.json` before QNN or phone work.

## Recreate the ORT/QNN toolchain

Required recorded versions:

- ONNX Runtime `v1.27.1`;
- upstream pad-selector backport at `experiments/0010-supertonic-qnn-htp-feasibility/patches/onnxruntime-a08e17-pad-empty-dq.patch`, SHA-256 `549be0692c1414ea35e97f401aaeb87ba55801480c7bd84dba0471cf25773bde`;
- QAIRT `2.49.0.260730` already licensed/installed by Moritz;
- Android NDK `26.2.11394342`;
- JDK 17, SDK/compile SDK 35;
- tracked QAIRT container recipe `experiments/0010-supertonic-qnn-htp-feasibility/host/Dockerfile.qairt-2.49.0`, SHA-256 `144e5e7d449c1c0b226a6b227a89ec19d62309cddb723721fd7680b772b6e2c7`.

Default local roots expected by scripts:

```text
/home/moritz/opt/qairt/2.49.0.260730
/home/moritz/opt/android-sdk
experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source
experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/Release
experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-android-arm64
```

Recreate source and patch:

```bash
git clone --branch v1.27.1 --depth 1 https://github.com/microsoft/onnxruntime \
  experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source
git -C experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source \
  apply ../../patches/onnxruntime-a08e17-pad-empty-dq.patch

docker build -t vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04 \
  -f experiments/0010-supertonic-qnn-htp-feasibility/host/Dockerfile.qairt-2.49.0 .
```

The experiment-0010 build scripts and records define the shared patched ORT toolchain. The essential flags are `--use_qnn shared_lib` for host and `--use_qnn static_lib --android --android_abi arm64-v8a --android_api 27` for Android.

After those builds:

```bash
experiments/0019-moss-tts-nano-qnn-htp-android/host/build_host_tools.sh
experiments/0019-moss-tts-nano-qnn-htp-android/device/build_android_runner.sh
```

Recorded library hashes were:

```text
host libonnxruntime.so      bc9df5a7df1b5d9de4d87adcaa4cc864bbde0f790e80d48e00ce0e4253a2ae11
Android libonnxruntime.so   40bc591798287525f365e8ded4bbc40e0c4e9440737e876026ec09ba359ac041
host libQnnHtp.so           e557ca522713ea7ee7efd252083b927009cd54c158899c086b23d92b63bf1f33
Android libQnnHtp.so        a09b3af28342331b3ec9e57ecbe42bfe54a5fff37c4323ce5685c395ae3ee604
```

Override defaults with `ORT_SOURCE`, `ORT_HOST_BUILD`, `ORT_ANDROID_BUILD`, `QAIRT_ROOT`, `ANDROID_NDK_ROOT`, `ANDROID_API`, or `QAIRT_IMAGE`.

## Target-specific QNN contexts

Contexts are target-specific research artifacts. For the old SM8550/V73 route:

```bash
SOC_MODEL=43 experiments/0019-moss-tts-nano-qnn-htp-android/host/generate_qnn_contexts.sh
```

The compiler is memory-heavy and must run without another near-machine-size QNN job. It samples `MemAvailable` and swap every second. Check its generated hashes against `results/fixed-capacity-context-provenance.json`.

For another SoC, do **not** reuse SM8550 contexts blindly. Determine the QAIRT `Qnn_SocModel_t` value and HTP architecture for that exact device, then set `SOC_MODEL` and `HTP_ARCH`. If unsure, begin with source ONNX (`USE_CONTEXTS=0`) and runtime SoC auto-detection.

## Run on another phone

### Required authorization

The old serial/model/SoC are not authorization for another device. Get Moritz's explicit new device identity first. Never weaken identity gates to “any connected device.” Use Windows ADB with `ADB_LIBUSB=1` where applicable, hold `artifacts/locks/phone.lock`, and ensure the lock FD is closed for every ADB child.

Scripts now accept target identity through environment variables while defaulting to the old phone:

```text
SERIAL
EXPECTED_MODEL
EXPECTED_SOC
EXPECTED_ABI       default arm64-v8a
HTP_ARCH           default 73
ADB
```

Before model work, verify on the new phone:

- exact serial/model/SoC/ABI/Android API;
- HTP architecture and matching QAIRT stub/skel;
- `/vendor/lib64/libcdsprpc.so` exists;
- `libcdsprpc.so` appears in a public native-library list;
- enough free internal storage for the selected stage;
- no stale experiment package or tmp stage.

### Recommended order

1. Re-run derivative hash and CPU-equivalence gates.
2. Test a tiny app-UID QNN/HTP smoke first. The old phone failed before graph assignment, so prove `CreateDevice` on the new carrier namespace before transferring large models.
3. For the same SM8550/V73 target, try regenerated context mode first:

   ```bash
   USE_CONTEXTS=1 HTP_ARCH=73 \
     experiments/0019-moss-tts-nano-qnn-htp-android/device/prepare_phone_stage.sh
   ```

   For another SoC, regenerate contexts with its `SOC_MODEL` and `HTP_ARCH`, or use source mode:

   ```bash
   USE_CONTEXTS=0 HTP_ARCH="$HTP_ARCH" \
     experiments/0019-moss-tts-nano-qnn-htp-android/device/prepare_phone_stage.sh
   ```

4. Inspect the generated stage manifest and carrier native manifest.
5. Run only with explicit phone-use confirmation and exact new identity:

   ```bash
   PHONE_USE_CONFIRMED=yes \
   SERIAL="$SERIAL" EXPECTED_MODEL="$EXPECTED_MODEL" EXPECTED_SOC="$EXPECTED_SOC" \
   EXPECTED_ABI=arm64-v8a HTP_ARCH="$HTP_ARCH" \
   ADB="$ADB" \
     experiments/0019-moss-tts-nano-qnn-htp-android/device/run_phone_all_htp.sh
   ```

The phone script uses unique staging, app-internal models, exact upload/internal/native/skel hashes, required `libcdsprpc.so`, unique DSP staging, thermal/battery capture, cleanup, uninstall, and lock release. Audit it again for the new OEM/Android build before execution.

## Success requirements for a new physical run

A full-HTP result requires all of the following; partial success is not enough:

- all four sessions create with CPU fallback disabled;
- prefill, every autoregressive decode call, every local-frame call, and codec call report QNN-only ORT provider events;
- zero CPU neural-provider events;
- matching physical RPC execute, accelerator time, accelerator cycles, and four-HVX evidence for every expected call;
- application CPU work is disclosed: fixed token IDs/prompt assembly, RNG/repetition orchestration, K/V slot copy, mono averaging, WAV encoding;
- benchmark process has one first generation plus at least five warm generations in the same sessions, with complete state reset before every run;
- every run completes the canonical-v2 utterance and reports actual emitted duration and per-run RTF;
- profile process is separate from unprofiled timing;
- setup, first/warm median, process memory method, thermal/battery context, and cleanup are retained;
- valid finite mono PCM16 48 kHz WAV and exact SHA-256;
- listening status remains `not_reviewed` until Moritz hears that exact new-device WAV, preferably blind against a matched CPU derivative sample.

A numerical difference is descriptive, not a listening rejection. A mixed diagnostic must never be called full HTP.

## What to update after a successful later run

Do not rewrite the old blocked record. Add a dated/device-specific continuation checkpoint and route. Retain:

- new device identity and authorization;
- source/derivative/runtime/context/carrier hashes;
- raw six-run CPU and HTP metrics;
- separate profile/provider/physical summaries;
- memory, thermal, battery, output metadata, hashes, cleanup;
- blind mapping and Moritz's exact route/sample-scoped verdict.

Commit the experiment evidence first. Then hand the commit to the dashboard owner. The existing exhaustive-only blocked route `0019-moss-canonical-v2-qnn-phone-blocked` must remain historical evidence even if another device succeeds.
