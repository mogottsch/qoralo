# Input-aligned reference: source-ready comparison design

**Host-only. No native build, model load, inference or ADB occurred.** The generated C++ is not yet compiled or phone-ready. Canonical0025 results/source and every QNN stage remain untouched.

## Question and smallest useful comparison

Can the previously successful LiteRT GPU route produce a non-collapsed response with the **same effective 1929 single-BOS input IDs** used by QNN? The completed source-runtime trace `2bcb58f0` already reproduces the QNN paragraph loop without selecting1,106 or50. Another EOS/BOS sweep or precision build is not the next discriminator.

Propose **one fresh-session GPU long request**, max2048, after a future coordinated slot. GPU is the first reference because its saved successful long requests completed in roughly48s versus116s on CPU; this is scheduling guidance, not a matched speed claim. CPU remains a separately scoped alternative, not an automatic fallback or second request.

Retain the successful reference's generic model bundle SHA256 `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`, LiteRT-LM v0.16.1 revision `924e79c91542761242244e4f1651851f822e4cbb`, `libLiteRt.so` SHA256 `3fdbf64355af65b3ca6ed0c633ffed1e4faa1bfa9256f5e7403fec1633ea1b74`, CPU TOP_P(k1,p1,temp1) sampler, reference stop metadata `[1],[50],[106]`, context8192 and GPU-only provider binding. Use a fresh owned real cache directory; reject `:nocache`, which already caused a historical GPU failure. No app/APK changes.

## Exact alignment, without changing QNN

The source path is explicit:

1. `SessionConfig` fills start token2 from model metadata.
2. `session_utils.cc:86–109` adds a separate BOS text chunk on the first turn even when session templates are disabled.
3. `StringToProcessedInputText` strips a leading BOS string from each chunk, tokenizes the remaining body, then reinserts that BOS ID.

The old caller supplied another literal `<bos>`. Both saved CPU/GPU full effective arrays are exactly **`[2] + QNN1929`**. Removing only the **caller-rendered** `<bos>` leaves the metadata-owned BOS, and the tokenizer receives the same remaining body bytes. No negative start-token sentinel, special-token override or QNN double-BOS workaround is used.

The derivative additionally recomputes **all actual session-preprocessed IDs immediately before `RunPrefill`** and compares them against the embedded, frozen1929-ID vector (int32le SHA256 `3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64`). It saves both arrays first. A mismatch submits no logical neural request. Count-only or rendered-text equality is insufficient.

## Source readiness and fidelity boundaries

`prepare_aligned_litert_reference.py` applies12 count-checked, exactly invertible source changes. It removes the campaign/probe branches, permits only one fresh-session long GPU request, rejects rewind/alternate caps/backends, preserves the reference sampler block, and adds the full-ID gate. Four host/source tests pass. The generated source SHA256 is `bd3e22b740fcfca317434f1e31a0f23e01af3bd8784aaeb6874a1a30f1e138d6`.

A provenance trap was found: the private `.local/LiteRT-LM/runtime/engine/litert_lm_canonical_runner.cc` is stale (SHA `6b0f6d14…634254`), with rewind defaults and without the later GPU-provider/fresh-session corrections. The preparer rejects it and pins the maintained source SHA `5148aec25a39178224e6765e63ff448d27211375d83d394739c7182afc74ba59`. The private LiteRT core checkout remains at the pinned revision, with only its added runner/BUILD target dirty. This does **not** establish the exact source-to-binary provenance of the historical GPU runner (`5f6c423a…2435ed`); that binary and the new frontend must remain separately identified.

Alignment removes the proven input-history confound, not all numerical differences. QNN uses a different artifact/quantization/conversion and context capacity. The source-built QNN runtime and any newly built reference frontend are new artifacts. Reference stop metadata still differs, and callback IDs may omit terminal tokens. No equal-text, hidden-state, kernel-arithmetic or universal CPU-free claim follows.

## Interpretation and remaining work

- **Aligned GPU remains sensible:** the tested single-BOS input does not itself require the observed collapse on this reference. Artifact/runtime/numerical-path differences remain candidates; no specific QNN defect is proved.
- **Aligned GPU also collapses:** investigate input sensitivity and reference fidelity before further precision work. Do not rewrite the old double-BOS successes or assume the same cause.
- **Input mismatch, load failure or incomplete capture:** retain the exact evidence and unavailable fields; no automatic second request.

Before a phone request, build the derivative in fresh bounded owned scratch, bind actual compiler/dependency/core/library/model identities, inspect ELF dependencies, and prepare a fresh full-lock lifecycle with current app identity/quiescence and raw-first cleanup. No historical source tree, binary or campaign may be overwritten. The future comparison should retain complete input IDs, visible output, available callback IDs/task state and descriptive repetition metrics; internal terminal-ID gaps remain nullable. Optional timing must not trigger a replay.
