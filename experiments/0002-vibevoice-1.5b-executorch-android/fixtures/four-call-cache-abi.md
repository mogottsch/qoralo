# Frozen four-call cache ABI v1

Status: **frozen before export**. The normative machine-readable contract is
[`four-call-cache-abi.json`](four-call-cache-abi.json). This document explains
the choices; it does not implement or authorize an export.

## Decision

Use one fixed-capacity FP32 cache ABI with an explicit scalar `phase` and an
ordered 34-element valid-length vector for each of the acoustic decoder and
semantic encoder. Calls 0–3 are phases 0–3; a successful call produces the
predeclared next lengths, and the controller alone advances to `phase + 1`.
There are no shape-specialized warm-up methods.

This is smaller than duplicating weights across warm-up methods and is correct
for the observed warm-up. The six transpose caches have capacities
`[15, 9, 9, 7, 3, 3]`, but cache 28 grows only `0→1→2→3→4` through the first
four calls. All six first enter with full context at call 15, so phase 4 is not
mislabelled as steady state. All other decoder caches and all semantic caches
are empty at reset and reach their fixed capacities after call 0.

Cache values occupy `[0, valid_length)` on the last axis. Remaining capacity is
canonical `+0.0`. Padding is never context. The JSON lists all 68 caches in
normative order, with source name, FP32 dtype, capacity shape and axis, reset
state, calls 0–3 pre/post lengths, and stabilization calls.

## Method tensor order

The single audio PTE will contain two methods:

1. `acoustic_decode(decoder_latent [1,1,64] FP32, phase [] INT32,
   decoder_valid_lengths [34] INT32, decoder_cache_00 … decoder_cache_33)` →
   `pcm [1,1,3200] FP32, decoder_next_valid_lengths [34] INT32,
   next_decoder_cache_00 … next_decoder_cache_33`.
2. `semantic_encode(pcm [1,1,3200] FP32, phase [] INT32,
   semantic_valid_lengths [34] INT32, semantic_cache_00 … semantic_cache_33)` →
   `semantic_output [1,1,128] FP32, semantic_next_valid_lengths [34] INT32,
   next_semantic_cache_00 … next_semantic_cache_33`.

The arrays under `methods.*.inputs` and `methods.*.outputs` are normative. A
runtime must reject a different tensor count, order, shape, dtype, phase, or
length. The decoder and semantic method receive the same phase. The controller
commits both output state sets atomically only after both pass validation.

## Reset, transitions, and mutation

Reset means phase zero, 68 zero-filled capacity tensors, and two zero-filled
length vectors. Calls may transition only `0→1→2→3→4`; the exact pre/post
vectors and 3,200-sample boundaries are frozen under `call_transitions`.
Call 3 covers samples 9,600–12,799 (0.400–0.533 seconds at 24 kHz).

Methods are pure. Input cache storage cannot alias output storage, and no
module buffer, runtime object, or in-place operation may retain hidden state.
The harness must hash or byte-compare every input before and after execution.
On a mutation, invalid output, or partial failure, it discards every output and
retains the complete prior state. **Silent cache mutation is prohibited.**

If fixed-capacity valid slicing cannot be exported faithfully, task 13 must
publish a host rejection. It must not silently switch to warm-up methods or
revise the ABI.

## Constants and precision

Retain the accepted INT8 Qwen2 choice (FP32 activations/cache transport) and
FP32 connectors, diffusion, acoustic decoder, semantic encoder, and audio
caches. This task starts no FP16/INT4 or other broad quantization work.

Package the two audio methods in one inline-constant multi-method PTE. Store
each component parameter once and create zero phase-specific PTEs. Task 11
proved that inline multi-method constant reuse works synthetically, but task 13
must measure the real PTE and reject any duplicate full parameter copy. Do not
use PTD external constants: ExecuTorch 1.2 can create them and a private host
binding can load them, but the public host runtime and current Android Java
`Module.load` path cannot supply them. Qwen2 remains its accepted separate
INT8 artifact.

## Frozen acceptance gates

Every call must have finite outputs, exact tensor metadata, exact selected
token, correct transition vectors, and a deterministic reset/four-call repeat.
The JSON freezes all numeric values; highlights are:

- INT8 Qwen2 versus the eager trace: hidden max-absolute error `≤0.65`, logits
  `≤0.50`, each KV cache `≤1.25`, plus exact selected token. These bounded INT8
  comparisons are not an FP32-allclose claim.
- FP32 connector, diffusion, and decoder-latent: `atol=1e-5, rtol=1e-4`.
- decoder PCM and host caches: `atol=2e-5, rtol=1e-5`; Android decoder caches
  alone retain `atol=6e-5, rtol=1e-5`.
- semantic output: `atol=1e-5, rtol=1e-4`; semantic caches retain the explicit
  `atol=1e-3, rtol=1e-4` cache-only gate.
- encoded PCM: zero alignment error, exactly 3,200 samples per chunk, and at
  most one signed-16-bit unit error at every sample.
- chunks 0–3 must stay within 3 dB of `[-93.6608, -93.4909, -52.3799,
  -21.7126]` dBFS respectively. Chunk 3 must therefore be in
  `[-24.7126, -18.7126]` dBFS, peak at least 1,023 S16 units, and not clip.
- the chunk-3 audibility gate requires a recorded speech-like voiced onset and
  rejects silence, steady tone, broadband noise, click-only output, or dropout.
  It is not an intelligibility, naturalness, identity, or full-quality score.

Numerical and perceptual gates are both mandatory and cannot override each
other. Thresholds may not be widened after seeing task-13/task-15 results; a
change requires a reviewed ABI revision. The known near-silent chunks 0–1 and
fade-in chunk 2 are expected. Prefix agreement alone remains insufficient for
quality acceptance.
