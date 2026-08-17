# Android inference paths

We will investigate all four paths below. The order reflects the current experiment plan, not a final architecture decision.

## 1. ExecuTorch — first Android attempt

PyTorch-native mobile runtime producing `.pte` models.

Why first:

- VibeVoice is implemented in PyTorch.
- General support for transformers, diffusion, and audio models.
- Android Kotlin/C++ APIs.
- CPU via XNNPACK/KleidiAI, Vulkan GPU, and Qualcomm backends.
- Components can be exported and validated independently.

Open questions:

- whether `torch.export` captures every VibeVoice component;
- unsupported/custom operators;
- dynamic shape and KV-cache handling;
- numerical stability of the diffusion and decoder paths;
- which backend works correctly on the Adreno 740.

## 2. LiteRT / LiteRT-LM

Google's current on-device runtime stack. Gemma 4 uses optimized pre-built LiteRT-LM artifacts.

Why it is relevant:

- Android CPU, GPU, and NPU paths;
- INT8/INT4 conversion and mobile-oriented operators;
- supported Qwen2/2.5 text architectures;
- custom LiteRT Torch building blocks and examples for LLMs, diffusion, and ASR.

Why Gemma's path is not directly reusable:

LiteRT-LM implements the conventional causal-language-model contract: token input, KV cache, next-token output, and updated state. VibeVoice is a composite speech system containing a modified Qwen-derived backbone, diffusion head, acoustic decoder, semantic tokenizer, speaker conditioning, and a custom generation controller.

The generic Hugging Face exporter recognizes standard architectures such as `Gemma4ForCausalLM` and `Qwen2ForCausalLM`. VibeVoice exposes `VibeVoiceForConditionalGeneration`, so there is no one-command conversion to a working `.litertlm` podcast model.

A viable LiteRT experiment may split the system:

- extracted text backbone under LiteRT-LM or a custom LiteRT graph;
- diffusion and tokenizer/decoder components under base LiteRT;
- native C++ or Kotlin generation orchestration.

## 3. ONNX Runtime Mobile

General Android runtime with mature graph inspection and CPU execution.

Why test it:

- straightforward component-level ONNX exports;
- broad operator coverage;
- useful CPU correctness baseline;
- FP16 and INT8 support;
- optional Qualcomm QNN execution provider.

Risks:

- dynamic autoregressive export and KV-cache plumbing;
- custom VibeVoice operations;
- graph fragmentation and memory copies;
- more complex Android QNN packaging;
- Android 16 KB native-library alignment requirements.

## 4. Qualcomm QNN / AI Engine Direct

Direct Snapdragon Hexagon/HTP path targeting the Galaxy S23 Ultra's SM8550.

Why test it:

- potential best performance and energy efficiency;
- native INT8/INT4 acceleration;
- avoids some generic runtime overhead.

Why last:

- proprietary, SoC-specific SDK and compilation;
- strict operator, shape, and quantization constraints;
- difficult debugging and graph partitioning;
- poor environment for establishing initial correctness.

QNN optimization begins only after ExecuTorch, LiteRT, or ONNX produces a correct component fixture.

## Not selected as primary paths

- **MLC-LLM:** useful for a standard text backbone, not the complete diffusion/audio system.
- **llama.cpp:** same limitation; it does not provide the VibeVoice speech pipeline.
- **Full PyTorch/Termux:** useful only as a crude proof, with excessive packaging and runtime overhead for a real Android application.
