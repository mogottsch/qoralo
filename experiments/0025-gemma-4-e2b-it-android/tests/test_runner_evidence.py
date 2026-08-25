#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "finalize_runner_evidence", ROOT / "tools" / "finalize_runner_evidence.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PersistenceFirstRegressionTest(unittest.TestCase):
    def test_successful_output_survives_empty_optional_benchmark_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            destination = base / "result"
            (source / "outputs").mkdir(parents=True)
            (source / "outputs" / "short.txt").write_text("A sensible response.\n")
            for tier in ("short", "medium", "long"):
                (source / f"rendered-{tier}.txt").write_text(f"rendered {tier}\n")
            raw = {
                "prompts": {
                    tier: {
                        "rendered_relative_path": f"rendered-{tier}.txt",
                        "token_ids": [2, 3, 4],
                    }
                    for tier in ("short", "medium", "long")
                },
                "runs": [
                    {
                        "id": "short-01",
                        "output_relative_path": "outputs/short.txt",
                        "emitted_token_ids": [10, 11, 12],
                        "runtime_benchmark_info": {
                            "prefill_turns_before": 0,
                            "prefill_turns_after": 0,
                            "decode_turns_before": 0,
                            "decode_turns_after": 0,
                        },
                        "timing": {"prefill_seconds": None},
                        "missing_reasons": {
                            "timing.prefill_seconds": "optional runtime turn absent"
                        },
                    }
                ],
            }
            (source / "runner-result.json").write_text(json.dumps(raw))

            result = MODULE.finalize(
                source, destination, "host_smoke", True, None
            )

            output = destination / result["runs"][0]["output"]["path"]
            self.assertEqual("A sensible response.\n", output.read_text())
            self.assertIsNone(result["runs"][0]["timing"]["prefill_seconds"])
            self.assertEqual(
                0,
                result["runs"][0]["runtime_benchmark_info"]["decode_turns_after"],
            )
            self.assertEqual(
                {"looks_sensible": True, "issue_notes": None},
                result["runs"][0]["output_sanity"],
            )


if __name__ == "__main__":
    unittest.main()
