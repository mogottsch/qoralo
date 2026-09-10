# Phone-return diagnostic plan — no execution permission

## Frozen candidate and current boundary

This preparation copies and hashes files only. It does not load Genie, a model, or an execution provider. It does not access ADB, acquire the phone lock, create an APK, run fidelity, or amend the completed campaign.

Private stage:

```text
.local/frozen-stages/stage-freeze-20260910T105830Z-01
```

The path is relative to this improvement track. Its external `frozen-manifest.json` SHA-256 is:

```text
584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25
```

The new context is `1d80d016…ca9f8` (1,186,430,976 bytes). Runtime libraries, executable, LUTs, tokenizer and config bytes are pinned against the accepted baseline runtime manifest `e74f21a3…2096`. Only the model-context payload is substituted under the unchanged context alias. Large files are **independent copies**, not links into the baseline. Inputs are read-only; `bin/genie-app` is read-only executable **0555**. Private directories remain 0700. Hash freeze is not hardware-enforced immutability: recheck the external manifest hash and every input before future use.

The baseline config is byte-identical (`f8008e04…7eba`), with `bos-token=-1`, context 4096, greedy sampling, and base output ceiling 2048. Its global/SWA positional configuration and cache groups are unchanged. All 120 compiled cache tensor boundaries are flat-buffer. No NativeKV, cache import/export/spec command, CPU fallback library, or hidden provider selection is added.

## Gate A: one bounded first-short request, only after a new slot

The frozen `first-short.script` creates one log/profile/config/dialog, saves optional setup profiling, applies a **16-token engineering/noncanonical output cap**, performs exactly one query, saves optional request profiling, and frees the dialog. The exact canonical short workload and rendered bytes are unchanged; the small diagnostic cap means this is **not** a canonical campaign or registry measurement.

Expected effective input is 170 tokens with one existing BOS. Tokenizer bytes are pinned to `cc8d3a0c…fe0f`; rendered short to `b286f8dd…0e7a`; token-ID bytes to `31a85f9c…ad78`. This preparation inherits the accepted tokenizer/BOS proof and does not rerun tokenization or claim a newly observed runtime count.

Required future lifecycle, all under one complete `phone.lock` lease:

1. Obtain a new explicit Pi/Moritz phone slot and reviewed candidate-specific orchestration. The device being connected does not grant permission.
2. Create a distinct host run ID/output directory. Verify stage hashes and executable mode. Do not reuse the old baseline runner: it deliberately hardcodes the old context and its cleanup does not provide the scoped-PID guarantees required here.
3. Verify exactly serial `R5CW81PR8SY`, Samsung `SM-S918B`/`dm3q`, SM8550, arm64-v8a, boot-complete, verified boot green/locked. Record build/fingerprint. A transport/identity failure stops before staging; do not automatically reconnect or retry.
4. Use a new owned remote root, check free space for the roughly 4 GB stage plus raw logs, and push only this frozen input set. Check remote hashes and required dependencies, including `libQnnHtpNetRunExtensions.so`. Create an `evidence/` directory before running Genie.
5. Record battery/thermal state and bounded process-memory telemetry as available. Launch one process with a 1,800-second outer deadline. Capture its exact owned PID and verify its executable path belongs to the remote root. Use that PID only for timeout cleanup; never `pkill genie-app` or signal an unrelated app process.
6. Stream/capture stdout/stderr immediately. Genie opens the output file before query and flushes response chunks; preserve whatever bytes exist on error/timeout. Do not retry a request, switch providers, or run long automatically.
7. **Pull the entire evidence directory, stdout/stderr and exit/timeout/phase observations before optional profile parsing or validation.** Preserve missing/partial outputs and profile/log errors. A successful request is not discarded merely because an optional timing split is unavailable: use null plus a reason. Conversely, exit code zero alone does not prove a successful native query.
8. Verify the owned process is gone, retain after-state telemetry, remove only the owned remote root, and verify absence before releasing the lock. If transport loss prevents cleanup proof, record cleanup as unknown and stop for a new authorized cleanup slot; do not claim success or issue unapproved reconnection attempts.

No candidate-specific ADB orchestration is implemented or approved by this preparation. That lifecycle still requires a reviewed runner before a physical slot.

### Commands for later review

Safe host-only re-verification (not a runtime launch):

```bash
TRACK=experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality
python3 "$TRACK/tools/prepare_frozen_genie_stage.py" \
  --stage-dir "$TRACK/.local/frozen-stages/stage-freeze-20260910T105830Z-01" \
  --verify-only \
  --expected-manifest-sha256 584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25
```

Future **remote process invocation only**, to be embedded inside the separately reviewed locked lifecycle/PID supervisor, never run standalone now:

```bash
# REMOTE must be the new verified owned root; evidence/ must already exist.
cd "$REMOTE"
export LD_LIBRARY_PATH="$REMOTE/lib" ADSP_LIBRARY_PATH="$REMOTE/lib" QNN_LOG_LEVEL=verbose
./bin/genie-app -s first-short.script
```

The future supervisor must capture PID/status/deadline and stdout/stderr outside this command. Input hashes must pass before launch because Genie treats a missing prompt file argument as literal prompt text.

### First-short review criteria

Keep setup, query, error and cleanup boundaries separate. Confirm actual context/provider binding and completed QnnDsp graph execution rather than inferring execution from context loading. Record effective input evidence and any mismatch; do not infer a token count from profile absence. Retain actual generated-token count and stop markers; do not infer EOS merely because output is shorter than the cap. Preserve raw Genie rates with their definition caveat, not a normalized decode number.

Apply only the narrow exact-output sanity check. Text variation against the accepted 16-token viability output is an observation, not an automatic failure. A coherent short result says nothing about long-output collapse. Source compatibility risks from `GENIE-FP16-CACHE-SOURCE-NOTES.md` remain until runtime evidence addresses them.

## Gate B: separately reviewed exact-long collapse comparison

No long execution script is present in the stage. Exact long input/workload/token-ID bytes are pinned now solely for future comparison planning: 1,929 expected tokens, rendered hash `450b519d…f260`, token-ID hash `3b5c04fe…2b64`, output ceiling **2048**; total capacity 3,977 < 4,096.

Only after Gate A evidence is retained/reviewed and a new explicit slot is granted, prepare a distinct long diagnostic revision/run. Use a fresh process/dialog/state, the same context/config/tokenizer, exact long bytes, greedy policy, a full 2,048-token ceiling and 1,800-second request deadline. No hidden prefixes, prompt rewriting, truncation, inherited KV state, in-place retry, or model/provider substitution.

Initially compare one complete candidate long output to all five retained baseline long outputs (which were identical). Do not rerun or replace the completed baseline campaign. Preserve output bytes/hash, actual count/stop reason, provider evidence, setup/request boundaries and thermal conditions. Recompute the existing declared repetition metrics (128-token/four-gram diversity and periodic suffix) with tokenizer/retokenization limitations explicit. Do not infer first internal logit/state divergence from text or turn one diagnostic into a matched performance distribution. Further repeats or a new canonical campaign need a separate scope.

## Source-bound capture rationale and risks

The exact inspected SDK source hashes/line ranges are retained in the readiness result:

- `genie-app/main.cpp:1694–1708` opens the output stream before `GenieDialog_query`; a missing prompt path otherwise becomes literal input.
- `main.cpp:184–237` writes callback response bytes with `std::flush`. Partial output retention is best-effort, not a guarantee that un-emitted tokens survive termination.
- `GenieDialog.hpp:213–223` allows certain warning statuses; therefore a normal CLI return must not be mistaken for EOS/full request success.
- BOS suppression and FP16/flat-cache assumptions are inherited from hash-bound prior source proofs. Mixed key-derived clear semantics, unused export/spec APIs, unknown physical placement and untested long fidelity remain explicit risks.

All artifacts from Gates A/B, if later authorized, are new engineering evidence. The completed campaign `37a2953`, publication `e91b3f5`, and normalized registry remain unchanged.
