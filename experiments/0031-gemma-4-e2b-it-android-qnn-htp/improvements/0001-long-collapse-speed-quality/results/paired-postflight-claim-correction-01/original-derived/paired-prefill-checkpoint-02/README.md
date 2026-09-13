# Paired checkpoint: native allocation failure before the first graph

**The corrected phone preflight passed, but the query failed with `std::bad_alloc`. No input/logit capture or host reference ran. The phone was released for Janek.**

Run `paired-prefill-20260912T140747Z-02` used the freshly granted slot, frozen observer/model/stage, both cap-1 controls, 300-second process deadline and 8 GiB address-space setting.

## What completed

- Fresh main/test APK hashes matched `04d9293b…aef7f` / `2dd4e0d8…6d3184`, before and after the attempt.
- Both streaming playback checks returned upstream exit 0, parse OK, zero owned active players and one owned inactive player. Generation/test processes were absent. The idle main process was not mislabeled as generation.
- Dialog creation completed in the retained profile: 2,300,470 microseconds. The runtime reported 104,235,008 bytes allocated for an I/O buffer set; that is **not** process RSS or total memory.
- One query was attempted. It returned `std::bad_alloc` and `Failed to query (-1)`.
- The retained provider log has **zero executing-graph, AR128-completion, AR1-completion or inference-step records**. No capture payload exists.
- Post-query tokenization still saved all **1,929 IDs**, independently matching `3b5c04fe…52b64`.

## Cleanup and release

Native and controller exit were 1. All 57 ADB operations were inside the phone lease. Raw pull completed before cleanup; all owned PID roles and the remote root were verified absent. No signal was sent. `phone.lock` was released promptly. Janek then had the next phone window for his combined app E2E/deploy.

No host reference was launched because the required capture was absent. No retry, continuation, model/dtype change or extra device probe occurred.

## Allocation-stage evidence, without overclaiming

Both LUT-tokenizer debug markers appear before the failure. The exact throwing allocation remains unknown, in the PLE preparation / encoded handoff window before the first strategy/graph/capture marker. Neither newly added payload-capture hook was reached, and its 80 MiB cap is not an up-front allocation.

The reviewed source computes these ordinary buffers from the input geometry:

| Buffer | Requested bytes |
|---|---:|
| Main LUT UINT8 | 2,962,944 |
| Main decoder UINT16 | 5,925,888 |
| PLE LUT UINT8 | 17,283,840 |
| PLE decoder UINT16 | 34,567,680 |
| Combined four vectors | 60,740,352 |

These expressions do not depend on the generation cap. In the reviewed source, config/API cap 1 becomes a `uint32_t m_tokenLimit` tested by generation-callback counters. No cap-dependent pre-token allocation underflow was demonstrated.

Device VmPeak, VmSize, RSS, native `getrlimit` readback and device memory headroom were **not recorded** before the short-lived failure. The configured 8 GiB address-space limit is therefore a candidate constraint, not an established sole cause. A retained-log scan found no SSR/cDSP/reset/RPC-fatal markers; this is not a new live health claim.

The next discriminator is fixed-stack allocation-stage telemetry: exact vector requests/current capacities, overflow-checked diagnostic arithmetic, `RLIMIT_AS`, self VmSize/VmPeak/RSS, and errno saved immediately at an original exception. It must preserve original calls and rethrow the same exception, with no heap allocation in the logger. `errno-at-observation` must not be promoted into proof that malloc set it. There is no justification here for a blind AS increase or replay.

## Evidence privacy

Private originals are hash-bound. Public battery files are explicitly labeled current-state extracts; unrelated Samsung learned charging/sleep history remains only in the private originals. The audio guard retained only target-UID counters and source/parse statuses, never the unrelated audio dump. Raw native logs, profiles and the full post-query ID verification are retained.
