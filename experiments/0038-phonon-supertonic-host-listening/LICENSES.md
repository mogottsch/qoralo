# Source and generated-sample licensing

All comparison speech is machine generated using documented stock presets. No individual is impersonated, no voice is cloned, and all supplied text is public repository material or original fictional nonprivate prose.

## Phonon 31m (not the NC 40m family)

- [Pinned model card](https://huggingface.co/gradium/phonon-31m-en/blob/92741c5b07d085ff840e26fea8ce43110b87852f/README.md): weights, tokenizer and voices **in this repository** are Apache-2.0. This experiment uses only its own `default-voice.safetensors`; no separately licensed external voice catalog asset.
- [Apache-2.0 text](https://www.apache.org/licenses/LICENSE-2.0).
- [Pinned runtime](https://github.com/gradium-ai/xn-ptts/tree/cc0c32bcad4e79121e98cb16d9a1b19f87772e82): MIT OR Apache-2.0. The installed ptts 0.4.2 wheel runs Rust inference without PyTorch.
- Neither Apache-2.0 nor the pinned model card imposes a separate noncommercial restriction on these outputs. No model weights, tokenizers or voice embeddings are redistributed here.

## Supertonic 3

- [Pinned model license](https://huggingface.co/Supertone/supertonic-3/blob/724fb5abbf5502583fb520898d45929e62f02c0b/LICENSE), reproduced for reference in [licenses/Supertonic-OpenRAIL-M.txt](licenses/Supertonic-OpenRAIL-M.txt): **BigScience OpenRAIL-M**, including use restrictions. It is not Apache-2.0 and must not be described as an unrestricted Apache model.
- Section 6: “Except as set forth herein, Licensor claims no rights in the Output You generate using the Model. You are accountable for the Output you generate and its subsequent uses. No use of the output can contravene any provision as stated in the License.”
- Attachment A(e) prohibits disseminating generated content without expressly and intelligibly disclosing that it is machine generated. The audition and README prominently disclose this. Preserve that disclosure when sharing a standalone WAV, and do not use these outputs for prohibited purposes (including impersonation or harmful misinformation).
- The [official Python SDK v1.3.1](https://github.com/supertone-inc/supertonic-py/tree/908a56486e821e833a80530ff0cae3ad0b046fce) is MIT; the accompanying M1 voice style is part of the separately licensed model assets.

## Distribution boundary

These benign listening examples are generated **outputs**, not model weights or a derivative model. The cited terms permit preparing and sharing this comparison with the notices and conditions above; section 6 does not impose a blanket noncommercial prohibition. The original new text and helper code follow the repository’s Apache-2.0 licensing, but that does not relicense either upstream model or warrant exclusive rights to synthetic output. No endorsement, voice-identity match or broader rights clearance is claimed. This is a source-license assessment for this bounded comparison, not legal advice.

Full model/voice/model-card asset hashes and immutable revisions are retained in `protocol/models.json`. Do not replace their pinned terms with those of current main or a different model family.
