# Mapping/AS discriminator: host-only, same limits

**No actual Android mmap failure is proven yet.** The preceding exit-139 run successfully allocated its PLE output vector, then failed before the encoder returned. Its last AS headroom was 2,246,283,264 bytes, while the PLE LUT is 2,348,810,240 bytes. The mapping was attempted **earlier than that snapshot**; comparing those numbers alone is not contemporaneous evidence of an AS failure.

This preparation retains the same model, LUTs, input, cap 1, 8 GiB AS and 300-second process deadline. It adds read-only mapping observations and fixes neither mapping-error propagation nor allocator behavior. No phone/model replay or AS revision occurred.

## Source contract established by the tiny fixture

The bound SDK can return `(null, 0)` from `mapFileInternal` after `mmap` returns `MAP_FAILED`, yet subsequently return true from `File::open`. The LUT caller obtains `mutableData()` without checking validity and keeps an independently measured file size.

A 4 KiB synthetic file and **test-only injected mmap failure** demonstrate the behavior through the public `remap(false)` API, which returns `File::open`'s result:

| Fixture | Return | `isOpen` | Pointer | Mapped bytes |
|---|---:|---:|---|---:|
| Successful map | true | true | non-null | 4,096 |
| Injected `MAP_FAILED` / `ENOMEM` | true | false | null | 0 |

Both the original and observed source produce the same results and exactly two original mmap calls per case. The observed fixture records the syscall failure and the contradictory open-return/pointer state independently. This proves **failure-propagation semantics**, not that the Android PLE map actually failed. The fixture never dereferences a null mapping and contains no model data.

## Contemporaneous observation points

Only the exact main and PLE LUT basenames are observed. The fixed-stack logger records:

1. **Before original mmap:** requested file length, actual `size_t` syscall length, representability, current `RLIMIT_AS` and self/system memory.
2. **Immediately after original mmap:** actual returned address, `MAP_FAILED`/null flags and errno saved in the very next statement, before diagnostics.
3. **At `File::open` return:** actual boolean return, mapped length, pointer and `isOpen` state, including early false-return paths.
4. **After LUT pointer caching:** actual cached address, independently declared file length, actual mapped length and validity.

The original mmap call, protection/flags/offset, return behavior and LUT assignment order are unchanged. No null-map guard or hidden retry is inserted. The observer restores caller errno; success plus a nonzero errno is not relabeled as a failed syscall.

Logging uses fixed arrays/manual integer formatting/direct file operations, is exclusive-create/CLOEXEC and flushed, and is capped at **32 records / 32 KiB**. The existing allocation and input/logit observers are unchanged. Test-only heap/mmap wrappers are **not** linked into the Android runtime.

## Frozen artifacts and bounded validation

- Android `libGenie.so`: **11,672,744 bytes**, SHA-256 **`ee2b10d89d9fec2442bdf6cfd6a1e369eb525ec1c0d091acd2ee19bcb00ba099`**.
- Native build exit 0; **8.842 seconds**, service 11.404 seconds, 1.2 GiB peak/no swap under 4 GiB RAM / 1 GiB swap / 2 CPU / 1,800-second bounds.
- AArch64 ELF, mapping marker and all **103** unchanged runner Genie imports verified.
- Two observed SDK C++ files plus the new header differ from the allocation-observer source; previous allocation/input/logit hooks are unchanged.
- Frozen `paired-mapping-observer-stage-01`: **19 files / 4,013,562,980 bytes**, manifest **`807980c106a59584752ce52abece89dd50062c827505fb2136ae0c950ca7206e`**. Only the observer library differs from the allocation stage.
- Stage copy/verification completed under 1 GiB / 1 CPU / 300 seconds; no swap.
- Four tiny fixture cases passed under 1 GiB / 1 CPU / 120 seconds. The fixed-stack logger was exercised with C++ `new` and link-wrapped `malloc`/`calloc`/`realloc` forbidden, with CLOEXEC and record/byte bounds checked. This checks authored logger calls, not all internals of platform libc.

`phone_mapping_stage_capture.py` is plan-only without a fresh scoped slot. It uses the corrected actual `_finish_remote` postflight hook, separates postflight identity from cleanup proof, and preserves the streaming job/playback check and full phone-lock/raw-first lifecycle. The correction does not manufacture postflight evidence for earlier new runs or invalidate independent Janek proofs.

## Proposed narrow next control

After app priority, schedule **one same-limit mapping-observer checkpoint**, not an AS increase:

- If PLE mmap returns `MAP_FAILED`/`ENOMEM` and its contemporaneous requested length exceeds measured AS headroom, the next proposal can isolate a specifically justified AS-budget change. That later change is not authorized or automatic here.
- If mapping succeeds but cached length/pointer/validity differs, investigate that propagation boundary without raising AS.
- If all mapping/binding observations are valid, the lookup/copy fault needs another explanation. Do not attribute it to the later headroom snapshot.
- If an allocation or observer fails, retain partial evidence and do not repeat blindly.

A full reference remains conditional on a complete valid input/logit capture and an explicitly bound observer stage after phone release. This preparation grants no device/model execution and no fallback to a different policy.
