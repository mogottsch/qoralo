# Single HTP/RPC-compatible invocation candidate

The only controller change replaces the generic **`--io_tensor_mem_handle_type dma_buf`** pair with legacy **`--shared_buffer` alone**. The argv has **18 fields**; Python and shell PID/executable/NUL guards derive from that single helper. Contexts, inputs, three cases and all limits are unchanged.

## Evidence for this choice

This is not based on Genie source alone:

- The actual Android runner's saved help describes `--shared_buffer` as shared graph-I/O buffers between application and device/coprocessor.
- The same SDK's **actual host qnn-net-run with the real HTP backend** accepts this single flag and passes initialization to deliberately missing input lists, without the DMA_BUF capability error. No context or graph is executed by this host admission check.
- The official HTP shared-buffer tutorial documents the FastRPC `rpcmem_alloc` / file-descriptor / `QNN_MEM_TYPE_ION` path.
- The SDK SharedBuffer sample's I/O code explicitly maps shared-buffer mode through `rpcmem_to_fd` and `memRegister(QNN_MEM_TYPE_ION)`.

The sample is supporting contract evidence, **not bit-for-bit source attestation for the stripped runner**. The expected registration path is HTP/FastRPC/ION; actual Android registration and graph execution remain unobserved until the separately granted window. No CPU result is transferred to HTP numerical policy.

## Boundaries

Use the same stage `51053482…b993`, three authored graphs once each, native raw input/output, **90 seconds / AS12 GiB**, file/evidence caps and actual **8 MiB FSIZE** readback. Fresh phone lease, USB, current `bf53c566…` / `f1543993…` APK identity, job/playback/resource checks, raw-first collection, actual postflight and independent cleanup remain required.

Pi authorized one fresh corrected window after this source-bound readiness passes. No extra case, full model, fallback, mode sweep, automatic retry or new user-approval loop is implied. Preserve both earlier zero-execution startup failures unchanged and report actual graph counts/codes before any pole or fusion claim.
