# Tiny HTP startup: generic DMA_BUF capability unavailable

The separately granted DMA-only attempt `htp-power-20260914T145546Z-02` passed argument parsing but stopped during initialization, native **9** / controller **1**:

> `Input output tensor memHandle type = 3. But backend does not support property =1104`

The SDK property definition identifies 1104 as `QNN_PROPERTY_MEMORY_SUPPORT_MEM_TYPE_DMA_BUF`. There were **zero graph executions/outputs**. This is a memory-registration capability mismatch, not a Power/fusion result, model failure or LLM/reference run.

All **52 ADB operations** were under the lease. Raw pull completed, all owned roles/root were verified absent, no signal operation occurred, actual postflight verified `bf53c566…c7721c` / `f1543993…f3b0a4`, and the phone was released before analysis. The actual pre-exec limits again show **AS12 GiB / FSIZE8 MiB**. Battery current-state extracts are labeled; full originals remain private and hash-bound.

The next single candidate is the SDK's legacy **`--shared_buffer` alone**, not a memory-mode sweep. Its expected HTP shared-buffer route is FastRPC/ION rather than generic DMA_BUF; actual runner admission, official help/tutorial and SDK shared-buffer code are bound in [htp-power-rpc-readiness-01](../htp-power-rpc-readiness-01/README.md). A fresh window is separately authorized; this consumed attempt is not relabeled or automatically retried.
