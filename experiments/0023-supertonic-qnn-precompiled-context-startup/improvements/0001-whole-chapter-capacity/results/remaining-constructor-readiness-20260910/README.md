# Remaining constructors — one focused readiness batch, NOT APPROVED

Duration's one successful constructor and its artifacts are immutable in commit `5c2e413`. This preparation adds **three separate text/vector/vocoder requests**. No additional ORT import, Docker container, SDK constructor, model forward, context reload or phone action occurred.

## Source changes and gates

- New `tools/compile_component_context.py` adapts the frozen duration worker only for these three exact T2048/L2048 ABIs, per-component output names, component-specific release permission and canonical I/O hash. Duration is explicitly ineligible, preventing a duration retry through this entry point.
- New `tools/run_component_constructor.py` keeps the reviewed duration lifecycle. It invokes one component only; it has no batch execution loop. Exact source diffs are `worker-scope.diff` and `launcher-scope.diff`.
- ORT1.27.1, QAIRT2.49.0.260730, existing pinned Docker image,13 runtime-file pins, SoC43, burst/offload0, CPU fallback disabled and external context options are unchanged.
- Actual session I/O and QNN provider presence, one non-embedded EPContext descriptor with exact I/O, external binary and unchanged source/runtime pins remain required. There is no `Session.Run` call or other inference API.

## Three requests, one review

Batch manifest `protocol/remaining-constructors/batch.NOT_APPROVED.json`:

```text
4943e159268df867b58adcde0e386a65fe6b0c16b2c29b5f1c4136a82aaf6cde
```

| Component | Graph bytes | Materialized graph SHA prefix | I/O SHA prefix | Request SHA256 |
|---|---:|---|---|---|
| Text |36,566,260|`6bdf11f5…e14568b`|`6cca7457…b49332`|`f21682b0965b48373470d77e2ebe4717e3dcae51cbd3ccba1813ba9e71b2c6f5`|
| Vector |256,526,661|`9b6b2a5e…ae70663`|`c60b6549…de97b0`|`1f71474cfec8800c2e8ccbc71293e5e1fbf8d064af06e7f40e9c3fbd52ec62c8`|
| Vocoder |101,449,891|`539f8ef7…61df792`|`3e15a281…a34ed6`|`135d1f1c0c238fc28667ff208d21343e578139e67a809665ff9044df54f8c967`|

Full graph/I/O hashes, exact input/output rows, metadata lineage and separate fresh output/release paths are in the requests and batch manifest. I/O hashes use ordered rows in canonical sorted-key compact JSON, UTF-8 without a trailing newline. All three actual ONNX files were streaming-hash/size checked; saved original metadata plus materialization deltas bind names, types, order and specialized shapes. This did not parse/load a model or import ORT/QNN.

Worker SHA `4cc89080950c3719e1fa338b5337d036b19c3833dfe817d981ae2705d436332a`; launcher SHA `5f501e7ec3558c8b44d5e9fef126f8dcc321e3824a94cdb3462c6a4cd2e1417a`.

## Bounds and plan-only commands

If separately released, order is **text → vector → vocoder**, serial, one constructor each, zero Run, no automatic retry, stop on first failure. Each component has a fresh output, approval path and unique container name.520s worker +20s grace/≤600s overall **per component**,8GiB/no extra swap,4CPU/math-thread environment, network off, no image pull/build. All `TMPDIR`, `QAIRT_TMP_DIR`, `TMP`, `TEMP` point to that component's owned disk scratch. App priority and external STOP/pressure guards remain. The unique-name/ownership-label cleanup boundary is **non-atomic**; no immutable-ID hardening is claimed.

Review the three exact Docker argv files here: `text.plan.json`, `vector.plan.json`, `vocoder.plan.json`. This command prints a plan and performs **no Docker/native call**:

```sh
P=experiments/0023-supertonic-qnn-precompiled-context-startup/improvements/0001-whole-chapter-capacity
python "$P/tools/run_component_constructor.py" --request "$P/protocol/remaining-constructors/text.request.NOT_APPROVED.json"
```

Change the filename to inspect the vector/vocoder plans. No real approvals or runtime phase directories exist for these requests.

## Validation

**39 tests passed** in0.349s (guard0.602s): the previous30 plus9 new mock-test methods covering all three ABIs, retained constructor/artifact/I/O/provider failures, no-overwrite/no-retry, exact release and I/O binding, duration exclusion, version mismatch, no native import, launcher rejection before Docker and request/runtime/bounds consistency. Mock descriptors/binaries are synthetic, not QNN artifacts or execution evidence.

Both preparation/test groups were reaped and absent; scratch empty. The prior duration request, worker, launcher, artifacts and evidence remain unchanged. Successful duration context generation is not support, execution or quality acceptance for these other components. No new listening claim, pack replacement or push.
