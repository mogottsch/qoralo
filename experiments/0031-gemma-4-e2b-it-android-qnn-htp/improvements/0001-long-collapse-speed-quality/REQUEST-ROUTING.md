# Request-level route policy — recommendation, not measured integration

The completed HTP campaign (`37a2953`) and accepted LiteRT CPU/GPU campaigns in experiment `0025` remain unchanged. No new combined route has been built, executed, or measured by this document.

## Explicit partition

For the existing canonical workload tiers only:

| Logical request | Selected neural backend | Artifact |
|---|---|---|
| Short | QNN HTP/v73 | Accepted 0031 context `7739ce52…d394` |
| Medium | QNN HTP/v73 | Same accepted 0031 context |
| Long | LiteRT GPU | Accepted generic LiteRT artifact `18193810…a63c` |

Selection occurs before submitting a complete request. There is no mid-request switching, tensor handoff, automatic retry on a different provider, or hidden fallback. A failed request remains failed evidence. Host tokenization/sampling and each neural provider remain separately labeled. This policy does not establish a general prompt-length threshold for arbitrary user input.

## Existing evidence, not a hybrid benchmark

The baseline comparison is in `results/long-collapse-baseline/result.json`, corrected in `1c5b7b6`.

- HTP short/medium routes retain their existing measurements and sensible-output observations.
- Accepted GPU long median completion is 48.310947 s versus HTP 118.256069 s: a 59.147% lower observed completion time across the separate campaigns.
- This is not fixed-token throughput improvement: GPU emits 756 tokens and EOS-stops; HTP emits 2,048 tokens with repetition collapse. Artifacts, tokenizers, runtime timing definitions, and thermal histories differ.
- QNN generation rates are raw Genie observations with unspecified first-token inclusion. LiteRT excludes the first token. The normalized cross-route decode delta is **null** and is not a ranking metric.

## Costs still requiring measurement

Two route initializations, provider libraries, artifact mappings and caches are required if both routes stay loaded. HTP's dialog initialization is about 2.112 s; the accepted GPU setup is about 10.520 s. Their different boundaries and separate-run observations must not be summed and presented as measured hybrid setup. Measure readiness from the first access until both arms can accept their assigned requests.

Likewise, process PSS observations cannot establish co-resident usage or private HTP/GPU memory. Measure actual peak process PSS/VmHWM, accelerator-private memory where exposed, transitions, thermal conditions, and retention costs. Preserve one loaded route per arm and isolate state for each logical request. Do not claim unchanged short/medium speed under co-residency until measured.

This is presently an evidence-backed recommendation for a future explicitly partitioned route, not a converted model, new phone run, replacement campaign, or registry row.
