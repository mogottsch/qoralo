# Article review record

## Current revision (story v3): source-audited, chapter removed, editable

Moritz's critique of story v2: too much subtext, the logit explanation did not answer WHY, the whole-chapter section was uninteresting, and the intro was not his voice.

What changed:

- Removed the chapter explorer, the setup chart and the three-stage EOS diagram. The old three-figure requirement was superseded by Moritz's request.
- Re-read the retained 0014 runner instead of repeating the logit observation. Found a definite C++ lifetime bug: `TV()` wraps `bos.data()` in a non-owning `Ort::Value`, and `bos` is destroyed before `Run()`. Details, hash, ORT API documentation and limits: `evidence/source-audit.md`.
- Built a host-only reproducer (`evidence/bos-lifetime-repro.cc`) using the real ORT tensor API under AddressSanitizer. No model, session, inference or phone. Original scope: heap-use-after-free. Buffer kept alive: passes. Two early launch failures were environment problems (library soname; an API22 mismatch on a const accessor) and were fixed before the valid comparison.
- The article states plainly that this is a source finding, not a proved cause of the 10.72 s clip. The retained phone binary hash is not bound to the retained source, the old model was not replayed with only the lifetime fixed, and the fixed-cache graph changed more than this. The invalid-Bria/zero-encoder cause is a separate failure.
- Added inline plain-text editing, local restore and `Save HTML copy`. The saved copy is built from original source text, strips editor state, and keeps working assets through a `<base>`. Nothing writes to the repository.
- The intro is deliberately plain placeholder text for Moritz to rewrite. It is not a new attempt at his voice.

Provenance: Pi independently read the source and confirmed the lifetime defect and the ORT ownership semantics, and advised the claim limits above. Pi did not review the final rewritten copy, and the earlier Thomas/Pi/nik passes belong to `cdfdfb0c`. This revision has no new three-pass review. Hermes style guidance (concise, direct, human, no invented quotes) still applies.

Verification: browser suite passed five widths × two scopes × four stages, keyboard sources, bounded replay/interruption, reduced motion, muted decoding of both exact WAVs with exclusive play, inline editing, local restore, an exported copy reopened from disk with working CSS/script/diagram, and script-failure fallback. Desktop 1440×1000 and mobile 390×844 captures inspected before and after one fix (a wider title measure). Main text is about 314 words including labels; editable copy about 208. Captures and logs: `/tmp/qoralo-story-v3/`.

Disposition: ready for Moritz to edit and review. Final app UI-to-audio demo and listening review remain pending; NotebookLM quality parity is not shown.

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
