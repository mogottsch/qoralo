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

## Authorized active gate

Moritz selected the updated local-toolchain/source-fix route. Completed authorization work:

1. established durable authenticated Qualcomm AI Hub and QPM catalog access without committing credentials;
2. personally activated the `Qualcomm_AI_Runtime_SDK` license;
3. acquired and privately extracted QAIRT 2.49.40 outside Git; and
4. bound its QIK, SDK manifest, selected converter sources, Gemma4 configuration, Android Genie runtime, QNN HTP host/stub, and v73 skeleton hashes in `results/qairt-2.49.40-capability/`.

QAIRT 2.49.40 did not itself remove the prior failure: the factory and implicated optimizer sources are byte-identical to 2.49.0. The isolated compatibility route now passes the bounded transform-only gate. It binds standards-valid `value_ints` constants, Gemma4 input-axis semantics, exact SWA cache/mask widths, and shape-preserving Reciprocal propagation without changing the checkpoint. AR1 and AR128 CL4096 one-split ONNX+encodings outputs pass static-IO and ONNX checks and are hash-bound in `results/qairt-2.49.40-transform-compat/`.

QNN conversion now passes for both variants, producing hash-bound AR1 and AR128 DLCs. `qairt-dlc-info` binds their HTP converter configuration, 2,280,676,608-parameter graph, operator inventory, I/O encodings, and mixed-precision boundary. The converter reports 15 RmsNorm float fallbacks per variant; AR1 has 15 Float16 value-cache outputs while AR128 outputs remain uFxp16. These are retained facts to validate at compile/runtime, not a CPU-provider claim.

The active next step is compiling both DLCs together into one weight-shared serialized context for SM8550/HTP v73, followed by context inspection and generation of matching embedding/PLE LUTs. Workbench compile/link remains a separate unapproved cost/terms checkpoint. Do not access the phone or run a canonical campaign before a compiled route exists.

## Stop conditions

Stop and report the exact required action if the public checkpoint cannot be downloaded without authentication, local installed QAIRT cannot prepare/compile Gemma4 for SM8550, transformer execution cannot be distinguished from CPU fallback, or phone priority/transport is unavailable. Never substitute a CPU response for HTP evidence.
