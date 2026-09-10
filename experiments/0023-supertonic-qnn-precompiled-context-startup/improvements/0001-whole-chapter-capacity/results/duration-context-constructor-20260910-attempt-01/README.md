# One T2048 duration constructor — passed; release consumed

The single released ORT1.27.1 / QAIRT2.49.0.260730 / SoC43 constructor produced an external QNN context with the required I/O. **One Python InferenceSession call, zero Session.Run calls.** No context reload, other component, neural/physical execution, audio or quality verdict follows from this result.

- Exact request: `aeee2b8a2e4c1306de6cf3ed84b9364e954347ea077588808630bb0cc842fa19`.
- Source graph: `394ea3e7be9b857da9fe20764e0772960e6a429938d06a5e827a3a139c8cbad9`.
- Constructor9.082848890s; worker body9.255210428s; external guard11.212286019s; outer launcher11.323975205s. One attempt, no retry.
- Native Python worker process peak `ru_maxrss`:607,488KiB. This is not whole-container memory; the guard's `/proc` samples describe the Docker CLI, not the native worker.
- Inputs: `text_ids INT64[1,2048]`, `style_dp FLOAT[1,8,16]`, `text_mask FLOAT[1,1,2048]`; output `duration FLOAT[1]`.
- CPU fallback explicitly disabled. Registered providers include QNN and CPU; registration alone is not execution. The descriptor contains one `com.microsoft::EPContext`, no initializers, exact required I/O and `embed_mode=0`.
- Source plus13 prospective runtime-file pins verified unchanged after construction. The request retains their scope; this is not a complete dynamic-dependency inventory.

## Actual artifacts: LOCAL-ONLY

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `duration-context.onnx` |815|`150e364906f1a9b536795df0cdc12275c38d765fc53eb31353e8fab46d2e99de`|
| `duration-context_qnn.bin` |6,638,456|`b4c20151ae62fd6c909bb0ff4f0ce0aa60aad22442a70f6a100c63cbaaf5b8e7`|

Actual bytes remain in `.local/constructor-duration-t2048-attempt-01/data/`, with `PRESERVE.md` and exact paths in `local-artifacts.json`. Post-close artifact hashes match the constructor receipt. Do not substitute hashes for bytes or add models/SDK/context binaries to Git.

## Logs and cleanup

Raw logs/receipts were retained before additional saved-record checks. The SDK log includes graph-preparation stages and a **compiler DDR summary**, not measured physical bandwidth. The file-mapped-weights warning says that optional feature is disabled on this host; it is retained verbatim.

Worker PID1906865 was reaped; PID/group absent, container absent, owned disk scratch empty. No extra cleanup removal was needed after Docker's `--rm`. The reviewed name/ownership-label cleanup boundary is non-atomic and retains a name-reuse race; no immutable-ID hardening is claimed.

The520s worker limit,20s grace,8GiB/no-extra-swap,4CPU/thread environment and all four owned disk scratch variables remained unchanged. No phone or app-pack action occurred. Pushes remain held.
