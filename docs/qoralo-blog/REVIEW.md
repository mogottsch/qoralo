# Article review record

## Simplification (story v4, latest)

Moritz called the page too elaborate: "no meaningless values", the NaN/zero rows and the phone-observation paragraph are bloat, the collapsible goes, and the cause should read "kept talking, and the voice changed because it is built on that wrong start". Removed the step diagram and collapsible, the rows, the toggles, the scrubber and readout, the phone-observation paragraph, the 134-frame cap, the raw scores and the arithmetic. Kept one simplified chart (two phone lines, seconds axis, a "stop line", no numeric scores) and the five-line source excerpt; the previous desktop-replay chart is gone from the page.

The tone/voice sentence is stated as what is established: every frame is built on the wrong start (the first internal state differs by about its own size in the replay). No claim is made about what the failing audio says or why this particular sound results. The limits and numbers remain in the notes and `evidence/`; the browser suite still checks them in both directions and now also fails if meaningless numbers return to the main text.

Next, pending agreement on the agenda: the experiments section (models, backends, condensed benchmark table, RTF note) and the full-system flow diagram, to be split across existing peers.

## Explaining the path to the stop check (story v4, later)

Moritz understood NaN versus zero but not how that changes the sound or ends up in the stop check. Moritz then found the result too elaborate and asked for the plain gist first with detail afterwards: the Why section now opens with three sentences, followed by the chart and phone evidence, and the one-step diagram and its two paragraphs moved into a collapsed "How a wrong start reaches the stop check" (the edit mode opens it). The browser suite checks that the gist is visible without opening anything, that the detail is collapsed by default and keyboard-operable, and that the order is gist, chart, detail. Content of the detail, as first written: added a one-step diagram (start vector or previous frame, model and cache, one internal state, next frame and stop score) and two short paragraphs: the frames are the audio and the length is frames × 80 ms; the stop score is read from the same state as the next frame; zeros put the first state and frame far off, the correct run's score rises at the end of the sentence (frame 53), the zero run's never passes -7.4. The scrubber readout now gives audio time and the stop-check verdict.

Checking the claim with data changed the story: the first internal state differs by about its own size (1.05) and the first frame by 0.76 from the correct run, so the difference is large immediately. The earlier sentence "the difference compounds" was dropped; the browser suite now fails if it returns, and checks the page's numbers against `bos-zero-replay.json`. What is not shown: what the failing audio actually says after the sentence, and why the model's stop head does not fire in the zero run beyond the score trajectory itself.

## Phone check (story v4, later): inference became observation

Moritz called "zeros are inferred, not observed" unacceptable and offered to connect the phone. One bounded CPU-only window ran four builds of the retained runner twice (unmodified, BOS-dump, buffer-kept-alive, both). Results, protocol record and limits: `evidence/phone-bos-check/README.md`. The page now states the observation with its exact limits (instrumented build only; old binary and original graph missing; second unmodified run differed; no allocator explanation; no new listening verdict).

- Pi required controller fixes before granting the window (single 300 s window, bounded per-run timeouts, owned-process identity, explicit cleanup states, fresh no-user-work preflight) and independently verified all eight raw JSON/WAV hashes, dumps, exits and cleanup receipts.
- Honest protocol notes: two read-only preflight-only invocations preceded the window to validate parsers; the memory gate was lowered from 3 GiB (QNN convention) to 1.5 GiB for this 712 MB CPU runner; the controller's cleanup step timed out and correctly reported incomplete, and a separate lock-held manual cleanup was verified (PIDs gone, no cwd in stage, `ABSENT` from a reachable device).
- The browser suite now reads `phone-bos-check/results.json` and fails if the page's run counts or limits drift from the receipts.

## Current revision (story v4): the WHY is the article

Moritz's latest direction: he does not care about the buffer-lifetime finding as a fix. He wants to explain where the divergence comes from, then quickly mention the fix actually applied. The WHY is the main thing.

What changed:

- Rebuilt the article around the explanation. The graph treats a NaN first input as "use the learned start vector". A host-only replay of the old loop, changing only that input, shows that all zeros reproduces the retained Android stop scores over all 134 frames (max 0.074, mean 0.006, no stop) and NaN does not (differs by up to 16.4, stops at 53). The retained Android fixed-cache run matches the correct-input replay within 0.0021. 62 partly zeroed inputs did not match.
- The earlier buffer-lifetime finding is now the likely way the NaN marker was lost, shown as a short source excerpt, not as my fix. The applied fix is one section: the NPU-oriented fixed-cache graphs, which have no NaN marker.
- Removed the buffer-lifetime stepper, the chapter section, the logit-only diagram and the setup chart.
- Added a baked-in SVG stop-score chart (generated from the evidence JSON), an input toggle and a keyboard frame scrubber with exact readouts.
- Fixed a real editor bug found by the new tests: an edit used to store and export every paragraph as plain text, which stripped inline `<code>`. Now only edited paragraphs are stored or exported.
- The intro remains deliberately plain placeholder text for Moritz to rewrite.

Claim discipline (applied after Pi's independent review): zeros were **inferred, not observed** at that point; the phone's memory had not been read. The phone check above has since observed them in the instrumented build. The retained source-to-binary binding is unverified. The exact original graph is missing and a same-size reconstruction was used, validated against the retained host run (first score -9.8847, stop at 53) and the retained Android fixed-cache scores. The 65-pattern scan includes one duplicate (all-zero) and the correct all-NaN case, so the page says 62 partly zeroed inputs, and it is not exhaustive. No audio was generated from the replay and no listening claim is made. The invalid-Bria/zero-encoder failure is a different cause.

Provenance: Pi independently reran the replay (reproduced -9.8847/stop 53, zero first score -10.2709, 134-step max 0.0736/mean 0.00577/no stop, fixed-cache max 0.0021) and read the source, and directed the wording above. Pi did not review the final rewritten copy. This revision has no new three-pass review; the original Thomas/Pi/nik passes belong to `cdfdfb0c`. Pi separately added the `0014/RESULTS.md` correction.

Verification: browser suite passed chart data against the evidence JSON; five widths × three input modes; chart, tick and annotation geometry; keyboard scrubber exact readouts; wording guards; reduced motion; both exact WAVs decoded with exclusive playback; inline editing, restore and an exported copy reopened from disk with a working chart; print; script-failure fallback; no external requests or page errors. Desktop 1440×1000 and mobile 390×844/320×740 captures inspected; one corrective pass moved the stop-note, dimmed it in zero mode and widened the mobile chart margin. Local captures and logs: `/tmp/qoralo-story-v3/`.

Disposition: ready for Moritz to edit and review. Final app UI-to-audio demo and listening review remain pending; NotebookLM quality parity is not shown.

### Story v3 (superseded)

Moritz asked to drop the chapter, reduce subtext, explain why, and make the text editable. v3 answered with the buffer-lifetime stepper alone and said the exact cause was unproved; v4 replaces that with the replay evidence.

## Previous revision (story v2, superseded)

### Story v2 details

Moritz replaced the brand-led story with a NotebookLM-inspired question: how close can a source-to-podcast workflow get with all inference on the phone? He explicitly wants a technical audience, useful engineering explanations, interactive/animated figures and the funny historical short-sentence Pocket TTS recording. The central portability point is that working on one device does not establish correct generation on another.

The current narrative is 253 words; default main content including figure labels/controls/captions is 561 visible words. The setup optimization moved to expandable details. Coding agents are no longer a main story point. One-voice narration is stated explicitly rather than implying NotebookLM's conversational format has been reproduced.

### Revised-copy review: Pi

Pi read the revised HTML/JS and the owning 0014 source records. His actual review is `/tmp/qoralo-article-reviews/story-v2-pi-review.md`; he made no repository edits, model run, browser run or listening judgment.

All three edits were applied before the visual pass:

1. State the engineering action in visible prose: fixed 256-slot cache, explicit positions and validity mask. Describe the recovery input as same text/voice/noise with a different cache layout, not identical input tensor layouts.
2. Replace the generic chapter moral with the specific takeaway to port text preparation and the synthesis loop, not only neural graphs. Use plain listening wording for the later exact CPU/HTP recordings.
3. State visibly that the current prototype writes a script and reads it in one voice.

The original three reviews below belong to the earlier article at `cdfdfb0c`. This revised copy received the additional Pi review, not three newly invented review passes.

### Revised implementation and verification

- Added three interactive figures: user-triggered route traces, a three-stage KV-state/EOS diagnostic with a bounded playable explanation, and a real-sample-length chapter-piece explorer.
- Both Pocket players are **historical Android CPU** recordings: original dynamic graph 10.72 s, fixed-cache derivative 4.48 s. Verified SHA-256 against the owning records; no regeneration or audio editing. The fixed graph is a different implementation. First stop-score divergence is not asserted to be the cause of the voice or a proved faulty operator. This is not labelled a Supertonic or NPU failure.
- Inspected desktop1440×1000 and mobile390×844 together, including all three diagnostic states. One corrective batch widened the desktop heading and made hover colors media-aware. Final desktop/mobile captures were inspected; no clipping or overlap. Desktop columns become readable rows on mobile.
- Final browser suite passed five widths (1440,1280,768,390,320) × three diagnostic states, exact audio/gap geometry, native keyboard sources, keyboard range exploration, bounded explanation/replay interruption, muted decoding/playback of both actual WAVs with exclusive playback, reduced-motion behavior, loaded-page offline interaction, print and script-failure fallback. No external runtime requests or page exceptions.
- One detector run: cross-media button-hover warnings addressed with an explicit print hover token; direct screen-style checks retain light text on the dark ground. Two trace-lane padding warnings correspond to intentional open row/column separators, not cramped boxed text; inspected actual insets and layouts. No second detector run.
- Local captures/test reports: `/tmp/qoralo-story-v2/`. No shipping raster assets. No phone/model run, new listening acceptance, app/runtime/deck edits or public publishing.

Disposition: ready for Moritz's story/design review. The final app UI-to-audio demonstration and exact-output listening review remain pending. NotebookLM quality parity has not been tested.

## Original article review history (cdfdfb0c)

The following records the superseded brand-led version, not current word counts, JavaScript behavior or a claim that its reviewers saw the revised story.

Scope: a short HTML article, not a LinkedIn post. No phone access, inference, public publishing or changes to the presentation/app/runtime. The final main article has 299 words, including diagram labels and captions; source notes are collapsed.

## Hermes style consultation

Consulted Moritz's existing `hermes-agent` gateway in its Kubernetes namespace through its supported chat-completions interface. The request used the gateway's existing in-process environment authentication without exposing its value. No Secret reads, deployments, pod/configuration changes, replacement Hermes, full-history retrieval or unrelated content scraping.

Hermes distinguished remembered preferences from suggestions. Remembered: concise, direct, human; lead with the useful point; avoid em dashes and internal process/guardrail boilerplate; do not invent Moritz quotations or anecdotes. It suggested concrete verbs and separating the historical failure from later experimental success. Its example phrases were explicitly samples, not quotations. No personal anecdote was manufactured from them.

## Three actual peer review passes

Moritz authorized review agents. The interactive-shell launcher rejected the attempted launches before creating a reviewer process because unused existing-session options conflicted with launch-only output selection. Pi explicitly approved using the existing peer sessions instead. These were **three real peer reviews**, not newly spawned subagents and not three self-reviews. Only Luke edited the article.

### Pass 1: Thomas

Inputs: first copy draft, bounded fact sheet and humanizer skill. Actual report: `/tmp/qoralo-article-reviews/pass-1.md`.

- Flagged “Startup took 22 seconds” as liable to mean app launch. Changed the subject to speech-model setup and labelled the timing boundary on the chart.
- Replaced unexplained “saved QNN contexts” with prepared files in visible prose; kept technical specifics in records.
- Simplified “join the full waveforms” to joining audio with gaps.
- Changed the administrative pending-review sentence to “I still need to run the final app demo and listen to its output.”

A revised copy draft was sent to the next reviewer.

### Pass 2: Pi

Inputs: revised copy, fact sheet and Thomas's critique. Actual report: `/tmp/qoralo-article-reviews/pass-2.md`.

- Cut “spoken podcasts” and reduced acronym-heavy opening prose; exact model/backend labels remain in the diagram.
- Changed the audio rows from “one call / 15 segments” to named approaches with listening verdicts. This avoids visually claiming that segmentation alone caused the improvement.
- Replaced report-generator wording such as “A later test used” and “I accepted” with direct first-person language.
- Retained the sentence that generation settings also changed. Explicitly identified the new CPU and HTP recordings in the listening sentence so it cannot refer to the old rejected and new accepted CPU bars as two good outputs.

Applied before the rendered page went to the final reviewer.

### Pass 3: nik

Inputs: actual rendered text, HTML, fact sheet, first two critiques and desktop/mobile screenshots. Actual report: `/tmp/qoralo-article-reviews/pass-3.md`.

- Found no hype or generic moral requiring a further rewrite.
- Flagged “provider” as ambiguous between Qualcomm's execution provider and Supertonic. Changed it to “Supertonic's recipe” and explicitly said it was the same chapter.
- Replaced “Four-session” and “per version” with four speech models and per method in visible captions. Kept the exact technical boundary in records.
- Asked for more prominence for “Both recordings: CPU. Bars show audio length, not generation time.” Increased critical captions to 14px and made the chart axis say “CPU audio length.”
- Simplified “implementation” to “code.” Kept the coding-agent explanation and pending final demo.

nik reviewed screenshots without a new browser/model run. He recommended applying those limited edits and finishing, not opening another editorial loop. They were applied and the browser checks/captures were repeated.

## Visual and browser verification

- Three figures: responsive phone routing schematic; proportional speech-session setup bars; sample-count-based chapter audio bars with all 15 real CPU segment extents and fourteen 0.3-second gaps.
- Initial and final full-page captures inspected at 1440×1000 and 390×844. Mobile rearranges the actual diagram rather than shrinking text into an unreadable miniature.
- Automated checks passed at widths 1440, 1280, 768, 390 and 320: no horizontal overflow or model-label overlap; exact bar/sample proportions; 15 segments/14 gaps; keyboard-operable source disclosure; loaded-page offline operation; print presence; no external runtime requests or page errors. The page has no JavaScript, embedded audio or external service dependency.
- One mechanical detector run found a skip-link hover contrast issue. Fixed the hover rule; direct computed-style verification shows foreground `rgb(11,16,23)` on `rgb(142,232,194)`. No second detector run or unrelated redesign.
- Final source links and data values were checked against retained local records. No fresh model performance or listening claim was created.

Capture/test files are local under `/tmp/qoralo-article-reviews/`; no screenshots or personal source text are required as shipping assets. `browser-checks.js` retains the reproducible browser checks. The page's data is static and works without JavaScript.

## Outcome and remaining input

Three peer critiques incorporated; final desktop/mobile inspection and browser checks passed. No public article or LinkedIn publication was performed. Moritz still needs to approve the prose in his own voice, choose any public destination, perform the final UI demonstration and review its exact audio. Earlier experimental listening acceptance remains limited to its original files.
