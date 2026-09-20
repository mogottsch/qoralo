---
version: 1
slug: "docs-presentation-index-html"
primary_target: "docs/presentation/index.html"
related_targets: ["docs/presentation/README.md","docs/presentation/browser-checks.js"]
---

# Supertonic HTP overview and reconstruction walkthrough

Mode: Read. Moritz wants one overview slide plus a detailed subslideshow visualizing docs/supertonic-android-htp-reconstruction.md. Extend the existing deck, not its visual identity. Preserve the existing six slides and architecture/long-input detours. At Moritz's explicit correction, append the new overview as root slide7 after Models & results; only its eleven-step detail route is optional. All detail exits return to root slide7.

## Direction contract

THESIS: Report what we tried, what failed, what we changed and what happened next. Moritz explicitly rejects sales-pitch headlines and unexplained implementation detail. Lead with the actual problem on each slide; distinguish reported failures from inferred causes.

OWN-WORLD: Inherit the dark #0b1017 canvas, incumbent sans typography and fixed 1920×1080 stage. Mint identifies HTP; blue identifies CPU/host work; amber identifies blocked or qualified results. Use flow diagrams, a placement table, exact-scale startup bars and sequence-boundary drawings rather than repeated cards.

STORY: Follow the root presentation through Models & results to the one-page summary on slide7; choose eleven numbered steps matching the Markdown; advance with arrows or visible controls; return to root slide7 at any time. Notes hold technical receipts, source links and causal qualifications.

FIRST VIEWPORT: Root slide7 keeps the host/phone overview. Details are literal reports: a CPU reference; missing QNN build support with recorded compilation options; rejected dynamic shapes; INT8 blockers and why FP32 avoids them; numerical versus listening results; long startup; Android packaging; rejected longer-chapter audio; the provider recipe; reusable app integration. Two byte-identical0036 audio samples have native click-to-play controls and explicit rejected labels. Preserve persistent navigation; move obscure edge-index and publication mechanics into Notes.

FORM: Code-led local extension of an established surface; no concept roll or replacement world is applicable. One root overview as the seventh and final main-story slide, plus one optional eleven-slide route using existing route metadata and stable hashes. Static diagrams prioritize comprehension over spectacle.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Scope qualification: Preserve the incumbent system; do not create a new root DESIGN.md for this local addition. No shipping raster assets. Two local WAVs are exact copies of rejected0036 outputs, never re-encoded or autoplayed; provenance binds them to Moritz's reviews. Build-command options come from the retained build log and CMake cache. Review runs in-session because this project forbids unrequested agent spawning.

## HTP extension finish review — 2026-09-20

disposition: ship

Review performed in-session; no separate agent was spawned. This is a scoped code-led extension, so the existing deck is visual authority. No PRODUCT.md interview, replacement DESIGN.md, concept roll or raster asset was required.

### persistence
Direction and route scope are recorded here; README documents all eleven steps, sources, controls and validation. Main story has seven slides, ending at the overview per Moritz's explicit correction. This brief is development-only, outside the served deck directory.

### fidelity
- TYPE — match: existing sans face, fixed-stage title/body hierarchy and comfortable desktop diagram labels.
- MATERIAL — match: native HTML/SVG reference and shape diagrams, exact measured startup bars, actual recorded compile options and two byte-identical rejected recordings. The obscure edge illustration was removed in favor of the provider recipe; implementation details remain in Notes.
- GROUND — match: existing #0b1017 dark canvas, mint HTP/blue CPU roles, amber qualification/failure text.
- Topology — corrected at Moritz's request: original root slides1–6 → overview as root slide7 → optional eleven-step route. Both detail boundaries and every direct exit return to root slide7; normal root arrows never force the details.
- Content — report revision matches Moritz's slide-specific feedback: CPU reference stated plainly; missing QNN build support plus command; actual dynamic-shape rejection; explanation of why FP32 avoids quantized-op blockers; simplified numerical-versus-listening comparison; startup problem first; short-clips-to-long-chapter failure with exact rejected audio; provider recipe in four steps; reusable app integration explained before implementation detail. Failed gates and multifactor boundaries remain.
- Captures — all thirteen initial changed/new destinations inspected at 1280×720 and 390×844. After Moritz's placement correction, slides5,6,7 were re-inspected at both sizes in /tmp/luke-htp-review/corrected-{desktop,phone}-{slide-5,slide-models,slide-supertonic-htp}.png. Slide6 has a visible forward control; slide7 shows Main story / 7 of7. Portrait letterboxing is required fixed-stage behavior, not missing content.
- Mechanical checks — all23slides × six viewports passed, including SVG labels, node/section bounds, exact startup ratio, corrected root-slide7 placement and eleven-step detour, old routes, notes, map, keyboard, history, fullscreen, offline and print. First content assertions were corrected to read active slides. A pre-existing hover-arrow translation was isolated and intrinsic-layout tests now park the pointer outside controls.

### ceiling
Reached for the report-style revision. /tmp/luke-htp-report/{desktop,phone}-0.png through -11.png and the audio-error captures were reviewed in-session. All23slides × six viewports passed again with exact audio hashes/durations, muted playback, no preload/autoplay, media keys, mutual exclusion and pause-on-exit. Build-command argument/value pairs match the retained log whose hash is recorded in evidence/qnn-build-record.json. Test-only fixes resolved unavailable sandbox URL and accessing note text through template.content. No additional visual polish round was needed. Browser-native text selection and keyboard focus use the deck palette.

### Precision clarification
Slide5 now explicitly states FP32 source / FP16 requested / per-operation precision unmeasured. The retained ORT repository is at df2ba1cf8108aa63627cf4cdf8f807880b938616 with the inspected header/implementation unmodified. The provider default, HTP precision request and runner's lack of override are recorded in docs/presentation/evidence/qnn-precision-policy.json. This does not upgrade a software request into physical per-operation proof or attribute the numerical difference solely to FP16. The full23-slide/six-viewport suite passed again; /tmp/luke-precision-{desktop,phone}.png were reviewed in-session.

### material_fixes
None outstanding. Detector warnings concern the inherited palette/font/cadence and h3 headings inside speaker-note templates; these render under the notes dialog's h2. No new eyebrow or new visual-world defaults were introduced. REJECTED is an intentional safety label on each failure sample. Actual audio testing was muted and grants no new listening verdict.

### keep
Keep the visible distinction between execution, numerical fidelity, exact-sample quality and multi-factor historical changes; keep the one-pager at root slide7, with only the eleven details optional.

## Prior long-input detour review

The following is historical review evidence for the pre-existing long-input slide, not approval of the new HTP walkthrough.

disposition: ship

### persistence
Scoped extension recorded here and in docs/presentation/README.md. Existing deck code remains the visual authority; no new world or root design-system change was requested.

### fidelity
- Type: matches the incumbent scale and sans family.
- Material and ground: matches the flat dark canvas and mint data emphasis; no simulated physical material.
- Reading order: dated original-release quote and version-3 boundary precede the measured comparison.
- Chart: real CPU sample counts, one time scale, fifteen segments and fourteen native gaps; actual evidence JSON cross-check passed.
- Navigation: nested entry/return, direct links, history, map, fullscreen and offline checks passed. Main story and independent explorer link preserved.
- Captures inspected: /tmp/supertonic-long-inputs-desktop.png, /tmp/supertonic-long-inputs-phone.png and /tmp/supertonic-architecture-linked.png. Phone letterboxing is the deck's required fixed-stage behavior.

### ceiling
Reached for the requested explanatory slide. One restrained reveal carries the timeline; no additional interaction or decorative asset is needed to explain the result.

### material_fixes
None in the new surface. Detector warnings about incumbent palette/font, uppercase text and existing template heading order are outside this local extension and were not rewritten.

### keep
Keep the original-release date, explicit unknown v3 cutoff, common audio scale and non-isolated-cause qualification visible.

## Documentation
README updated with nested route, link, evidence provenance and review boundaries. No global design files changed. Full browser suite passed for eleven slides at six viewport sizes. Review was performed in-session, not by an independent spawned reviewer.
