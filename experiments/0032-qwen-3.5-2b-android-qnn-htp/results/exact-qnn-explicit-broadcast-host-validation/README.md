# Exact explicit-broadcast QNN host validation

The exact 24-layer checkpoint was recompiled after replacing implicit recurrent broadcasts with explicit static expansion. All 4,210 tensor-compute nodes, including 120 expand nodes, are delegated across four SM8550/HTP-v73 subgraphs. Every graph finalized and serialized successfully. The revised local-only PTE is 1,994,754,552 bytes with SHA-256 `23ac8abd7e39b596d62bdc6b098a3e61fe0688bf6d1f4d537959e13492d2c506`.

## First-token QNN-x86 validation

At position zero with zero state, the deployed PTE's layer-0 recurrent output had cosine 0.0064 against QDQ, about 118× the reference norm, and led to 39,209 logits tied at the exact maximum. The revised exact PTE produces:

- layer-0 recurrent-state cosine 0.999829 and norm ratio 0.9983;
- unchanged layer-0 convolution-state cosine 0.9999996;
- finite logits with one unique maximum rather than 39,209 tied maxima.

This confirms that the exact recompile carries the broadcast repair and removes the first identified corruption. QNN-x86 logits still differ from PT2E QDQ overall (argmax 198 versus 62 at the first input token), so the result is not a full numerical-equivalence claim.

A full 174-token x86 simulator replay was attempted but stopped at the one-hour tool timeout after position 29. The four logged checkpoints had finite logits and unique maxima. The simulator's speed makes it unsuitable as a full-prompt gate; the partial log is retained only as an implementation diagnostic.

## Claim boundary

This is exact-model host AOT and QNN-x86 simulator evidence. The revised PTE has not been staged or physically executed, and the earlier physical token-0 result remains unchanged. There is no revised physical output, useful-text, campaign, performance, or registry claim. A new explicit Pi handoff would be required for any phone run.
