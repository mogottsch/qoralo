# Decision log

## 2026-08-08 — Repository scope

This repository contains only VibeVoice runtime and Android feasibility work. The broader Podleaf product design, Gemma 4 integration, source handling, and application architecture belong elsewhere.

## 2026-08-08 — Reference before conversion

Start by producing one fixed approximately 15-second two-speaker VibeVoice 1.5B output with the official local PyTorch implementation. All Android engines use this run's locked inputs and outputs as their comparison fixture.

## 2026-08-08 — Runtime investigation order

Investigate:

1. ExecuTorch first;
2. LiteRT / LiteRT-LM;
3. ONNX Runtime Mobile;
4. Qualcomm QNN / AI Engine Direct.

ExecuTorch comes first because it is PyTorch-native and supports general transformer, diffusion, audio, Android, Vulkan, and Qualcomm workflows. QNN comes last because direct hardware optimization should follow a correct portable implementation.

## 2026-08-08 — Model order

Test VibeVoice TTS 1.5B first because it is the smallest released model with joint multi-speaker podcast behavior. Test VibeVoice Realtime 0.5B afterward as a smaller single-speaker deployment comparison. Exclude VibeVoice Large/7B from the phone spike.

## 2026-08-08 — No premature architecture

Do not define a product or deployment architecture before measuring export compatibility, numerical correctness, memory use, and runtime.

## 2026-08-09 — Candidate evidence published; user decision required

Publish the protocol-v2 host listening samples, the correctly gated negative VibeVoice 1.5B Android result, and the Realtime 0.5B feasibility estimates as distinct evidence classes. Preserve the historical 39/39 rejection; the locked-prefix supplement only clarifies why the old two-chunk near-silence was not proof of waveform divergence.

At publication time, subjective ratings remained `pending_user_review`. Start no conversion or follow-up until the user explicitly chooses one of the five actions in [`candidate-decision-report.md`](candidate-decision-report.md).

## 2026-08-09 — Listening review recorded

The user clearly preferred Candidate C / Kokoro 82M. Candidate A / VibeVoice Realtime and Candidate B / Pocket TTS were hard to distinguish and are effectively tied for second. Record this as subjective listening evidence only; it is not an Android-feasibility result.

## 2026-08-13 — Conversation state reconciled

The latest conversation adds no implementation authorization beyond the recorded listening preference. The 18-task candidate campaign is complete, no candidate follow-up has started, and the repository remains stopped at the explicit next-step gate in [`candidate-decision-report.md`](candidate-decision-report.md). The listening-preferred path is Kokoro turn-by-turn mobile composition, but it has not yet been explicitly selected for implementation.

## 2026-08-13 — Expand the listening bake-off before Android

Record the updated historical order as Kokoro first, Pocket TTS second, and VibeVoice Realtime third. Add official Supertonic 3, Inflect Nano v1, and Kitten TTS Mini 80M v0.8 host samples before selecting an Android candidate. Use stock voices only and do not start Android work.

## 2026-08-13 — Compare natural-duration outputs

Retire the 15-second gate and normalization from the active listening bake-off. Publish all six natural-duration outputs at their measured durations and native rates. Historical protocol-v2 derivations remain provenance only. Hide model identities initially; reveal one card or all cards only after explicit interaction.

## 2026-08-13 — Android optimization priorities

Continue with three measured follow-ups: exact Kokoro v1.0 INT8 export and quality validation; a bounded 1/2/4 CPU-thread sweep for Pocket, Kokoro, and Supertonic; and a narrow Qualcomm QNN/HTP component probe before any full accelerator conversion. Do not pursue naive sentence or clause splitting: the user rejects context-blind chunking because it degrades prosody and naturalness. Preserve full-context generation unless a future model-native contextual streaming mechanism is evaluated separately. QNN SDK or license acceptance remains a separate approval gate.

## 2026-08-13 — Experiment 0009 host quality gate and phone thread sweep

Retain the exact Kokoro v1.0 mixed S8S8 QDQ candidate as `awaiting_user_listening`: it is 46.0% smaller and passed the automated host checks, but it has no subjective-equivalence or Android-performance approval yet. For the measured phone thread sweep, retain observed best warm-median RTFs of Pocket two-thread `0.367`, Kokoro four-thread `0.753`, and Supertonic two-thread `0.362`. Treat changes below 5–10% as inconclusive and larger changes as directional because this is one rotated campaign and the user authorized a mid-campaign thermal-policy amendment. Future practical sweeps may run at Android thermal status NONE or LIGHT and should pause only at MODERATE or higher; record status without treating battery temperature as a throttling proxy.

## 2026-08-13 — Select experiment 0008 Android candidates

Retire VibeVoice Realtime 0.5B, Inflect Nano v1, and Kitten TTS Mini 80M v0.8 from active follow-up; they remain historical-only under immutable experiment 0007 evidence. Select Pocket TTS 100M, exact Kokoro v1.0, and Supertonic 3 for real-device measurement in that fixed order under experiment 0008.

Use pinned sherpa-onnx v1.13.5 Android CPU deployments with one canonical inference thread and app-specific external model storage. Preserve the experiment 0007 transcript byte-for-byte. Record requested and actual Pocket voices separately, prove Kokoro SID 3/`af_heart` and Supertonic M1 mapping, and block rather than guess. No Android result exists until the device campaign records it; host timing is not a substitute.

## 2026-08-13 — Publish the measured Android decision

Select the pinned Supertonic 3 INT8 SID 5/M1 English deployment as the measured technical default on the Galaxy S23 Ultra: one-thread warm median RTF is 0.370 with four valid WAVs and sampled peak PSS of 463,003,648 bytes. Classify it as `works`.

Classify Pocket as `works_with_limitations`: warm median RTF is 0.389 and four WAVs are valid, but the public package provides Bria rather than requested Alba (`voice_match=false`), its non-commercial workflow wording conflicts with its bundled CC BY 4.0 license, and no manual listening was performed. Classify exact Kokoro v1.0 SID 3/`af_heart` as `works_with_limitations`: canonical one-thread warm median RTF is 1.195; its separately triggered two-thread median is 0.963.

All canonical campaigns began thermally eligible in the fixed Pocket–Kokoro–Supertonic order. Preserve the earlier Pocket and Kokoro callback-bridge native crashes as disclosed harness failures. Keep experiment 0007 and VibeVoice Realtime, Inflect Nano, and Kitten TTS historical-only; do not present their host PyTorch evidence as Android deployment measurements.
