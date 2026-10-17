# Qoralo: LinkedIn draft and article plan

Working draft for Moritz. Nothing has been published. The post below can describe the retained experiments now; a final demonstration on the chosen app build and a listening review of its exact output are still pending. Update that status only after they happen.

## Proposed opening angle

A working short audio sample did not mean the phone could read a chapter. Use that failure to explain what deploying local models actually involved, then show the current division of work: Gemma on the GPU and Supertonic on HTP. Keep the voice close to the presentation's report style.

## LinkedIn post draft

I'm building Qoralo, an Android prototype for generating podcast scripts and turning them into speech on my Galaxy S23 Ultra.

Gemma handles text generation on the GPU. Supertonic 3 handles speech through Qualcomm's Hexagon accelerator, using the QNN HTP backend. The CPU still coordinates the work.

The short speech tests worked. Then we gave Supertonic a whole 487-word chapter in one call. Both the CPU and HTP versions produced about 30 seconds of unusable audio. I rejected both recordings.

Getting computation onto the accelerator had answered only part of the question.

Even that took some work. Our original ONNX Runtime build had no QNN support. After rebuilding it, the packaged INT8 model still contained operations that could not run entirely on HTP. The official FP32 graphs avoided those quantization-specific blockers; replacing one unsupported Softplus operation then enabled all four neural components to run there.

FP32 describes those source graphs. Our runtime requested FP16 execution; we did not measure the arithmetic precision of every operation inside HTP.

Startup was another problem. In a matched short-input experiment, loading precompiled QNN contexts reduced the four speech-model sessions' median setup from 21.6 seconds to 0.50 seconds. That measurement excludes speech generation and offline compilation.

For the longer chapter, we followed the provider's full recipe: group sentences into shorter segments, normalize each segment, use the prescribed generation settings, and join the resulting waveforms. That produced about 210 seconds of audio. I accepted both experimental recordings after listening. Several settings changed together, so I can't credit segmentation alone.

A lot of the implementation was done with coding agents. I then had to reconstruct the steps and learn what they meant. Keeping the failed attempts made that conversation much more useful than a list of successful benchmarks.

The app is still a prototype. The model paths have been exercised under the Qoralo app identity, but a final demonstration through the UI and a listening review of its output are still pending.

## Optional longer technical article

Working title: **Running a podcast prototype on a Galaxy S23 Ultra: Gemma on the GPU, Supertonic on HTP**

Suggested structure:

1. **What the app is trying to do.** Start with the intended workflow: prepare source material, generate and review a script, create speech, then listen or export. Separate intended workflow from what the final demo actually demonstrates. Show the current UI only after capturing the chosen build.
2. **Where the computation goes.** One simple diagram: Gemma 4 E2B IT through LiteRT-LM's GPU route, Supertonic 3 through ONNX Runtime/QNN HTP, CPU orchestration around both. Model preparation and context compilation happen on the development machine. Do not describe the whole app as all-NPU or entirely GPU-free/CPU-free.
3. **Establish a CPU reference before changing the backend.** Briefly identify Supertonic's four graphs. Explain why ONNX model files and an ONNX Runtime binary are different artifacts. The runtime has to include the QNN provider; the caller must also select it.
4. **Why the smaller INT8 export was harder to deploy.** The first route remained a CPU/HTP hybrid because of unsupported quantization operations. The official FP32 graphs used a different computation representation. Explain the single Softplus rewrite, then distinguish FP32 source precision from the runtime's FP16 request. Avoid claiming that INT8 models generally cannot use HTP.
5. **Fixed sizes and reusable inputs.** Start with the actual dynamic-shape rejection. Show how a fixed array can hold a shorter valid sequence, but explain that masking alone did not preserve Supertonic's convolution boundaries. Keep the initial fixed-transcript demonstration separate from the later reusable app pack.
6. **The startup result.** Use the existing chart and exact setup boundary from experiment 0023. Three fresh processes per arm, one phone, one fixed legacy input. Source and context output bytes matched each other. That equality does not imply equality with the CPU reference, and the ratio is not a speech-generation or app-launch speedup.
7. **The whole-input failure and the provider recipe.** The rejected 0036 samples are a useful failure illustration if included deliberately and labelled before playback. Then explain the complete 0037 recipe: raw sentence grouping toward 300 code points, per-segment normalization, M1/English, eight steps, speed 1.05, full native waveforms and 0.3-second gaps. Overlong sentences remain intact. The observed roughly 30-second failures do not establish a hard model cap.
8. **What each test could tell us.** The all-HTP short output failed a numerical waveform threshold but was accepted in listening. The later provider source numerical check also remained failed. Automatic ASR supports coverage; human listening evaluates the exact audio. None of those findings substitutes for the others or proves universal quality.
9. **Integrating the recipe into an app.** Explain why the chapter-specific 32-context experiment became four reusable contexts with explicit capacities. Include the Android native-library visibility issue if space permits. Progressive playback has retained genuine generation/playback overlap evidence, with other controls tested using retained-audio replay; do not turn the combined record into one uninterrupted clean demo.
10. **The remaining demonstration.** End with the chosen build, actual input and exact audio that Moritz has reviewed. Until available, retain a clear statement that the final UI demonstration and listening review are pending. If script generation fails, describe that outcome instead of editing it out of a claimed uninterrupted run.

### Performance wording for the article

The short LinkedIn draft deliberately omits a headline CPU-versus-HTP throughput ratio. If the longer article includes experiment 0037's chapter timings, use this wording:

> For one 487-word chapter, the CPU configuration took 113.55 seconds from process entry to final WAV close; the HTP configuration took 88.36 seconds. The resulting audio was about 210 seconds long in each case. These were first runs with different profiling, tensor shapes and session lifecycles, so this is a comparison of the two tested configurations, not an isolated accelerator speedup or a warm benchmark.

CPU profiling was on and HTP profiling was off. Later active noise inputs also diverged because each route predicted its own duration. Preparation, compilation and staging were outside that device timing boundary. Do not infer device-wide memory or energy savings from process RSS.

## Claim-to-source check

These are internal review references, not automatically public links for the LinkedIn post. The repository is private. Moritz needs to choose which diagrams, results or article location to share publicly.

| Claim | Retained source | Wording limit |
|---|---|---|
| Qoralo uses Gemma GPU and Supertonic HTP. Both model routes were exercised after the rename. | [Renamed script-path result](../podcast-app/evidence/qoralo-rebrand/script-path-20260920/result.json), [renamed bridge result](../podcast-app/evidence/qoralo-rebrand/single-app-20260920/result.json) | Separate smoke tests, not a final UI-to-export episode run. GPU route does not mean every LLM operation uses the GPU; CPU orchestration remains. |
| The packaged runtime lacked a usable QNN route; we built QNN-enabled ORT. | [Reconstruction, step 2](supertonic-android-htp-reconstruction.md), [recorded build options](presentation/evidence/qnn-build-record.json) | Specific runtime build and sherpa TTS path. The displayed wrapper command reconstructs saved options; it is not a new build result. |
| Packaged INT8 reached a hybrid; official FP32 plus a Softplus rewrite enabled all four neural graphs on HTP. | [0010 handoff](../experiments/0010-supertonic-qnn-htp-feasibility/HANDOFF.md), [0011 result](../experiments/0011-supertonic-official-fp32-phone-comparison/results/softplus-matched-e2e-checkpoint.json) | Preserve the failed numerical threshold and CPU application work. No retraining or blanket claim about all INT8 exports. |
| FP32 source does not establish FP32 hardware arithmetic; the provider requested FP16. | [Pinned precision-policy inspection](presentation/evidence/qnn-precision-policy.json) | Software configuration verified; per-operation/accumulation precision and sole cause of numerical differences were not measured. |
| Precompiled contexts reduced median four-session setup from 21.6129 s to 0.497816 s. | [0023 phone result](../experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/phone-result.json) | Fixed legacy input, matched runtime, three fresh processes per arm. Excludes offline compilation and inference. Byte equality is source-HTP versus context-HTP, not CPU versus HTP. |
| A 487-word whole-input chapter produced about 30 seconds of unusable audio on both CPU and HTP. | [0036 results](../experiments/0036-supertonic-whole-chapter-cpu-htp/README.md), [CPU rejection](../experiments/0036-supertonic-whole-chapter-cpu-htp/cpu/results/listening-review-20260911.json), [HTP rejection](../experiments/0036-supertonic-whole-chapter-cpu-htp/htp/results/listening-review-20260911.json) | Historical failure, not showcase audio. No demonstrated universal 30-second cap. |
| The complete provider recipe produced about 210 seconds; Moritz accepted the two experimental files. | [0037 recipe/results](../experiments/0037-supertonic-provider-pipeline/README.md), [listening review](../experiments/0037-supertonic-provider-pipeline/results/listening-review-20260911.json) | CPU accepted hash starts `6848fcd6`; HTP starts `0ddfc170`. Acceptance is specific to those files. Several recipe factors changed; the strict source numerical failure remains. |
| The chapter took 113.55 s on CPU versus 88.36 s in the HTP configuration. | [0037 comparison](../experiments/0037-supertonic-provider-pipeline/htp/results/comparison-01.json) | Same process-entry-to-WAV-close boundary. One first run per route; CPU profile ON, HTP OFF; geometry, lifecycle and later noise differ. No pure-provider or warm-speedup claim. |
| Genuine playback advanced while HTP generated; later control checks used retained audio. | [Progressive Player handoff and coverage table](../podcast-app/docs/progressive-player-handoff-2026-09-13.md) | Historical build, muted advancement, not a new audible-latency or current-build full E2E result. Original all-in-one capture script failed. |
| The final app demonstration and exact-output listening review are pending. | [Renamed script result: notVerified](../podcast-app/evidence/qoralo-rebrand/script-path-20260920/result.json), [renamed export scope](../podcast-app/evidence/qoralo-rebrand/export-20260920/result.json), [historical app WAV status](../podcast-app/evidence/provider-integration/README.md) | Export smoke used an owned fixture, not a newly generated episode through the Files picker. Historical app WAV `2194bce6…` has no transferred 0037 verdict. Final status needs a new receipt and Moritz's review. |

## Demo and screenshots still needed

No phone activity or capture is requested while Moritz is away. These are inputs to arrange with him when he returns.

| Needed item | Specific capture | Why it is needed |
|---|---|---|
| Final build identity | Chosen app build/commit, model-pack identities and basic device/runtime context | Existing evidence spans different app identities and builds. Do not label old screens as the final build. |
| A permitted demonstration input | Short, non-sensitive source material and instructions that Moritz is happy to publish | Avoid using personal episode content, account details or work-profile material accidentally. |
| One real UI-driven run | Screen recording from input through script review and Create audio; retain waits and failures, or label time cuts explicitly | Separate route smoke tests are not this demonstration. If space is limited, show a clearly labelled excerpt and preserve the complete attempt internally. |
| Script and audio progress | One readable script-review screen and one actual generation screen from that run | Make the role of Gemma and Supertonic understandable without showing raw diagnostics. |
| Player and audible sample | Capture the Player for the same completed chapter/episode; Moritz listens and records a verdict against the exact WAV hash | Earlier experimental acceptance does not approve a new waveform. Use a confirmed accepted sample for the showcase. |
| Final state | Library/Ready screen for that same attempt; export only if the post intends to claim it was demonstrated | Do not substitute a synthetic UI fixture or the export smoke fixture. A Files-picker export remains outside the renamed smoke result. |
| An offline demonstration, if claimed | After provisioning, an agreed run with network access disabled and the relevant state visible | Local backends establish compute placement, not a network/privacy audit. Do not assert that nothing ever leaves the phone. |
| Public destination | Moritz's choice of article URL, code/results excerpt or downloadable material | Private repository links are not useful to LinkedIn readers, and no public download or app release should be promised yet. |

Existing material that can support the article without a new phone session:

- [Presentation](presentation/index.html#slide-supertonic-htp): root slide 7 and its report-style walkthrough. Screen captures for publication should use the selected version and preserve captions/measurement boundaries.
- [Reconstruction](supertonic-android-htp-reconstruction.md): the source-backed history for drafting technical explanations.
- The exact rejected 0036 examples already bundled with the deck. Use only as optional, clearly introduced historical failure audio. They must not accompany an unqualified Qoralo product demonstration.

## Before Moritz posts

The retained [SCRIPT failure notes](../podcast-app/docs/chapter-json-failure-notes.md) describe real JSON-parse failures with unresolved cause. A successful short renamed script-path test does not establish reliable multi-chapter generation. Do not claim that pending prompt/runtime changes have fixed those failures before checking the selected build and its actual run.

- Confirm that the first-person wording matches what he wants to say about coding agents and learning the deployment steps.
- Keep "prototype" and the pending-demo sentence unless new evidence closes those points. Finishing the work this weekend is a goal, not a result to announce in advance.
- Listen to and approve the exact showcase file; identify it internally without burdening the post with hashes.
- Keep Gemma GPU + Supertonic HTP explicit. Avoid "all-NPU," blanket bit-exactness, universal reliability, broad privacy guarantees, and SDK token-rate figures that were never observed.
- If adding a performance number, preserve its workload and timing boundary in the same paragraph. Use the longer article for the profile-asymmetry qualifications.
- Check public sharing permissions for source text, images and audio; do not distribute Qualcomm SDK/runtime/context binaries as post attachments. Private-repository access is not a redistribution license.
- Replace private links with an approved public destination, or omit the link. Publishing to LinkedIn remains Moritz's action.
