# Android GPU blocker

No GPU benchmark result is claimed. The bounded Android smoke stopped before inference because the pinned dedicated GPU artifact could not create an engine in the pinned official LiteRT-LM v0.16.1 source build.

The staged artifact matched the locked `a53a5900…3c` SHA-256 and 2,008,432,640-byte size. LiteRT-LM inspected it, detected an Artisan text-decoder section, and changed the requested `GPU` backend to `GPU_ARTISAN`. `EngineFactory` then failed exactly because that backend prefers `kAdvancedLegacyTfLite` or `kLegacyTfLite`, while the pinned open-source build registered only `kAdvancedLiteRTCompiledModel`.

The failure occurred before prompt inventory and before any logical request. No output, timing, or CPU fallback is presented as GPU evidence. Raw stderr, pinned-source excerpts, artifact/runner/workload hashes, phone conditions, lock lifecycle, and verified scoped cleanup are retained here.

## Decision required

The locked arm cannot continue as written. A maintainer must choose one of these explicit route changes:

1. authorize testing the generic 2,588,147,712-byte `gemma-4-E2B-it.litertlm` artifact with `Backend::GPU`; the pinned deployment model card reports an Android GPU model size of 2,583 MB, which matches this generic artifact rather than the 2,008 MB dedicated GPU artifact; or
2. provide or authorize a LiteRT-LM Android runtime route that registers a supported legacy TFLite engine for the pinned Artisan GPU artifact.

Neither change was made silently because each changes the locked route. The remote experiment root was removed and verified absent, and `phone.lock` was released.
