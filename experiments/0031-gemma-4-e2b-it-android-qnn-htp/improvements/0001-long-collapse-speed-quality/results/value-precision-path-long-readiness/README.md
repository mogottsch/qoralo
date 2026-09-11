# Precision-path exact-long readiness

Host-only preparation following this candidate's actual short compatibility
success (`df07102`). No new ADB or long inference occurred here.

Fresh private stage: `.local/frozen-stages/value-path-long-20260911T125353Z-01`.
External manifest SHA-256:
`373ca1b67b3ce65920127eede27df84b2832a783aee14d934d328835bc9f0996`.
It contains18 independent read-only payloads,4,003,803,601 bytes, with the same
context `27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd`.
All large model, tokenizer, LUT and runtime binaries remain private.

The unchanged exact-long script requests one fresh-dialog query with the frozen
1929-token/single-BOS input and max2048 output ceiling;3977 tokens fit CL4096.
There is no short request, warmup, prefix reuse, sampler change, truncation or
output repair. The stage copied only bound bytes from the new short stage, then
was independently reverified. Saved child-exit receipt is0. Host preparation used
1GiB RAM/no swap/1CPU/nice15 and a240-second deadline; no neural model was loaded.

`prepare_value_precision_long_stage.py` changes six fixed identity/provenance
bindings in the preserved long preparer. `phone_value_precision_long.py` changes
eight scoped bindings over the new short controller and two exact shell argv
literals. Inverse tests reconstruct the respective original sources. The new
candidate's actual short result is hash-pinned as the prerequisite; no previous
candidate's GateA can satisfy it.

All200 host tests passed, including exact-long fake-transport timeout, full lock,
identity-checked signals, raw retention and cleanup. Direct-nohup launch,
1800-second process watchdog, noninherited lock, no-retry/one-use-slot policy and
unknown-identity retention are unchanged. PID signalling remains non-atomic.
The CLI is plan-only without explicit execution and an actual Pi-granted slot.

Compilation, metadata and this stage are not long-output, numerical-fidelity,
root-cause or speed evidence. The accepted campaign and previous negative remain
unchanged. Pi coordinates the separate exact-long slot around Ben's TTS work.
