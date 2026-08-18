# Plan — faithful Kokoro FP ONNX Runtime versus ExecuTorch on Android CPU

## Scope

Compare two Android CPU deployment routes for the **same official Kokoro v1.0 model**:

1. unquantized floating-point ONNX Runtime; and
2. current supported ExecuTorch using `torch.export`, preferably lowered to XNNPACK CPU.

The source is fixed to `hexgrad/Kokoro-82M@f3ff3571791e39611d31c381e3a41a3af07b4987`, `kokoro-v1_0.pth`, and `voices/af_heart.pt`. No q8/q4 artifact, experiment-0009 QDQ graph, HTP, QNN, NNAPI, GPU, Vulkan, or other quantization/acceleration path is eligible. Large inputs, builds, binaries, raw evidence, serial-bearing logs, and WAV files remain ignored.

## Step 0 — prospective contract

Before physical outputs, freeze [`protocol/benchmark-policy.json`](protocol/benchmark-policy.json): exact text, voice, speed, source revision, one-thread request, route order, one first plus five warm generations, audio gates, source-fidelity thresholds, timing boundaries, memory semantics, and stop conditions.

## Step 1 — source and representation proof

1. Download only the pinned official model/config/voice and record resolved URLs, LFS metadata, byte sizes, hashes, and Apache-2.0 evidence.
2. Pin and hash the official Kokoro Python implementation used to instantiate `KModel`; record PyTorch and export/runtime versions.
3. Use the pinned sherpa v1.0 FP32 ONNX only if all of the following are established:
   - the archive and graph match their existing project pins;
   - graph initializers derive from the exact official checkpoint;
   - the graph implements the official `KModelForONNX` path without quantization;
   - the selected `af_heart` tensor is losslessly identical to the official `.pt` tensor;
   - source PyTorch and ONNX pass the prospective exact-input host fidelity gate.
4. Use the real tokenizer/phonemizer assets. Prove the selected text is completely covered by the pinned US-English lexicon, resolve its token IDs at runtime, select `af_heart[token_count]`, pass speed `1.0`, and run the complete model. Neural intermediate fixtures are forbidden.

## Step 2 — bounded ExecuTorch export screen

1. Run eager source inference for the exact deployment inputs.
2. Attempt `torch.export.export` on the exact required official model wrapper with fixed example shapes first; separately record a bounded dynamic-shape attempt only when supported constraints are meaningful.
3. Capture graph breaks, unsupported operators, data-dependent control flow/shapes, decompositions, and required kernels. Narrow wrappers or standard decompositions are allowed only with source-equivalence tests and explicit provenance.
4. If portable export succeeds, lower with current ExecuTorch CPU tooling (prefer XNNPACK), serialize `.pte`, run the host ExecuTorch runtime, and require the same prospective fidelity gate.
5. Stop and report if completion would require broad model surgery, semantics-changing padding, a custom kernel, or an unbounded export investigation. A bounded exact blocker is a valid route-B result.

## Step 3 — Android CPU runs

Only host-eligible routes proceed.

1. Build a deterministic arm64 Android harness that shares one text frontend, token/style/speed construction, WAV writer, and metrics implementation between routes.
2. Use a fresh process per route. Measure frontend/model asset loading, runtime initialization/session construction, first complete generation, five warm complete generations, component timing where exposed, WAV encoding, RTF, actual token/style/audio shapes, output validity, and `/proc/self/status` `VmHWM` with its high-water limitation.
3. Prove CPU-only execution from runtime configuration/package inventory and route evidence. Zero QNN is mandatory.
4. For each successful route, retain the first-generation mono 24-kHz PCM16 WAV under ignored `work/` and record its absolute path and full SHA-256.
5. Use only the authorized `R5CW81PR8SY` / `SM-S918B` / `SM8550`. Acquire `artifacts/locks/phone.lock`; use Windows `adb.exe` with `ADB_LIBUSB=1`; close lock FD 9 on every ADB call; verify identity; use a unique experiment-0013 remote stage; never inspect personal data; pull scoped evidence; remove all scoped remote state; release the lock.

## Step 4 — checkpoint and stop

Commit deterministic tools, policies, documentation, source manifests, and bounded checkpoints only. Report per-route status, exact representation rationale, source/voice provenance, package sizes, host fidelity, phone latency/memory/shape/provider evidence, WAV paths and hashes, blocker details, remote cleanup, lock release, and repository status to Pi. Stop before any HTP/QNN or quantization work.

## Outcome

- The sherpa `disable_complex=True` FP32 graph was rejected for this exact-source comparison.
- A deliberate exact-source-derived FP32 fixed-contract ONNX passed controlled-eager equivalence, ONNX checker, host ORT CPU validity/provider checks, and the separately frozen phase-tolerant acoustic policy. The earlier `.999/.01` host ORT waveform screen remains failed.
- ExecuTorch stopped before a full-model PTE because the duration-driven `repeat_interleave` length is data-dependent and then consumed by LSTMs; the official complex inverse STFT is an additional edge-lowering blocker. No broad rewrite or custom kernel was attempted.
- The only eligible phone route stopped twice before ORT initialization. After the one authorized path-check correction, Android scoped-storage ownership still made the shell-copied app asset invisible as a regular file. Both scoped stages were removed and locks released.
- Consequently no phone model inference, WAV, latency, RTF, or memory result exists for either route. The experiment stops with host representation evidence and exact deployment blockers only.
