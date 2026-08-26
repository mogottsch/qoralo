# 0029 continuation plan

## Completed on the reconstructed workstation

1. Downloaded the exact official GGUF from the pinned URL and verified 1,674,455,040 bytes and SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`.
2. Recreated clean llama.cpp revision `5c0d18881e0e9794c96b2602736b758bac9d9388` (build 7446).
3. Reproduced the bounded host smoke exactly: 171 input tokens, 323 output bytes, output SHA-256 `3f703023ba052195c3f074178b1979bed040bfff867fbc917e5de77994490f52`, exit zero.
4. Completed the route contract:
   - GGUF-embedded upstream revision `ab00687315bc1298e9d54e9c4b611dde9867ccc2` and exact LFM Open License provenance;
   - official Q4_K_M tensor inventory plus explicit null reasons for unpublished converter revision and calibration provenance;
   - upstream tokenizer file hashes and byte-identical embedded/native chat template;
   - rendered prompt and int32le token-ID hashes for all tiers;
   - 171/600/1922 input-token counts and 8,192-token route-capacity proof with the 2,048-token ceiling;
   - shared Android LLM protocol v2 loaded-route semantics and the boundary between the one-process smoke and a future canonical campaign.
5. Built and validated stripped Android `llama-completion` with NDK `28.1.13356709`, `arm64-v8a`, API 31, Release, static libraries, `c++_static`, `GGML_NATIVE=OFF`, `GGML_OPENMP=OFF`, and `LLAMA_CURL=OFF`:
   - 5,074,184 bytes;
   - SHA-256 `88a91aba5511a712f45aca21c566275681de30e2161f10bb99f9ac54f45b979e`;
   - AArch64 PIE; only `libm.so`, `libdl.so`, and `libc.so` are dynamically required.
6. Added a bounded phone-smoke harness with fresh coordination and phone-lock gates, exact device/storage/hash checks, scoped staging, direct-to-host raw output capture, nullable optional telemetry, and verified cleanup.
7. Preserved a bounded passive cooldown observation and a first pre-inference ADB transport failure separately. The failed attempt stopped before remote hash verification completed, was never counted, and ended with verified scoped cleanup.
8. Ran one fresh approved Android CPU short smoke:
   - exact 171-token prompt; 64 generated tokens; exit zero;
   - output SHA-256 `75f52326f67379c63d86b49e4520a074dbbd074329fc0d8d53693340ffc0a0c5`;
   - peak sampled PSS 1,870,697 KiB and VmHWM 1,873,176 KiB;
   - warm starting thermal state retained rather than hidden;
   - local/remote hashes matched and scoped cleanup was verified absent.

## Next coordinated steps

1. Do not rerun the one-request smoke or loop `llama-completion`.
2. Bind a persistent loaded-route runner before a canonical campaign; a per-process completion loop would reload/remap the model and violate protocol v2.
3. Prove and record one allowed request-isolation strategy (full in-session conversation/KV reset or fresh Session per logical request), including reset/creation duration and whether it is in total-request timing.
4. Run the fresh canonical 1+5+5+5 campaign only after that proof and new coordination.
5. Send the owning smoke evidence as a structured handoff. Do not publish this noncanonical smoke in the shared Android benchmark registry or experiment HTML.

The two historical `llama-cli` attempts remain invalid. One entered automatic conversation and generated a 9.2 GiB runaway stdout before termination. Only bounded, noninteractive tooling is permitted.
