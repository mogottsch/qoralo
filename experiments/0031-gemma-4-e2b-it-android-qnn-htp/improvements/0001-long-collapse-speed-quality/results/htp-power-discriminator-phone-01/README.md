# Tiny HTP window: argument validation stopped before graph execution

The single granted `htp-power-20260914T144241Z-01` attempt exited native/controller **1**. The runner rejected the simultaneous flags:

> `--shared_buffer and --io_tensor_mem_handle_type are mutually exclusive.`

There were **zero observed graph executions and no graph output files**. This is a command-line contract failure, not an HTP Power/fusion result or LLM/reference run. No automatic retry occurred.

The actual same-PID pre-exec readback records **AS soft/hard 12,884,901,888 bytes** and **file-size soft/hard 8,388,608 bytes (8 MiB)**. Do not infer the file limit from assumed shell block units.

All **52 ADB commands** were under the full lease. Raw pull completed; all owned roles/root were verified absent; no signal operation occurred. Actual pre/post APK checks verified `bf53c566…c7721c` / `f1543993…f3b0a4`. The phone was released before saved analysis. Battery output is a labeled current-state extract; full originals remain private and hash-bound.

The scoped correction is to remove only the legacy `--shared_buffer` flag while retaining explicit `--io_tensor_mem_handle_type dma_buf`. Contexts, inputs, cases and limits remain unchanged. See [the separately frozen argv correction](../htp-power-argv-readiness-01/README.md). A new explicitly granted window is separate from this consumed attempt.
