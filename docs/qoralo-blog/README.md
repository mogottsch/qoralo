# Building a NotebookLM-like podcast on my phone

Open `index.html`, or serve the repository root:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
# http://127.0.0.1:8766/docs/qoralo-blog/
```

A short technical article about a source-to-podcast workflow with local phone inference. Qoralo is the experiment's app name, not the article's subject. The prototype generates a script and narrates it in one voice; this is not NotebookLM's conversational format or an established quality match.

## What the page contains

1. **Phone placement:** Gemma on GPU, Supertonic on NPU/HTP, CPU orchestration. The route buttons show one illustrative signal; they are not timing.
2. **The first Android port:** the exact historical Pocket TTS Android CPU recordings, working clip first (fixed-cache derivative, 4.48 s), then the broken one (original dynamic graph, 10.72 s). No audio was generated, trimmed, normalized or re-encoded for the page.
3. **Why it went wrong:** a four-sentence gist (the model expects a NaN marker as its first input and swaps in its learned start vector; our phone code freed that buffer too early so it got zeros; it never found the end and kept talking until we cut it off; the voice went wrong too because every sound is built on that wrong start). One chart of the stop score over seconds of speech, both lines from the same controlled phone window: the original code never reaches the stop line, the same code with the buffer kept alive stops at 4.5 s. Then the five-line source excerpt.
4. **The fix we applied:** the NPU version has the start vector built in, so there is no NaN marker to lose; one sentence and one takeaway.

Moritz asked for no meaningless values in the main text: no frame cap, raw scores, thresholds as numbers or RTF-style detail there. The step-by-step explanation, the NaN/zero rows, the toggles, the scrubber and the phone-observation paragraph were removed on request. Their content survives only in the notes at the bottom of the page and in `evidence/`. The chart is baked into the HTML (works without JavaScript) by `evidence/build-chart.py` from `evidence/phone-bos-check/raw/`.

## Agenda (agreed with Moritz) and status

1. The question: title, intro and question, **approved and frozen** (the browser suite fails if their text changes).
2. **Demo video** directly after the question. Slot only: `media/demo.mp4` does not exist yet, so the page shows an explicit "Demo video goes here" notice instead of a broken player. No synthetic footage.
3. What we tried (models and backends), and 4. the numbers (a small benchmark table, with a small RTF note): **to do**, table being built by Thomas from the benchmark registry.
5. Where it ends up: the full-system flow diagram (sources to audio, each neural step tagged GPU/NPU/CPU, computer-side preparation visibly separate): **to do**, being built by nik.
6. The funniest failure: the Pocket TTS NaN bug (done, currently placed second; it moves after the system section).
7. Close: "If you wanna take a look, here it is" linking the repository, which is private, so the link will not open for others until that changes. There is deliberately no "what is left" section.

Pi reviews the table and diagram before integration. Review vetoes recorded: RTFs only within named comparable groups and shown as plain values; "sounds good" only for a row's own exact reviewed output; a package size is not measured memory; LLM rates stay separate from TTS RTF; flow tags describe the selected neural routes, not every operation.

## What is and is not established

**Observed on the phone** (`evidence/phone-bos-check/`, one CPU-only window, Pi-scheduled, 8 planned runs, no retries; rebuilt retained source, NDK 27, same ORT 1.27.1): the instrumented build printed 32 zero words before `Run()` with the original lifetime (2 of 2) and 32 NaN words with the buffer kept alive (2 of 2). The unmodified original's first run reproduced the retained 10.72 s failure recording byte for byte (and both dump runs did too). A second unmodified run gave a different wrong answer (first stop score -4.37, no stop), so the failure is nondeterministic. The four kept-alive runs stopped at frame 53 with identical 4.48 s audio (correlation 0.999996 with the accepted fixed-cache recording; no new listening verdict).

**Reproduced on a host:** with the same text, voice cache and noise, an all-zero first input matches the retained Android stop scores over 134 frames (max difference 0.074, mean 0.006) with no stop; the correct NaN input differs by up to 16.4 and stops at 53. None of 62 prefix/suffix partly zeroed inputs matched. Measured against the correct run's size, the zero-input internal state is off by 1.05 at the first frame (median 1.21 over 56 frames) and the frame itself by 0.76 (median 1.36): the difference is already large at the first step rather than building up slowly, so the page no longer says it "compounds". The stop score and the next frame are both read from that state in the model's source (`c=out_norm(x)[:,-1]; return (c, out_eos(c))`), and each frame is fed back as the next input in the runner loop. Pi independently reran the replay.

**Confirmed in source:** the old runner wraps a NaN buffer in a non-owning tensor and frees it before `Run()`; a host AddressSanitizer test using ONNX Runtime's real tensor API shows the dangling read (`evidence/source-audit.md`).

**Not shown (kept in the page notes, not in the way of the explanation):** the old phone executable (`a11685f5...`) is not retained, so nothing is bound to it; the exact original `flow_lm_main` graph is missing and a same-size reconstruction was used (it reproduced the failing recording exactly); the dump build may perturb allocation and the unmodified build's start values were never printed; there is no explanation for why this allocator returned zeros; no replay or phone output has been listened to. The invalid-Bria/zero-encoder failure is a different cause.

## Editing the copy

`Edit text` makes the outlined paragraphs and headings editable as **plain text**. Edits persist in this browser's local storage so a reload keeps them. `Save HTML copy` downloads `phone-podcast-edited.html`, built from the original page source rather than the live DOM, so it carries your text but no editor state. It adds a `<base>` pointing at the original folder, so the saved copy still finds `style.css`, `article.js` and the WAVs if you move it. Nothing writes into the repository; to keep a revision, copy that file in yourself. Escape leaves edit mode; Ctrl/Cmd+S saves while editing.

Only paragraphs you change are stored or exported, so untouched text keeps its inline formatting; a paragraph you edit becomes plain text. The intro is placeholder wording, not Moritz's voice. Replace it.

## Browser checks

```sh
PW="$HOME/.pi/agent/skills/chrome-browser/scripts/pw"
"$PW" -s=qoralo-story open http://127.0.0.1:8766/docs/qoralo-blog/
"$PW" -s=qoralo-story run-code "$(python3 -c 'from pathlib import Path; print(Path("docs/qoralo-blog/browser-checks.js").read_text())')"
"$PW" -s=qoralo-story close
```

Covers the chart against the phone raw results (points and seconds axis), a main text free of meaningless numbers, five widths of chart/tick/annotation geometry, receipts that match the notes in both directions (run counts, limits, drift numbers), wording guards (no invented allocator explanation), reduced motion, muted decoding of both WAVs with exclusive playback, inline editing with local restore, an exported copy reopened from disk with a working chart, print, and script-failure fallback. Browser playback is not a human listening verdict.

Reproduce the replay (about 3 s, host CPU, needs the retained local model files):

```sh
experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/export-venv/bin/python docs/qoralo-blog/evidence/bos-zero-replay.py
python3 docs/qoralo-blog/evidence/build-chart.py
```

`article.js` is local only: no libraries, fonts, analytics or remote requests. Nothing autoplays.

Private draft. No public article or app release is announced.
