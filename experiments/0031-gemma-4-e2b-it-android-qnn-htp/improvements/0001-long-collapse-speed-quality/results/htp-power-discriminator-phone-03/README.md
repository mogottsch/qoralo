# Valid isolated HTP Power result; chain cases were not executed

The shared-buffer run `htp-power-20260914T152014Z-03` completed native/controller **0**. It loaded/described three graphs, but the actual runner's global `--num_inferences 1` budget produced **one execution**, not one per graph. `execution_metadata.yaml`, the single raw output and the RPC/accelerator profile all identify **`power_edge` only**.

## Actual native UINT16 codes

All 128 output words were checked. Each four-row pattern repeats identically 32 times:

| Input raw code | Output raw code |
|---:|---:|
| 0 | **65535** |
| 1 | 62816 |
| 2 | 44417 |
| 65535 | 245 |

The full 256-byte raw output remains private, SHA-256 **`7ea556daf84b1bbd89eba2ad069b9e567d5dad550e50a590b50a68fbfde76c90`**. The finite controls match the frozen formulas. On this specific HTP/v73 fixture, zero to exponent −0.5 produced the upper output code **65535**.

This is **not yet a normalization/fusion or full-model policy result**. Neither `normalization_chain` nor `normalization_exposed` executed. Loading three graph descriptions is not execution of three graphs, and no missing output is inferred or synthesized.

The basic profile separately records Graph 0 RPC and accelerator execution. Its single-run timings are not a performance benchmark or a claim of universally CPU-free operation. The output sidecar rounds its printed scale; exact grid interpretation remains bound to the inspected compiled context, not that rounded display.

## Ownership and next scope

All 52 ADB commands were under the full lease; actual AS12 GiB / FSIZE8 MiB readbacks, raw pull, owned-role/root absence, no signal operations and genuine `bf53c566…` / `f1543993…` postflight are retained. The phone was released before analysis.

Pi authorized preparation of explicitly selected, separate one-execution invocations for **only the two unexecuted chain cases**, under one continuous future phone lease. The valid Power case must not be repeated merely to complete a table. No full reference/LLM run, guessed pole policy or automatic retry is implied.
