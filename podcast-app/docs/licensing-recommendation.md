# Own-code licensing recommendation

**Decision proposal only. No project license has been selected or granted by this
page.** No `LICENSE` file or repository visibility change is part of this work.
Existing third-party notices remain in force. This is a focused review of the
Qoralo app route, not a legal clearance of every historical experiment or asset.

## Recommendation and alternatives

Recommend **Apache-2.0 for the original Qoralo application code, original tests and
original tooling under `podcast-app/` that Moritz has authority to license**.
It permits commercial and noncommercial reuse and includes an express contributor
patent grant with a patent-litigation termination provision. That is useful for
reusable Android/native integration code; it does not grant Qualcomm or model
vendor patents, waive SDK terms, or require downstream applications to open their
own code. Preserve required upstream licenses/attribution alongside our license.

| Option | Reason to choose it | Tradeoff |
| --- | --- | --- |
| **Apache-2.0 (recommended)** | Permissive reuse with explicit contributor patent terms. | Longer license; preserve applicable notices and modification notices. |
| **MIT** | Prefer the shortest, familiar permissive license. | No express patent-license clause; the copyright/permission notice must accompany copies or substantial portions. Does not replace any upstream notice. |
| **Keep own-code licensing undecided** | Moritz does not yet want to grant broad reuse rights. | No general project permission to reuse is provided. Public visibility alone would not make the original code open source. |

**Only needed input from Moritz:** choose Apache-2.0, MIT, or hold; confirm the
copyright holder name/year and that he can authorize licensing the original work
(including any employer/other-contributor interests). Agent-session names and Git
authorship are not proof of ownership. If chosen, a follow-up can add the scoped
license, attribution inventory and appropriate file notices. Do not apply a
repository-wide blanket to the archive, model derivatives, data or external art.
The setup guide can be published independently of this decision.

## What stays separate, whichever option is chosen

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
