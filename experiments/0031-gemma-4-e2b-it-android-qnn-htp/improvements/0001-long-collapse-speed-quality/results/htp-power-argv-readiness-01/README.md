# Exact argv correction: explicit DMA_BUF only

The only controller-source change from `578b5c95` removes **`--shared_buffer`**. Explicit **`--io_tensor_mem_handle_type dma_buf`** remains. The native argv now has **19 fields**, and both Python `/proc` validation and the shell NUL/byte-count guard derive from the same helper.

The original Android parse failure and zero graph executions remain preserved separately. A bounded host-parser fixture confirms the former 20-field combination is rejected as mutually exclusive. The corrected 19-field arguments pass that check and reach an intentionally nonexistent backend (exit 9); no backend, context, model or phone is executed in that parser fixture. This is not a second Android attempt or an assumption that host and Android binaries are identical.

The same immutable stage **`51053482d9d0d198b43343830503d8c1c3d2ee3337c4ccb598e792248dffb993`**, context, synthetic inputs, three cases, 90-second native limit, AS12 readback and evidence limits remain unchanged. The prior physical readback established **8 MiB FSIZE**, retained as an observation rather than guessed shell units. Each future attempt records its own readback.

Pi separately authorized one corrected three-graph window once fresh lease/USB/current `bf53c566…` / `f1543993…` identity and job/playback/resource checks admit. No other phone work is assigned. There is no extra graph, full-model/reference run, app restoration, retry loop or additional user-approval request. Raw pull, actual postflight, independent cleanup and release precede analysis.
