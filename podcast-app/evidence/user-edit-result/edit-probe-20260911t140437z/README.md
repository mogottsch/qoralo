# Actual edit parse failure reproduced; draft recovery verified

One reconstructed real EDIT request under source4a8722a6/candidate0bb29c, app677be111…/teste3e752…, with the original IDs/text/instruction and unchanged unconstrained v1 JSON generation. This is a diagnostic engine call, not a persisted normal chat E2E result.

Request SHA `0d165d3d4a2472670f2e81e65a8ad6d73b37a339178fecdc28d293693f70c4aa`. Raw returned reply6,959B SHA `dc6d04767024a2382d0a2c6779ca7fbea831ddcd90fa8c551936d574bb183786`. Both the actual Android parser and strict host parse reject an unexpected closing-object token between chapter entries at position2550 of the extracted object. The reply ends with a closing object and Markdown fence and contains no required summary key. No parser repair was attempted. The historical user reply remains unavailable, so this reproduces the same failure phase with a newly captured concrete defect—not proof of byte-identical historical output.

The actual SDK returned KV token count3848; decode/prefill counters and stop reason were unavailable. The immediate defect is malformed interior structure, not an evidenced output-ceiling termination. `responseWords` in the raw-shape record counts whitespace in the entire returned payload, including JSON/fences; it is not a narration word count. Load wall6.946s and request+close wall64.901s are functional observations, not warm/neural-only benchmark rates.

The real repository recovery transaction passed under an always-rollback outer transaction. Actual UI displayed an enabled **Return to saved draft** button, which was deliberately not clicked. ALL9episodes/8sources/7revisions/22chapters/5messages/12jobs, remaining rows/catalog and19episode files are unchanged;0jobs/revisions/TTS/Play/export were added. Cleanup errors[], app/generation/test PIDs and controls absent, phone lock released.

Three identical45,056B private archives have SHA `89cc090e9686f0942bad1d32655f89af87ffa01c68c7387d1bc16754fed97bf2`. Seven safe original receipts are public;230 original captures5,802,156B remain private/hash-bound. Raw request/reply/exception/user data are not published. Nik was disconnected: no independent review is claimed or substituted. No push.

The subsequent EDIT-only schema-constrained decoder is a separate changed candidate and must retain its own outcome. This baseline failure must not be replaced by its result.
