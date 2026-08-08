# Qwen2 prefill/decode ABI (Lane C)

This is the FP32 correctness ABI for the locked `microsoft/VibeVoice-1.5B`
backbone. The machine-readable shape/order contract is
[`qwen2-backbone-abi.json`](qwen2-backbone-abi.json). It is based on official
source revision `6dd49cb7200c0367205a5f1e650244259e9e423d`, Transformers 4.51.3,
and the checkpoint config (28 layers, hidden size 1536, 12 query heads, 2 KV
heads, head dimension 128, vocabulary 151936). No checkpoint was loaded while
establishing this contract.

## Fixed cache and ordering

The first proof uses batch 1, FP32, and cache capacity `C=1024`. That bound
covers the locked reference's observed 503 input plus 102 generated tokens and
makes decode reusable without a shape-changing append. Each cache is
`[1,2,1024,128]` and all 56 caches occupy 56 MiB.

Cache tensors are always flattened in this exact order:

```text
layer_00_key, layer_00_value,
layer_01_key, layer_01_value,
...
layer_27_key, layer_27_value
```

The same order applies to prefill outputs, decode inputs, and decode outputs.
There is no mutable Hugging Face cache object across the runtime boundary.
Invalid cache slots are zero-filled for fixture readability, but zero content
does **not** establish validity; `attention_mask` and the controller's
`valid_length` do.

## Prefill ABI

Let `S <= 1024` be the conditioned prompt length.

Ordered inputs:

1. `inputs_embeds`: FP32 `[1,S,1536]`;
2. `attention_mask`: int64 `[1,1024]` (`1` at valid source positions, `0`
   elsewhere);
3. `position_ids`: int64 `[1,S]` (RoPE positions for each input embedding);
4. `cache_position`: int64 `[S]` (absolute destination slots, normally
   `0..S-1`).

Ordered outputs:

1. `last_hidden_state`: FP32 `[1,1,1536]` for the final input position;
2. `next_token_logits`: FP32 `[1,151936]`;
3. 56 full-capacity KV tensors in the normative order above.

After a normal unpadded prefill, native orchestration records
`valid_length=S`, retains the returned cache tensors, and sets mask slots
`[0,S)` to one.

## Single-token decode ABI

Ordered inputs:

1. `inputs_embeds`: FP32 `[1,1,1536]`;
2. `attention_mask`: int64 `[1,1024]`;
3. `position_ids`: int64 `[1,1]`;
4. `cache_position`: int64 `[1]`;
5. 56 full-capacity KV tensors in normative order.

Ordered outputs are the same as prefill. Before call `n`, where `n` is the
controller's valid length, set `cache_position=[n]`, `position_ids=[[n]]`, and
`attention_mask[0,n]=1`. The wrapper replaces slot `n` in every key/value
cache and returns all full-capacity tensors; the controller then advances
`valid_length` to `n+1`. Calls with `n >= 1024` are rejected by orchestration,
not wrapped or evicted silently. Padding/batching needs a separate proved ABI.

## Conditioning and token-selection boundaries

The Qwen2 modules consume **embeddings**, not token IDs:

- The text tokenizer and tied embedding table produce dense
  `token_embeddings [1,S,1536]`.
- Speaker audio encoding, scaling, and `acoustic_connector` remain outside the
  backbone. They produce dense speaker embeddings. `SpeakerConditioning`
  replaces only positions selected by `speaker_input_mask [1,S]`, matching the
  official source's prefill-only scatter. The resulting tensor is
  `inputs_embeds`.
- On decode, `inputs_embeds` is either the selected token's tied embedding or,
  for a diffusion token, the official acoustic-plus-semantic connector sum.
- The graph returns FP32 logits and does not select a token. Native
  orchestration applies the official allowlist processor (speech start, speech
  end, speech diffusion, EOS, and BOS when configured), then greedy argmax or
  softmax/multinomial according to the locked generation config. This avoids
  baking random sampling or control flow into the backbone PTE.

`last_hidden_state` remains an output because a selected speech-diffusion token
uses it as the positive diffusion condition.

## Tiny ExecuTorch/XNNPACK finding

With PyTorch 2.11.0, Transformers 4.51.3, and ExecuTorch 1.2.0, both tiny
prefill and one-token decode wrappers pass strict `torch.export`, XNNPACK
lowering, and host runtime execution. The synthetic two-layer proof creates 24
XNNPACK delegate segments per entry; it therefore proves mixed delegated
execution and ABI mechanics, not complete full-model delegation. Fixed shapes
and explicit static cache updates avoid the shape-growing `DynamicCache` that
cannot be a reusable Android ABI. The environment emits non-fatal torchao
extension warnings for incompatible optional CUTLASS/MXFP8 binaries.

That tiny proof used no phone, full checkpoint, or quantization.

## Real locked-checkpoint result (heavy RAM)

The real capture was run twice with the locked transcript, voices, seed 42,
CFG scale 1.3, FP32, and source/model revisions above. Both runs produced
byte-identical `manifest.json`, `prefill.pt`, and `decode.pt` files. Prefill
length is 503 and decode position is 503. Validation compared 181 raw tensors,
confirmed finite outputs, exact ordered cache handoff, and zero unused slots.
All 58 eager wrapper outputs per entry pass `atol=1e-5, rtol=1e-4`.

Both 28-layer entries pass strict export and XNNPACK lowering (284 delegate
segments each) and execute on the host. The 6.18 GB PTEs do **not** pass the
initial numerical tolerance: prefill has 12,844 mismatched values and chained
decode has 11,315, with `4.73e-4` maximum absolute error for each. Decode used
the actual ExecuTorch prefill cache outputs. All runtime outputs remain finite.
The tolerance is not widened, so Android and quantization remain blocked.

Reproduce capture twice, structural/eager validation, export, and chained host
execution from a worktree with access to the ignored model/source artifacts:

```bash
PY=.venv/bin/python
ETPY=artifacts/venv-executorch-1.2/bin/python
EXP=experiments/0002-vibevoice-1.5b-executorch-android/export
MODEL=artifacts/models/microsoft-VibeVoice-1.5B
SOURCE=artifacts/source/microsoft-vibevoice
FIXTURES=artifacts/0002/lane-c/qwen2-fixtures
REPEAT=artifacts/0002/lane-c/qwen2-fixtures-repeat

for OUTPUT in "$FIXTURES" "$REPEAT"; do
  "$PY" "$EXP/capture_qwen2_fixtures.py" \
    --source "$SOURCE" --model "$MODEL" \
    --transcript experiments/0001-vibevoice-1.5b-local-reference/transcript.txt \
    --cache-capacity 1024 --seed 42 --cfg-scale 1.3 --output "$OUTPUT"
done

"$PY" "$EXP/validate_qwen2_fixtures.py" "$FIXTURES" \
  --repeat-dir "$REPEAT" --model "$MODEL" \
  --output artifacts/0002/lane-c/qwen2-fixture-validation.json

export PATH="$PWD/artifacts/tools/flatbuffers-25.12.19:$PATH"
for ENTRY in prefill decode; do
  "$ETPY" "$EXP/export_qwen2_real.py" --entry "$ENTRY" \
    --model "$MODEL" --fixture-dir "$FIXTURES" \
    --output "artifacts/0002/lane-c/qwen2-${ENTRY}-fp32-xnnpack.pte"
done

"$ETPY" "$EXP/validate_qwen2_pte.py" \
  artifacts/0002/lane-c/qwen2-prefill-fp32-xnnpack.pte \
  --decode-pte artifacts/0002/lane-c/qwen2-decode-fp32-xnnpack.pte \
  --fixture-dir "$FIXTURES" \
  --output artifacts/0002/lane-c/qwen2-prefill-decode-host.json
```

Raw fixtures, PTEs, generated audio, and logs stay under ignored `artifacts/`.
Structured summaries are committed as
[`../results/qwen2-fixtures-host.json`](../results/qwen2-fixtures-host.json) and
[`../results/qwen2-backbone-host.json`](../results/qwen2-backbone-host.json).
No phone was used.
