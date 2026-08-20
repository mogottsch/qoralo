# Current plan

## Goal

Find a text-to-speech model that can become the local voice of a future NotebookLM-like Android experience. It should sound pleasant and natural over sustained listening, with podcast-like delivery rather than merely intelligible speech.

A convincing two-speaker conversation would be useful, but it is not required. A strong narrator or persistent voices generated turn by turn can also meet the goal if the deployment runs well on a modern phone.

## Evidence-language convention

Keep four claims separate in every decision:

1. **Technical execution** — the declared model path completed on the stated runtime/device with the required provider proof.
2. **Structurally valid WAV** — the file decoded and met format, length, finiteness, silence, and clipping checks. This does not establish intelligibility, naturalness, or usability.
3. **Objective or descriptive comparison** — numerical/acoustic metrics passed or failed their named policy. This is not a listening verdict.
4. **Moritz listening verdict** — only explicit listening feedback can accept or reject the reviewed route/sample. “No audible difference” between A and B is a comparison observation, not acceptance of either sample, unless Moritz separately says it is usable.

A route-level verdict stays bound to its exact artifact and configuration. It must not be generalized to a model family without an explicit family-level decision. Unsupported or unreviewed subjective claims are recorded as **not reviewed / unknown**, never inferred from technical success.

## Current phase: preserve technical baselines, require exact-route listening evidence

The completed record now contains several technically executable Android routes, but technical completion has not closed the product-quality question:

| Route | Technical record | Moritz listening status |
|---|---|---|
| Supertonic 3 CPU reference and mixed hybrid in experiments [`0008`](../experiments/0008-sherpa-onnx-android-tts-benchmark/) / [`0010`](../experiments/0010-supertonic-qnn-htp-feasibility/) | CPU is the supported Android technical reference; hybrid was faster warm but failed its prospective numerical policy | Moritz accepted exact CPU SHA `7e83537630b3e354f7586b9887f7a8359d62e438c9addeea61d87d878b2a84ff` and hybrid SHA `9b0d488776b144c972e8be4e9434fac14ce3ceddfcfa5a10d137fca41b772668` as “Good.” His earlier no-audible-difference report remains comparison-only; the separate verdicts supply sample-level acceptance. |
| Supertonic official FP32 CPU/all-HTP in [`0011`](../experiments/0011-supertonic-official-fp32-phone-comparison/) | CPU and all-HTP routes executed; all-HTP was faster warm but failed its prospective numerical policy | CPU SHA `8db92db13567b86be503d204fe367f2052b54dbfc99c0f7bfc5b23d9fd431da7` accepted: “Good—even a bit more crisp than samples 1 and 2.” All-HTP SHA `47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c` accepted: “Same as sample 3”; this is perceptual comparison only, not numerical equivalence. |
| Pocket FP ONNX CPU in [`0012`](../experiments/0012-pocket-onnx-vs-executorch-android/) | Complete CPU route, warm median RTF `0.630`, structurally valid deterministic WAV | **Rejected for this exact route/sample.** Moritz blind-listened to SHA `40634981606f37c59a91c14d99cecb3ef4cc21b1391882e870940b0716857d22` and called the repetitive “takakakakakakakaka” output unusable. This does not reject Pocket as a family. |
| Kokoro exact-source-derived FP32 ONNX CPU in [`0013`](../experiments/0013-kokoro-onnx-vs-executorch-android/) | Complete fixed-contract CPU route, warm median RTF `0.9800`; separate acoustic policy passed while the retained strict waveform screen failed | Exact retained sample SHA `c046e8337b86ccf221ecd91db7dba90845f7c20b0ab1d8c248a36146c4eaecd3` accepted: “Good.” Sample-level only. |
| Pocket mixed QNN/CPU in [`0016`](../experiments/0016-pocket-onnx-qnn-hybrid-android/) | Physical HTP execution, but slower normalized RTF and changed EOS/output length | Exact hybrid SHA `6cd3a98fb821ad76b0c0ad55a20f910da7be9d3058e511ff807b4a4f694aa45f` rejected: “takataktaka.” This is route/sample-only and is not a Pocket-family rejection. |
| Kokoro QNN preparation in [`0017`](../experiments/0017-kokoro-onnx-qnn-htp-android/) | Full capability assignment only; host graph sequencing was kernel-OOM-killed before session finalization or inference | Not applicable: no QNN audio exists. |
| MOSS-TTS-Nano ONNX CPU in [`0018`](../experiments/0018-moss-tts-nano-onnx-android/) | Complete CPU route, warm median RTF `1.125`, large process-memory footprint, structurally valid retained WAV | Exact SHA `173850781b055e70a606fb561d93b70e6d8c6318db1b29b2324f83506c21ad6b` accepted: “Okay to good, but with a bit of a Chinese accent.” Sample-level acceptance with an accent caveat. |

Two older listening records remain deliberately narrow:

- experiment [`0007`](../experiments/0007-mobile-podcast-preview-bakeoff/) ranked the exact historical Kokoro, Pocket, and VibeVoice Realtime host previews in that order. No usability acceptance was recorded for any of them; Supertonic, Inflect, and Kitten were not reviewed.
- experiment [`0009`](../experiments/0009-android-tts-optimization/) passed a blind **relative INT8-vs-FP32 degradation gate** for Kokoro: four ties and one low-confidence preference per variant. That result found no systematic degradation; it did not establish absolute usability for either sample.

## Current decision

- Keep Supertonic CPU as the supported **technical** Android reference. Its exact experiment-0010 sample is also listening-accepted as “Good,” but broader long-form/product quality still needs corpus evidence.
- Keep experiment 0010's hybrid and experiment 0011's all-HTP route as bounded technical research evidence. Their exact samples have positive listening verdicts, but both HTP routes failed their prospective numerical policies.
- Reject the exact experiment-0012 Pocket FP ONNX CPU and experiment-0016 Pocket hybrid route/samples for listening use. Do not generalize either rejection to Pocket TTS as a family.
- Record Kokoro 0013 as sample-level accepted “Good.” Record MOSS 0018 as sample-level accepted “Okay to good,” with Moritz's Chinese-accent caveat.
- Never promote a structurally valid WAV, an acoustic-policy pass, or a provider/latency result into a quality claim.

Active implementation work remains governed by its experiment-specific plan and is not summarized here as completed evidence. Before any technically viable route becomes the product choice, retain its exact artifact hash and obtain an explicit Moritz listening verdict on that route/sample. A comparative “no audible difference” answer is insufficient unless it also includes an explicit usability decision.

Completed experiment details and chronology are in [`history.md`](history.md) and its [HTML mirror](history.html).
