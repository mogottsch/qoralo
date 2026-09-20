# How we got Supertonic running on Android HTP

A reconstruction from the experiment records, implementation tools, result files and Git history. This is a reading document for discussing how the deployment works, not a proposal for a presentation format or a claim that we have rerun the experiments.

The main sequence below covers the work from August 13 through September 12, 2026. Some later app and long-text work overlapped. The app is now named **Qoralo**, with package `dev.qoralo.podcast`; the cited historical app records predate that rename.

## The central finding

There was not one “convert Supertonic to HTP” step. We solved several different problems, with a significant change of approach along the way.

> The successful all-neural-HTP route started from Supertonic’s official FP32 ONNX files—not the INT8 package we initially tried. We did not retrain the model.

The essential work was:

**Establish a reference → supply an HTP-capable runtime → make dimensions concrete → adapt unsupported operations → verify real execution and output → precompile → preserve variable-length semantics → integrate the complete synthesis recipe into Android.**

## Part 1 — Get Supertonic’s computations onto HTP

### 1. Establish a working CPU reference

We first ran the packaged Supertonic 3 model on Android using **sherpa-onnx and ONNX Runtime on the CPU**.

That gave us something working to compare against: model files, voice, text preparation, generated audio, timing and memory use.

We also established that “Supertonic” is **four neural networks plus code that connects them**:

| Component | Job |
|---|---|
| Duration predictor | Estimate how much speech to generate |
| Text encoder | Turn the text into numerical features |
| Vector estimator | Repeatedly refine a noisy internal speech representation |
| Vocoder | Convert that representation into audio samples |

The surrounding code prepares text and voice inputs, creates the initial noise, calls those networks in order, and saves the audio. Duration prediction and text encoding receive the prepared text separately; the duration predictor does not produce the text encoder’s input.

**We already had ONNX files. Exporting a PyTorch model to ONNX was not a required new step in the successful route.**

Sources:

- [0010 architecture and baseline](../experiments/0010-supertonic-qnn-htp-feasibility/README.md)
- [Pinned model provenance](../experiments/0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/conversion-provenance.json)

### 2. Build a runtime that could actually reach Qualcomm’s accelerator

**ONNX Runtime already supported HTP. But the ready-made sherpa Android package we were using did not expose a usable QNN/HTP route for Supertonic.** This was a build-and-integration limitation, not a fundamental limitation of ONNX.

First, distinguish the layers:

| Term | Role |
|---|---|
| **ONNX** | The model format: computation graph, learned weights and tensor definitions. It does not execute itself. |
| **ONNX Runtime (ORT)** | The software that loads a graph and manages its execution, including memory and operation implementations. |
| **QNN Execution Provider** | An optional ORT integration that sends supported graph computations to Qualcomm’s QNN software. |
| **QNN HTP backend** | The Qualcomm backend that targets Hexagon. QNN can have other backends; QNN does not always mean HTP. |

Here, **runtime** means execution software, not elapsed execution time. When referring to ORT together with its Qualcomm dependencies, **runtime stack** is the clearer term. Our own application code still connects Supertonic’s four graphs and controls the refinement loop; ORT executes each graph rather than inventing the synthesis recipe.

There were two separate obstacles:

1. **The packaged runtime.** ONNX Runtime supports many execution providers as a project, but every prebuilt binary does not contain all of them. QNN support is optional at build time; the retained version’s CMake configuration defaults `onnxruntime_USE_QNN` to `OFF`. Our original packaged runtime lacked the required integration. Setting `provider="qnn"` at execution time cannot add code that was not included when the runtime was built.
2. **The sherpa wrapper.** Our app called sherpa-onnx, which created the model sessions. Its pinned generic TTS provider-selection path did not recognize `qnn`. Even supplying a QNN-capable runtime would not, by itself, teach that wrapper to select and configure it. This is a statement about that specific version and path, not every sherpa feature or release.

The original route was:

```text
Our app → sherpa-onnx → packaged ONNX Runtime → CPU
```

We built a separate Android ARM64 runtime and used our own C++ runner to connect the four components:

```text
Our C++ runner
    → ONNX Runtime with QNN support
        → QNN Execution Provider
            → QNN HTP backend
                → Hexagon
```

That route used:

- **ONNX Runtime 1.27.1**, built with QNN integration.
- **Qualcomm QAIRT 2.49**, supplying QNN tools and libraries.
- The **QNN HTP backend**, targeting the S23 Ultra’s **SM8550 / Hexagon V73**.

We also needed the matching phone-side libraries: the HTP backend, preparation library, V73 stub/skeleton and related runtime components.

Before trying Supertonic, we tested a tiny addition graph. The first attempt failed because `libQnnHtpPrepare.so` was missing. After supplying it, profiling demonstrated real accelerator execution.

**Three requirements must hold separately:** the runtime has QNN integration; the calling code selects and configures it correctly; and the model’s operations and shapes are supported. Fixing the first two did not automatically satisfy the third.

**Why this mattered:** it separated “our Android-to-HTP connection works” from “Supertonic is compatible with it.”

Sources:

- [0010 runtime choice and packaged-runtime findings](../experiments/0010-supertonic-qnn-htp-feasibility/README.md#runtime-choice)
- [ORT build options at the recorded source revision](https://github.com/microsoft/onnxruntime/blob/df2ba1cf8108aa63627cf4cdf8f807880b938616/cmake/CMakeLists.txt)
- [0010 physical-control and runtime record](../experiments/0010-supertonic-qnn-htp-feasibility/results/phone-probe-checkpoint.json)

### 3. Give the graphs concrete input sizes

The source model accepted variable-length inputs. Our QNN HTP route needed **concrete tensor dimensions**.

We captured real inputs from a CPU run and created fixed-shape derivatives. The initial contract was:

- **T239:** 239 processed text positions, including language tags.
- **L238:** 238 positions in the internal speech representation—not 238 audio samples.

This was a deliberately narrow deployment for a known input, not arbitrary-text support. We recorded the changed model hashes and checked the specialized graphs against the CPU originals. The later official-FP32 experiment repeated this specialization and validation for its own source files.

**Why this mattered:** the compiler needed to know the sizes of the arrays it would process.

Sources:

- [Initial shape capture and derivative requirements](../experiments/0010-supertonic-qnn-htp-feasibility/README.md)
- [0011 specialization and compatibility results](../experiments/0011-supertonic-official-fp32-phone-comparison/results/step2-fail-closed-htp-checkpoint.json)

### 4. Discover that the initial INT8 route was a dead end for full offload

The first approach reused the packaged INT8 graphs.

Several problems appeared:

- An ONNX Runtime crash required a small upstream bug-fix backport.
- The vocoder contained operations expressed in forms the backend could not handle. Constant weight dequantization was folded, and decomposed GELU activations were rewritten as explicit GELU operations.
- The vector estimator still contained unsupported dynamic-quantization operations and a `Softplus`.

The eventual result was **hybrid**, not all-HTP:

- Duration and text encoding ran on CPU.
- The vector estimator alternated between HTP partitions and CPU operations.
- The vocoder ran fully through HTP.

A separate re-quantized vocoder attempt also failed numerical checks. We did not turn that into the successful route.

**Lesson:** a model being “INT8” does not mean its particular graph is suitable for an NPU.

Source: [0010 final handoff](../experiments/0010-supertonic-qnn-htp-feasibility/HANDOFF.md). Hybrid milestone: `728cfc75`.

### 5. Switch to the official FP32 files and replace one unsupported operation

This was the decisive pivot.

We took Supertone’s official FP32 ONNX assets and verified a complete Android CPU run. After fixing their shapes:

- Duration predictor: supported.
- Text encoder: supported.
- Vocoder: supported.
- Vector estimator: blocked by **one `Softplus` operation**.

We replaced that operation with a mathematically equivalent, numerically stable expression:

```text
Softplus(x) = max(x, 0) + log(1 + exp(-abs(x)))
```

Those constituent operations were supported. The rewrite preserved the learned weights and all unrelated operations, and CPU comparisons checked its numerical effect.

**That enabled all four neural components to execute through HTP, with CPU fallback disabled.**

This did **not** involve a new training run, calibration campaign or explicit INT8 conversion. “FP32” describes the source files; the retained evidence does not establish the accelerator’s internal arithmetic precision.

Sources:

- [Exact rewrite tool](../experiments/0011-supertonic-official-fp32-phone-comparison/tools/rewrite_vector_softplus.py)
- [All-HTP result](../experiments/0011-supertonic-official-fp32-phone-comparison/results/softplus-matched-e2e-checkpoint.json)

Runner implementation milestone: `70080a47`. The separately linked result file records the execution and validation outcome.

### 6. Run the complete pipeline—and verify more than “it returned audio”

A native C++ runner connected the stages:

```text
Prepare text and voice inputs
        ↓
Predict duration + encode text
        ↓
Create initial noise
        ↓
Run the vector estimator repeatedly
        ↓
Run the vocoder
        ↓
Write a WAV
```

The CPU still orchestrated this. **“All HTP” meant all four neural graphs, not every instruction in the application.**

We disabled automatic CPU fallback and checked both ONNX Runtime provider events and physical accelerator/RPC profiling. Across the recorded campaign, all 48 neural calls had HTP evidence and no CPU-provider node events.

There were two different quality outcomes:

- Moritz accepted the exact CPU and HTP listening samples.
- The HTP waveform **failed the predeclared numerical comparison threshold** against CPU.

Both facts remain true. Listening acceptance did not turn the numerical test into a pass.

Source: [0011 results and listening verdicts](../experiments/0011-supertonic-official-fp32-phone-comparison/README.md).

## Part 2 — Make startup practical

### 7. Move graph preparation off the phone’s startup path

The working route spent roughly 22 seconds creating its four sessions. Much of that was graph preparation and compilation.

We therefore generated **precompiled QNN contexts** on the development machine. Each component became:

- A small **EPContext ONNX descriptor** that ONNX Runtime could load.
- An external **QNN context binary** containing the prepared graph.

There was an important failed attempt first: experiment 0022 tried to reuse the old fixed graphs for a shorter benchmark input by adding masked padding. **Padding changed the calculation**, so that experiment stopped.

Experiment 0023 instead kept the original graph/input contract and successfully compared source loading with context loading:

| Four-session setup on the phone | Median |
|---|---:|
| Prepare from source ONNX | 21.61 s |
| Load precompiled contexts | 0.50 s |

The generated output was byte-identical. Context loading also worked with the source ONNX files deliberately unavailable.

**This was primarily a startup improvement, not a new speech model or a comparable improvement in synthesis speed.** Offline context generation was outside that phone setup measurement.

Sources:

- [0022 failed compatibility gate](../experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/README.md)
- [0023 phone result](../experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/phone-result.json)

Milestone: `1ac06f15`.

## Part 3 — Make it work in an app and on useful amounts of text

### 8. Solve Android-app integration separately

A standalone native runner working on Android did not guarantee that the same libraries would load inside an APK.

The app initially failed during QNN device creation. A subsequent diagnostic identified a native-library visibility problem: the V73 stub could not resolve the public **`libcdsprpc.so`** library in the app’s namespace.

A manifest declaration addressed that issue. A load-only test succeeded, followed by a complete short app synthesis with physical QNN evidence. Moritz accepted that exact short WAV.

**This was an Android packaging/runtime-access problem, not a change to Supertonic’s weights.**

Source: [Phone integration history, sections 2–3](../podcast-app/docs/phone-return-handoff.md).

### 9. Try larger whole-input graphs—and find that execution was not enough

The short fixed graphs could not handle podcast chapters. We first pursued larger graphs rather than segmentation.

That introduced more engineering:

- Extending a nonlearned positional table beyond its original 1,000 entries.
- Rewriting two large vocoder convolutions after HTP compilation hit local-memory/tiling limits.
- In the later whole-chapter test, dividing the text encoder by **network depth**, because a single context hit an RPC allocation-size limit. This did not split the text.

We eventually produced whole-input CPU and HTP WAVs for a 487-word chapter.

**Both were failures as speech results.** They contained only about 29.57 seconds of audio, automatic word-error rates were around 89%, and Moritz rejected both.

Making a graph large enough to execute had not made that synthesis recipe suitable for a chapter.

Sources:

- [Larger-context engineering](../experiments/0023-supertonic-qnn-precompiled-context-startup/improvements/0001-whole-chapter-capacity/README.md)
- [0036 outcome](../experiments/0036-supertonic-whole-chapter-cpu-htp/README.md)

### 10. Follow the provider’s long-text recipe—and fix padding correctly

Experiment 0037 switched to the provider’s actual pipeline:

- Group raw sentences toward 300 characters.
- Normalize and index each resulting segment.
- Use eight refinement steps and speed 1.05.
- Keep each segment’s full native vocoder output.
- Insert 0.3-second gaps between segments.

The chapter became 15 synthesis segments. The 300-character target was not a hard limit: the pinned provider recipe kept individually overlong sentences intact.

HTP still required fixed-size graphs. Simply filling unused positions with zeros was **not** sufficient: some convolutions repeated values at the sequence edge, and padding moved that edge.

We therefore changed those operations to use explicit indices that preserve the **real segment boundary**, even inside a larger fixed-size buffer.

The first implementation used 32 prepared contexts: 15 exact-length duration/text pairs, plus shared vector and vocoder contexts.

This produced about 210 seconds of speech. Automatic coverage was much better, and Moritz accepted both exact CPU and HTP files. The stricter source numerical gate nevertheless remained failed.

**Several recipe settings changed together; the records do not prove segmentation alone caused the improvement.** The new results do not retroactively validate the rejected whole-input attempts.

Sources:

- [0037 recipe](../experiments/0037-supertonic-provider-pipeline/README.md)
- [HTP boundary adaptations](../experiments/0037-supertonic-provider-pipeline/htp/README.md)
- [Hash-bound listening acceptance](../experiments/0037-supertonic-provider-pipeline/results/listening-review-20260911.json)

### 11. Replace the chapter-specific context collection with four reusable app contexts

The later app integration generalized that approach:

- Fixed text capacity **T320**.
- Fixed latent capacity **L512**.
- Runtime boundary indices for the actual text and latent lengths.
- Four resident contexts rather than 32 chapter-specific ones.

It also ported the provider’s text normalization and random-noise behavior, and added checks to reject inputs outside the supported capacities. Reusable within those capacities does not mean unlimited input lengths or guaranteed synthesis quality.

A real app run synthesized all 15 segments. It then failed during final file publication—not during neural synthesis. A separate, zero-inference recovery published the already-generated bytes after fixing the file-location requirement.

The retained handoff marks that **new app WAV as not reviewed**; the earlier experimental listening verdict was not transferred to it. This is evidence from a real synthesis followed by a separate publication recovery, not a clean full neural replay on the corrected app build.

Sources:

- [Reusable-context integration](../podcast-app/docs/provider-htp-integration.md)
- [Actual app evidence sequence](../podcast-app/evidence/provider-integration/README.md)

Milestones: `3a13c651`, `897571ce`.

## What was a demonstrated fix, and what was only a later improvement?

Chronological order alone does not establish why something improved.

| Change | What the evidence supports |
|---|---|
| Supply the missing HTP preparation library | The tiny graph’s missing-dependency failure was resolved and physical execution followed. This was not a Supertonic quality test. |
| Replace the single unsupported Softplus | The rejected vector graph became fully delegable. CPU comparisons separately checked the rewrite; HTP numerical equivalence did not automatically follow. |
| Load external contexts instead of preparing source ONNX | A matched comparison demonstrated reduced four-session setup time with byte-identical output. |
| Declare the public FastRPC library in the APK manifest | The otherwise unchanged manifest variant passed the previously blocked duration-session load. That load-only result did not itself prove synthesis. |
| Preserve native sequence edges inside fixed buffers | Source controls identified naive latent padding as a source of large errors and demonstrated a much closer boundary-aware calculation. The original strict numerical gate still failed. |
| Change from the 0036 whole-input recipe to the 0037 provider recipe | The new complete recipe produced much better coverage and accepted exact samples. Segmentation, normalization, step count, speed and output assembly changed together; segmentation alone was not isolated. |
| Fix final artifact staging and recover the completed file | Publication succeeded using the retained audio with zero new model calls. That was a file-publication fix, not a new successful synthesis run. |

## Evidence limits and reference status

- This reconstruction is based on retained records, not a fresh rerun or a check of the currently installed phone state.
- The original 0011 runtime binary was already unavailable during 0023. That experiment explicitly used the same newer runtime for both comparison arms rather than claiming historical binary identity.
- We know the source model precision, but not the exact internal arithmetic chosen throughout QNN’s HTP execution.
- Successful execution, numerical similarity, spoken-text coverage and Moritz’s listening verdict are separate findings—not interchangeable definitions of success.
- Later provider/app runs had profiling disabled. Their reported calls and physical RPC/runtime logs must not be described as the detailed cycle/HVX profiling collected in the earlier experiments.
- The linked source/result documents exist in the committed repository. Their contents and the five milestone commits were checked against HEAD when this reconstruction was prepared. Proprietary runtime/context files and private content-bearing evidence referenced inside those records are not assumed to be publicly reproducible assets.
- The Qoralo name/package changes are recorded in `fab2f552` and `2f9af40e`; those commits do not retroactively change the identities in historical evidence.

## Starting point for our discussion

Start with **what is actually inside the four ONNX files, and what remains outside them in ordinary code**.

That distinction makes the later steps—fixed shapes, graph rewriting, compilation and contexts—much easier to follow. The numbered steps above can serve as references for questions; presentation format can wait.
