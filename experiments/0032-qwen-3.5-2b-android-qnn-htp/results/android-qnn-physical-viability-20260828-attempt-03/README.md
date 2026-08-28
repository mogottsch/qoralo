# Repaired-PTE physical QNN/HTP check (attempt 03)

## Outcome

The single explicitly authorized repaired-route check completed successfully. The exact explicit-broadcast W4A16 PTE (`23ac8abd…d2c506`) ran the canonical 174-token short input on the authorized Samsung SM-S918B / SM8550 through four QNN HTP-v73 graphs. The provider log records 696 graph starts and 696 status-`0x0` completions, exactly four executions per input token. ETDump reports four HVX threads per graph call, 253.641795 aggregate accelerator-execute seconds, 255.033891 aggregate RPC-execute seconds, and 61,253,612,902 accelerator cycles.

The runner exited 0 and produced token ID 1206, decoded with the pinned tokenizer as `To`. This is an ordinary English lexical token rather than the unrepaired route's token 0 (`!`). The narrow superficial sanity check is therefore `looks_sensible: true, issue_notes: null`. This means only that the exact two output bytes are not obvious gibberish or corruption; a one-token fragment cannot demonstrate sentence-level usefulness, quality, or correctness.

## Fidelity boundary

The physical output does not match the saved host W4A16 QDQ replay, whose final token is 760 (`The`). The repair removes the previously localized recurrent-state corruption and its token-0 symptom, but this check does not establish numerical or output equivalence. The remaining QDQ/QNN difference stays explicit.

This was not a benchmark campaign. Setup took 3.777 seconds, the request/TTFT took 332.784 seconds, and prefill model execution took 332.367 seconds (0.524 input tokens/s). These are single-request gate observations with no loaded-route reuse or latency distribution.

## Evidence retention

- Every staged artifact matched its pinned hash locally and remotely.
- `raw/generated.int32le` preserves token ID 1206 and `output.txt` preserves its exact UTF-8 decoding.
- `profile-summary.json` summarizes QNN-native profile units from the complete ETDump.
- The 107,315,601-byte provider log and 56,603,888-byte ETDump remain exact locally. Git retains lossless zstd copies. `compression-manifest.json` records raw and compressed sizes/hashes and verifies recovery of both raw SHA-256 values.
- Device, battery, thermal, inventory, metric, hash, and pull records are retained under `raw/`.
- The experiment-owned process and remote root were verified absent by the lifecycle script, independently rechecked under the phone lock, and confirmed by Pi before priority transferred away.

## Claim boundary

This proves one-token physical execution of the repaired exact route through QNN/HTP. It removes the prior token-0 corruption symptom but does not prove QDQ equivalence, sentence-level useful output, loaded-route isolation/reuse, campaign readiness, campaign performance, or benchmark-registry eligibility. No retry or campaign was authorized or performed.
