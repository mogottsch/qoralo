# Qoralo own-code licensing decision

**Chosen: Apache-2.0.** On 2026-10-17 Moritz approved the license: “yeah apache is
fine.” Copyright **2026 Moritz Gottschling**. This records the decision in place
of the earlier proposal; no further license-choice approval is pending.

## Licensed work and scope

The unmodified root [Apache License 2.0](../../LICENSE) applies to **our original
Qoralo application code, tests and tools under `podcast-app/`**. Root
[NOTICE](../../NOTICE) identifies that work and retained third-party attribution;
it does not alter the Apache license terms.

This is **not a blanket relicensing of the repository**. Model weights, vendor
binaries and compiled payloads, imported/ported code and data, recordings, source
documents, external art and the historical experiment archive are not covered by
this project grant. Their applicable existing licenses, agreements and notices
remain in force. In particular, the Supertonic frontend port retains Supertone's
MIT terms and Unicode data retains Unicode License V3.

Apache-2.0 permits commercial and noncommercial reuse of the licensed work and
includes an express contributor patent grant with a patent-litigation termination
provision. It does not grant independent vendor rights or clear redistribution of
an APK, model pack or Qualcomm payload. This is a focused record of the Qoralo
code decision, not a complete repository/dependency rights audit. No per-file
boilerplate sweep or third-party notice removal accompanies the decision.

## Existing upstream terms and distribution boundaries

| Material inspected | Existing terms/evidence | Consequence |
| --- | --- | --- |
| Supertonic Python frontend port | [`SUPERTONIC-PY-LICENSE.txt`](../app/src/main/resources/provider-frontend/SUPERTONIC-PY-LICENSE.txt) is MIT, copyright 2025 Supertone Inc. The frontend identifies itself as a port of pinned `supertonic-py` 1.3.1 (`908a5648`). | Keep Supertone's MIT notice for the adapted code. Our original changes cannot erase its attribution. |
| Unicode normalization data | [`UNICODE-LICENSE.txt`](../app/src/main/resources/provider-frontend/UNICODE-LICENSE.txt), Unicode License V3, alongside generated tables. | Keep the Unicode notice with the data or its associated documentation; these tables are not newly MIT/Apache data. |
| Supertonic 3 model and derived contexts | [Recorded notices](../../experiments/0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/licenses.json) distinguish MIT **sample code** from the pinned model's [OpenRAIL-M license](../../experiments/0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/licenses/LICENSE.OpenRAIL-M). | Model/derivative use and redistribution restrictions remain separate. In particular, do not call the model MIT because its sample archive contains MIT code. The model license also addresses generated output and accountability. |
| Gemma 4 E2B model and deployment artifact | [Pinned experiment-0025 contract](../../experiments/0025-gemma-4-e2b-it-android/protocol/experiment-contract.json) records Apache-2.0 for base revision `3e22461f…` and LiteRT deployment revision `6b78abd0…`; the retained deployment card agrees. | Treat these as separately identified upstream artifacts; retain their applicable licenses/notices. Do not import assumptions about older Gemma releases or imply our code license grants model rights. |
| LiteRT-LM, Gradle wrapper and Maven dependencies | Retained LiteRT-LM source license is Apache-2.0; [`gradlew`](../gradlew) already carries its own Apache notice. App dependencies are listed in [`app/build.gradle.kts`](../app/build.gradle.kts). | Preserve upstream notices and inspect the actual dependency distributions/transitive licenses before a release; this review is not a full dependency bill of materials. |
| ONNX Runtime | Retained 1.27.1 source `LICENSE` is MIT (Microsoft); it also supplies `ThirdPartyNotices.txt`. | Preserve ORT and bundled dependency notices. ORT's MIT license does **not** turn its separately supplied QNN/QAIRT backend libraries into MIT libraries. |
| Qualcomm QAIRT/QNN libraries, headers, tools and compiled payloads | [Experiment 0010](../../experiments/0010-supertonic-qnn-htp-feasibility/README.md) records local-only authorized SDK use and no proprietary payload publication. | Exact redistribution permissions have not been cleared here. Keep those inputs outside Git; do not distribute frozen APKs/contexts or agreements on the strength of our source-code license. Any release needs its own applicable SDK/contract review. |
| Source documents, recordings, screenshots, diagrams and historical model tracks | Independent content/upstream provenance. The Sandyford fixture, for example, contains attributed Wikipedia text, not original app code. | Do not blanket-license these assets. Preserve their provenance and assess content-specific rights separately. |

The local-only notices inspected were:

- `experiments/0037-supertonic-provider-pipeline/.local/upstream/LICENSE`
  (agrees with the committed Supertone notice).
- `experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source/{LICENSE,ThirdPartyNotices.txt}`
  (`LICENSE` read; the separate third-party inventory must accompany any applicable redistribution review).
- `experiments/0025-gemma-4-e2b-it-android/.local/LiteRT-LM/LICENSE` and
  `.local/model/README.md` (Apache runtime text and deployment-card declaration).

These local paths are evidence of this inspection, **not files supplied by a new
clone**. No vendor agreement was accepted or reproduced. Before distributing an
APK, explicitly collect its required third-party notices; Gradle packaging excludes
some `META-INF` license resources, so do not assume an assembled APK already has a
complete notice bundle. None of that prevents documenting the current setup now.
