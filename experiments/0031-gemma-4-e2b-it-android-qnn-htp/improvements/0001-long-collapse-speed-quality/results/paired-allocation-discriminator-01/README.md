# Allocation discriminator: exit 139 after the PLE buffer resize

The single granted run `allocation-20260912T144721Z-01` retained nine allocation observations, then exited **139** before a graph or input/logit capture. This is **not the prior caught `std::bad_alloc` outcome**. There is no throw record or captured fault address/backtrace identifying the final instruction.

## What the saved observations establish

- Main LUT output (2,962,944 bytes), main decoder input (5,925,888 bytes), and PLE LUT output (17,283,840 bytes) all resized successfully.
- The last record is **after the PLE LUT output resize**, with exact size and capacity 17,283,840. The encoder did not record a return. The failure window is therefore its subsequent lookup/copy work, not a demonstrated failure of that resize.
- Both actual LUT token-vector counts were 1,929 and frozen inputs were hash-verified. The complete post-query ID file is **absent after the process crash**; the earlier run's full ID proof must not be copied onto this one.
- No executing/completed graph marker, non-cache input payload, final logits or host-reference execution exists.

Last recorded process/system snapshot (bytes):

| Observation | Bytes |
|---|---:|
| RLIMIT_AS soft and hard | 8,589,934,592 |
| VmSize / VmPeak at the snapshot | 6,343,651,328 |
| VmRSS at the snapshot | 144,318,464 |
| MemAvailable at the snapshot | 3,364,196,352 |
| AS minus VmSize | 2,246,283,264 |

These are explicitly timed observations, not a final process peak or HTP-private-memory measurement. `errno=12` was already present at the first marker and remained after successful allocations. It is stale **errno-at-observation**, not proof those allocations failed.

## Mapping hypothesis and timing boundary

The bound PLE file is 2,348,810,240 bytes, which exceeds the **last** recorded AS headroom by 102,526,976 bytes. However, the LUT mapping was attempted earlier, during setup. The later snapshot is **not contemporaneous evidence that its mmap could not fit**.

The saved SDK source exposes a possible failure-propagation path: `mapFileInternal` returns null/zero on mmap failure; `File::open` can still return true; the LUT stores `mutableData()` without checking mapping validity while retaining its independently measured file size. A null mapping could then pass the independent row-size check and fail during copy. The actual Android mapping address/result was not captured, so this remains a hypothesis.

The next host-prepared discriminator records the actual mmap request, address/result and immediate errno, plus `File::open` return and cached-pointer validity at their real times. An injected tiny mmap-failure fixture can establish the source contract, not the actual Android cause. No AS revision or device/model replay is justified by this record alone.

## Identity, privacy and release

Fresh **preflight** hashes matched `da9d015e…c2ee27` / `173e4744…a718bd`. Generation/test processes and the main app process were absent at both job checks. **Postflight APK verification was not recorded** because the new controller used the wrong cleanup-hook override; see the [scoped additive correction](../paired-postflight-claim-correction-01/README.md). No independent Janek or older-run identity proof is invalidated.

All 58 ADB operations were inside the lease. Raw pull completed before owned cleanup; all owned PID roles and the root were verified absent. No signal operation was sent, and the phone lock was released promptly for Janek's next app work. The conditional host reference stayed unstarted. There was no retry or extra device probe.

Private originals are hash-bound. Public battery files are labeled current-state extracts; unrelated learned charging/sleep history stays private. No unrelated audio dump or restricted model/input tensor was published.
