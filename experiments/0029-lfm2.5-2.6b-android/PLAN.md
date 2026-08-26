# 0029 continuation plan

1. Download the exact GGUF from the pinned URL in `README.md`; verify byte size and SHA-256 before use.
2. Clone llama.cpp and check out `5c0d18881e0e9794c96b2602736b758bac9d9388` (build 7446).
3. Recreate the bounded host smoke from `results/host-smoke/command.txt`; verify the 171-token short prompt, output limit, noninteractive mode, no double BOS, and raw output hash behavior.
4. Complete the experiment contract before phone use:
   - exact upstream/base revision and LFM Open License provenance;
   - GGUF quantization/conversion metadata;
   - embedded tokenizer and native chat-template bytes/hash;
   - rendered prompt and token-ID hashes for all tiers;
   - context-capacity proof for every prompt plus the 2,048-token ceiling;
   - exact Android binary and runtime options.
5. Rebuild `llama-completion` with NDK `28.1.13356709`, `arm64-v8a`, API 31, Release, static libraries, `GGML_NATIVE=OFF`, `GGML_OPENMP=OFF`, and `LLAMA_CURL=OFF`. The previous build was interrupted and produced no executable.
6. Add a persistence-first phone harness with the repository lock, exact SM-S918B/SM8550/ABI checks, storage gate, hash verification, scoped stage, timeout/output cap, memory/thermal capture, and verified cleanup.
7. Run one bounded Android CPU short smoke. Only after it passes should the fresh full 1+5+5+5 campaign run.
8. Commit owning evidence and send a structured handoff to the publisher. Do not edit the shared dashboard or experiment HTML from this experiment session.

Do not reuse either invalid `llama-cli` attempt. One entered automatic conversation and generated a 9.2 GiB runaway stdout before termination. `llama-completion` plus external timeout and file-size limits is the required bounded route.
