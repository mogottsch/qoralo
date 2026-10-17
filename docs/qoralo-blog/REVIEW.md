# Article review record

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
