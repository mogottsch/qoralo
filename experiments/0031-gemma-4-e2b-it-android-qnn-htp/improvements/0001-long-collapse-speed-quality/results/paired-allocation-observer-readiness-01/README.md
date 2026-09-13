# Allocation-stage discriminator: frozen, host-only preparation

> **Controller postflight correction:** this frozen preparation inherited an APK-postflight override on the wrong lifecycle hook. That promise is superseded by the [scoped correction and tested future `_finish_remote` dispatch](../paired-postflight-claim-correction-01/README.md). No postflight identity is inferred for the new runs; genuine preflight, cleanup and release evidence remains separate. The observer/model artifacts are unchanged.

**The allocation cause remains unknown.** This preparation adds bounded fixed-stack observations around the original allocations; it does not raise the 8 GiB address-space limit, change cap 1, alter model arithmetic, or replay the phone/model. Janek retains device priority.

## Cheap retained-launch clue

The last successful **same-variant, base source-runtime** run (`2bcb58f0`) used context `27e19e32…fabdd` and source-built Genie `43b9bf47…f022a`. Its retained model-entry script contains **no explicit AS-limit setting**.

The failed capture derivative (`3a61a7ea…8dccc2`) used the same context/LUT/input variant but explicitly executed `ulimit -v 8388608`. This is a genuine recorded launch-setting difference. It is **not** proof that the old inherited limit was unlimited, that runtime binaries were identical, or that the new AS limit alone caused `std::bad_alloc`. Neither run recorded the actual native `getrlimit` value or failing allocation size.

The cap-1 source path remains a generation-callback threshold, not a demonstrated input-allocation multiplier. The prior failure occurred after both LUT tokenizer markers and before any strategy/graph/capture marker. Those observations are retained without turning UNKNOWN into a diagnosis.

## What the observer records

The new header uses fixed stack buffers, manual integer formatting and direct file operations. Production code does not install an allocator hook and does not use JSON, heap strings, `new`, `malloc`, `calloc` or `realloc` for logging.

For the original LUT/output, decoder-main and decoder-PLE resizes, EOS-vector construction and encoded/engine handoffs, it records:

- Named before/after/throw stage, monotonic timestamp and event ordinal.
- Exact requested vector elements, element width, current size and capacity.
- Overflow-checked diagnostic products and validity flags. The **original allocation expression is left unchanged**; an invalid diagnostic product is not invented as a valid size.
- `RLIMIT_AS` soft/hard values with validity and unlimited flags.
- Self VmSize, VmPeak and VmRSS, plus MemAvailable where readable, with explicit validity bits and truncation status.
- `errno` saved **immediately at the original exception, before diagnostics**. It is labeled **errno-at-observation**, not proof that malloc set it. Logging restores the caller's errno.

The original callable runs once, its return value is preserved (including `size_t` counts), and the same exception is rethrown. No input/weight/scale/dtype/allocator/cap/call-order correction is made. The previous actual-input/final-logit capture hooks remain unchanged.

The separate allocation metadata file is bounded to **64 records / 64 KiB**, exclusive-create, CLOEXEC and flushed with `fdatasync`. It contains no tensor values or unrelated process state. The existing 80 MiB input/logit capture and 512 KiB capture-journal caps remain unchanged.

## Host validation and frozen artifacts

A bounded tiny C++ test forbids C++ `new` and link-wrapped `malloc`/`calloc`/`realloc` while the logger runs. It verifies caller errno preservation, original call counts/values/exception, checked overflow, real self-memory/rlimit readbacks, CLOEXEC and the log cap. The synthetic test exited 0; 64 records used 32,745 bytes. This is a test of the authored logger path, not a claim about every implementation detail inside platform libc.

Native Android build exited 0:

- `libGenie.so`: **11,654,912 bytes**
- SHA-256: **`87f8b9b624d9de6e08de372740e5814fc64eb352c68b2c73fd07c8190e41d9eb`**
- AArch64 ELF, allocation marker and all **103** unchanged runner Genie imports verified.
- Exactly **three observed C++ files plus the new header** differ from the previous capture source. No previous input/logit capture code changed.

Frozen stage:

- `TRACK/.local/frozen-stages/paired-allocation-observer-stage-01`
- Manifest **`6a36db9747f674dcf3410b8d226958898c03cce8f96c67d27b68fcddfe4fc71a`**
- 19 files / **4,013,545,148 bytes**.
- Only `lib/libGenie.so` differs from the failed capture stage. Config and script cap 1, model, context, LUTs and input bytes are identical.

Build preparation used 4 GiB RAM / 1 GiB swap / 2 CPU / 1,800-second caps; native build took 15.59 seconds, service 17.51 seconds, peak 1.5 GiB with no swap. Stage copying used 1 GiB / 1 CPU / 300 seconds and completed in 18.99 seconds. The tiny logger test used 1 GiB / 1 CPU / 60 seconds and completed in 0.529 seconds. Environments were credential-free; no memory-lock admission, global toolchain change or device access occurred.

`phone_allocation_stage_capture.py` is **plan-only** without a fresh scheduled slot and full current APK/job/playback checks. It preserves the corrected streaming playback guard, full phone-lock lifecycle, 300-second process / 8 GiB AS policy, raw-first pull and independent cleanup. This preparation does not authorize a replay. The existing host-reference guard intentionally does not silently accept a different stage.

## Next discriminator, not a guessed fix

After the app wave, one specifically scheduled run can identify the last successful allocation and the exact request that throws, with actual AS and resident/headroom observations at that point. A small requested vector plus a nearly exhausted AS limit would support a different next action than a wrapped size, unexpected capacity, insufficient physical headroom or an allocator failure with ample AS remaining.

Until that evidence exists, keep the allocation stage UNKNOWN. Do not label sole RAM exhaustion, remove or raise AS blindly, change model/caps, inject HTP caches, or run the conditional host reference without a complete valid capture.
