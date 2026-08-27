# Physical QNN/HTP viability attempt 01

## Outcome

The authorized Samsung SM-S918B / SM8550 accepted the exact hash-bound Qwen3.5-2B PTE, Android runner, canonical short token IDs, ExecuTorch QNN backend, and QAIRT 2.49 HTP v73 libraries. Local and remote hashes matched.

Physical provider initialization succeeded far enough to establish a narrow but real provider/context-load result. The raw QNN log identifies `kHtpBackend` four times, reports DSP architecture 73 for all four graphs, maps memory through FastRPC, successfully creates all four contexts from their binaries, and retrieves all four QNN graphs with status `0x0`.

The attempt then stopped before method execution. ExecuTorch could not find the three `llama::fallback.out` kernels used only as non-compute graph-sharding boundaries. Method loading failed with `There are 3 instructions don't have corresponding operator registered.` The runner exited 1. No graph execution, ETDump, metrics, generated token, or output file exists.

No retry was attempted. The scoped runner process and `/data/local/tmp/vibevoice-0032-qwen35-qnn-viability` were both verified absent; Pi independently reverified cleanup and lock release.

## Claim boundary

This evidence proves physical QNN/HTP-v73 provider initialization, FastRPC memory mapping, and exact serialized-context loading/retrieval on the authorized phone. It does **not** prove physical model inference, generated output, output sanity, or performance. It is eligible only for a page-level blocker/progress update and not for the benchmark registry.

The complete raw first-attempt evidence is retained under `raw/`, including the 126,807-byte QNN provider log, exact local/remote hashes, device identity, operating-condition snapshots, pull failures for the correctly absent outputs, and verified cleanup state.
