# Plan: Gemma 4 E2B IT QNN/HTP

## Completed

1. Re-read the Android LLM protocol and verified all canonical workload hashes.
2. Kept `0025` immutable and established independent `0031` ownership.
3. Bound the already-installed QAIRT 2.49 SDK manifest, release notes, Gemma4 HTP example, Android Genie runtime, and QNN HTP library hashes.
4. Confirmed first-party Gemma 4 support, `QnnHtp`, serialized-context, CL8192, and SM8550 compile-target evidence.
5. Pinned Qualcomm AI Hub Models v0.61.0 at commit `5975a79b55b40f5cbc61f3ac5e52abe47d9d8bd5`.
6. Located the unauthenticated public 2,013,959,998-byte w4a16 checkpoint archive.
7. Rejected the direct GGUF shortcut because installed GGUF conversion does not support the artifact's `gemma4` architecture.

## Completed artifact and conversion gates

1. Acquired `artifacts/locks/heavy-ram.lock` and held it across the full checkpoint download, integrity test, extraction, and member hashing.
2. Bound the 2,013,959,998-byte archive, its 9.1 GB external data relationship, w4a16 encodings, source revision, tokenizer, template, and canonical 170/594/1929-token prompt inventories.
3. Created an isolated local QAIRT environment without altering system tooling or accepting another license.
4. Ran the smallest faithful QAIRT support probes under `heavy-ram.lock`:
   - the factory resolved SM8550 to HTP v73 but identified Gemma4 as unknown/unsupported and used a generic builder;
   - the transform-only AR1+AR128, CL4096, one-graph probe failed in ONNX ConstantPropagation with `KeyError('value')` before conversion or compilation;
   - post-failure hashes proved that ONNX, external data, and encodings remained unchanged.
5. Stopped at the exact unsupported-graph blocker. No context binary, Android execution, or HTP claim was fabricated.

## Blocked next gate

Moritz must choose one of the following before work can continue:

1. supply an authorized Gemma4 E2B w4a16 serialized QNN context compiled for SM8550/HTP v73 plus the matching embedding and PLE LUT bundle and full provenance;
2. authorize authenticated Qualcomm AI Hub Workbench use if a supported QNN context export currently exists for this checkpoint and target; or
3. authorize an updated QAIRT/toolchain installation or an architecture-aware source fix that handles the public graph, with the new tooling separately bound.

Until then: do not patch the graph ad hoc, do not access the phone, do not run a canonical campaign, and do not publish.

## Stop conditions

Stop and report the exact required action if the public checkpoint cannot be downloaded without authentication, local installed QAIRT cannot prepare/compile Gemma4 for SM8550, transformer execution cannot be distinguished from CPU fallback, or phone priority/transport is unavailable. Never substitute a CPU response for HTP evidence.
