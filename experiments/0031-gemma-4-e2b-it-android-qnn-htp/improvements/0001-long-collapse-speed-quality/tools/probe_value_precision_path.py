#!/usr/bin/env python3
"""Build/convert a tiny, authored V-norm/cache/attention-read precision fixture.

No checkpoint weights, tokenizer, model inference or device access. Baseline and
candidate differ only in named activation overrides. Raw failures stay retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from value_precision_path import fixture_gate, override_float16, parse_dlc_csv


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def int_encoding(name, scale=0.000625, offset=-32768):
    return {"name": name, "enc_type": "PER_TENSOR", "dtype": "INT", "bw": 16,
            "is_sym": offset == -32768, "scale": [scale], "offset": [float(offset)]}


def create_fixture(root, ar, candidate):
    import numpy as np
    import onnx
    from onnx import TensorProto as T, helper as h, numpy_helper

    width, context = 32, 256
    nodes = [
        h.make_node("Mul", ["v_projected", "v_projected"], ["v_squared"], name="v_square"),
        h.make_node("ReduceMean", ["v_squared"], ["v_mean"], axes=[3], keepdims=1, name="v_mean"),
        h.make_node("Add", ["v_mean", "epsilon"], ["v_variance"], name="v_epsilon"),
        h.make_node("Sqrt", ["v_variance"], ["v_denominator"], name="v_sqrt"),
        h.make_node("Div", ["v_projected", "v_denominator"], ["v_normalized"], name="v_normalize"),
        h.make_node("Transpose", ["v_normalized"], ["v_transposed"], perm=[0, 2, 1, 3], name="v_transpose"),
        h.make_node("Cast", ["v_transposed"], ["cache_out"], to=T.FLOAT16, name="cache_export"),
        h.make_node("Cast", ["cache_in"], ["cache_float_internal"], to=T.FLOAT, name="cache_import"),
        h.make_node("Concat", ["cache_float_internal", "v_transposed"], ["v_joined"], axis=2, name="cache_concat"),
        h.make_node("Softmax", ["scores"], ["probabilities"], axis=3, name="probabilities"),
        h.make_node("MatMul", ["probabilities", "v_joined"], ["attention_read"], name="value_attention"),
    ]
    inputs = [h.make_tensor_value_info("v_projected", T.FLOAT, [1, ar, 1, width]),
              h.make_tensor_value_info("cache_in", T.FLOAT16, [1, 1, context-ar, width]),
              h.make_tensor_value_info("scores", T.FLOAT, [1, 1, ar, context])]
    outputs = [h.make_tensor_value_info("cache_out", T.FLOAT16, [1, 1, ar, width]),
               h.make_tensor_value_info("attention_read", T.FLOAT, [1, 1, ar, width])]
    graph = h.make_graph(nodes, f"value_precision_ar{ar}", inputs, outputs,
                         [numpy_helper.from_array(np.array(1e-6, dtype=np.float32), "epsilon")])
    model = h.make_model(graph, opset_imports=[h.make_opsetid("", 13)], producer_name="gemma-value-precision-fixture")
    model.ir_version = 8
    onnx.checker.check_model(model)
    onnx_path = root / "fixture.onnx"
    onnx.save(model, onnx_path)
    enc = {"version": "1.0.0", "activation_encodings": [
        int_encoding("v_projected"), int_encoding("scores"),
        int_encoding("v_normalized"), int_encoding("v_transposed"),
        int_encoding("v_joined"), int_encoding("attention_read"),
        int_encoding("probabilities", 1.0/65535, 0),
    ], "param_encodings": []}
    edits = []
    if candidate:
        enc, edits = override_float16(enc, {"v_normalized", "v_transposed", "v_joined", "attention_read"})
    enc_path = root / "fixture.encodings"
    enc_path.write_text(json.dumps(enc, indent=2) + "\n")
    return onnx_path, enc_path, {"ar": ar, "width": width, "context": context,
                                 "checkpoint_weights": False, "normalization_epsilon": 1e-6,
                                 "changes": edits, "onnx_sha256": sha256(onnx_path),
                                 "encodings_sha256": sha256(enc_path)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--ar", type=int, choices=(1, 128), required=True)
    p.add_argument("--candidate", action="store_true")
    args = p.parse_args()
    root = args.run_dir.resolve()
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.umask(0o077)
    start = time.monotonic()
    receipt = {"classification": "started", "ar": args.ar, "candidate": args.candidate,
               "sdk": os.environ["QAIRT_SDK_ROOT"], "script_sha256": sha256(__file__),
               "helper_sha256": sha256(Path(__file__).with_name("value_precision_path.py")),
               "inference": False, "phone_access": False}
    def retain():
        receipt["elapsed_seconds"] = time.monotonic() - start
        (root / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    retain()
    try:
        model_path, enc_path, receipt["fixture"] = create_fixture(root, args.ar, args.candidate)
        retain()
        import qairt
        config = {"float_precision": 32, "float_bias_precision": 32,
                  "input_tensor_config": [
                      {"name": "v_projected", "layout": "NONTRIVIAL"},
                      {"name": "cache_in", "layout": "NONTRIVIAL"},
                      {"name": "scores", "layout": "NONTRIVIAL"}],
                  "output_tensor_config": [], "use_quantize_v2": False}
        receipt["conversion_config"] = config
        retain()
        converted = qairt.convert(model_path, encodings=enc_path, backend="HTP", **config)
        dlc = root / "fixture.dlc"
        shutil.copyfile(converted.module.path, dlc)
        receipt["dlc"] = {"path": str(dlc), "bytes": dlc.stat().st_size, "sha256": sha256(dlc)}
        retain()
        csv_path = root / "fixture.csv"
        command = [sys.executable, str(Path(os.environ["QAIRT_SDK_ROOT"]) / "bin/x86_64-linux-clang/qairt-dlc-info"),
                   "-i", str(dlc), "--save", str(csv_path)]
        receipt["inspection_command"] = command
        with (root / "dlc-info.stdout").open("w") as out, (root / "dlc-info.stderr").open("w") as err:
            info = subprocess.run(command, stdout=out, stderr=err, timeout=60, close_fds=True)
        receipt["inspection_exit"] = info.returncode
        if info.returncode:
            raise RuntimeError("DLC inspection failed; raw conversion retained")
        receipt["csv_sha256"] = sha256(csv_path)
        receipt["gate"] = fixture_gate(parse_dlc_csv(csv_path), args.candidate)
        receipt["classification"] = "fixture_dlc_precision_gate_passed" if receipt["gate"]["passed"] else "fixture_dlc_precision_gate_failed"
        retain()
        return 0 if receipt["gate"]["passed"] else 2
    except Exception as error:
        receipt["classification"] = "fixture_error"
        receipt["error"] = {"type": type(error).__name__, "message": str(error)}
        retain()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
