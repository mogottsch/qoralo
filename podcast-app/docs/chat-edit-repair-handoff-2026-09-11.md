# Earlier chat-edit repair — 2026-09-11

**Current installation:** provider HTP app `04d9293b…` supersedes this artifact while retaining its chat fixes. See [the current provider handoff](provider-app-handoff-2026-09-12.md). The e1b33f27… artifacts and results below remain historical evidence.

## Use the updated app

The update is installed. Open the newest failed podcast, choose **Return to saved draft**, then **Edit with agent** to submit the change you want. Returning to the draft does not retry generation, delete the failed chat request or modify its text. Future editing failures keep the draft accessible.

The diagnostic's generated response was deliberately **not applied** to your episode. Your original chapters and chat history remain intact; the next deliberate normal chat request creates a new immutable revision if successful.

## Exact installed artifact

- App: `podcast-app/.local/user-edit-ready/candidate-02/app.apk`
- App SHA256: **`e1b33f276aa7f267c778a1c3fe6c113700aa401d61472956a4769a098fcc89ba`**
- Test: `podcast-app/.local/user-edit-ready/candidate-02/test.apk`
- Test SHA256: `060edd5f0679b79ec928319a5b1e93c1bbcbd42d775b2df05c78307ad849d0f9`
- Source: `4466077f7cd7e84dd98e67afd7b3b319772ac872`
- Candidate SHA256: `6468097a818c6cab82c3619824d88eee090e4c7916b4eaa87f586a8f0effa0d0`

The same Gemma model, LiteRT-LM0.16.1 GPU runtime, native9 and Supertonic packs remain. Only EDIT decoding now uses the SDK's JSON-schema constraint. The8,192 context,4,096 edit output ceiling, sampling scalars and edit instruction are unchanged. No CPU fallback, model/native rebuild or post-generation JSON repair was added.

## What failed and what changed

The newest saved AGENT_EDIT failed during JSON parsing, after Gemma returned a reply. A single reconstructed-input diagnostic reproduced the phase and captured the concrete error: **an extra closing-object token between chapters**, plus a missing required change summary. The reply had a document-closing brace/fence; no token-limit termination was established. The historical user reply was not retained, so its exact bytes remain unknown.

There were two fixes:

1. **Preserve access to the draft.** Running edit failures now retain SCRIPT_DRAFT, failed job and chat error. Already affected episodes have an explicit recovery action. Its transaction rechecks current episode/job/revision/message ownership, absence of active work and lock/audio state, and the saved revision artifact hash. No SQL patch or automatic migration rewrites old episodes.
2. **Generate the required structure.** EDIT requests now use the pinned SDK's built-in LLGuidance JSON-schema response format. The schema requires the complete revision and summary. The same strict parser and semantic script validator still reject invalid responses; nothing is repaired, pruned or accepted as a partial revision.

## Actual changed-setting comparison

| | Baseline | Structured EDIT |
|---|---|---|
| Run | `edit-probe-20260911t140437z` | `edit-probe-20260911t142958z` |
| Logical model calls |1|1|
| JSON parsing |Failed|Passed|
| Normal complete-revision validation |Not reached|Passed|
| New response committed |No|No|

Both calls used **byte-identical request and system instruction**, with unchanged sampling scalars and limits. Actual request SHA: `0d165d3d4a2472670f2e81e65a8ad6d73b37a339178fecdc28d293693f70c4aa`.

Structured schema SHA: `30febb7dd5dde64f201c4983dba6f3f4b0ee557b2547e957c4011be2e667a864`. The valid raw reply was8,394B, SHA `4e83504ed1044f7c63441b3a70aea03efe275ade007a96f64d080aef3a56a613`. All five original chapter IDs were retained, all five texts changed, and a nonblank summary was returned. This is a real format/validation result, **not automatic acceptance of humor, factual quality, unchanged narration length or general model reliability**. Model rewriting changed word counts; the app did not truncate text to fit audio.

The actual recovery transaction passed inside an always-rollback outer transaction, and the real recovery button was displayed/enabled without being clicked. Across each test, **all9episodes/8sources/7revisions/22chapters/12jobs, other rows/catalog and19episode files remained unchanged**. No new jobs, revisions, TTS, playback or exports. Cleanup errors[], exact app/generation/test PIDs and controls absent, full phone lock released.

## Validation limits and preserved evidence

-184 host JVM tests passed; one unrelated optional long-TTS pack fixture was skipped and recorded.12 focused Python checks passed. Debug app/test assembly and release Kotlin compilation passed.
- Full release APK assembly was not completed: an offline Compose-mapping dependency was not cached. The installed/nominated artifact is the tested **debug** APK above.
- Nik was disconnected. No independent review verdict or substitute reviewer is claimed.
- No normal-chat E2E success is inferred from the diagnostic engine call. It validated real model output with the same production parser/validator without committing it. One result does not guarantee every future edit will succeed, especially if a genuine context/output limit is reached.
- All raw user text, requests/replies, exception details, DB/WAL, inventories and logs remain private/hash-bound. Original failures and frozen candidates remain preserved. No push/history rewrite.

[Detailed diagnosis and protocol](user-edit-failure-diagnostic.md) · [Earlier capacity repair](app-repair-handoff-2026-09-11.md) · [Accepted short-flow/audio milestone](final-short-app-handoff.md).

**Audio scope is unchanged:** the installed short voice still has its230-normalized-codepoint chapter input limit. The separate long-speech CPU/HTP work is not incorporated here. The previously accepted21.067s master and its local SAF export remain untouched.
