# Explicit exception to the retained baseline contract

This note binds **only** frozen candidate `ac4d325f7f5b66ca5ff144590b991775d616c18bfb9ac56065f3c66c6af89fb2`, app `78488901d63032b87d2d575c6bec5b7f578b3a7ee38c92e3c633ed943dcb96ab` and unchanged test `120420d6925283ccf44478b58aef29a12e4575bbf6f1027df9a3d98e83cf2c8c`.

The embedded baseline contract still says:

`namespacePolicy = unchanged-no-new-uses-native-library-no-explicit-fastrpc-dlopen`

Those bytes are retained for baseline identity and unchanged test/limit enforcement. **That descriptive field is overridden for this reviewed derivative:** its effective policy adds exactly one optional public `libcdsprpc.so` uses-native-library declaration. We do not claim an unchanged namespace policy.

All other contract fields remain effective and unchanged. There is no added library payload, explicit FastRPC dlopen/preload, namespace bypass, ADSP/LD change, fallback or inference. Optional installation does not permit CPU execution. Same original signing certificate is verified for baseline app, derivative app and reused test: `9f85ef2878be3a65c2428870ce570dc7d36e125e1b708a21148ecd7a016abad6`.

`namespace-policy-exception.json` records the exact candidate and exception for inclusion beside any new raw collection. The raw embedded contract must remain untouched and be described as the baseline record plus this explicit exception.

Pi's conditional slot permits the one-constructor diagnostic immediately after Nik's exact output approval. No additional build or administrative approval round is required. The signed APK, test, frozen candidate and embedded contract were not modified to add this annotation.
