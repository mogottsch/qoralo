from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parents[1]
WORKLOADS = ROOT / "protocols/android-llm-benchmark/workloads/inference-v1"

spec = importlib.util.spec_from_file_location("render_workloads", EXP / "tools/render_workloads.py")
assert spec and spec.loader
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HandoverEvidenceTest(unittest.TestCase):
    def test_renderer_reproduces_retained_prompts(self) -> None:
        for tier in ("short", "medium", "long"):
            workload = json.loads((WORKLOADS / f"{tier}.json").read_bytes())
            expected = EXP / "results/host-smoke/rendered" / f"{tier}.txt"
            self.assertEqual(expected.read_bytes(), renderer.render(workload["messages"]))

    def test_host_output_is_hash_bound_and_host_only(self) -> None:
        result = json.loads((EXP / "results/host-smoke/result.json").read_text())
        self.assertFalse(result["android_evidence"])
        self.assertEqual(171, result["prompt"]["input_tokens"])
        self.assertEqual(
            result["generation"]["output_sha256"],
            sha(EXP / "results/host-smoke/output.txt"),
        )
        self.assertEqual(64, result["generation"]["ceiling_tokens"])

    def test_pinned_model_identity(self) -> None:
        result = json.loads((EXP / "results/host-smoke/result.json").read_text())
        artifact = result["model_artifact"]
        self.assertEqual(1674455040, artifact["bytes"])
        self.assertEqual(
            "02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed",
            artifact["sha256"],
        )
        self.assertEqual(
            "5c0d18881e0e9794c96b2602736b758bac9d9388",
            result["runtime"]["revision"],
        )


if __name__ == "__main__":
    unittest.main()
