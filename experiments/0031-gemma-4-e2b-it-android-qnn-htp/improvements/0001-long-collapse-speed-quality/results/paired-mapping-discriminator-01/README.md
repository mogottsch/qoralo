# Same-8-GiB mapping checkpoint: valid LUT maps, later shadow-stack abort

The single granted `mapping-20260913T103155Z-01` attempt kept the same observer, model, LUTs, input, cap 1, 300-second deadline and **8 GiB RLIMIT_AS**. It exited **134** with `failed to allocate shadow stack: Out of memory`. This is separate from the older caught `std::bad_alloc` and exit-139 outcomes.

## The mappings in this run were valid

The actual syscall, `File::open`, mapped length and cached-pointer records agree:

| LUT | Requested / mapped bytes | AS headroom before | AS headroom after |
|---|---:|---:|---:|
| Main | 402,653,184 | 2,830,323,712 | 2,427,670,528 |
| PLE | 2,348,810,240 | 2,427,670,528 | 78,860,288 |

Both mmap results were non-null, not `MAP_FAILED`, with immediate errno 0. `File::open`/`isOpen` and the cached addresses/lengths were consistent. **A null LUT mapping is not the cause demonstrated in this run.** These successes do not retroactively identify the mapping state or cause of earlier runs.

All observed main/PLE vector allocations and EOS-vector constructions completed. Immediately before the engine handoff:

- Actual AS soft/hard limit: **8,589,934,592 bytes**.
- VmSize: **8,585,527,296 bytes**, leaving **4,407,296 bytes**.
- VmRSS: **188,313,600 bytes**.
- System MemAvailable: **2,922,344,448 bytes**.

The explicit shadow-stack allocation failure and very small AS margin support a controlled virtual-address-budget follow-up. They are **not proof of physical-RAM exhaustion**. The exact shadow-stack allocation request and its syscall return were not captured.

## Other errors and incomplete capture remain evidence

The provider also recorded context-from-binary error 5005, a shared-weight size/offset mismatch (expected offset 0, received 1,161,822,208 for 25,640,960 bytes), shared-weight mapping error 6000, and QNN-skel connection error 1009. Their causal relationship and ordering relative to the shadow-stack abort are unresolved. No explicit SSR/restart marker was found; a cDSP effective-domain fallback warning is not being relabeled as a reset.

One AR128 graph-entry marker was recorded, with **no completed graph**. Eight non-cache input buffers for step 0 / 128 real rows were captured: **4,096,000 bytes**, kept private and hash-bound. This is not the required 16-chunk prefill capture; no final logits exist. Both LUT token-vector counts were 1,929, but the full post-query ID file is absent after the abort. The host reference therefore remained **unstarted**. Partial inputs must not be replaced with formulas or HTP caches to manufacture a complete comparison.

## Identity, raw preservation and release

This run has genuine fresh **preflight and corrected actual-postflight** verification of `7989af04…db82d` / `27e8d84c…6da279`. Job checks found main/generation/test processes absent. This valid new postflight observation does not repair missing verification in older new runs; the [earlier scoped correction](../paired-postflight-claim-correction-01/README.md) remains applicable.

All 61 ADB commands were under the phone lock. Raw pull completed before independent owned-process/root cleanup; all owned roles and the root were verified absent. No signal was sent, and the lease was released promptly for Janek. No second attempt or AS change occurred.

Public evidence excludes the eight restricted input tensors; `private-input-payloads.json` binds their private originals. Battery files are labeled current-state extracts; full learned charging/sleep history remains private.

## Authorized preparation only

Pi authorized preparing one **12 GiB RLIMIT_AS** follow-up: 12,884,901,888 bytes, changing virtual-address allowance only, not RAM budget. All other artifacts, caps, guards and checks must remain unchanged. Execution is queued after Janek's entire priority validation window and requires the actual resource handoff; there is no sweep or automatic retry. Any host reference remains conditional on a complete validated capture and phone release.
