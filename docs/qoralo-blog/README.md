# Building a NotebookLM-like podcast on my phone

Open `index.html`, or serve the repository root:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
# http://127.0.0.1:8766/docs/qoralo-blog/
```

A short technical article about a source-to-podcast workflow with local phone inference. Qoralo is the experiment's app name, not the article's subject. The prototype generates a script and narrates it in one voice; this is not NotebookLM's conversational format or an established quality match.

## Agenda (agreed with Moritz) and status

1. The question: title, intro and question, **approved and frozen** (the browser suite fails if their text changes). Under it a one-line **tl;dr** ("tl;dr, if you don't care about the details: jump to the demo") linking to the demo at the end, for readers who don't want the details.
2. **The demo is at the end** (Moritz's request), a section "The demo" right before the closing line. Slot only: `media/demo.mp4` does not exist yet, so the page shows an explicit "Demo video goes here" notice instead of a broken player. No synthetic footage, no autoplay.
3. **What I tried** (first person, as Moritz asked; the whole article is now first person): two subsections. **Speech:** five speech models on CPU and, where they ran, the NPU (HTP): a five-row table with columns "CPU RTF" and "NPU RTF" (plain warm medians), a small note box with the RTF formula rendered as a fraction (MathML, no library) and a one-line example. **Script writing:** a seven-row table with "Prefill" and "Decode" in tokens per second, kept strictly separate from the speech numbers (never RTF), from Thomas's packet (`evidence/llm-table.json`, five-request long-tier medians of generic text benchmarks, recalculated independently by Pi). The Gemma NPU row is a different build that ran but repeated itself on long prompts, its decode rate is withheld as words, and it is not presented as a recommended route. The app uses Gemma on the GPU.

   **Tables are sorted by an explicit rule, in code** (`build-table.py`, `build-llm-table.py`), and the browser suite checks the order. Speech: by how far each model got (ran on the NPU, ran on the CPU only, produced no speech), then by speed inside each group, so speeds are never ranked across groups. Script writing: grouped by model, the app's model first and the others by name, then fastest decode first inside a model, a route without a decode rate last; models are never ranked against each other.

   **No footnotes under the tables** (Moritz asked for them to be removed). The caveats they carried (warm medians after setup, each model on its own test text so compare within a row, HTP versions are rewritten graphs checked by ear, the table's Pocket samples are not the clips in the next section; the LLM tests are generic long-text tests, not the app's script pipeline or script quality, medians of five loaded requests, same input for every row, tokenizers differ) now live in `NOTES.md` next to the article (the page itself has no notes or sources section any more). Both tables are generated from committed packets and checked value by value in the browser suite.
**Reference links** (Moritz asked for them; the deep dives into the repo's own docs were deliberately left out). Eleven on the page (plus two in `NOTES.md`), all `class="ref"`, https, `rel="noopener noreferrer"`, quiet underline, mint on hover, none in the title. Each URL resolved with HTTP 200 when added. "NotebookLM" in the intro goes to Google's Audio Overviews announcement, because Google renamed NotebookLM to Gemini Notebook on 16 July 2026 and `notebooklm.google` now redirects to a page titled "Gemini Notebook" (the frozen intro keeps its words; only markup was added). The five speech models and the three language models link to their Hugging Face pages (a model's name is a link on its first row only in the script-writing table); Supertonic uses the Hugging Face page because its GitHub repository is now archived; the Pocket TTS table row links to the weights variant this repository used, and the Pocket TTS mention in the Pocket section links to Kyutai's repository. "Hexagon Tensor Processor, HTP" links to Qualcomm's AI Engine Direct SDK page, and `NOTES.md` links LiteRT-LM and ONNX Runtime's QNN execution provider (they were only in the notes section, which Moritz removed from the page, so they are no longer on the page). The generators (`build-table.py`, `build-llm-table.py`) hold the model URLs; the browser suite pins the exact set.

**Editing keeps links.** The inline editor used to flatten a paragraph to plain text, which would have silently dropped a link when you rewrote that paragraph. Edited paragraphs are now stored as text with `[label](https://…)` for each link and rebuilt as real anchors (DOM nodes, http(s) only, never `innerHTML`), including in `Save HTML copy`. You can add a link by typing `[label](https://…)`. Other schemes and typed tags stay plain text. The browser suite checks the round trip, a typed link, `javascript:` staying text, and the export.

4. **Where I ended up:** the full-system flow as **device swimlanes** (Moritz's request): one lane per device (Computer, Phone CPU, Phone GPU, Phone NPU), one column per step in the order it happens, so the figure shows what runs where. Eleven steps, generated by `evidence/build-system-flow.py` (fixed-pixel gap columns and lane rows, so the SVG connectors are exact). Computer: adapt the ONNX graphs, compile HTP contexts, once. Phone CPU: add sources, review & edit, split into chunks, join audio, play/export. Phone GPU: Gemma writes the script. Phone NPU: Supertonic predicts + encodes, then generates the voice. **Review & edit is an optional chat with Gemma** (Moritz's correction; the old figure had it as a plain human step): you chat on the CPU, Gemma revises the script on the GPU, and the two-way arrow between them is an optional loop. "Group sentences" became "Split into chunks / Sized for the voice model". A dotted line from the compile step lands on a dashed box around the two NPU steps ("Supertonic 3, prepared once and copied to the phone"). There is no caption under the figure (Moritz removed it; a screen-reader description remains). Below 1040px the same steps become a single-column list, each with its device chip and a device-coloured left rail. The lane tags describe the selected neural routes, not every operation. `evidence/system-flow-spec.md` is the earlier (superseded) ten-node spec; its source proofs still stand.
5. **Pocket TTS on my phone, then "So what went wrong?":** the exact historical Pocket TTS clips, working one first (labelled "The one that works" and "The one that doesn't") (fixed-cache derivative, 4.48 s), then the broken one (original dynamic graph, 10.72 s). No audio was generated, trimmed, normalized or re-encoded. Then a plain gist (the model expects a NaN marker as its first input and swaps in its learned start vector; our phone code freed that buffer too early so it got zeros; it never found the end and kept talking until we cut it off; the voice went wrong because every sound is built on that wrong start) and one chart of the stop score over seconds of speech, both lines from the same controlled phone window. The code excerpt, the cause paragraph, the fix section and the takeaway were removed on request; their content survives in the technical notes and `evidence/` (`source-audit.md`, `phone-bos-check/`).
6. **Close** (after the demo): "If you wanna take a look, here it is" linking the repository (public since Moritz made it so). There is deliberately no "what is left" section.

Review vetoes recorded: RTFs only within comparable rows and as plain values; "sounds good" only for a row's own exact reviewed output; a package size is not measured memory; LLM rates stay separate from TTS RTF; flow tags describe the selected neural routes; the table's Pocket samples differ from the Pocket clips shown later.

## What is and is not established

**Observed on the phone** (`evidence/phone-bos-check/`, one CPU-only window, Pi-scheduled, 8 planned runs, no retries; rebuilt retained source, NDK 27, same ORT 1.27.1): the instrumented build printed 32 zero words before `Run()` with the original lifetime (2 of 2) and 32 NaN words with the buffer kept alive (2 of 2). The unmodified original's first run reproduced the retained 10.72 s failure recording byte for byte (and both dump runs did too). A second unmodified run gave a different wrong answer (first stop score -4.37, no stop), so the failure is nondeterministic. The four kept-alive runs stopped at frame 53 with identical 4.48 s audio (correlation 0.999996 with the accepted fixed-cache recording; no new listening verdict).

**Reproduced on a host:** with the same text, voice cache and noise, an all-zero first input matches the retained Android stop scores over 134 frames (max difference 0.074, mean 0.006) with no stop; the correct NaN input differs by up to 16.4 and stops at 53. None of 62 prefix/suffix partly zeroed inputs matched. Measured against the correct run's size, the zero-input internal state is off by 1.05 at the first frame (median 1.21 over 56 frames) and the frame itself by 0.76 (median 1.36): the difference is already large at the first step rather than building up slowly, so the page no longer says it "compounds". The stop score and the next frame are both read from that state in the model's source (`c=out_norm(x)[:,-1]; return (c, out_eos(c))`), and each frame is fed back as the next input in the runner loop. Pi independently reran the replay.

**Confirmed in source:** the old runner wraps a NaN buffer in a non-owning tensor and frees it before `Run()`; a host AddressSanitizer test using ONNX Runtime's real tensor API shows the dangling read (`evidence/source-audit.md`).

**Not shown (kept in the page notes, not in the way of the explanation):** the old phone executable (`a11685f5...`) is not retained, so nothing is bound to it; the exact original `flow_lm_main` graph is missing and a same-size reconstruction was used (it reproduced the failing recording exactly); the dump build may perturb allocation and the unmodified build's start values were never printed; there is no explanation for why this allocator returned zeros; no replay or phone output has been listened to. The invalid-Bria/zero-encoder failure is a different cause.

## Editing the copy

`Edit text` makes the outlined paragraphs and headings editable as **plain text**. Edits persist in this browser's local storage so a reload keeps them. `Save HTML copy` downloads `phone-podcast-edited.html`, built from the original page source rather than the live DOM, so it carries your text but no editor state. It adds a `<base>` pointing at the original folder, so the saved copy still finds `style.css`, `article.js` and the WAVs if you move it. Nothing writes into the repository; to keep a revision, copy that file in yourself. Escape leaves edit mode; Ctrl/Cmd+S saves while editing.

Only paragraphs you change are stored or exported, so untouched text keeps its inline formatting; a paragraph you edit becomes plain text. The opening (title, intro, question) is Moritz's approved wording.

## Browser checks

```sh
PW="$HOME/.pi/agent/skills/chrome-browser/scripts/pw"
"$PW" -s=qoralo-story open http://127.0.0.1:8766/docs/qoralo-blog/
"$PW" -s=qoralo-story run-code "$(python3 -c 'from pathlib import Path; print(Path("docs/qoralo-blog/browser-checks.js").read_text())')"
"$PW" -s=qoralo-story close
```

Covers the chart against the phone raw results (points and seconds axis), a main text free of meaningless numbers, five widths of chart/tick/annotation geometry, receipts that match `NOTES.md` in both directions, and that every evidence link in it resolves (run counts, limits, drift numbers), wording guards (no invented allocator explanation), reduced motion, muted decoding of both WAVs with exclusive playback, inline editing with local restore, an exported copy reopened from disk with a working chart, print, and script-failure fallback. Browser playback is not a human listening verdict.

Reproduce the replay (about 3 s, host CPU, needs the retained local model files):

```sh
experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/export-venv/bin/python docs/qoralo-blog/evidence/bos-zero-replay.py
python3 docs/qoralo-blog/evidence/build-chart.py
```

`article.js` is local only: no libraries, fonts, analytics or remote requests. Nothing autoplays.

Unpublished draft. The repository is public (Moritz's decision), but the article is not published, deployed or linked from a homepage, and no app release is announced. Moritz is still editing the text.
