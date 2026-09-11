# HTP provider-pipeline route

**One full15-chunk HTP chapter completed; qualified unprompted ASR WER3.03%.**
The exact WAV awaits Moritz's listening verdict. Naive latent padding is wrong;
the explicit native-boundary lowering removes that large error, but remains
numerically nonidentical. The original strict numerical gate **failed and is
preserved as failed**. Physical execution and strong coverage do not relabel it.

This is a noncanonical, single-chapter experiment, not a warm-median benchmark,
registry-quality claim or generic app-ready model pack. Jens's native/dynamic
Android CPU baseline is independent and was not reshaped or delayed for this route.

## Completed phone result

The one granted slot is **consumed**; phone/ASR locks are released and the owned
remote directory was removed. Live APK and all captured DB/WAL/SHM hashes are
unchanged. No further TTS run, ASR retry, audio repair or playback was performed.

Private exact PCM16 mono44.1kHz WAV:

```
experiments/0037-supertonic-provider-pipeline/htp/.local/phone-provider-full-01/evidence/run/chapter.wav
SHA256 0ddfc170d5fca1a11018d68fea6a403175d422ca5b454f1cc9a6bbcddc287209
```

| Measurement | First HTP provider-pipeline chapter |
|---|---:|
| Actual audio including14x0.3s prescribed gaps | 210.184218s |
| Complete native speech extent | 205.984218s |
| Constructors / maximum resident sessions | 32 / 4 |
| Shared-session setup | 0.559414s |
| Interleaved exactT constructors | 0.496209s |
| All constructor time | 1.055379s |
| Interleaved pair teardown | 0.096857s |
| First native waveform ready from process entry | 6.441463s |
| First closed/playable chunk from process entry | 6.457313s |
| First completed chunk available on host from launch | 6.949330s |
| Generation wall including interleaved setup | 87.778723s |
| Process entry through final WAV close | 88.364559s |
| Generation excluding interleaved constructor/teardown | 87.185656s |
| RTF including prescribed gaps/interleaved setup | 0.417628 |
| RTF including gaps, excluding session lifecycle | 0.414806 |
| Own-process `ru_maxrss` | 173,864KiB |
| Sampled own VmRSS / PSS peaks | 77,816 / 74,440KiB |
| Battery before staging → last native sample | 28.3 → 28.8°C |
| Qualified unprompted ASR | 3.0303%WER;480/495 exact matches |
| Exact-WAV human listening | `not_reviewed` |

All15 chunk payloads and14 zero gaps reconstruct the final PCM byte-for-byte.
Fourteen complete chunk files were pulled before the final chapter file existed;
all15 delivered chunk hashes match the final assembly. This is chunk-level file
availability, not sample-level streaming or playback.

All165 reported neural Run calls used fail-closed QNN contexts, with own duration,
features and state. Owned-PID/time-filtered CDSP/v73-skeleton/PD/queue/remote-handle
logs corroborate physical RPC use and cleanup. ProfileOFF means **no hardware
cycle/HVX counters or independent per-node device profiler count**. Nonfatal
startup/teardown diagnostics are retained, not hidden. Linux RSS/PSS omits some
DSP/DMA/global memory and does not prove a total-memory advantage over CPU.

HTP ownnativeL differs at zero-based006(96vsCPU95) and014(250vsCPU249). Only000–005
have matching complete active-noise hashes; all later hashes differ. This is
expected own-duration stochastic behavior, not grounds to inject CPU durations.

One offline Whisper-small decode recovered493words vs495normalizedreference,
13substitutions+2deletions+0insertions,480exactmatches,46–50matches in every decile,
and29/last30words. Model/runtime/settings match the retained canonical control
(36words,0WER). Automatic coverage is strong, but not a human quality verdict.

- `results/first-chapter-01.json`: execution snapshot, own extent/noise/index and
  assembly validation. Its ASR status reflects the pre-ASR capture boundary.
- `results/asr-first-chapter-01.json`: additive one-pass qualified coverage.
- `results/physical-evidence-01.json`: RPC, memory, thermal and app-preservation
  metadata; all content-bearing logs remain private.
- `results/comparison-01.json`: CPU/HTP first-route observations, setup/profile
  qualifications, exact noise correspondence and human-review-pending state.

The preferred matched process-entry → final WAV-close comparison is CPU
113.552973394s / HTP88.364558664s = **1.285x configuration-level wall ratio**.
It includes upfront/interleaved setup through the same output boundary, excluding
post-output teardown and offline preparation/staging. The earlier1.284x generation
ratio is retained only as a historical diagnostic with unmatched setup boundaries.
This is not a controlled pure-provider speedup: geometry, precision/lowering,
profiling, lifecycle and later active noise differ. No warm median, app-ready pack
or accepted-quality throughput is claimed.

## Frozen provider recipe

Authority: `supertonic-py` v1.3.1, commit
`908a56486e821e833a80530ff0cae3ad0b046fce`; frozen common files in
`../protocol/{inputs,freeze}.json`. Bundle manifest SHA:
`ea3b4830da25a5d9a01ae5da343296700ae841a019248f3be8364b39243715df`.

- Segment original raw text first, target300 characters, preserving whole
  sentences even if longer. Normalize/tag/index each provider chunk afterward.
- Fifteen actual native text extents:
  `[309,213,243,153,188,298,106,212,97,239,224,236,252,229,280]`.
  The target300 is not treated as a hard input bound.
- M1/SID5, explicit English,8 steps, speed1.05; append full native vocoder output
  `nativeL*3072`, plus exactly13230 zero frames between chunks, no final gap.
- Every route computes its **own** duration/nativeL with the frozen float32
  arithmetic. No forced duration, CPU duration injection, or old floor-duration
  audio crop. Fail if the provider's extent/mask calculations disagree.
- Consume144*own-nativeL contiguous values from the frozen Gaussian stream per
  chunk, then channel-aware pad. Do not consume bucket-stride noise. Record actual
  offsets and active hashes; equal seed does not imply equal route noise.

## Static adaptation and boundary semantics

Duration and text need their exact nativeT specializations; these are experimental
case-specific preparation, not a general app solution. Shared vector T320/L512 and
vocoder L512 retain the original1000-position table and every learned weight.

Vocoder's12 EDGE pads are **left-only/causal**. Its complete native output prefix
was bitwise equal with native vs zero-padded latent input on all15 tested source
CPU cases (nativeL92–279). This is measured case coverage, not universal or HTP
proof. NativeL still must come from HTP on the real route.

Vector's28 EDGE pads are **symmetric**, with radii2/4/8/16. Zero-padding latent
features moves the right edge and changes active outputs even with a latent mask.
The derivative substitutes each EDGE Pad with `Gather(axis=2)` using:

```
indices[r] = clip(arange(-r, bucketL+r), 0, own_nativeL-1).astype(int32)
```

These four coordinate arrays are nonlearned layout inputs, derived only from the
HTP route's own nativeL. Each original convolution receives its native EDGE span;
all neural Gather/Conv/attention operations remain on HTP. No waveform repair,
CPU feature substitution, arbitrary chunking or learned-weight change is involved.
Seven synthetic tests include exact native EDGE spans for **every L1–512** and all
four radii, with adversarial garbage in inactive positions.

The vector also retains the audited stable Softplus identity
`relu(x)+log(1+exp(-abs(x)))`, needed by the QNN route. It is mathematically the same
function, not a promise of bitwise floating-point equality.

## Preserved source evidence

All neural probes here used host CPU ORT1.23.2 / NumPy1.26.4, four intra-op threads,
one inter-op thread,8GiB address-space/900s limits and `heavy-ram.lock`.
Explicit float32 scalar boundaries reproduce the frozen NumPy2.3.5 extent recipe.
This host runtime differs from Android ORT1.27.1. Activations/PCM remain private;
none may be staged as HTP synthesis inputs. No host chapter was assembled or
played, and no ASR/listening acceptance is inferred from numerical tests.

| Probe | Result | Evidence |
|---|---|---|
| Naive T320/L512, chunks000/008,8 steps | Active latent max error3.50/3.14; failed | `results/padding-baseline-01.json` |
| T-only vs L-only isolation | T-only bitwise equal in these two cases; L-only reproduces the failure | `results/padding-isolation-01.json` |
| Native EDGE + stable Softplus, all15 chunks | Vector max2.06e-4, RMSE≤3.56e-6; original strict gate failed | `results/native-boundary-full-source-01.json` |
| Same native latent through native/static vocoder | Complete native prefixes bitwise equal15/15 | same full-source evidence |
| Original Softplus, native vs EDGE bucket | Final latent max2.99e-4, RMSE≤9.02e-6 | `results/boundary-controls-01.json` |
| Stable Softplus, native vs EDGE bucket | Final latent max2.02e-4, RMSE≤6.08e-6 | same controls |
| Original vs stable Softplus, both native T/L | Final latent max1.59e-4, RMSE≤4.87e-6 | same controls |

The controls start from identical active state/noise and reuse preserved native
reference outputs. Dynamic stable-Softplus control binds batch1 only; T/L remain
dynamic. Residual error is **not solely Softplus**: static/layout floating-point
execution also differs. Node/initializer audits and synthetic exact EDGE-span
checks support the boundary mapping; whole-network bitwise equality is not claimed.

### Numerical allowance ledger, not a replacement pass threshold

The predeclared source gate was max absolute error≤1e-4 and RMSE≤1e-5.
It remains **failed**; thresholds have not been tuned to relabel it. For the15
observed end-to-end source cases, the explicit numerical contribution is bounded
by0.003733 normalized full-scale peak error and0.0929% of reference RMS
(worst SNR60.64dB). These are **observed case bounds**, not universal guarantees,
perceptual acceptance, or a prospective HTP error threshold. HTP precision/provider
error must be reported separately; intelligibility needs the actual HTP WAV and
qualified unprompted ASR, with listening acceptance only from Moritz.

Source runs retained privately include two zero-execution preparation failures:
missing `/usr/bin/time` in the first launcher, and a too-strict constant-only Pad
resolver that initially rejected the source's six-element INT64 pad initializer.
A first native-shape Softplus control preparation also rejected symbolic batch
metadata; the corrected control binds actual batch1, leaving T/L dynamic. No
failed execution or gate was discarded and no audio was repaired.

## Export, standalone runner and resource boundary

All32 external single-QNN-EPContext exports passed with zero `Session.run`, CPU
fallback disabled and profile OFF. This includes the four INT32 native-edge input
arrays. ORT registers a CPU provider, but registration does not mean execution;
unsupported neural fallback is forbidden. See `results/context-export-01.json`.

- Host constructors: serial `heavy-ram.lock`,4CPU/8GiB/no extra swap, no network,
 520s per constructor, immutable container-ID cleanup. All32 constructors total
 40.30s; maximum observed cgroup peak1771.1MiB. All owned containers removed.
- All32 allocation plans pass: maximum conservative per-context estimate320MiB,
  minimum signed-size margin1,811,939,327 bytes. This includes128MiB allowance and
 64MiB rounding, not a guaranteed native allocator formula. See
  `results/context-footprints-01.json`.
- Standalone ARM64 runner builds with warnings-as-errors and FMA contraction OFF.
  Nine pre-run tests passed, including the **actual C++ runner helpers** for FP32 own extent,
  all edge indices, channel-aware stream layout and provider-equivalent PCM16;
  these tests neither link nor load ORT and perform no neural execution. Five
  retained-result/aggregate checks bring the test total to14.
- Session lifecycle is bounded: vector/vocoder reused throughout; a current-T
  duration/text pair cache has capacity one T. All15 T values are unique, so older
  pairs have no reuse benefit.32 constructors, maximum four resident sessions;
  interleaved constructor/teardown time is measured separately from CPU's four
  resident dynamic sessions. No old whole-chapter text-depth partitions.
- Private stage payload567,061,554 bytes:32 contexts, six pinned libraries,
  runner, common style/step/noise arrays and exact chunk tokens/masks. No raw text,
  source ONNX, CPU duration/features or precomputed edge indices are staged.
- The completed phone run used>=3.5GiB available, battery<42°C,5GiB native AS,
 3GiB own RSS limit,600MiB available floor,45°C thermal ceiling,1800s native alarm.
  Read-only live APK and double DB/WAL snapshot checks protect existing rows.
  Dedicated generation/test PIDs must be absent; main/Room presence alone is not
  generation. While main is present, live read-only job snapshots enforce no
  queued/running jobs. Actual conflicting work makes us stop only our runner.
- Phone only in Pi's scheduled slot, full `phone.lock` lifecycle and live app/job,
  thermal/memory preflight. No app/data modification, playback or global kills.
  Current app identity is discovered live, never restored to an older experiment.
- The one initial HTP chapter and one qualified unprompted ASR pass are complete.
  First outcomes, exact hashes and all availability boundaries are preserved.
  Do not consume a delayed duplicate slot message or rerun while waiting to listen.

## Reproduce source checks

Use `experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/.local/proof-venv/bin/python`
with bounded affinity/environment and the heavy-RAM lock. Outputs must be fresh
private `.local/` directories.

- `tools/check_padding.py`: original dynamic baseline; optional vector/vocoder
  candidate paths for the static native-boundary comparison.
- `tools/isolate_padding.py --baseline ... --output ...`: isolate T/L and resolve
  only bounded source padding constants, not guessed EDGE behavior.
- `tools/materialize.py --component vector --text-length 320 --latent-length 512
  --output-dir ...`: checked static derivative. Duration/text reject non-frozen
  T values.
- `tools/check_controls.py --baseline ... --output ...`: native-Softplus geometry
  and native-shape stable-Softplus controls, with the original gate intact.
- `python -m unittest discover -s htp/tests -v` from the experiment directory:
  fourteen synthetic/retained-result tests, no source model/ORT execution or
  device use. One compiles only nonneural C++ helpers without linking ORT.
