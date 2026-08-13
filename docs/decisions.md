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
