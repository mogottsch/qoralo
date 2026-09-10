# Experiment 0032 tests

From the repository root, run the saved-evidence contract tests with ordinary Python:

```sh
python experiments/0032-qwen-3.5-2b-android-qnn-htp/tests/test_contract.py
```

For the complete CPU/mock suite, use the pinned Torch environment:

```sh
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 \
  artifacts/venv-executorch-1.2/bin/python -m unittest discover \
  -s experiments/0032-qwen-3.5-2b-android-qnn-htp/tests -p 'test_*.py'
```

Neither command performs native QNN execution. The full suite includes tiny CPU graph operations/exports and mock backend calls, not a model campaign.

## Immutable evidence and Python bytecode

`results/**` is hash-bound evidence. Do not import a saved analyzer there with `SourceFileLoader.exec_module`: ordinary Python may write an adjacent `__pycache__/*.pyc`, violating the exact manifest file set.

`test_contract.load_evidence_source` instead compiles the trusted source bytes and executes them in a fresh module namespace. It writes no bytecode and does not change global bytecode policy. The regression explicitly enables bytecode writing, loads a copied real analyzer twice, verifies no files were added, and checks the original evidence bytes stayed unchanged.

`PYTHONDONTWRITEBYTECODE=1` is optional defense in depth, **not required** for these tests. Do not weaken the manifest test with cache exclusions. If a prior test command generated a cache under evidence, remove only the identified generated cache after coordinating with its owner; never clean output tensors or native artifacts.
