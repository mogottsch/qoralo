---
experiment: 0034-lfm2.5-2.6b-android-qnn-htp
status: active
summary: The hash-bound 539-file phone stage and native runner are ready locally, but the experiment is waiting for ADB RSA authorization; no phone contact or physical HTP execution exists.
benchmark: android-llm
---

# Experiment 0034 — LFM2.5-2.6B Android QNN/HTP

## Experiment description

LFM2.5-2.6B has complete Android CPU and OpenCL benchmark routes, but its original QNN assessment found no high-level tool path for the model's `lfm2` architecture. This experiment now tests an architecture-aware route: export the exact model to Q4 ONNX, split its stateful computation into memory-bounded parts, compile every claimed neural part for the Galaxy S23 Ultra's SM8550/HTP v73 target with CPU provider fallback disabled, and then prove that the complete route can execute physically on the phone.

LFM2 is not a renamed Llama-like transformer. Its 30 layers combine 22 recurrent short-convolution layers with 8 full-attention layers, so the route must preserve both convolution state and attention KV state, bind their reset behavior, and prove that claimed model computation runs through QNN HTP. The intentionally CPU-side tokenizer, selected-row Q4 embedding lookup, request orchestration, and one global greedy argmax remain explicit; they are not hidden provider fallback.

The route binds `LiquidAI/LFM2.5-2.6B` revision `ab006873…`, the architecture-aware `Liquid4All/onnx-export` exporter at `9a23ddd…`, symmetric block-32 INT4 weights, ONNX Runtime QNN EP 2.5.0, and host QNN runtime 2.49.40 targeting SoC model 43 / SM8550 / HTP v73. Moritz reviewed and authorized the named public Qualcomm package license. Packages, source weights, large ONNX data, compiled contexts, and the assembled phone stage stay outside Git. The owning [experiment README](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/protocol/experiment-contract.json), [QNN AOT result](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-aot/result.json), [host pipeline comparison](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/htp-pipeline-host-equivalence/result.json), and [phone-preparation result](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/phone-preparation/result.json) are the evidence authority.

## Progress

The historical high-level blocker remains a rejected route: installed QAIRT's direct-GGUF and factory paths do not support `lfm2`. The experiment instead bound the exact source shards and produced an architecture-aware Q4 ONNX export containing the expected 22 convolution nodes, 8 `GroupQueryAttention` nodes, and 167 `MatMulNBits` nodes. A standard-ONNX RMSNorm rewrite corrected an invalid contrib-operator domain emission, after which the graph passed the ONNX checker and completed a bounded canonical-short host CPU smoke. That smoke established export viability only, not QNN or Android execution.

The model was then lowered into a one-token pipeline with a fixed 4,096-token attention capacity. Reset is explicit: all 22 convolution caches and all 8 attention K/V pairs start at zero for each logical request. RoPE and grouped-query attention are expanded into QNN-owned standard operations while returning only the new K/V slices for a left-aligned cache.

The selected-row asymmetric Q4 embedding remains an intentional CPU frontend because QNN EP 2.5 does not claim `GatherBlockQuantized` on HTP. Wide 10,752-element MLP projections were split into 6,144 + 4,608 paths; only the second down-projection dot product receives mathematically zero activation and quantized-weight padding to meet the v73-supported width. The 128,000-wide LM head was split into 22 HTP chunks, followed by one declared CPU global argmax. Tokenizer work and orchestration are also CPU-side. No QNN CPU provider fallback is accepted for the submitted neural parts.

The final memory-bounded route contains 263 compiled parts covering convolution and attention cores, MLP projection/activation/residual work, final normalization, and the 22 LM-head chunks. Every part compiled through ONNX Runtime QNN EP 2.5.0 with `session.disable_cpu_ep_fallback=1`, block-quant optimization, framework-operation tracing, and target SoC 43 / HTP v73. Across the retained QNN source parts:

- all 1,583 source ONNX nodes are marked supported;
- zero source nodes are unsupported;
- the traces map them to 2,747 QNN operations;
- 263 context binaries total 1,779,492,144 bytes and remain outside Git.

A bounded host reconstruction then submitted the exact 171-token canonical short prompt through the final 263-part ordering with zeroed state. The first five greedy token IDs matched the original export, the transformed monolith, and the final split pipeline. This protects the selected route wiring and greedy decisions for those five steps; the recorded logits are not numerically identical, and the host timings/logits are not Android or physical-HTP evidence.

The native phone runner and ignored local stage are now prepared. The 106,080-byte Android API-31 AArch64 PIE runner has SHA-256 `9b799bb6…89d2`. It is configured to load all 263 context sessions once, keep CPU EP fallback disabled, request shared HTP resources and basic profiling, zero all recurrent and attention state, submit the exact 171-token canonical-short prompt, and cap the viability continuation at 16 tokens. It retains only the declared CPU selected-row embedding, request orchestration, and global argmax boundary.

The locally verified stage contains 539 payload files totaling 2,015,057,362 bytes before its additional metadata and SHA manifest. It covers the public Android runtime artifacts, runner, every context pair, Q4 embedding tables, and prompt. The complete stage is ignored and remains outside Git; committed hashes bind its metadata, manifest, runner, and public packages.

This preparation made no ADB contact. The 0034 owner did not acquire `phone.lock`, stage or install anything, or execute the runner. Pi's committed coordination state reports `R5CW81PR8SY unauthorized`, so work waits for Moritz to accept the Android RSA prompt and for Pi to confirm `device` state. Only then may 0034 hold the full phone-lock lifecycle for identity checks, staging, one bounded request, evidence pull, and scoped cleanup.

## Results

**The experiment remains active, with target-specific fallback-disabled host AOT complete and physical execution pending.** The durable result establishes that every retained neural source part can be prepared into an SM8550/v73 QNN context under the stated ONNX Runtime QNN configuration, with complete framework-operation ownership traces and no CPU EP fallback inside those parts.

| Evidence boundary | Current result |
|---|---|
| Exact-model architecture-aware Q4 export | Completed and hash-bound |
| Target-specific QNN AOT | 263 contexts compiled for SoC 43 / SM8550 / HTP v73 |
| Retained source-part ownership | 1,583/1,583 source nodes supported; 0 unsupported; 2,747 QNN operations |
| CPU provider fallback inside QNN parts | Disabled |
| Declared CPU work outside QNN parts | Tokenizer, selected-row Q4 embedding, orchestration, and global argmax across 22 HTP LM-head chunks |
| Host route-wiring comparison | First five greedy tokens matched reference, transformed monolith, and final pipeline; not exact-logit equivalence |
| Host-only phone preparation | API-31 AArch64 runner plus 539 payload files / 2,015,057,362 bytes locally hash-verified outside Git |
| ADB contact, phone lock, or phone staging | None; waiting for RSA authorization and Pi confirmation |
| Android / physical HTP execution | Not yet attempted; no claim |
| Canonical campaign and Android performance | Not run; no setup, TTFT, prefill, decode, memory, thermal, or power result |
| Android LLM registry row | None; host AOT and wiring evidence are not registry-eligible |

The fallback-disabled compiler result and locally verified phone stage are stronger than generic target availability, but both remain host preparation evidence. A ready native runner and 2.0 GB local stage do not show that the authorized phone can load 1,779,492,144 bytes of contexts, keep the complete route resident, execute every context through physical HTP, reset state correctly, or return valid text. No inference output exists from this runner. Host context creation, stage hashes, host output sanity, and matching five greedy decisions cannot substitute for phone provider/RPC/accelerator/cycle/HVX proof.

No 0034 row belongs in the Android LLM registry until a complete valid physical Android canonical campaign exists. If physical context loading fails, CPU work expands beyond the declared boundary, any neural context falls back, or full request reset cannot be proven, the route must stop rather than weaken the HTP claim.
