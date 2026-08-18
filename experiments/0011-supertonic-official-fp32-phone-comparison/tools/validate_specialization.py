#!/usr/bin/env python3
"""Prove that an I/O-shape specialization did not alter executable graph content."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import onnx


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("specialized", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = onnx.load(str(args.source), load_external_data=True)
    derived = onnx.load(str(args.specialized), load_external_data=True)

    source_nodes = [digest_bytes(node.SerializeToString()) for node in source.graph.node]
    derived_nodes = [digest_bytes(node.SerializeToString()) for node in derived.graph.node]
    source_initializers = [digest_bytes(item.SerializeToString()) for item in source.graph.initializer]
    derived_initializers = [digest_bytes(item.SerializeToString()) for item in derived.graph.initializer]
    source_ops = [(node.domain, node.op_type) for node in source.graph.node]
    derived_ops = [(node.domain, node.op_type) for node in derived.graph.node]
    checks = {
        "ordered_nodes_byte_identical": source_nodes == derived_nodes,
        "ordered_initializers_byte_identical": source_initializers == derived_initializers,
        "ordered_operator_sequence_identical": source_ops == derived_ops,
        "graph_input_names_identical": [x.name for x in source.graph.input] == [x.name for x in derived.graph.input],
        "graph_output_names_identical": [x.name for x in source.graph.output] == [x.name for x in derived.graph.output],
    }
    report = {
        "schema_version": 1,
        "claim": "only graph I/O shapes were specialized; executable nodes and weights are unchanged",
        "source": {"path": str(args.source), "sha256": digest_file(args.source)},
        "specialized": {"path": str(args.specialized), "sha256": digest_file(args.specialized)},
        "counts": {"nodes": len(source_nodes), "initializers": len(source_initializers)},
        "checks": checks,
    }
    if not all(checks.values()):
        raise SystemExit(json.dumps(report, indent=2))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
