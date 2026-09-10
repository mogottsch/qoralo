# Duration source trace: learned sentence-token readout, no fixed text horizon found

**Source-only conclusion:** the official duration graph processes the entire masked text sequence before reading a learned sentence token. Its final `Slice[0:1]` is **not an input-prefix crop**. All31 slices and4 clips are accounted for. There is no fixed300/512/1000-token truncation or30-second clamp to remove in this graph.

This explains which mechanism produces the scalar—a learned sequence summary—not why this particular long input produces29.81s. The completed CPU pair already showed29.8093147s unpadded and29.8190823s padded. A universal learned30s cap, trained maximum horizon, or numerical attention saturation is **not established**.

## Exact path from inputs to the Exp head

Original official dynamic model SHA `c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db`,1086nodes/98initializers. `source-trace.json` references the retained source metadata and checks all1086 node interfaces against one fresh protobuf source parse. Learned bytes were parsed opaquely, never evaluated or copied here. No ORT import, session, forward, graph edit, SDK or phone action.

Let T be physical text length and S=T+1. The two previous CPU cases therefore used S=1334 and2049.

1. **Text IDs and mask, nodes0–29.** All `text_ids[B,T]` enter the embedding Gather. Its64 channels are transposed and multiplied by `text_mask[B,1,T]`. A learned `sentence_token[1,64,1]` is expanded only in batch and prepended on time: `[B,64,S]`. A mask value1 is prepended to the **entire** original mask. The early `text_mask[:,:,0:1]` only provides the shape for `ConstantOfShape(1)`; it does not crop the subsequent text/mask inputs. The FLOAT constant was separately decoded and verified as1.
2. **Six masked ConvNeXt blocks, nodes29–238.** Each depthwise Conv is group64/kernel5/dilation1/stride1 with symmetric **EDGE pad(2,2)**; pointwise kernels are1. No Conv downsamples time. Six local blocks have a25-position structural receptive field (radius12), but this is followed by global attention, so it is not the predictor's total text horizon. Mask multiplications occur around the sublayers/residual paths.
3. **Two global attention layers.** Two heads of32 channels; dynamic Q/K/V time extent S is taken from Conv output shapes. Base `QKᵀ/sqrt(32)` produces `[B,2,S,S]`. The mask is an outer product of the augmented mask; invalid entries are replaced by the verified finite FLOAT sentinel−10000 before Softmax over the full key axis. No causal or local-window mask is inserted. Masking/normalization/residuals and pointwise FFNs retain the time axis.
4. **Relative-position terms are not a text cap.** Each layer has learned K/V tables `[1,9,32]` for relative offsets−4…4. They are zero-padded by `max(S−5,0)` on both sides and sliced from `max(5−S,0)` for2S−1 entries. Their additive key/value terms are rearranged alongside full global content attention. Outside the learned relative-offset range the padded relative contribution is zero; the global QK/value path remains. Four `Clip` nodes only implement those nonnegative pad/crop sizes; none has an upper bound or acts on predicted duration.
5. **Learned readout, nodes1050–1085.** Add the encoded features and local ConvNeXt bypass, then `Slice` time position0: the **prepended sentence token after it has attended to the full sequence**. Its corresponding mask is1. Pointwise projection produces64 features; concatenate the128 supplied M1 duration-style values →192. Two learned Gemms/PRelu form192→128→1, followed by Exp and Squeeze. There is no `ReduceMean`, `ReduceSum`, global/ordinary pool, per-token duration summation, or explicit active-length multiplier into this head. LayerNorm operates across feature channels, not sequence pooling.

This is learned sentence-token aggregation, not a simple arithmetic mean and not additive character/word timing. Full-sequence structural reachability does not prove that every position gets meaningful learned attention, that long-text timing extrapolates correctly, or that downstream speech is complete.

### All31 slices, with no unclassified site

| Count | Purpose | Why it is not a fixed text horizon |
|---:|---|---|
|18|Reverse padding-pair control rows|Six ConvNeXt pads plus six pad conversions per attention layer; INT control vectors, not text tensors.|
|4|Relative K/V table extraction|Two per layer; interval depends on dynamic S and covers2S−1 relative positions.|
|4|Relative-to-absolute score alignment|Per layer: axis2`[0:S]`, then axis3`[S−1:]`, reconstructing full S×S scores.|
|2|Absolute-to-relative weight alignment|Axis3`[1:]` of a rearranged `[B,2,S,2S]` tensor, leaving2S−1 relative positions.|
|1|Shape seed for sentence-token mask|The complete original text mask remains in the concatenation.|
|2|Final sentence-token feature/mask readout|Select position0 only **after** the full encoder. Removing these would break the learned fixed192-dimensional predictor input.|

Every site, original node index, input and recursively expanded start/end/axis/step control is retained in `source-trace.json`. The9 relative entries must not be mistaken for a9-token attention cap; neither they nor the final readout justify a position-table extension analogous to the separate vector graph.

**Padding can still affect semantics.** EDGE padding is applied at the physical tensor end. An unpadded active final token is edge-replicated; a padded sequence instead has zero masked positions beyond the active end. Local boundary features can differ and reach the global readout. Thus the measured9.77ms delta need not be roundoff alone, and this result does not make padding universally quality-neutral.

## What upstream actually documents

Locally installed official `supertonic` package1.3.1 links to `supertone-inc/supertonic-py`. Exact file hashes and bounded passages are in `upstream-source.json`.

- `config.py:201–205`: default8steps/speed1.05, general chunk target300characters, Korean120, inter-chunk silence0.3s.
- `pipeline.py:158–184,261–321`: documents automatic chunks, selects the language-dependent target, calls the model separately for every chunk, then concatenates waveforms with silence.
- `utils.py:154–216`: splits paragraphs/sentences and groups whole sentences. A single overlong sentence can exceed `max_len`;300 is not a hard graph input cap.
- `config.py:243` and `pipeline.py:235–239`:100,000characters is a frontend whole-request guard before chunking, not a model trained horizon.
- `core.py:451–461,506–539`: low-level synthesis prepares the complete supplied text list, obtains DP duration, divides by speed, chooses latent length/mask, and runs text/vector/vocoder. No duration horizon or fixed-prefix crop appears there. The app's speed1/M1/five-step/English-tag/StableSeed/xorshift route remains distinct from upstream defaults.
- The retained `tts.json` DP configuration describes64-dimensional sentence features, six local blocks, two attention layers and the192→128→1 predictor. It supplies no explicit DP maximum input length or duration cap.

Our1324-normalized-character chapter substantially exceeds the packaged300-character chunk target. This is evidence that the high-level long-text recipe relies on **multiple short model calls**; it is not evidence of a precise training horizon, and it cannot be silently used to satisfy the one-chapter/one-render contract.

## Concrete cause boundary and remedy options

**Established:** the unchanged official FP32 duration computation, using all1333 active IDs and the correct style, selects approximately30s. Added padding and a QNN-only numerical difference are not the major timing-gap explanation in the completed pair. No removable prefix/slice/maximum-step bug was found.

**Still unknown:** training length distribution; learned attention/readout behavior on this chapter; whether additional generative time would recover speech; independent text/vector/vocoder long-context fidelity; and how much of the ASR disagreement is rendering versus recognizer loss. Source inspection cannot determine these. It would be incorrect to call the regressor inherently capped at30s just because its Exp output is near30 here.

The smallest defensible choices are:

1. **Keep the current contract unchanged and report its limit honestly.** There is no justified source-preserving graph fix that turns this exact predictor output into~90s. More RAM, removing final readout slices, extending the9-entry relative tables, or blindly repeating the same render do not address an identified defect.
2. **If Pi explicitly authorizes a new diagnostic, test full-request duration conditioning rather than change model weights.** Retain the actual DP scalar separately, but choose an explicitly declared, independently justified generation-time budget before latent mask/noise construction; feed the full chapter once through text/vector/vocoder, producing one WAV. This would test whether the short generated-time budget is responsible for lost content. It is **not** post-hoc time stretching, audio stitching or a proven fix. It also **changes the inference contract and prepared latent mask/noise**, cannot be called the original DP prediction or achieved through a hidden speed change, and would require a fresh reviewed native/debug control, candidate, exact arrays/budget and execution release. Existing native9/candidate/pack must remain preserved. Do not force90s merely to satisfy a dashboard target.
3. **If explicit duration conditioning is not permitted or fails coverage, long-input model adaptation is a different scope.** Training/calibration or learned-model changes need new evidence and permission; none is implied by this trace. No implementation-ready, quality-preserving remedy has been demonstrated under unchanged DP-output behavior.

Rejected under the current goal: upstream text/audio chunk-and-concatenate; silently summing short-chunk predictions as if it were one DP call; truncating/rephrasing the chapter; model substitution; speed/rate overrides; silence padding; time stretching; or claiming success based only on a longer WAV. Moritz alone can accept an exact listening result. No new model run or graph change has occurred here.
