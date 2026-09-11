# Paired precision-path HTP context

**Full paired compilation and official interface metadata passed. No physical inference yet.**

- Context: **1,186,381,824 bytes**.
- SHA-256: `27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd`.
- One native compilation, using the unchanged accepted recipe/options with only new DLC identities and fresh storage.
- Guard: actual child exit 0, no stop, **475.14 seconds**. Compiler receipt: 466.31 seconds, 18,649,060 KiB process RSS high-water.
- Existing-swap-only limits: MemoryHigh15GiB / MemoryMax17GiB / SwapMax16GiB, two CPU quota, nice15, 1800-second outer timeout and owned disk/pressure guards.

Official `qnn-context-binary-utility` extraction completed once (exit0, 0.516s). The existing context inspector passed:

- backend6, SM8550/soc43, exact QAIRT build;
- original AR1/AR128 aliases;
- 38 inputs and31 outputs per graph;
- three selected Float16 value inputs and outputs per graph;
- all30 active four-way cache contracts, including24 SWA outputs;
- **all120 cache boundaries FLAT_BUFFER**;
- unchanged unselected interface metadata, dimensions and position-ID names.

The separately retained full DLC gates establish the floating post-V-projection/cache/value-read path, coupled Float16 head reassembly and return to original quantized projection-input grids. Context creation/interface metadata do **not** reveal every finalized kernel’s arithmetic or establish numerical fidelity, repetition cause, speed or quality.

## First controller preflight preserved

`context-20260911T111220Z-01` stopped before SDK model loading or native compilation: its cache enumeration counted only `past_*` globals and omitted the24 `swa_*` outputs. The exact30-name contract and mixed global/SWA regression fixture were corrected. The original result, source snapshot and logs remain in `raw/precompile-01/`.

`context-20260911T111531Z-02` then passed fresh capacity checks and completed the **first native compile** of this pair. It did not repeat a failed native model compilation.

Both source ONNX files, both associated original external-data files and the new encoding files passed a post-conversion hash check. Model/context/SDK binaries remain private; this result retains metadata, raw logs, input identities and exact source snapshots only.

The canonical campaign, prior exact-long negative, frozen stages and private original evidence remain unchanged. Next: fresh frozen stage and guarded phone validation when scheduled behind app work. No app modification, new agent, Nik review, registry update or push is part of this result.
