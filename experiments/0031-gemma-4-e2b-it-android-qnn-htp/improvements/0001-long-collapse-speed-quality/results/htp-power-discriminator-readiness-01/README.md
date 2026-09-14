# Tiny HTP Power edge and normalization/fusion discriminator

**Host-only preparation. No phone execution, full reference or LLM run is authorized by this packet.** Pi will schedule one physical window after Nik's priority work and stable USB.

## Three small authored graphs

All inputs are synthetic native UINT16 codes; no captured LLM input, learned weight, LUT, tokenizer or Genie runtime is included.

| Graph | Requested graph executions | Shape and purpose |
|---|---:|---|
| `power_edge` | 1 | Exact op6294 grids/dtypes/Power exponent and attributes, shape `[1,128,1]`; rows repeat codes 0, 1, 2 and 65535. |
| `normalization_chain` | 1 | Exact-shape `[1,128,1536]` square → mean(axis2) → epsilon-add → Power(−0.5) → multiply fragment; intermediates native/internal. |
| `normalization_exposed` | 1 | Same five operators and inputs, but squared/mean/denominator/inverse are also graph outputs. This is explicit instrumentation that can change fusion/materialization opportunities. |

The chain uses the actual layer-31 grids, scalar epsilon code 655 and exponent code 0. It is a normalization **fragment**, not the complete layer/model. No learned gamma is introduced. Actual DLC inspection confirms one/five/five operators, all requested scalar/operator attributes and all UF16 grids. Context inspection confirms backend 6 / SM8550 SoC 43, graph order, native flat-buffer I/O shapes and unchanged grids.

## Expected formulas without a guessed pole policy

`expected-formulas.json` freezes finite-control nearest-even results and contrasting literal-per-operator versus fused-RMS formulas. **Native integer outputs at a pole are deliberately unspecified.** No upper clamp, epsilon floor, NaN repair, CPU→HTP policy transfer or assumed fusion is encoded.

The exposed chain may inhibit, duplicate or alter backend optimizations. The unexposed chain is not proof of fusion either. A difference between them must be reported with this instrumentation boundary, not generalized from isolated Power to the complete model.

## Frozen bundle and limits

- Context: **167,936 bytes**, SHA-256 `6cd4e825a5a55430ced91b2238ab0c060ab60b7956f49dd84c248246087c0ee4`.
- Stage: **9 files / 26,698,768 bytes**, manifest **`51053482d9d0d198b43343830503d8c1c3d2ee3337c4ccb598e792248dffb993`**.
- Explicit Android `qnn-net-run` + `libQnnHtp.so` + V73 stub/skel/System libraries only; no CPU or Genie backend/runtime in the bundle.
- One input-list record per graph, `--num_inferences 1`, native input/output files and shared DMA buffers. Future raw logs must verify actual graph executions; prebuilt-binary behavior is not inferred solely from sample source.
- Expected raw tensor output: **1,180,672 bytes**.
- Process deadline **90 seconds**, **12 GiB virtual-address limit**, and actual same-PID pre-exec AS/file-limit readback. Each output file is limited to at most 16 MiB; a 16 MiB evidence-directory budget is polled by the watchdog, so polling overshoot is disclosed.

Each tiny graph received one finite **authored** host calibration sample solely to avoid QAIRT's forced float-fallback-without-data path. All actual encodings are supplied and verified; final tiny DLCs contain no float tensors. This is not calibration on model/user data. An inactive unsupported Sigmoid config flag was removed (there are no Sigmoid nodes).

## Lifecycle safety

`phone_htp_power_discriminator.py` preserves the existing full phone lease, one-use Pi slot, fresh APK/job/playback/RPC checks, raw-before-delete cleanup and the actual corrected postflight hook. Native identity checks bind PID, starttime, executable and the complete NUL-delimited `qnn-net-run` argv, including empty-argument rejection. These are sequential checks, not pidfd-atomic signals.

Fake-ADB tests exercise real lifecycle dispatch for success/native failure, partial pull, postflight failure and unknown native identity. The shell guard and syntax are tested independently. There are no app installs/restores/stops, broad kills or automatic retries.

## Preserved preparation failures

The first combined compile failed because all three converted graphs were named `fixture`; no physical execution occurred. Unique ONNX/DLC names resolved this. The first metadata helper was named `inspect.py`, shadowing Python's standard library; its service failure and partial metadata are retained. A fresh `verify_tiny_context.py` helper completed cleanly. The final host preparation service, including conversion and context compilation, completed in **4.611 seconds / 641 MiB / no swap** under 4 GiB RAM / 1 GiB swap / 2 CPU / 600 seconds.

Restricted SDK/runtime binaries and compiled context remain private and hash-bound. This packet publishes authored source, synthetic specifications, scoped metadata and receipts only.
