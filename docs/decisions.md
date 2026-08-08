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
