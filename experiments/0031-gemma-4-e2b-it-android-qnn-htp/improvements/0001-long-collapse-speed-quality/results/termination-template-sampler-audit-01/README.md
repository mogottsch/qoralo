# Saved/source check: termination, template and sampler

**A real stop-policy discrepancy exists, but a missed stop in the QNN run is
unproven.** No model/runtime was executed, no ADB was used and no termination,
BOS, workload, sampler, stage or previous result was changed. The changed-output
but still-collapsing result in `f11df93` remains a negative candidate result.

## Termination

| Source | Stop IDs |
|---|---|
| Frozen QNN config and actual `ctx-new` runtime log |1,106|
| QNN checkpoint's `generation_config.json` |1,106,50|
| Base model's `generation_config.json` |1,106,50|
| Generic LiteRT bundle used by both successful CPU/GPU routes |1,50,106|

The QNN builder hard-codes `[1,106]` in `prepare_runtime_bundle.py:89`.
ID1 is `<eos>`,106 is `<turn|>` and50 is `<|tool_response>`. Thus the ordinary
end-of-turn marker106 was not omitted; the missing stop is the tool-response
boundary50, also present in upstream generation policy. This is not permission
to add50 or another stop sequence as a purported fix.

The generic LiteRT model was stream-hashed against its accepted identity
`18193810…a63c`. Its12,192-byte metadata section was read directly and decoded
using the retained protobuf schema, not inferred from a model name or the unused
GPU-specialized bundle. LiteRT SessionConfig fills unspecified stop IDs from this
metadata. Source `tasks.cc:210–254` detects stops before exposing callback IDs.

The successful CPU/GPU runs each retain756 filtered callback IDs and a runtime
count757. Their matching stop ID is not retained in that callback list. The
runner labels normal below-cap completion `eos`; this does not independently
identify whether1,50 or106 terminated it. None of these facts should be replaced
with an EOS-ID guess.

The QNN package retains decoded text, input-ID prefixes, counts and partial
pre-sampler logits, **not the actual selected-token stream**. Consequently this
check cannot establish that50 occurred, was absent, or was missed. Re-encoding
the decoded output is not used to make that claim. Genie source accepts the
configured EOS array and tests sampled IDs before emitting text; source behavior
alone is not a capture of what this run sampled.

## Template and input history

All three rendered prompt files are byte-identical across QNN and the successful
LiteRT CPU/GPU routes. The no-tools/no-thinking system+user specialization ends
with the same model-turn prefix.

However, their **recorded effective token histories differ**. LiteRT has two
leading BOS IDs, `[2,2,105,…]`; QNN has `[2,105,…]`. Across all three tiers and
both reference routes, the *entire* LiteRT sequence equals one extra leading2
followed by the QNN sequence. Counts are171/595/1930 versus170/594/1929.
This is proven from the retained effective input arrays, not guessed from text.

Therefore the existing good CPU/GPU outputs are not same-token-history numerical
controls for QNN. This does not prove that the extra BOS causes or fixes anything,
and neither accepted input history was changed. Different model artifacts,
quantization and context limits remain additional cross-route confounders.

## Sampler

QNN's frozen and logged configuration is greedy=true, top-k1, top-p1, temp0,
seed42. Source `Sampler::basic_process` takes a direct argmax hot path when one
token and no probabilities are requested. The reference runner explicitly uses
CPU TOP_P(k1,p1,temp1) for both neural backends: a singleton argmax-equivalent
candidate, not evidence of random sampling. Its seed is unset. These parameter
differences do not by themselves establish a stochastic-sampling explanation;
full score equality, ties and runtime numeric correctness are not proven here.

## Next genuinely discriminating check

Do not spend another precision conversion or simply repeat the long output.
First prepare a **selected-ID/stop-decision trace before stop/text filtering**,
keeping the candidate, exact input, sampler and existing termination unchanged.
It should bind sampled IDs, configured stop membership and the stopping event,
including a missing-event reason if the API cannot expose one. This directly
distinguishes “token50 was generated but not recognized” from an unsupported
missed-marker story. Adding50 without that evidence could merely hide/truncate
bad generation.

Any future paired numerical comparison must separately account for the proven
BOS-history difference. It must not silently rewrite either campaign. A missing
marker cannot be ruled out from the current saved QNN text, and a configuration
gap is not proof that it caused the44-token loop. No new phone run is authorized
or queued by this audit; Janek/Ben resource priorities remain in force.

## Evidence handling

`result.json` binds actual runtime config lines, both reference input/callback
summaries, the metadata section/model identity, upstream generation configs and
source hashes/locations. SDK source stays private; only citations and hashes are
retained publicly. The inspection used a1GiB address-space/180-second outer bound
and nice15. Stream hashing is not model loading/inference. Source/parser and saved
claim-boundary tests are provided; no expensive model or device validation was
repeated.
