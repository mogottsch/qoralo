# Provider-prescribed HTP integration

## Authority and product boundary

This integrates the complete accepted0037 recipe, not merely a preprocessor or a larger input buffer. The upstream authority is supertonic-py1.3.1, commit908a56486e821e833a80530ff0cae3ad0b046fce. Moritz accepted the exact0037 HTP WAV0ddfc170…7209 and CPU WAV6848fcd6…a0be. That acceptance does not transfer to a new app waveform or erase the old vector strict numerical-gate failure.

The product still has immutable complete chapters. Internally the provider groups raw paragraphs/sentences toward300 Unicode codepoints; overlong sentences remain intact. Per-segment global Unicode14 NFKD/provider normalization/tags precede indexing. English/M1,8steps,speed1.05, own HTP duration/nativeL and continuous NumPy-compatible Gaussian consumption are explicit. Each segment contributes its full nativeL×3072 vocoder extent, with13,230 zero frames only between segments. No forced duration, script rewrite, extra word/comma splitting or CPU neural fallback.

The app reports completed speech-segment progress. Complete chapter WAVs and the final episode are still the publication units; **streaming playback is not implemented or claimed**. Existing chapter-to-chapter pauses remain separate from provider-internal0.3s gaps.

## Reusable contexts instead of the case-specific32-context experiment

The initial0037 pack specialized duration/text for15 exact nativeT values. The app pack instead uses four resident contexts:

- duration T320, plus a runtime native-edge array that includes the existing learned sentence-token prefix (sequence extentT+1);
- text T320, plus native-edge arrays for radii2/4/8;
- accepted shared vector T320/L512, with the existing four native-L EDGE Gather arrays and stable Softplus lowering;
- accepted shared vocoder L512, retaining its causal native-output prefix.

Each of the six duration/text symmetric EDGE pads is replaced by a Gather whose indices clamp to the **actual native sequence edge**, not the padded bucket edge. Every other computational node and every initializer is byte-identical. This supports arbitrary nativeT within1–320, not a list of the reference chapter's lengths. A raw overlong sentence whose processed text exceeds320 is rejected before lock rather than forcibly split. Own predicted nativeL must still fit1–512 at runtime; input admission is not a promise that hardware, duration or quality can never fail.

The first source preparation omitted DP's learned-prefix position and failed during session construction, before any forward. It is retained. The corrected host comparison passed27 cases per component (15 actual segments plus12 boundary shapes), within predeclared maxAbs1e-4/RMSE1e-5: observed maxAbs DP1.43e-6, text1.03e-5. Both new QNN exports passed with zero Run calls; their owned containers were removed. The old vector gate remains failed/non-bit-exact, and new physical validation is a distinct requirement.

Pack: `supertonic-3-provider/current`, manifest SHA423429c6642da131ac62511e3b233f1a121b97975aa5b6e9aa755bb13a927670,13 data files/212,921,074B. The old packs are neither overwritten nor removed.

## Frontend and stochastic fidelity

The Kotlin port is independent of Android/JVM Unicode-version drift: a hash-bound non-neural Unicode14 decomposition/combining-class/word-boundary table implements global NFKD and the pinned Python regex boundary semantics. Licenses and a reproducible generator accompany the table.

267 synthetic cases and all15 exact private reference raw-chunk/processed/ID hashes pass. All22 saved chapters from the prior read-only snapshot form180 provider segments; the largest processedT is309. This is descriptive saved-input coverage, not a universal language/quality guarantee.

The actual C++ Gaussian helper matches all2,160,000 frozen NumPy legacy RandomState samples byte-for-byte on the host. The app chooses the documented seed20260911 **per whole chapter**, keeps its stream continuous across that chapter's segments, and consumes144×own-nativeL values—not static-bucket padding. A bounded pure-native Android check is included before the first app-model validation. Equal seeds alone do not imply equal CPU/HTP active inputs when own durations change nativeL.

## Transactional admission and durable plan identity

Manual lock and review-OFF auto-lock assess the actual current chapter text using the installed pack's pinned manifest/indexer. The UI result is advisory; the repository recomputes inside the lock transaction. Unsupported input or unavailable capability data retains the entire draft. A failure to save the audio plan after successful SCRIPT generation also retains the completed draft instead of discarding model work.

A new provider AUDIO job ID is the **SHA256 of its immutable plan**, rather than a UUID. The plan includes a fresh per-attempt UUID nonce, episode/revision/content hash, pack hash, frontend/Unicode-table identities, recipe, and each segment's raw/processed/token hashes. Thus identical content under a deliberate new attempt has a new ID; duplicate lock actions cannot overwrite the first job or its files. UUIDs remain valid legacy job IDs and are not reinterpreted as provider plans. The existing database schema and historical rows are unchanged.

The plan file is written atomically and the job/lock is committed transactionally. Failed transactions remove only their owned new plan. Before audio execution, the worker verifies the plan hash against its job ID and regenerates the same capability plan from the locked revision and verified pack. Missing/tampered/stale plans or changed pack settings stop before inference. No mutable status/error field is abused as a plan store, and no automatic retry is introduced.

Tests cover duplicate lock, persisted nonce verification, fresh-attempt identity, missing/tampered/stale/legacy plans, unsupported/overlong sentences, review-OFF preservation and sparse capability fixtures that are correctly rejected by full model-integrity verification. Capability checking alone is not labelled full neural-pack verification.

## Validation workflow and preservation

The planned app test starts from a **labelled copy of the authentic487-word saved chapter**. A new episode is created through Main UI; a debug-only fixture copies immutable saved content into that newly owned episode. No SCRIPT/EDIT inference or fake completed SCRIPT job is inserted. The normal lock UI then queues the actual hash-bound AUDIO job through the dispatcher/foreground service/provider HTP route through Ready.

Only that new episode may acquire source/revision/audio/playback artifacts. All prior episodes, sources, revisions, jobs, playback, accepted WAVs/exports and old model packs remain unchanged. The current verified-TTS catalog cache may legitimately update to the new verified pack; Gemma and all other cache rows are fixed. The test does not request Play or export.

Following Moritz's later direction, new host launches do not require a memory lock. Per-process CPU/RAM/swap/time bounds, actual live headroom checks, credential-free environments and owned cleanup remain. Earlier lock-using probe receipts are historical and are not rewritten.

Full phone.lock and fresh installed identity/coherent DB/no-active-user-job checks precede any install. The provider pack is staged in a new namespace and hash-verified. Cleanup is independent of log/archive parsing and refuses foreign active work. Raw content, WAVs, snapshots, logs and diagnostic segment artifacts stay private/hash-bound. No broad environment dumps or credentials belong in build evidence.

The exact app/device/WAV outcome will be retained separately; this source design is not a physical-run or listening verdict. Ben/Jens remain paused. Nik is the only eligible independent reviewer of this app work; absence is not a gate or permission to substitute a reviewer. Push/history-rewrite holds remain.
