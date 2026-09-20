# Handoff — Gemma4 E2B QNN/HTP long-output collapse investigation

Written 2026-09-14 by Jere, on request from Moritz through Pi, closing this investigation for now.

**Gemma's long-output repetition collapse remains UNRESOLVED. Nothing in this work proves a QNN defect, a quantization-only cause, or any model/runtime correctness verdict.** No work continues after this document.

Paths below are relative to `experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/` unless stated otherwise. Restricted SDK/model/DLC artifacts, raw input/logit vectors, captured payloads and device dumps stay private under `.local/`; published packages contain hashes, scoped metadata and bounded derived statistics only.

## 1. Current state

- No phone lease, no `artifacts/locks/phone.lock` ownership, no host job, no reservations, no remaining execution grant.
- The last authorization (one bounded run of the frozen embedding-boundary checkpoint) was **withdrawn before any execution**. Nothing from it ran.
- All committed evidence is on `main`. The latest relevant commits are listed in §9.

## 2. Canonical problem, unchanged

The canonical max2048 campaign (`37a2953`, registry `e91b3f5`, baselines `f24fd21` / `1c5b7b6`) remains the reference symptom: one SM8550 HTP route, 15 resets/16 requests, 117 AR128 + 15,158 AR1 executions all status 0, and severe repetition collapse on the long tier (baseline period 9, suffix 1,570 tokens, 174 cycles + 4, max history 3,977 < 4,096). Warm TTFT 462433/907551/2605519 µs. None of the later work changed or reproduced a fix for this.

## 3. Established (with their exact limits)

### 3.1 FP16 static-storage defect and the preserved invalid v1 reference

- The original complete declared-policy host reference ran to completion (`legacy-ref-20260913T131149Z-01`) and disagreed badly with the captured QNN endpoint: 0 equal codes, top-20 overlap 0, cosine −0.50660946, MAE 27.3911266.
- A later static audit proved the cause was a **reference-side storage defect**, not a model finding: all 30 declared Float16 static tensors were saved by IR extraction as NumPy `uint16` transport words, so 15 RMS gamma tensors with `0x3c00` (binary16 one) were numerically cast to `15360.0` (4,608 wrong gamma values; first affected operator `op52 rms_norm_node___413645`; 240 affected invocations in the saved trace).
- Audit: `e6085004153ee38eb1c0d5bb0c8c865cbd56a87f`, `results/declared-reference-static-audit-01/`, result SHA `39dad46b698bc4e5fc454961061e0937794335889920579756436e184ae3a048`.
- The invalid run is **preserved, not deleted or relabelled**: `fe6c4df8db616a7b1a8235e4c7d55530f056b981`, `results/paired-declared-policy-prefill-01/` with an additive `INVALID-REFERENCE.json` and README banner. Its vectors, comparison and exits are unchanged.
- The immutable defective adapter is pinned at `declared_dlc_reference.py` SHA `06f108e24d5370d94e57b24cb8e285106deeef8be0d03d9f29b28187b4cd2045`.
- Independent support for the BW4 signed weight interpretation (not chosen to fit logits): `QnnTypes.h` definitions plus exact/near-exact agreement against a hash-verified float export (LM head 1,572,864 sampled values exact; complete q_proj 393,216 codes match, max float error 1.49e−8).

### 3.2 Storage-corrected reference: partial, no final vector

- Fix frozen at `e260dcf8d85d18bff032adb906ffe1535294cbe1`, `results/corrected-reference-storage-readiness-01/` (344 tests / 21 hashes). Corrected adapter SHA `3ececc8f93c6535a728bfa38eac64c471eafb72fdf13df57d0b25ae625c57582`; `storage_view()` normalizes only declared Float16 uint16 words, leaving true UF16 and BW4 untouched.
- The corrected run `corrected-ref-20260914T082259Z-01` completed 5 of 16 chunks and **stopped at the first non-finite intermediate**: chunk 5, operator 6294 `node_pow_606`, phase `logical_op`, `divide by zero encountered in power`, recorded in `native/nonfinite-first.json`. `stop_reason: null` — not a memory or time stop.
- Package: `5aaf7e29484c2bd0912a1681c9c156a0c73c4109`, `results/corrected-declared-policy-prefill-01/`. **There is no corrected final vector and no corrected comparison.** Both full-reference grants are consumed.
- A saved zero-boundary audit established that `0^-0.5 → +Inf` is an IEEE pole, not NaN, and that the declared epsilon (`val_54` raw 655 → 9.994658967116266e−7 ≈ 4.29181855e−5 grid steps) changes **zero** of the 65,536 mean codes. No epsilon floor, clamp or arithmetic repair was introduced.

### 3.3 Complete paired capture (the one genuinely matched dataset)

- `legacy-prefill-20260913T125558Z-01`: 129 raw payloads / 66,060,288 B — **128 actual non-cache inputs across 16 AR128 chunks plus the full final row-8 logits** (524,288 B, SHA `7b6c6e2d755a024e59d8ac05fbe4a27e992bfa4774c2286fff85144da26bafe9`), captured before the original dequantization and before the sampler.
- Reaching it required relocating the observer to the real dispatch path (`NspEngine::process` → `processAll` → legacy `runInference(...)` → `getDequantLogits`); the earlier hook in `getLogits(Tensor&)` was never dispatched. Readiness `6550abb59ea228b4c2e22b4bb27cfa1ab4e4250c`.
- Strict host binding: `ade71463e89ef5ae2e3f917d1ccdd7edfa42ca41` + `1257b57127dcb000a6a6f0a5cfe8b3a5ebf28e30`, `results/paired-legacy-host-binding-01/`. All 128 captured input arrays / 32,768,000 UINT16 codes matched the prepared host formulas with **zero differing elements**.
- Exact history: 1,929 single-BOS IDs, SHA `3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64`.

### 3.4 Isolated physical HTP observations (tiny fixtures only)

All three used the same frozen three-graph stage `htp-power-edge-stage-01` (manifest `51053482d9d0d198b43343830503d8c1c3d2ee3337c4ccb598e792248dffb993`, context `6cd4e825a5a55430ced91b2238ab0c060ab60b7956f49dd84c248246087c0ee4`), with no learned weights, no LLM inputs, no LUTs, no Genie and no CPU fallback.

| Observation | Commit / package | Result |
|---|---|---|
| Power edge | `1e8b74fe2168f526372ca5f707182d62ca1a1c91`, `results/htp-power-discriminator-phone-03/` | Input `[0,1,2,65535]` → `[65535,62816,44417,245]`, 32× |
| Chain + exposed chain | `b31e5ca98aab4e5159e7b5670441950af60ebbcf`, `results/htp-chain-discriminator-phone-01/` | Normalized `[31507,31549,33778,33552]`; exposed squared `[0,0,1,20]`, mean and denom both `[1,1,22,434]`, inverse `[62816,62816,13392,3015]` |
| Isolated Mean / epsilon-Add | `2e465ac4b9f0022dbfc71c22ea0db7fff936343d`, `results/htp-mean-add-phone-01/` | Mean `[1,1,22,434]` (64/128 codes differ from the literal comparator by one quantum); Add `[0,1,22,434]` (0/128 differ) |

Scope limits that must not be dropped:

- Zero → 65535 for Power is valid **for that fixture only**; it is not a general normalization or full-model policy.
- The chain/exposed final outputs are byte-identical (`74767fb3…`) and mean/denom are byte-identical (`9bcb2e46…`), but **native buffer addresses/FDs were never captured**: distinct tensor IDs and equal files do not prove buffer independence, absence of fusion, or any aliasing/materialization mechanism.
- The isolated Mean shows the low code 1 **without** Add, Power or multi-output exposure, so chain fusion is not needed to explain it — but this is specific to that shape, grid, backend and those inputs. **No universal mean floor, rounding law or `max(1,q)` patch was adopted.**
- Reviewed SDK docs (`MasterOpDef.html`, `HtpOpDefSupplement.html`, `general/quantization.html`, `general/htp/htp_backend.html`) define semantics, UF16 support and general converter quantization, but supply **no** ReduceMean minimum-one rule, instruction-level rounding scheme or runtime error tolerance.
- CPU fixtures (unsupported exact-UF16 Power; F32 Power → Convert mapping ±Inf/NaN to code 0) are **CPU behaviour and must not be transferred to HTP**.

### 3.5 Endpoint rank packet (last executed comparison)

`a305bd0ab4641d22b4609738f4fdf5f5a5210e1b`, `results/saved-endpoint-ranks-01/`, result SHA `c64474f98dbeef9bde6d9ee8fb3d4e882cc4368135c12355ad961f3e575e57ef`. Valid native-QAT CPU endpoint vs the actual captured QNN endpoint after the same 1,929 IDs; the invalid v1 and partial corrected references were **not** used.

| Quantity | Value |
|---|---|
| Native unique argmax 8291 | rank **3** in QNN |
| QNN unique argmax 818 | rank **5** in native |
| Top-5 / top-20 overlap | **4/5**, **13/20** |
| Tie-aware top-128 overlap | **79–80/128** (native 13-way tie at ranks 128–140 for 1 slot) |
| Global tie-aware Spearman | **0.8883254478291734** |

Both winners are unique (no tie decides them). **High global correlation does not mean small decision or prefill drift** — the vocabulary tail can dominate the global statistic, which is why winner displacement, fixed top-k disagreement and tie structure are reported separately. Native endpoint SHAs: BF16 `021585a7…528c`, exact F32 expansion `f2c76d88…53ec`.

Interpretation, unchanged: the routes already differ in unique winner and top-k membership **before decode**, so those differences were not created entirely during decoding. This does **not** mean the repetition is explained at prefill, does not exclude a decode-specific mechanism, and is not matched-policy ground truth (native mixed INT2/4/8 BF16/SRQ vs calibrated QNN/HTP, plus different upstream embedding/PLE and LUT requantization math).

## 4. Disclosed output-budget exception (do not quietly drop)

During preparation for the endpoint packet, an overly broad metadata print expanded a full per-channel head-encoding descriptor into a private tool-managed spill file of **18,753,798 B**, `/tmp/pi-bash-23fa864ca3738bb5.log`, SHA `5f8f53c886f4937fea7570cf384330783b920886183cf20bbf3d3737050c5513`.

Therefore the overall 1 MiB new-output bound for that assignment was **not met**, even though the bounded comparison service itself stayed inside 1 GiB / 0 swap / 1 CPU / 60 s and wrote 9,358 B. No endpoint vector or token text was printed. The spill is retained privately, hash-bound in `results/saved-endpoint-ranks-01/budget-exception.json`, never published, and the small final packet does **not** repair the breach.

## 5. Frozen but unexecuted embedding-boundary checkpoint

`7d361399396e403a9beea355f4b955835860ebac`, `results/embedding-boundary-checkpoint-01/` (16 hashes, 5 tests). Frozen contract only — **it was never executed, and the later authorization to run it was withdrawn**.

It would compare, for exactly the 1,929 captured IDs, the captured QNN `inputs_embeds` / `per_layer_inputs` against the static embedding tables of the **same checkpoint** the native run loaded (`efab429012b97ab986c4d4838a46ff3ad95d618b42ce514771ca40fadc76a9a4`), using only declared transforms: LUT provenance source keys, the INT2/INT4 low-bits-first signed mapping, and architectural scales (verified `39.191835884530846 == sqrt(1536)`, and 16.0 for per-layer). Recomputing UINT8→UINT16 reproduced the recorded export contract (`81.15119161593829`, offset `16574`); **zero fitted parameters**. A freeze-time check confirmed all 196,608 chunk-0 captured codes lie inside the declared LUT image, spanning exactly 16574–37267 across 70 distinct codes.

Declared per-element budget: LUT UINT8 half-step `0.0252606476` + measured requantization error `≤ 0.00080416` + native BF16 half-ulp at the element magnitude. That is a storage/quantization budget, **not an accuracy acceptance threshold**.

**Unexecuted draft warning:** `tools/compare_embedding_boundary.py` exists in the working tree as an **untracked, untested, never-executed draft** with a banner saying so. It is not evidence and must not be reused without fresh review, tests and a new authorization. Deleting it is acceptable.

## 6. The honest limit: per-layer localization is not decidable from saved evidence

- The QNN capture contains **graph inputs only** (8 non-cache inputs per chunk × 16 chunks) plus the final row-8 logits. No internal layer activation was captured.
- The native-QAT run saved **only** the final logits plus module call counts. No internal activation was saved.
- Therefore **no intermediate exists on both routes between the model input and the endpoint.** The endpoint is already compared; the model input is the only other two-sided boundary, and that comparison is frozen and unexecuted.
- No reference intermediate activations were saved either, so the first actual zero row / upstream values feeding operator 6294 are unknown.

Any future per-layer claim requires **new instrumented capture on both routes**, not reinterpretation of what exists.

## 7. Unproven / explicitly not claimed

- Root cause of the long-output repetition collapse: **unresolved**.
- No QNN defect, no quantization-only cause, no HTP kernel identification, no fusion/aliasing mechanism, no general normalization or pole policy.
- No long-generation quality, speed or fidelity verdict follows from any tiny fixture, profile timing, op count, endpoint statistic or frozen contract.
- Proprietary DSP rounding, fusion, accumulation and transcendental behaviour, and the exporter's producer revision, remain unknown. This work was never proprietary bit-exact DSP emulation.
- Earlier failure modes keep their separate, unrepaired status: caught `std::bad_alloc`; allocation exit 139; mapping exit 134 with `failed to allocate shadow stack: Out of memory`; the missing-output AS12 observer run; provider errors QNN 5005 / 6000 / 1009; the CLI mutual-exclusion stop; the DMA capability rejection (`property = 1104`). Later successes do **not** retro-diagnose earlier failures, and AS12 success does not prove unique necessity or physical-RAM exhaustion.
- Missing historical postflight observations remain irrecoverable; the real lifecycle hook is `_finish_remote`, and new passes never repair absent past checks.

## 8. Privacy and process boundaries that stay in force

- Restricted SDK/model/DLC/context/static arrays and all raw input/logit vectors stay private; publish hashes, scoped metadata and bounded derived statistics only. Battery dumps are published only as labelled current-state extracts, full originals private.
- A past private Bazel transcript contained credential-like values: never repeat values, publish raw Java logs, test/rotate credentials, or rewrite history.
- Exact-owned commits only (`git commit --only -- <owned paths>`); no broad shared-index commit, push or history rewrite. The old collision backup `refs/backup/pi-index-collision-f637a74` stays untouched.
- Device identity (`R5CW81PR8SY`, SM-S918B) is not permission. Every future device action needs a fresh scoped grant, full lease ownership, fresh APK/job/playback/resource checks, staging, raw-first preservation, owned cleanup and real postflight. Observed APK hashes are observations, never standing permission; never restore older pairs.
- Closed and not to be reopened here: the ASR coverage pass, the app contract failures (Janek/Nik own app/provider work), and all listening/WER acceptance questions.

## 9. Commit index for this investigation

| Work | Commit |
|---|---|
| Complete phone capture + invalid v1 preserved | `fe6c4df8db616a7b1a8235e4c7d55530f056b981` |
| FP16 static audit | `e6085004153ee38eb1c0d5bb0c8c865cbd56a87f` |
| Corrected storage freeze | `e260dcf8d85d18bff032adb906ffe1535294cbe1` |
| Corrected partial run + CPU zero-boundary | `5aaf7e29484c2bd0912a1681c9c156a0c73c4109` |
| Tiny HTP stage freeze | `578b5c957b8b4f0ea87e3a0118dcc308cf499304` |
| CLI stop / DMA argv / DMA stop / RPC argv | `65cbb9abec84a4618b569d06bd8a94fc46146ab3`, `5bc77007d2ac578ce84df8c69d385c3457072e61`, `814b1202348deda336a426f8aa2dc1aadba4c619`, `f9886494e690037901275ff9188f3202727580ef` |
| Valid isolated Power | `1e8b74fe2168f526372ca5f707182d62ca1a1c91` |
| Two-chain selection readiness | `03a32ff47ac72ec9c6af26d8c8f65849ff7f4c1d` |
| Chain + exposed outcome | `b31e5ca98aab4e5159e7b5670441950af60ebbcf` |
| Mean/Add controls frozen | `99ac077844abb733746f5c2183a785574f5ea013` |
| Mean/Add outcome + rescale/source audit | `2e465ac4b9f0022dbfc71c22ea0db7fff936343d` |
| Endpoint rank packet + budget exception | `a305bd0ab4641d22b4609738f4fdf5f5a5210e1b` |
| Frozen embedding-boundary checkpoint (unexecuted) | `7d361399396e403a9beea355f4b955835860ebac` |

## 10. If this is ever resumed

The cheapest honest next step is **not** another tiny DSP fixture and not another full portable reference. It is a decision about instrumentation: either capture matched internal activations on both routes at a small number of declared boundaries, or accept that only the input boundary and the endpoint are comparable and execute the frozen input-boundary checkpoint as specified. Everything else in this area risks fitting a policy to outputs, which was deliberately avoided throughout.
