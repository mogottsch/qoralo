# Mobile podcast TTS — parallel preview and feasibility plan

## Purpose

Continue toward high-quality, podcast-like local audio generation on the Samsung Galaxy S23 Ultra by running four coordinated tracks:

1. generate a directly listenable approximately 15-second preview with `microsoft/VibeVoice-Realtime-0.5B`;
2. generate the same preview with Kyutai Pocket TTS 100M;
3. generate the same preview with Kokoro 82M;
4. continue the existing VibeVoice 1.5B Android work only far enough to reach the fourth 3,200-sample chunk, where the locked PyTorch reference first becomes clearly audible.

This plan supersedes the completed 19-task ExecuTorch plan for future Crew work. The prior 39/39 result remains immutable historical evidence: the tested VibeVoice 1.5B ExecuTorch/XNNPACK package is rejected as deployed, but deeper review shows that the two Android chunks closely match the reference's expected introductory silence. The next experiment must distinguish a repairable cache warm-up/export limitation from a model-quality failure.

Generate the plan only. Do not start workers until the user reviews and explicitly approves it.

## Product goal

The target is high-quality podcast-like speech generated locally on a mobile device. Joint multi-speaker modeling is desirable but not mandatory if a smaller model can retain persistent per-speaker voice state and generate turns that can be assembled into convincing dialogue.

Candidate acceptance targets for later Android work:

- package preferably at or below 1.5 GB, with 2 GB as a provisional hard ceiling;
- peak PSS below 3 GB;
- no fixed two-chunk or short-duration ceiling;
- real-time factor at or below 1.0, preferably 0.5 or lower;
- first audible audio within two seconds;
- stable operation for at least three to five minutes without severe thermal throttling;
- intelligible speech, stable voice identity, no text omissions/repetitions, and acceptable blind listening results.

These are target criteria, not claims about any candidate.

## Shared preview protocol

All three new models must use one locked input protocol so the user can compare their sound rather than different scripts or post-processing.

Create and commit a small manifest containing:

- one speaker-neutral English podcast-style monologue of approximately 35–45 words, with punctuation that elicits natural pacing;
- exact UTF-8 transcript and SHA-256;
- deterministic seed where supported;
- selected voice and voice-source provenance for each model;
- native sample rate and output format;
- exact commands and model/source revisions;
- raw-output duration and hash;
- derivation of a listenable exactly 15.000-second, 24 kHz mono PCM/WAV preview.

Do not time-stretch audio. If raw generation exceeds 15 seconds, preserve the raw output and derive the preview using a zero-crossing-aware trim plus a short fade. If it is shorter than 15 seconds, do not loop or fabricate speech; revise punctuation or voice speed within the model's documented controls and regenerate. Record all transformations. Loudness-normalize only derived comparison copies to a common target, while preserving unnormalized originals.

The preview comparison should include both:

- `raw/` files preserving each model's native output;
- `normalized/` exactly 15-second files for listening comparison.

Generated audio, weights, virtual environments, converted models, caches, and logs remain ignored under `artifacts/`. Commit scripts, manifests, hashes, measurements, and conclusions. The preview publisher may upload ignored WAVs to the existing private/static preview so the user can listen in the browser; it must not add WAVs to Git.

## Model track A — VibeVoice Realtime 0.5B

Use the official Microsoft model and source first. Pin exact source/model revisions before generation. Record license/intended-use text and stop if proprietary acceptance or a new manual agreement is required.

Required work:

1. establish a dedicated reproducible environment without changing system Python or contaminating the existing VibeVoice 1.5B environments;
2. inspect the model card and source to identify supported voices, conditioning inputs, deterministic controls, sample rate, and streaming behavior;
3. generate the locked preview transcript with an appropriate podcast-style voice;
4. preserve raw streaming chunks and the assembled raw WAV;
5. produce the normalized 15-second comparison copy;
6. record generation wall time, time to first audio where observable, peak host RSS, real-time factor, model/download bytes, output hashes, RMS/peak/loudness, and any audible anomalies;
7. add a browser audio player to the existing preview dashboard.

Do not claim mobile feasibility from host generation. This task is first a listening preview and reproducibility test.

## Model track B — Pocket TTS 100M

Use the official `kyutai-labs/pocket-tts` implementation and official model weights. Pin source/model revisions and create an isolated environment.

Required work mirrors the Realtime track:

- use the exact locked transcript;
- choose a documented stock voice with clear provenance rather than cloning personal audio;
- generate and preserve raw streaming/native output;
- derive the normalized exact 15-second comparison copy;
- record wall time, first-chunk latency, peak RSS, RTF, model bytes, hashes, audio statistics, and anomalies;
- publish a browser audio player.

Record the model's ability to retain multiple voice states as a later podcast-composition capability, but do not add a second transcript or change the fair single-voice bake-off input in this phase.

## Model track C — Kokoro 82M

Use the official `hexgrad/Kokoro-82M` weights and official/recommended implementation. Pin exact revisions and use an isolated environment.

Required work mirrors the other preview tracks:

- exact locked transcript;
- one documented stock voice with provenance;
- raw native output plus normalized exact 15-second comparison copy;
- wall time, first-output latency where available, peak RSS, RTF, model bytes, hashes, audio statistics, and anomalies;
- browser audio player in the existing preview.

Record phonemizer/system dependency requirements. Do not perform privileged package installation. If a required binary is absent, use a project-local artifact or block with the exact requirement.

## Model track D — VibeVoice 1.5B fourth-chunk recovery

Keep the locked evidence and accepted INT8/FP32 component choices unless a narrowly scoped diagnostic requires otherwise.

Important new evidence to preserve:

- locked PyTorch reference chunks 0 and 1 are approximately `-93.66` and `-93.49` dBFS;
- Android's two-chunk output is approximately `-118.83` dBFS, but differs from the corresponding 6,400-sample PyTorch prefix by at most one signed 16-bit PCM unit, with mean absolute difference approximately 0.471 units;
- reference chunk 2 is a fade-in around `-52.38` dBFS;
- reference chunk 3, covering 0.400–0.533 seconds, is clearly voiced around `-21.71` dBFS.

Required work:

1. create a structured supplementary prefix-comparison result so the previous quality rejection is not misread as proof of divergence;
2. capture at least the first 16–20 real PyTorch recurrent calls, including all acoustic and semantic cache shapes, selected tokens, diffusion outputs, decoder inputs, PCM hashes, and per-chunk RMS;
3. determine exactly when each `SConvTranspose1d` cache reaches its configured `kernel_size - 1` steady-state context;
4. choose and document the smallest correct ABI: preferably fixed maximum-size cache plus valid-length/phase input, otherwise a minimal warm-up set plus a repeatable steady-state entry;
5. avoid multiplying full weight copies for every warm-up phase; evaluate one multi-method PTE and/or PTD external constants before accepting phase-specific artifacts;
6. validate calls 0–3 on the host against the locked PyTorch trace;
7. run the Galaxy S23 Ultra through at least four chunks under the existing phone lock;
8. compare Android and PyTorch at Qwen hidden/logits, selected token, connector output, diffusion final latent, decoder latent, PCM, semantic output, and recurrent cache boundaries;
9. require chunk 3 to contain the expected audible energy and pass a documented numerical/perceptual comparison before extending to three seconds.

Do not start broad new quantization work inside this recovery track. Its purpose is to establish recurrent and audible correctness.

## Follow-up mobile feasibility tasks

After all three previews and the 1.5B fourth-chunk result are available, prepare—but do not silently assume—the next Android candidates:

### Realtime 0.5B Android decomposition

- inventory active parameters and tensor operators;
- identify the Qwen 0.5B, approximately 40M diffusion head, and approximately 340M acoustic decoder boundaries;
- determine whether the official streaming state is fixed-size;
- estimate FP16, INT8, and mixed/groupwise INT4 package sizes without overclaiming runtime support;
- define component-first fixtures compatible with the existing evidence methodology.

### Runtime/accelerator probes

Prioritize Qualcomm QNN/HTP on the SM8550 for components whose operators are supported. Use microprobes before full integration and record partition coverage, CPU fallbacks, tensor transfers, numerical error, and latency. Candidate quantization schemes include `8a8w`, `16a8w`, and blockwise `16a4w`. A proprietary SDK/license requirement must block for user approval.

LiteRT/LiteRT-LM and ONNX Runtime Mobile remain valid comparison runtimes. Do not duplicate full conversion effort until the candidate model and its quality have passed the user's listening review.

### Turn-by-turn podcast composition

For single-speaker models, design a later evaluation where two persistent voice states generate alternating turns from a shared script, followed by native pause/crossfade assembly. Keep this separate from the fair single-voice 15-second bake-off.

## Required Crew task graph

The planner may refine titles, but the following objectives must remain traceable. Expose safe parallelism and preserve strict dependencies.

1. **Lock the shared 15-second preview protocol and create reproducible audio-analysis utilities.**
2. **Prepare and pin VibeVoice Realtime 0.5B.** Depends on task 1.
3. **Prepare and pin Pocket TTS 100M.** Depends on task 1.
4. **Prepare and pin Kokoro 82M.** Depends on task 1.
5. **Generate and measure the VibeVoice Realtime preview.** Depends on task 2.
6. **Generate and measure the Pocket TTS preview.** Depends on task 3.
7. **Generate and measure the Kokoro preview.** Depends on task 4.
8. **Capture VibeVoice 1.5B recurrent calls 0–19 and document cache stabilization.** May run in parallel with the lightweight setup tasks but owns the heavy-RAM slot.
9. **Design and host-validate the VibeVoice 1.5B warm-up/steady-state cache ABI through chunk 4.** Depends on task 8.
10. **Run and compare VibeVoice 1.5B chunks 0–3 on Android.** Depends on task 9 and owns the phone.
11. **Build the listening bake-off page and structured comparison.** Depends on tasks 5–7; publish ignored WAVs through the existing preview mechanism.
12. **Prepare Realtime 0.5B Android component/runtime feasibility recommendations.** Depends on task 5 and may run in parallel with tasks 9–11.
13. **Synthesize the candidate decision report and update the preview.** Depends on tasks 10–12. This is an integration-writer task and must not start further model conversions.

The final task must leave the project ready for a user decision among:

- proceed with Realtime 0.5B on Android;
- proceed with Pocket TTS or Kokoro turn-by-turn mobile composition;
- continue VibeVoice 1.5B recovery;
- run a narrow QNN accelerator bake-off;
- reject a candidate based on listening quality.

## Parallelism and serialized resources

- **Heavy-RAM capacity: one.** VibeVoice 1.5B capture/export and Realtime 0.5B heavyweight generation may not overlap. Pocket TTS and Kokoro can run concurrently only after observing that combined RSS remains safely below the 32 GiB host limit.
- **Phone capacity: one.** No concurrent ADB/device tasks. The fourth-chunk Android recovery owns the phone exclusively.
- **Integration writer: one.** Shared transcript/manifest, common comparison result, experiment index, preview HTML, and publication are serialized.
- Use separate virtual environments and artifact roots per model.
- Workers reserve committed files before editing and avoid staging unrelated concurrent changes.

Use up to three workers for setup/research, but at most two simultaneous generation processes and never two heavy-RAM jobs.

## Evidence and artifact policy

- Keep weights, generated WAVs, PTEs, APKs, converted models, caches, raw tensors, logs, and telemetry ignored.
- Commit exact revisions, scripts, environment locks or version manifests, result JSON, hashes, measurements, acceptance criteria, and conclusions.
- Every result distinguishes host listening preview from Android feasibility.
- Every failed setup or generation attempt remains useful evidence when reproducible.
- Do not use personal voice samples or device data.
- Do not accept paid services or proprietary terms without stopping for user approval.
- No product UI, feed ingestion, Podleaf, Gemma, or unrelated application work.

## Review gate

Planning ends with a task graph only. Do not call autonomous work. The user must review the PRD and generated Crew plan before workers start.
