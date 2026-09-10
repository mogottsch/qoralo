# Whole-chapter capacity — host preparation, no model execution

**Target: T2048/L2048, one complete1–2minute chapter per logical render/WAV. Status: internally blocked by the released vector graph's1000-position table.** Preparation is complete; no real derivative, context, QNN compilation, model forward or phone call has been made. This is not larger-shape support or listening-quality approval. Original0023 recipes, packs, hashlocks and app paths remain unchanged. Git pushes remain held by Pi's separate privacy review.

## Target and exact barrier

`protocol/target.json` pins the same official FP32 ONNX revision `724fb5abbf5502583fb520898d45929e62f02c0b`, M1/SID5, five steps, speed1.0, ORT1.27.1/QAIRT2.49.0.260730, SM8550/v73 and disabled CPU fallback. T and L are independent. One logical render comprises duration1/text1/vector5/vocoder1; profiler callback counts are not a new fatal gate.

| Option | Pre-tag normalized/NFKD codepoints | Audio capacity at3072 samples/latent,44100Hz | Meaning |
|---|---:|---:|---|
| T2048/L2048 |2039|142.6634s|Full two-minute target; positional extension required |
| T2048/L1792 |2039|124.8305s|Less L-dependent work/headroom; still needs extension |
| T1000/L1000 |991|69.6599s|Possible one-minute intermediate without table extension; unvalidated |

The earlier T1024/L1024 suggestion **also exceeds the actual1000-entry table**. Neither1000 nor1024 is two-minute capacity. Text capacity does not guarantee duration, and a 60-second natural chapter must independently fit both limits.

Five guarded metadata parses inspected all four exact official ONNX files, then reread only vector metadata to decode the scoped positional constants. ONNX1.17.0 used `load_external_data=False`; the protobuf necessarily contains embedded initializers, which were parsed, not evaluated. External data, Torch, ORT and QNN were not loaded. No shape inference/checker was run on the real graphs in this milestone; those operations were tested only on synthetic protobuf graphs.

The vector initializer

```text
vector_estimator.tts.ttl.vector_field.main_blocks.3.attn.increments
INT64 [1,1000,1] = exactly [0,1,...,999]
logical int64-le SHA256 702746827e553786bb026ac120cb58745fef3d3f554c33891809001cc37639f0
```

is an arithmetic position table, not an opaque learned float array. Its two direct `Slice` consumers select axis1, start0, step1, ending at the latent-mask and text-mask **tensor extents** respectively. A slice ending at2048 still returns only1000 positions. Those positions pass through FLOAT32 Cast, division by the **sum of active mask entries**, multiplication by the shared `theta[1,1,32]`, and Sin/Cos. The four trig outputs are reused in attention blocks3,9,15,21 (eight direct numerical consumers each). There is no intervening extension back to2048 before the rotary multiplications.

Stored theta values match `10 * 10000 ** (-j/32)` to FP32 rounding, consistent with public `tts.json` rotary scale10/base10000. **Keep the exact existing theta bytes; do not regenerate or rescale them.** The original neural Python constructor is not present in the inspected public inference package: the arange identity is established from actual stored integer values, not a guessed source line.

All four graph interfaces are symbolic in batch and relevant T/L dimensions. There are no external initializers, local ONNX functions or sparse initializers in these graphs. This does not prove that no other larger-shape backend barrier exists. See [`results/host-preparation-20260910/position-analysis.json`](results/host-preparation-20260910/position-analysis.json) and the complete weight-free metadata records.

## Smallest proposed full-target change — NOT implemented

For a separately reviewed full-target branch, replace **one** initializer by INT64 `arange(0,2048)` with shape `[1,2048,1]`, preserving its original1000-element prefix, name and consumers. Logical integer storage would change8,000→16,384 bytes; this is not a measured model/context-file size delta. Preserve all learned initializers, theta, active-mask normalization and rotary wiring. Re-specialize all four graph I/O contracts and retain the existing audited seven-node stable Softplus identity in vector.

Extending the table alone leaves the used positions/phases identical for unchanged T/L≤1000 and identical active masks. That does **not** imply neutrality when increasing padded graph extents: experiment0022 already showed T235→T239 masked padding changed duration15.8623657→15.6378775s and embeddings by max0.1110139. For positions≥1000, extension defines previously unavailable computations; model quality there is unproven. Changing normalization to divide by compiled capacity instead of active counts would be a different, unjustified operation.

The current helper deliberately **rejects vector T or L above1000** and rejects a missing, external, differently-shaped or non-arange table. It implements no positional extension. Full-target materialization remains blocked until Pi reviews a new exact constant-change plan. An unchanged-table≤1000 intermediate is a separate one-minute decision, not a silent target reduction.

## Prepared helpers and next bounded command

- `tools/onnx_capacity.py`: pinned-source metadata inspection, new shape-specialization helper, same seven-node stable Softplus derivative, explicit source/target/helper/output-bound materialization release. No runtime/context-generation branch.
- `tools/run_guarded.py`: thin reuse of the existing read-only host supervisor; fresh owned EXT4 scratch,4thread environment, nice15/ionice2:7,8GiB address-space ceiling, external deadline/STOP/pressure/TERM/KILL/reap. It confers no permission.
- `tests/test_onnx_capacity.py`: **18 tests passed** using synthetic graphs, scalar arithmetic and retained JSON. Tests cover ABI/type/rank/order, internal fixed-shape conflicts, source inventory, unchanged nodes/initializers, stable Softplus structure/stability, exact-release gates, external/opaque positional rejection, both1000-cap branches and shared mask-normalized positional semantics. No synthetic graph was evaluated by an inference runtime.

`protocol/next-duration-request.json` and `protocol/next-duration-release.NOT_APPROVED.json` bind a prospective **duration-only T2048 source derivative**, the smallest3.7MB component, under a120s guard. They are not execution approval. The request names a fresh owned output directory; an exact separate approval must replace the false approval value in a new release file. No real output exists. This would test only duration shape specialization, not vector's positional fix, QNN support, waveform quality or full chapter capacity.

Historical0011/0022/0023 helpers remain frozen: their T239/L238 fixture constants and old vector SHA lock cannot simply be changed in place. Full new graphs/contexts and separately reviewed app trust pins are required; descriptor-only replacement is invalid. Existing app JNI/manifest shape ranges already permit these dimensions, so no splitting API is needed. Existing `prepare_local_runtime.py` deletes current pack directories; any future packaging must use a fresh namespace, not overwrite frozen packs.

## Comparison and resource boundaries

Use the app's normalization, M1/SID5, five steps, speed1.0 and chapter-seeded xorshift64*/Box–Muller inputs. Future source/ORT/QNN comparisons must reuse **identical prepared masks and initial-noise arrays**, not just equal text or a textual seed. Public wrapper defaults8steps/1.05 and NumPy-PCG64 fixture inputs are different references. `wrapper.synthesize()` automatically chunks/concatenates and is not an admissible chapter path. Keep one complete native render and one naturally duration-trimmed WAV. New exact-WAV listening belongs to Moritz; old differently seeded/shape WAV acceptance does not transfer. Janek's separate current one-canonical-request T239/L238 viability gate is unchanged.

T2048/L2048 would increase L-linear dimensions8.605×, T² area73.43× and T·L area73.74× relative to239/238. App FP32 latent/embedding/full-wave buffers would be1.125/2/24MiB, plus output copying and PCM. Config-based single-batch attention score examples are64MiB (4headT²) and128MiB (8headT·L). Actual vector metadata shows doubled classifier-free batch paths, so the latter dense expression could be256MiB before other temporaries. These are arithmetic illustrations, **not native allocation or peak-memory measurements**. Saved0023 setup baseline24.7316s source vs0.20087s external context and roughly1.54GiB vs0.49GiB host high-water cannot be linearly extrapolated to this target.

Actual preparation only: original vector metadata parse peaked546,376KiB; scoped positional reread546,840KiB. Full parse results/logs and seven-worker cleanup are retained. No inference-performance, physical capacity, canonical benchmark, warm median or learned-history/battery evidence was collected. Future model/context work needs separately released budgets and app-build priority.
