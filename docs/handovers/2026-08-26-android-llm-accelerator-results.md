# 2026-08-26 — Android LLM accelerator results

Persistent handover after completing the authorized CPU and GPU benchmark work for Gemma 4 E2B IT, Qwen3.5-2B, and LFM2.5-2.6B, and after recording exact pre-conversion blockers for their QNN/HTP routes. This supersedes the resume plan in the earlier [parallel-experiments handover](2026-08-26-parallel-llm-experiments.md) where later committed evidence differs.

## Sessions and responsibilities

The work was coordinated through existing user-created Pi Messenger sessions:

- Pi: orchestration, phone/resource ordering, and independent evidence verification;
- Jere: Gemma 0025 CPU/GPU work and the shared protocol-v2 amendment;
- Ben: Qwen CPU/Vulkan/OpenCL work and LFM loaded-route CPU/OpenCL work;
- Jens: Gemma, Qwen, and LFM QNN/HTP feasibility work;
- Omer: experiment HTML and Android LLM registry/dashboard publication.

The local session logs are not required to resume. Committed owning evidence, this handover, and each experiment README/contract are authoritative.

## Repository and machine state at handover

- Branch: `main`.
- Last verified publication commit before this handover: `6245e85` (`Publish LFM Android OpenCL benchmark`).
- `main` was 36 commits ahead of `origin/main` before adding this handover. These commits had **not yet been pushed**.
- Working tree was clean before adding this handover.
- Android LLM registry validation and deterministic dashboard generation passed with six canonical rows.
- Global experiment-page generation check and 16 shared registry/page tests passed.
- No benchmark, inference, conversion, build, or ADB child process was running.
- `artifacts/locks/phone.lock` and `artifacts/locks/heavy-ram.lock` were free.
- Authorized phone `R5CW81PR8SY` was connected as `SM-S918B` / `SM8550` when checked.
- Final committed phone runs report their experiment-scoped remote roots removed and verified absent; no experiment process remained.
- Filesystem had about 720 GiB free; the machine had about 21 GiB available RAM.

### Windows-owned USB ADB bridge

Windows owns the physical USB device. The reliable bridge used by WSL is:

- Windows executable: `C:\Users\mgottschling\AppData\Local\Android\platform-tools-pi\adb.exe`;
- daemon invocation: `adb.exe -a -P 5037 nodaemon server`;
- WSL client setting: `ADB_SERVER_SOCKET=tcp:172.27.80.1:5037`;
- authorized serial: `R5CW81PR8SY`.

The Windows daemon occasionally remained alive while losing its USB transport. A clean daemon restart that forced a fresh USB/auth scan restored it. Physical connection alone is not sufficient: verify both `adb devices -l` and `adb -s R5CW81PR8SY get-state` before taking `phone.lock`.

## Shared benchmark contract

Commit `01c94c1` amended the Android LLM protocol to version 2 semantics. The expensive loaded model/runtime route is reused, while per-request isolation may use either a proven complete in-session reset or a fresh Session. Session/reset duration is recorded separately, model remapping/reloading and accelerator recompilation are forbidden, and retained prompt/KV state is forbidden.

Commit `1354d36` clarifies that a bounded smoke is only a viability milestone. A numbered benchmark experiment targets its intended end-to-end canonical campaign. If that cannot be reached, the experiment remains active, blocked, or stopped with durable evidence; a smoke alone cannot make it complete or produce a canonical leaderboard row.

Canonical workload hashes remain:

- short: `81d23ec04cb821625d3717ab50db7df3d9821a8d2987f1eb107fc90df9d1f2ae`;
- medium: `5e168aa3232f06c92959b686188192471b2d1a62cd1c857a616fd8e29456ddf1`;
- long: `092840fbe879259110fa4d0b15bc383012f16b7b42a38d224b2ead231e86aad8`.

## Completed canonical Android routes

The registry contains six normalized rows. All routes ran one first short request plus five loaded-route requests for each of short, medium, and long. Token counts and rates are route-specific because tokenizers differ.

| Model / route | Owning evidence | Setup | Warm medium median: TTFT / prefill / decode / total | Peak sampled PSS | Publication |
|---|---|---:|---|---:|---|
| Gemma 4 E2B IT, LiteRT-LM CPU | `12e0e32` | 6.474 s | 7.560 s / 80.08 tok/s / 10.28 tok/s / 75.57 s | 5,726,960,640 B | `8d5d9d9` |
| Gemma 4 E2B IT, LiteRT GPU | `c2d1906` | 10.520 s | 1.339 s / 485.17 tok/s / 13.16 tok/s / 50.80 s | 1,003,954,176 B | `1605cf4` |
| Qwen3.5-2B Q4_K_M, llama.cpp CPU | `8ee4679` | 2.936 s | 16.689 s / 38.72 tok/s / 8.77 tok/s / 81.02 s | 2,833,463,296 B | `0efcc4e` |
| Qwen3.5-2B Q4_K_M, llama.cpp OpenCL/Adreno | `338091e` | 17.113 s | 9.186 s / 66.74 tok/s / 7.93 tok/s / 81.53 s | 1,365,059,584 B | `a2c457c` |
| LFM2.5-2.6B Q4_K_M, llama.cpp CPU | `8c71f03` | 15.806 s | 20.378 s / 30.34 tok/s / 7.94 tok/s / 230.93 s | 3,559,703,552 B | `4d29867` |
| LFM2.5-2.6B Q4_K_M, llama.cpp OpenCL/Adreno | `306c777` | 20.764 s | 10.282 s / 60.53 tok/s / 7.14 tok/s / 296.00 s | 675,495,936 B | `6245e85` |

Registry route IDs:

- `0025-gemma-4-e2b-it-litert-lm-cpu`;
- `0025-gemma-4-e2b-it-litert-lm-generic-gpu`;
- `0027-qwen35-2b-unsloth-q4km-llamacpp-cpu`;
- `0035-qwen35-2b-unsloth-q4km-llamacpp-opencl-adreno`;
- `0033-lfm25-26b-liquidai-q4km-llamacpp-cpu`;
- `0033-lfm25-26b-liquidai-q4km-llamacpp-opencl-adreno`.

Read the normalized registry and owning `result.json` files for exact per-request values, output hashes, stop reasons, thermal context, and limitations. GPU/OpenCL routes are not GPU-exclusive: their provider proof binds actual accelerator buffers/layer offload while retaining disclosed CPU orchestration and unsupported-operation boundaries. Process PSS/VmHWM excludes independently allocated GPU-private/vendor memory.

## Experiment outcomes

### 0025 — Gemma 4 E2B IT

Complete CPU and GPU campaigns are committed and published.

- Shared fresh-Session protocol amendment: `01c94c1`.
- Experiment runner/contract amendment: `0eb92be`.
- CPU campaign: `12e0e32`.
- Initial dedicated 2,008 MB Artisan GPU artifact blocker: `eb1465c`. LiteRT-LM selected `GPU_ARTISAN`, but the available runtime registered no compatible legacy engine. It produced no request or GPU metric.
- Approved generic-artifact GPU route amendment: `566fa25`.
- Canonical provider-proven GPU campaign: `c2d1906`.
- CPU/GPU publication: `8d5d9d9` and `1605cf4`.

GPU campaign provider proof includes the GPU-only/no-CPU-fallback backend bit, fully delegated single-delegate hint, LiteRT GPU accelerator and Qualcomm/Adreno driver mappings, and open `/dev/kgsl-3d0`. The historical Artisan blocker and a non-counted missing-cache launch diagnostic remain visible.

### 0027 — Qwen3.5-2B CPU

Complete canonical CPU campaign is committed and published.

- Reproducible UI-disabled Android artifact: `f0b10dd`.
- Complete CPU campaign: `8ee4679`.
- Publication: `0efcc4e`.

The older smoke/interrupted evidence remains bound to its historical executable. Do not relabel it as the canonical campaign.

### 0029 — LFM2.5-2.6B viability predecessor

Commit `b5c1c73` contains a one-request Android CPU viability smoke. Page publication is `d57db13`. It remains viability-only historical evidence and has no registry row. The completed persistent CPU/OpenCL routes are owned by 0033; never promote the 0029 smoke itself to canonical evidence.

### 0030 — Qwen3.5-2B Vulkan

Blocked before request one and published as blocked.

- Reproducible Vulkan route preparation: `b8be3bb`.
- Durable provider blocker: `115d315`.
- Blocked page: `c286c65`.

Three controlled variants all failed on Adreno 740 while creating `mul_mat_vec_q5_k_f32_f32`: baseline NDK `glslc`, `GGML_VK_DISABLE_F16=1`, and pinned Ubuntu shaderc/glslc 2023.8. Every attempt failed before health/model readiness and produced no inference or performance metric. The successful OpenCL route is separately owned by 0035 and must not be called Vulkan.

### 0035 — Qwen3.5-2B OpenCL/Adreno

Complete canonical OpenCL campaign is committed and published.

- Reproducible host/phone-ready artifact: `d30b5a3`.
- Zero-device preflight diagnostic: `9dbf590`.
- Provider-bound smoke milestone: `64e0869`.
- Complete campaign: `338091e`.
- Publication: `a2c457c`.

Provider evidence binds sysfs Adreno740v2, Qualcomm OpenCL 3.0 compiler E031.41.03.64, Adreno source kernels, 25/25 layer offload, and OpenCL model/KV/recurrent/compute buffers. CPU and CPU_REPACK model buffers, CPU compute, CPU orchestration, and disabled Flash Attention remain explicit.

### 0033 — LFM2.5-2.6B persistent CPU and OpenCL

Both canonical arms are complete and published.

- Persistent CPU/OpenCL route preparation: `72adc37`.
- Complete CPU campaign: `8c71f03`.
- Complete OpenCL campaign and final local-state inventory: `306c777`.
- CPU/OpenCL publications: `4d29867` and `6245e85`.

The CPU arm uses `--device none --gpu-layers 0`. The OpenCL arm proves sysfs Adreno740v2, Qualcomm OpenCL, Adreno source kernels, 31/31 layer offload, and exact OpenCL model/KV/recurrent/compute buffers. The two arms use separate staged artifacts, remote roots, evidence, and registry rows.

## QNN/HTP routes — blocked before conversion

None of the QNN experiments produced a context binary, accessed the phone, executed on Android, or established HTP performance. Their pages are published as blocked with no registry rows in commit `da8d6d9`.

### 0031 — Gemma 4 E2B IT QNN/HTP

- Initial support assessment: `956545d`.
- Durable transform blocker: `83bc2fe`.

Installed QAIRT resolves SM8550 to HTP v73 but has no Gemma4 architecture dispatch. The exact public W4A16 ONNX+encodings checkpoint was downloaded and verified. The smallest faithful transform fails before conversion/compile during ShapeInference → ConstantPropagation → `get_constant_np` with `KeyError('value')`.

### 0032 — Qwen3.5-2B QNN/HTP

- Durable support blocker: `44da2f2`.

Installed direct-GGUF support covers qwen2/qwen3, not qwen35. No public 2B quantized ONNX+encodings or SM8550 QNN context was found. The installed Qwen3.5 specialization is 4B-derived and dimension-incompatible with the 2B model; borrowing it would weaken model identity.

### 0034 — LFM2.5-2.6B QNN/HTP

- Durable support blocker: `cd82622`.

Installed QAIRT has no `lfm2` GGUF support, HTP factory dispatch, Genie configuration, or public Qualcomm recipe/context. LFM's hybrid 22 convolutional-state plus 8 attention layers requires model-specific conversion, runtime orchestration, and reset proof.

### Explicit authorization required to resume QNN

At least one of the following is required:

1. provide provenance-bound SM8550/HTP-v73 contexts and complete runtime/LUT bundles for the exact models;
2. explicitly authorize authenticated Qualcomm AI Hub/Workbench/engineering access and any service terms or costs;
3. explicitly authorize installing and binding a newer licensed QAIRT/toolchain;
4. explicitly authorize new architecture-aware converter/runtime engineering, including host numerical equivalence, context identity, full HTP partition/no-fallback proof, and request-state isolation.

Without this authorization, preserve 0031/0032/0034 unchanged. Do not use generic fallback, mismatched model configurations, borrowed metrics, authenticated Qualcomm services, new SDKs, or ad hoc graph patches.

## Publication state

Publication infrastructure preparation is commit `172c13e`. The dashboard and pages use protocol-v2 `loaded_route` terminology and record route-specific isolation instead of falsely requiring reuse of one runtime Session object.

Published pages:

- 0025: completed CPU + GPU;
- 0027: completed CPU;
- 0029: active viability predecessor, no row;
- 0030: blocked Vulkan, no row;
- 0031: blocked Gemma QNN, no row;
- 0032: blocked Qwen QNN, no row;
- 0033: completed CPU + OpenCL;
- 0034: blocked LFM QNN, no row;
- 0035: completed OpenCL.

Final publication validation at `6245e85`:

- registry validate → build check → validate: pass with six rows;
- shared registry/page suite: 16/16;
- global generated-page `--check`: pass;
- dashboard and pages regenerate deterministically;
- no speculative Vulkan or QNN performance row exists.

## Machine-local assets

Committed evidence and build recipes are authoritative. Ignored assets below are useful to avoid multi-gigabyte downloads but are not required for publication.

### Shared prerequisites

- NDK r28b: `/home/moritz/opt/android-sdk/ndk/28.1.13356709` and `/home/moritz/Android/Sdk/ndk/28.1.13356709` were present; verify `Pkg.Revision = 28.1.13356709`.
- Windows Platform Tools: `C:\Users\mgottschling\AppData\Local\Android\platform-tools-pi`.
- Installed QAIRT: `/home/moritz/opt/qairt/2.49.0.260730`, approximately 5.7 GiB; `sdk.yaml` SHA-256 `309ac8f6c75c2fdc808f1c9b9d0da60be123c21a79532cca70a9c4b144d983f4`. It was preinstalled; no license was accepted during this work. Do not assume it may be copied to another machine.

### Gemma / Qwen / LFM assets

- 0025 `.local/`: LiteRT-LM checkout `924e79c…`, generic model 2,588,147,712 B / SHA `18193810…a63c`, historical Artisan model 2,008,432,640 B / SHA `a53a5900…5cf5`, Bazelisk, Android prebuilts, and build trees.
- 0027/0030/0035 `.local/`: Qwen GGUF 1,280,835,840 B / SHA `aaf42c8b…9223`, pinned llama.cpp/build trees, Vulkan diagnostics, and OpenCL artifacts.
- 0029/0033 `.local/`: LFM GGUF 1,674,455,040 B / SHA `02a8b7e…52ed`, pinned llama.cpp/build trees, and staged CPU/OpenCL servers.
- 0035 `.local/` was about 3.3 GiB. Its OpenCL server is 12,313,808 B / SHA `64409e6e…4ced`.
- 0033 `.local/` was about 3.7 GiB. Its CPU server is 9,844,576 B / SHA `8ce2767e…b217`; its OpenCL server is the same 12,313,808 B / SHA `64409e6e…4ced`. See committed `experiments/0033-lfm2.5-2.6b-android-loaded-route/LOCAL_STATE.md`.

### QNN assets

0031 `.local/` was about 13 GiB:

- public ZIP: 2,013,959,998 B / SHA `ed45053c8582f2646fb8dd80e0d8f55a462394199160bade96401615b6ce84a7`;
- `model.data`: 9,119,006,720 B / SHA `e156c33d176273555003039959ecb0ae0ddc8a328eceeec1e8f4a6255840e072`;
- `model.encodings`: 74,795,410 B / SHA `254c439615e1c0a7b40fb0076c844cc3f9a5ec7ef0b93001077eec2adb228e9c`;
- `model_dynamic.onnx`: 20,653,219 B / SHA `51d4e8183a6734a8c7bbd24ebc072768f080e54b011725ae645dfa32498bf0d0`;
- tokenizer: 32,169,626 B / SHA `cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f`.

0032 and 0034 retain reproducible tokenizer/QAIHM environments but no authorized conversion weights or context.

## Safe resume order

No currently authorized benchmark execution remains unfinished. On a future machine:

1. pull the handover commit and read this file plus the owning experiment README/contract before rebuilding;
2. validate the six-row registry and generated pages;
3. provision exact local dependencies from committed URLs/revisions/hashes rather than copying unverified binaries;
4. resume QNN only after Moritz explicitly selects an authorization option above;
5. before any phone work, verify authorized serial, take `phone.lock`, require the experiment root absent, preserve raw/checkpoint evidence before validation, and clean only the scoped remote root;
6. never resume or count a partial canonical campaign;
7. add a newer dated handover when work moves again.
