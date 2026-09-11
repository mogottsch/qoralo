#!/usr/bin/env python3
"""Pure helpers for a scoped post-V-projection FP16 precision island.

These helpers do not load the SDK/model. Explicit FLOAT16 activation overrides
also require the consumer's coupled dtypes to be inspected in the resulting DLC.
"""
from __future__ import annotations

import copy
import csv
import gzip
from pathlib import Path
import re


def float16_encoding(name: str) -> dict:
    return {"name": name, "enc_type": "PER_TENSOR", "dtype": "FLOAT", "bw": 16}


def override_float16(encodings: dict, names: set[str]) -> tuple[dict, list[dict]]:
    """Only replace/insert explicitly named v1 activation entries; retain params."""
    if encodings.get("version") != "1.0.0":
        raise ValueError("requires the retained v1.0.0 encoding format, not v2 conversion")
    if not names or any(not isinstance(n, str) or not n for n in names):
        raise ValueError("explicit nonempty tensor-name set required")
    original = encodings["activation_encodings"]
    if len({e["name"] for e in original}) != len(original):
        raise ValueError("duplicate activation encoding names")
    result = copy.deepcopy(encodings)
    changes = []
    found = set()
    entries = result["activation_encodings"]
    for i, entry in enumerate(entries):
        name = entry["name"]
        if name in names:
            found.add(name)
            new = float16_encoding(name)
            changes.append({"name": name, "before": copy.deepcopy(entry), "after": new})
            entries[i] = new
    for name in sorted(names - found):
        new = float16_encoding(name)
        changes.append({"name": name, "before": None, "after": new})
        entries.append(new)
    assert result.get("param_encodings") == encodings.get("param_encodings")
    return result, sorted(changes, key=lambda c: c["name"])


_TENSOR = re.compile(r"^(.*?) \(data type: ([^;]+); tensor dimension: \[([^\]]*)\]; tensor type: ([^)]+)\)")


def parse_dlc_csv(path: Path) -> dict:
    """Read actual metadata, never infer precision from a tensor's name."""
    opener = gzip.open if path.suffix == ".gz" else open
    ops, cur, mode = [], None, None
    ios = {"input": {}, "output": {}}
    with opener(path, "rt", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if row[0] in ("Input Name", "Output Name"):
                mode = "input" if row[0] == "Input Name" else "output"
                cur = None
            elif mode:
                if row[0].startswith("Total "):
                    mode = None
                elif len(row) >= 4:
                    ios[mode][row[0]] = {"dimensions": row[1], "datatype": row[2], "encoding": row[3]}
            elif len(row) >= 8:
                if row[0].isdigit():
                    cur = {"id": int(row[0]), "name": row[1], "type": row[2],
                           "first_line": reader.line_num, "last_line": reader.line_num,
                           "inputs": [], "outputs": [], "parameters": []}
                    ops.append(cur)
                if cur is None:
                    continue
                cur["last_line"] = reader.line_num
                for col, key in ((3, "inputs"), (4, "outputs")):
                    if row[col]:
                        match = _TENSOR.match(row[col])
                        if not match:
                            raise ValueError(f"unrecognized tensor metadata: {row[col]}")
                        cur[key].append(dict(zip(("name", "datatype", "dimensions", "tensor_type"), match.groups())))
                if row[7]:
                    cur["parameters"].append(row[7])
    if not ops:
        raise ValueError("CSV contains no operators")
    return {"operators": ops, "io": ios}


def fixture_gate(graph: dict, expected_fp16: bool, cache_output_name: str = "cache_out") -> dict:
    """Critical claim gate: internal value production AND both MatMul operands."""
    ops = graph["operators"]
    producers = {t["name"]: op for op in ops for t in op["outputs"]}
    mm = [op for op in ops if op["type"] == "MatMul"]
    cats = [op for op in ops if op["type"] == "Concat"]
    issues = []
    if len(mm) != 1 or len(cats) != 1:
        issues.append("expected one dynamic value MatMul and one cache Concat")
    if graph["io"]["output"].get(cache_output_name, {}).get("datatype") != "Float_16":
        issues.append("cache export is not Float16")
    export_path = []
    pending, seen = [cache_output_name], set()
    while pending:
        name = pending.pop()
        op = producers.get(name)
        if op is None or op["id"] in seen:
            continue
        seen.add(op["id"])
        export_path.append(op)
        # Input values represent the quantized V-projection boundary, not weights.
        pending.extend(t["name"] for t in op["inputs"] if t["tensor_type"] != "STATIC")
    postnorm_quantize = [op for op in export_path if op["type"] in ("Convert", "Quantize")
                        and any(t["datatype"] in ("uFxp_16", "sFxp_16", "uFxp_8", "sFxp_8") for t in op["outputs"])]
    if expected_fp16:
        if postnorm_quantize:
            issues.append("fixed-point conversion remains on normalized-value export path")
        if mm and any(t["datatype"] != "Float_16" for t in mm[0]["inputs"] + mm[0]["outputs"]):
            issues.append("value MatMul coupled operands/output not all Float16")
        if cats and any(t["datatype"] != "Float_16" for t in cats[0]["inputs"] + cats[0]["outputs"]):
            issues.append("cache Concat operands/output not all Float16")
    else:
        if not postnorm_quantize:
            issues.append("control failed to demonstrate retained producer quantization")
        if mm and not any(t["datatype"] == "uFxp_16" for t in mm[0]["inputs"]):
            issues.append("control failed to demonstrate quantized value read")
    return {"passed": not issues, "issues": issues, "expected_fp16_island": expected_fp16,
            "export_path": export_path, "concat": cats, "value_matmul": mm,
            "physical_execution": False, "full_model_precision_proven": False}
