# Plan: Gemma 4 E2B IT QNN/HTP

## Completed

1. Re-read the Android LLM protocol and verified all canonical workload hashes.
2. Kept `0025` immutable and established independent `0031` ownership.
3. Bound the already-installed QAIRT 2.49 SDK manifest, release notes, Gemma4 HTP example, Android Genie runtime, and QNN HTP library hashes.
4. Confirmed first-party Gemma 4 support, `QnnHtp`, serialized-context, CL8192, and SM8550 compile-target evidence.
5. Pinned Qualcomm AI Hub Models v0.61.0 at commit `5975a79b55b40f5cbc61f3ac5e52abe47d9d8bd5`.
6. Located the unauthenticated public 2,013,959,998-byte w4a16 checkpoint archive.
7. Rejected the direct GGUF shortcut because installed GGUF conversion does not support the artifact's `gemma4` architecture.

## Next gates

1. Acquire `artifacts/locks/heavy-ram.lock`; only then download and unpack the public checkpoint.
2. Bind archive and member sizes/hashes, quantization encodings, source revision, tokenizer, template, and all canonical prompt/token inventories.
3. Attempt the cheapest local installed-QAIRT preparation and SM8550 HTP compilation. Preserve raw logs and stop at any auth, license, missing converter, unsupported graph, or hardware-target blocker.
4. Bind the compiled serialized context and all LUT/runtime artifacts. Prove that the entire transformer prompt/decode graph is HTP-bound and document intentional CPU frontend/sampler boundaries.
5. Build a raw-first Android runner that reuses one loaded Engine and proves fresh-Dialog or full-reset isolation per logical request.
6. Wait for Pi's explicit phone priority. Under `phone.lock`, run one bounded viability request with physical HTP proof and scoped cleanup.
7. Only if viability and isolation pass, run one complete canonical first-short + 5 short + 5 medium + 5 long campaign on the same loaded route.
8. Validate and commit owning evidence. Do not publish from this experiment.

## Stop conditions

Stop and report the exact required action if the public checkpoint cannot be downloaded without authentication, local installed QAIRT cannot prepare/compile Gemma4 for SM8550, transformer execution cannot be distinguished from CPU fallback, or phone priority/transport is unavailable. Never substitute a CPU response for HTP evidence.
