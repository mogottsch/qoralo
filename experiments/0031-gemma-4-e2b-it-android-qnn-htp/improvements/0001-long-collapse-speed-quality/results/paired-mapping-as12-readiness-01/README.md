# One 12 GiB address-space control: prepared, not executed

Pi authorized preparing a single narrowly controlled follow-up to the same-8-GiB shadow-stack abort. **Only RLIMIT_AS changes:**

- Before: **8,589,934,592 bytes** (`ulimit -v 8388608`).
- Control: **12,884,901,888 bytes** (`ulimit -v 12582912`).
- Delta: **4,294,967,296 bytes of virtual-address allowance**, not a physical-RAM-budget increase.

The observer binary, model, DLC/context, LUTs, input, config/script cap 1, 300-second process limit, capture limits, headroom/RPC/job/playback checks, full phone lease and raw-first cleanup are unchanged. No null-mapping fix or other runtime code change is included. The frozen stage remains **`807980c106a59584752ce52abece89dd50062c827505fb2136ae0c950ca7206e`**, library `ee2b10d8…ba099`.

## Evidence and limitations

The 8 GiB run mapped both LUTs correctly, then reached VmSize **8,585,527,296** against actual AS **8,589,934,592**, leaving **4,407,296 bytes**, before `failed to allocate shadow stack: Out of memory`. This is sufficient evidence for an AS-only control, not a guarantee of completion or proof of physical-RAM exhaustion.

That run also retained QNN context/shared-weight mapping/connection errors. Their relationship to the abort remains unresolved and must remain visible in the follow-up. Successful mappings in that run do not retrodiagnose the older `std::bad_alloc` or exit-139 outcomes, and no result here resolves QNN generation fidelity.

## Frozen control and readback

`phone_mapping_as12_capture.py` pins and reconstructs the corrected mapping controller. Count-checked, invertible replacements change the one model-entry AS line, its two metadata declarations and fresh owned run-root names. With the same synthetic root, **all other materialized shell scripts are byte-identical**. There is no arbitrary AS knob or sweep.

The existing native observers read actual soft/hard `RLIMIT_AS`. Both must report **12,884,901,888** before that setting is claimed as observed. Missing readback remains unknown; an 8 GiB or mixed readback does not pass. Preparation alone supplies no runtime readback. Caller errno and original model/observer behavior remain unchanged.

## Scheduling boundary

This is **host-only preparation**, not an execution grant. The single phone attempt is queued **after Janek's entire priority app-validation window**, not between its probe and genuine phases. Wait for Pi's actual resource handoff rather than seeking another user approval. Then use a fresh one-use slot, current full APK identities, actual job/playback checks and the full `phone.lock` lifecycle. No app changes, restores, stops, second attempt or automatic retry.

Raw capture must be pulled before independent cleanup and prompt phone release. The still-unused single host reference may run only after a **complete** validated 16-chunk input/final-logit capture, strict observer/AS/input binding and lease release. The eight partial first-chunk inputs from the failed baseline are not sufficient. Host RAM/swap/CPU/time/output/trace caps remain unchanged.
