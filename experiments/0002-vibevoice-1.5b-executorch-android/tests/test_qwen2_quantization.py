#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import torch

EXPORT_DIR = Path(__file__).resolve().parents[1] / "export"
sys.path.insert(0, str(EXPORT_DIR))

from qwen2_quantization import (  # noqa: E402
    deployment_benefit,
    quantization_spec,
    quantize_dynamic_int8,
    quantized_comparison,
)


class Qwen2QuantizationTests(unittest.TestCase):
    def test_locked_spec_is_dynamic_int8_and_per_channel_weight(self):
        spec = quantization_spec()
        self.assertEqual(spec["activation"]["dtype"], "int8")
        self.assertIn("dynamic", spec["activation"]["granularity"])
        self.assertEqual(spec["weight"]["dtype"], "int8")
        self.assertIn("per-output-channel", spec["weight"]["granularity"])
        self.assertIn("pinned prefill/decode fixtures", spec["calibration"])

    def test_pt2e_quantizes_linear_without_fallback(self):
        torch.manual_seed(4)
        module = torch.nn.Linear(16, 8).eval()
        inputs = (torch.randn(1, 3, 16),)
        converted, coverage = quantize_dynamic_int8(module, inputs)
        self.assertEqual(coverage["eligible_linear_ops"], 1)
        self.assertEqual(coverage["quantized_linear_ops"], 1)
        self.assertEqual(coverage["fallback_linear_ops"], 0)
        self.assertTrue(coverage["accepted"])
        self.assertEqual(tuple(converted(*inputs).shape), (1, 3, 8))

    def test_comparison_requires_exact_token_and_all_finite(self):
        names = ["last_hidden_state", "next_token_logits", "layer_00_key"]
        expected = (
            torch.tensor([[[1.0, 2.0]]]),
            torch.tensor([[0.1, 0.9, 0.2]]),
            torch.ones(1, 1, 2, 2),
        )
        accepted = quantized_comparison(expected, expected, names)
        self.assertTrue(accepted["accepted"])
        wrong_token = (expected[0], torch.tensor([[1.1, 0.9, 0.2]]), expected[2])
        self.assertFalse(quantized_comparison(wrong_token, expected, names)["accepted"])
        nonfinite = (expected[0], expected[1], torch.full_like(expected[2], float("nan")))
        self.assertFalse(quantized_comparison(nonfinite, expected, names)["accepted"])

    def test_deployment_benefit_rejects_coverage_or_weak_size_reduction(self):
        covered = {"accepted": True}
        fallback = {"accepted": False}
        self.assertTrue(deployment_benefit(int8_bytes=50, fp32_bytes=100, coverages=[covered])["accepted"])
        self.assertFalse(deployment_benefit(int8_bytes=50, fp32_bytes=100, coverages=[fallback])["accepted"])
        weak = deployment_benefit(int8_bytes=80, fp32_bytes=100, coverages=[covered])
        self.assertFalse(weak["accepted"])
        self.assertIn("fallback/size", weak["rejection_reason"])

    def test_comparison_rejects_incomplete_abi(self):
        with self.assertRaisesRegex(ValueError, "equal lengths"):
            quantized_comparison((torch.zeros(1),), (torch.zeros(1),), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
