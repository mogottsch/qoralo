# Non-counted GPU launch diagnostic — missing cache directory

After the provider-bound smoke passed, the first canonical orchestration staged exact inputs but omitted creation of its configured GPU cache directory. LiteRT loaded and registered the GPU accelerator and fully delegated all 2,068 decode nodes to one `LITERT_CL` partition, then failed during Engine setup because the weight-cache path's parent did not exist.

No prompt inventory, checkpoint, or logical request was produced. Raw setup logs were pulled before the scoped root was removed and verified absent. This attempt is never resumed or counted. The succeeding canonical campaign was staged entirely fresh with an explicit writable-cache preflight.
