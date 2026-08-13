#!/usr/bin/env python3
"""Build the exact Kokoro v1.0 static S8S8 QDQ candidate."""
from __future__ import annotations

import argparse
import importlib.metadata
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT_ROOT,
    load_corpus,
    load_json,
    sha256_bytes,
    sha256_file,
    validate_source,
    verify_file,
    write_json,
)


def verify_toolchain(lock_path: Path, wheel_dir: Path, espeak_bin: Path) -> dict[str, Any]:
    lock = load_json(lock_path)
    if platform.python_version() != lock["build_platform"]["python"].removeprefix("CPython "):
        raise RuntimeError(
            f"build requires {lock['build_platform']['python']}, got CPython {platform.python_version()}"
        )
    expected_wheels = {item["filename"] for item in lock["wheels"]}
    actual_wheels = {path.name for path in wheel_dir.glob("*.whl")}
    if actual_wheels != expected_wheels:
        raise RuntimeError(
            "wheelhouse differs from lock; "
            f"missing={sorted(expected_wheels - actual_wheels)}, "
            f"unexpected={sorted(actual_wheels - expected_wheels)}"
        )
    installed: dict[str, str] = {}
    for item in lock["wheels"]:
        wheel = wheel_dir / item["filename"]
        verify_file(wheel, item, f"locked wheel {item['filename']}")
        version = importlib.metadata.version(item["distribution"])
        if version != item["version"]:
            raise RuntimeError(f"installed {item['distribution']} version drift: {version} != {item['version']}")
        installed[item["distribution"]] = version
    frontend = lock["calibration_frontend"]
    verify_file(espeak_bin, {"sha256": frontend["executable_sha256"]}, "pinned espeak-ng executable")
    library = Path(frontend["library"])
    verify_file(library, {"sha256": frontend["library_sha256"]}, "pinned espeak-ng library")
    output = subprocess.check_output([str(espeak_bin), "--version"], text=True).splitlines()[0]
    if frontend["version"] not in output:
        raise RuntimeError(f"unexpected espeak-ng version output: {output}")
    return {
        "python": f"CPython {platform.python_version()}",
        "installed_distributions": installed,
        "wheel_count": len(lock["wheels"]),
        "espeak_ng": output,
        "espeak_executable_sha256": sha256_file(espeak_bin),
        "espeak_library_sha256": sha256_file(library),
    }


def token_map(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        symbol, token_id = line.rsplit(" ", 1)
        values[symbol] = int(token_id)
    return values


def calibration_records(
    source_root: Path, corpus: dict[str, Any], espeak_bin: Path
) -> tuple[list[dict[str, "Any"]], list[dict[str, Any]]]:
    import numpy as np

    tokens = token_map(source_root / "tokens.txt")
    voices = np.memmap(source_root / "voices.bin", dtype=np.float32, mode="r", shape=(53, 510, 1, 256))
    records: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for utterance in corpus["calibration"]:
        completed = subprocess.run(
            [
                str(espeak_bin),
                f"--path={source_root}",
                "-q",
                "--ipa=3",
                "-v",
                "en-us",
                utterance["text"],
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        # Zero-width joiners mark IPA ties rather than model tokens. Remove them first,
        # then normalize eSpeak's punctuation newlines without splitting source text.
        phonemes = re.sub(r"\s+", " ", completed.stdout.replace("\u200d", "")).strip()
        unknown = sorted({symbol for symbol in phonemes if symbol not in tokens})
        if unknown:
            raise RuntimeError(f"calibration phonemes not present in exact tokens.txt: {unknown!r}")
        token_ids = [0, *[tokens[symbol] for symbol in phonemes], 0]
        if len(token_ids) >= 510:
            raise RuntimeError(f"calibration input exceeds style table: {utterance['id']}")
        style = np.asarray(voices[3, len(token_ids)], dtype=np.float32)
        record = {
            "tokens": np.asarray([token_ids], dtype=np.int64),
            "style": style,
            "speed": np.asarray([1.0], dtype=np.float32),
        }
        records.append(record)
        evidence.append(
            {
                "id": utterance["id"],
                "text_sha256": sha256_bytes(utterance["text"].encode("utf-8")),
                "phonemes": phonemes,
                "phonemes_sha256": sha256_bytes(phonemes.encode("utf-8")),
                "token_count_with_boundaries": len(token_ids),
                "token_ids_sha256": sha256_bytes(record["tokens"].astype("<i8").tobytes()),
                "style_row": len(token_ids),
            }
        )
    return records, evidence


class RecordsReader:
    def __init__(self, records: list[dict[str, "Any"]]) -> None:
        self.records = records
        self.rewind()

    def get_next(self) -> dict[str, "Any"] | None:
        return next(self._iterator, None)

    def rewind(self) -> None:
        self._iterator = iter(self.records)


def graph_summary(path: Path) -> tuple[dict[str, int], dict[str, Any]]:
    import numpy as np
    import onnx

    model = onnx.load(str(path), load_external_data=False)
    operations = dict(sorted(Counter(node.op_type for node in model.graph.node).items()))
    initializer_types = Counter()
    initializer_bytes = Counter()
    for tensor in model.graph.initializer:
        type_name = onnx.TensorProto.DataType.Name(tensor.data_type)
        initializer_types[type_name] += 1
        initializer_bytes[type_name] += int(np.asarray(onnx.numpy_helper.to_array(tensor)).nbytes)
    metadata = {entry.key: entry.value for entry in model.metadata_props}
    if "3->af_heart" not in metadata.get("id2speaker", ""):
        raise RuntimeError("candidate metadata no longer proves SID 3 is af_heart")
    return operations, {
        "nodes": len(model.graph.node),
        "initializers": len(model.graph.initializer),
        "initializer_count_by_type": dict(sorted(initializer_types.items())),
        "initializer_bytes_by_type": dict(sorted(initializer_bytes.items())),
        "metadata_proves_sid_3_af_heart": True,
        "model_type": metadata.get("model_type"),
        "version": metadata.get("version"),
    }


def resolve_excluded_nodes(model_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Resolve optional, auditable node-name prefixes against the exact source graph."""
    import onnx

    prefixes = config.get("exclude_node_name_prefixes", [])
    if not isinstance(prefixes, list) or any(not isinstance(prefix, str) or not prefix for prefix in prefixes):
        raise RuntimeError("exclude_node_name_prefixes must be a list of non-empty strings")
    if len(prefixes) != len(set(prefixes)):
        raise RuntimeError("exclude_node_name_prefixes contains duplicates")
    model = onnx.load(str(model_path), load_external_data=False)
    eligible_types = set(config["op_types_to_quantize"])
    names: list[str] = []
    matched_prefixes: set[str] = set()
    for node in model.graph.node:
        if node.op_type not in eligible_types:
            continue
        for prefix in prefixes:
            if node.name.startswith(prefix):
                if not node.name:
                    raise RuntimeError("an excluded eligible node has no stable name")
                names.append(node.name)
                matched_prefixes.add(prefix)
                break
    missing = set(prefixes) - matched_prefixes
    if missing:
        raise RuntimeError(f"exclusion prefixes matched no eligible source nodes: {sorted(missing)}")
    if len(names) != len(set(names)):
        raise RuntimeError("resolved exclusion node names are not unique")
    return {
        "prefixes": prefixes,
        "node_names": names,
        "node_count": len(names),
        "node_names_sha256": sha256_bytes("\n".join(names).encode("utf-8")),
    }


def effective_quantization_audit(
    source_path: Path,
    candidate_path: Path,
    config: dict[str, Any],
    exclusions: dict[str, Any],
) -> dict[str, Any]:
    """Prove which requested operators received weight QDQ in the emitted graph.

    QDQ leaves Conv/MatMul/Gemm nodes in the graph, so operation counts alone do not
    prove the effective mixed-precision boundary. A selected node must consume its
    weight through DequantizeLinear; an excluded node must retain the exact FP32 source
    weight input. Upstream activations may still carry quantization effects.
    """
    import onnx

    source = onnx.load(str(source_path), load_external_data=False)
    candidate = onnx.load(str(candidate_path), load_external_data=False)
    eligible_types = set(config["op_types_to_quantize"])
    excluded_names = set(exclusions["node_names"])

    source_nodes: dict[str, Any] = {}
    for node in source.graph.node:
        if node.op_type not in eligible_types:
            continue
        if not node.name or node.name in source_nodes or len(node.input) < 2:
            raise RuntimeError(f"eligible source node lacks a unique name or weight input: {node.name!r}")
        source_nodes[node.name] = node
    if not excluded_names <= set(source_nodes):
        raise RuntimeError("resolved exclusions are not a subset of eligible source nodes")

    candidate_nodes = {
        node.name: node for node in candidate.graph.node if node.op_type in eligible_types
    }
    if set(candidate_nodes) != set(source_nodes):
        raise RuntimeError("quantization changed the eligible operator name set")
    producers = {output: node for node in candidate.graph.node for output in node.output}
    source_initializers = {tensor.name: tensor for tensor in source.graph.initializer}
    candidate_initializers = {tensor.name: tensor for tensor in candidate.graph.initializer}

    expected_quantized = set(source_nodes) - excluded_names
    effective_quantized: list[str] = []
    effective_by_type: Counter[str] = Counter()
    excluded_with_activation_qdq = 0
    for name, source_node in source_nodes.items():
        node = candidate_nodes[name]
        if node.op_type != source_node.op_type:
            raise RuntimeError(f"eligible operator type drifted for {name}")
        weight_producer = producers.get(node.input[1])
        weight_has_qdq = weight_producer is not None and weight_producer.op_type == "DequantizeLinear"
        if name in expected_quantized:
            if not weight_has_qdq:
                raise RuntimeError(f"requested node did not receive weight QDQ: {name}")
            effective_quantized.append(name)
            effective_by_type[node.op_type] += 1
            continue

        if weight_has_qdq or node.input[1] != source_node.input[1]:
            raise RuntimeError(f"excluded node weight was quantized or rewired: {name}")
        source_weight = source_initializers.get(source_node.input[1])
        candidate_weight = candidate_initializers.get(node.input[1])
        if source_weight is not None and (
            candidate_weight is None
            or source_weight.data_type != onnx.TensorProto.FLOAT
            or candidate_weight.data_type != onnx.TensorProto.FLOAT
        ):
            raise RuntimeError(f"excluded node did not retain a FLOAT initializer: {name}")
        activation_producer = producers.get(node.input[0])
        excluded_with_activation_qdq += int(
            activation_producer is not None and activation_producer.op_type == "DequantizeLinear"
        )

    source_by_type = Counter(node.op_type for node in source_nodes.values())
    excluded_by_type = Counter(source_nodes[name].op_type for name in excluded_names)
    quantized_names = sorted(effective_quantized)
    excluded_sorted = sorted(excluded_names)
    return {
        "audit_method": "eligible node-name preservation plus weight-input DequantizeLinear tracing",
        "source_eligible_node_count": len(source_nodes),
        "source_eligible_count_by_type": dict(sorted(source_by_type.items())),
        "requested_excluded_node_count": len(excluded_names),
        "requested_excluded_count_by_type": dict(sorted(excluded_by_type.items())),
        "expected_quantized_node_count": len(expected_quantized),
        "effective_weight_qdq_node_count": len(effective_quantized),
        "effective_weight_qdq_count_by_type": dict(sorted(effective_by_type.items())),
        "effective_weight_qdq_node_names_sha256": sha256_bytes(
            "\n".join(quantized_names).encode("utf-8")
        ),
        "excluded_node_names_sha256": sha256_bytes("\n".join(excluded_sorted).encode("utf-8")),
        "excluded_nodes_with_weight_qdq": 0,
        "excluded_nodes_retaining_source_float_weight_input": len(excluded_names),
        "excluded_nodes_with_upstream_activation_qdq": excluded_with_activation_qdq,
        "eligible_node_name_set_preserved": True,
        "all_requested_nodes_have_weight_qdq": set(effective_quantized) == expected_quantized,
        "all_excluded_nodes_retain_unquantized_weights": True,
        "precision_boundary_note": (
            "Excluded nodes retain their original FLOAT weight inputs and are not selected for "
            "weight QDQ. Some can consume activations dequantized after upstream quantized nodes, "
            "so exclusion does not erase quantization effects produced before the boundary."
        ),
    }


def checker_probe(source_path: Path, candidate_path: Path) -> dict[str, Any]:
    """Retain the known ORT-quantizer ordering diagnostic without hiding it."""
    import onnx

    onnx.checker.check_model(str(source_path), full_check=True)
    try:
        onnx.checker.check_model(str(candidate_path), full_check=True)
    except onnx.checker.ValidationError as caught:
        message = str(caught)
        required = ("topologically sorted", "/SplitToSequence_output_0", "/SequenceAt", "/Loop")
        if not all(fragment in message for fragment in required):
            raise RuntimeError(f"candidate checker failed differently: {message}") from caught
        candidate_result = {
            "passed": False,
            "error_type": type(caught).__name__,
            "error": message,
        }
    else:
        candidate_result = {"passed": True, "error_type": None, "error": None}
    return {
        "tool": f"onnx {onnx.__version__}",
        "full_check": True,
        "source_passed": True,
        "candidate": candidate_result,
        "status": (
            "candidate_passed"
            if candidate_result["passed"]
            else "known_quantizer_outer_scope_topological_order_limitation"
        ),
        "handling": (
            "The exact source passes the checker. ONNX Runtime quantization moves an outer-scope "
            "SplitToSequence producer after its consuming Loop, which the checker rejects even "
            "though pinned ONNX Runtime CPU and sherpa-onnx sessions construct and infer. The "
            "diagnostic is retained as a structural limitation; executable runtime probes are "
            "the host compatibility gate."
        ),
    }


def runtime_probe(model_path: Path, calibration: dict[str, "Any"]) -> dict[str, Any]:
    import numpy as np
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    started = time.perf_counter()
    session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
    load_seconds = time.perf_counter() - started
    started = time.perf_counter()
    outputs = session.run(None, calibration)
    inference_seconds = time.perf_counter() - started
    if not outputs or outputs[0].size == 0 or not np.all(np.isfinite(outputs[0])):
        raise RuntimeError("standalone ONNX Runtime CPU probe returned invalid audio")
    return {
        "runtime": f"onnxruntime {ort.__version__}",
        "provider": session.get_providers()[0],
        "num_threads": 1,
        "load_seconds_context_only": load_seconds,
        "inference_seconds_context_only": inference_seconds,
        "output_samples": int(outputs[0].size),
        "output_finite": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=EXPERIMENT_ROOT / "generated" / "model.static-qdq-s8s8-generator-fp32.onnx",
    )
    parser.add_argument("--report", type=Path, default=EXPERIMENT_ROOT / "reports" / "quantization-report.json")
    parser.add_argument("--corpus", type=Path, default=EXPERIMENT_ROOT / "corpus.json")
    parser.add_argument("--config", type=Path, default=EXPERIMENT_ROOT / "quantization-config.json")
    parser.add_argument("--source-manifest", type=Path, default=EXPERIMENT_ROOT / "source-manifest.json")
    parser.add_argument("--toolchain-lock", type=Path, default=EXPERIMENT_ROOT / "toolchain.lock.json")
    parser.add_argument("--wheel-dir", type=Path, default=EXPERIMENT_ROOT / ".cache" / "wheels")
    parser.add_argument("--espeak-bin", type=Path, default=Path("/usr/bin/espeak-ng"))
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    source_evidence = validate_source(source_root, args.source_manifest, verify_archive=True)
    tools = verify_toolchain(args.toolchain_lock, args.wheel_dir, args.espeak_bin)
    corpus = load_corpus(args.corpus)
    config = load_json(args.config)
    candidate_name = config.get("candidate_name")
    if not isinstance(candidate_name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]+", candidate_name):
        raise RuntimeError("quantization config requires a filesystem-safe candidate_name")
    calibration, calibration_evidence = calibration_records(source_root, corpus, args.espeak_bin)
    exclusions = resolve_excluded_nodes(source_root / "model.onnx", config)

    from onnxruntime.quantization import CalibrationMethod, QuantFormat, QuantType, quantize_static

    formats = {"QDQ": QuantFormat.QDQ}
    types = {"QInt8": QuantType.QInt8}
    methods = {"MinMax": CalibrationMethod.MinMax}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    temporary.unlink(missing_ok=True)
    started = time.perf_counter()
    quantize_static(
        str(source_root / "model.onnx"),
        str(temporary),
        RecordsReader(calibration),
        quant_format=formats[config["quant_format"]],
        op_types_to_quantize=config["op_types_to_quantize"],
        per_channel=config["per_channel"],
        reduce_range=config["reduce_range"],
        activation_type=types[config["activation_type"]],
        weight_type=types[config["weight_type"]],
        nodes_to_exclude=exclusions["node_names"],
        calibrate_method=methods[config["calibration_method"]],
        extra_options=config["extra_options"],
    )
    elapsed = time.perf_counter() - started
    operations, graph = graph_summary(temporary)
    audit = effective_quantization_audit(source_root / "model.onnx", temporary, config, exclusions)
    checker = checker_probe(source_root / "model.onnx", temporary)
    probe = runtime_probe(temporary, calibration[0])
    temporary.replace(args.output)

    source_size = (source_root / "model.onnx").stat().st_size
    output_size = args.output.stat().st_size
    report = {
        "schema_version": 1,
        "status": "candidate_built_host_cpu_probe_passed",
        "deployment_variant": "kokoro-multi-lang-v1_0",
        "candidate_name": candidate_name,
        "source": source_evidence,
        "voice": {"speaker_id": 3, "speaker": "af_heart", "proven_from_exact_model_metadata": True},
        "inputs": {
            "corpus_path": args.corpus.name,
            "corpus_sha256": sha256_file(args.corpus),
            "quantization_config_path": args.config.name,
            "quantization_config_sha256": sha256_file(args.config),
            "calibration": calibration_evidence,
        },
        "method": config,
        "resolved_node_exclusions": exclusions,
        "tools": tools,
        "candidate": {
            "path": args.output.resolve().relative_to(EXPERIMENT_ROOT).as_posix(),
            "bytes": output_size,
            "sha256": sha256_file(args.output),
            "source_model_bytes": source_size,
            "source_model_sha256": sha256_file(source_root / "model.onnx"),
            "size_reduction_bytes": source_size - output_size,
            "size_reduction_fraction": (source_size - output_size) / source_size,
            "graph": graph,
            "operation_counts": operations,
            "effective_quantization_audit": audit,
        },
        "validation": {
            "standalone_cpu_runtime_probe": probe,
            "onnx_checker": checker,
            "sherpa_cpu_synthesis": "run scripts/synthesize.py for both variants before the quality report",
        },
        "timing_context_only": {
            "quantization_seconds": elapsed,
            "not_android_evidence": True,
        },
        "android_rtf_pss": {
            "status": "deferred_until_quality_gate_passes_and_candidate_is_deployed",
            "evidence_in_this_report": False,
        },
    }
    write_json(args.report, report)
    print(f"candidate: {args.output} ({output_size} bytes, {report['candidate']['sha256']})")
    print(f"report: {args.report}")


if __name__ == "__main__":
    main()
