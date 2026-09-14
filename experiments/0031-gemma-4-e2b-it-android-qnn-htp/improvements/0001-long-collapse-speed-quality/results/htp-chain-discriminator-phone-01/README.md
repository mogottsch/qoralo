# Valid selected chain results, with materialization limits

`htp-chains-20260914T160058Z-01` executed **only `normalization_chain` and `normalization_exposed`, once each**, in separate native processes under one continuous phone lease. Both native exits and the controller exit were 0. Each execution metadata file reports one inference; only its selected output files exist. **Power was not repeated.** Separate basic profiles record RPC/accelerator execution for the selected graph names.

All **six raw outputs / 1,180,416 bytes** were checked across every channel and all 32 repetitions of each input pattern.

| Readout | Codes for zero / small / finite / larger-finite patterns |
|---|---|
| Native chain normalized | 31507, 31549, 33778, 33552 |
| Exposed chain normalized | 31507, 31549, 33778, 33552 |
| Exposed squared | 0, 0, 1, 20 |
| Exposed mean | 1, 1, 22, 434 |
| Exposed denominator | 1, 1, 22, 434 |
| Exposed inverse | 62816, 62816, 13392, 3015 |

The two complete normalized outputs are byte-identical: **`74767fb3de4fec47b19a2da19764400f6771652db0d46bfec7e0ad1304195db8`**. Mean and denominator files are also byte-identical: **`9bcb2e46917d0b6df8e3aa7750fe69584f43942ee351bd7cb4c39f9afcacc268`**.

## What the binding audit does and does not establish

Compiled-context and execution metadata names, IDs, dimensions and datatypes match. Exposed output IDs are distinct: squared 14, mean 15, denominator 18, inverse 20, normalized 21. File lengths and native-output sidecars match. Exact grids come from the hash-bound compiled context, **not rounded sidecar scale displays**.

**Native output-buffer addresses/file descriptors were not captured.** Distinct tensor IDs and identical files do not establish independent semantic observations or prove that internal buffers cannot alias/materialize differently. The output named `mean` is not automatically a snapshot of an unfused ReduceMean kernel.

The literal portable reference expects zero mean/add codes for the two low patterns. These actual named mean/denominator readouts contain code 1 even where the squared readout is code 0. This identifies an observable boundary discrepancy, **not** a justified mean/epsilon floor, proof of fusion, or a complete reference correction. Equal final outputs do not prove absence of optimization effects.

## Ownership and scope

All **95 ADB calls** were under one lease. Each phase's owned processes were verified absent before the next launch, then independently rechecked before final cleanup. Raw pull completed before deletion; no signal operations occurred; actual `bf53c566…` / `f1543993…` postflight passed; the phone was released before analysis. Both phases read back AS12 GiB and FSIZE8 MiB.

Raw arrays remain private and hash-bound. Battery files are labeled current-state extracts. No full model/reference was run, no Power case was repeated, and no arithmetic rule was fitted to full QNN logits.

The next host-only prepared checkpoint uses two **single-output** same-grid controls isolating ReduceMean and epsilon-Add. Those remove this same-graph multi-output observation ambiguity without adopting a policy. See [htp-mean-add-readiness-01](../htp-mean-add-readiness-01/README.md).
