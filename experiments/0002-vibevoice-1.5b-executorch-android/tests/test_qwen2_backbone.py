#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import torch
from transformers import DynamicCache, Qwen2Config
from transformers.models.qwen2.modeling_qwen2 import Qwen2Model

EXPORT_DIR = Path(__file__).resolve().parents[1] / "export"
sys.path.insert(0, str(EXPORT_DIR))

from qwen2_backbone import (  # noqa: E402
    Qwen2Decode,
    Qwen2Prefill,
    Qwen2PrefillFinal,
    Qwen2PrefillLayer,
    Qwen2PrefillPrepare,
    SpeakerConditioning,
    cache_tensor_names,
    flatten_cache,
)
from diagnose_qwen2 import (  # noqa: E402
    EXPECTED_NAMES,
    aggregate_details,
    evaluate_acceptance,
)
from qwen2_checkpoint import TiedLMHead  # noqa: E402
from validate_qwen2_fixtures import compare_tuple  # noqa: E402
from validate_qwen2_pte import compare_outputs  # noqa: E402
from qwen2_android_io import _validate_control  # noqa: E402


class Qwen2BackboneTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(7)
        self.config = Qwen2Config(
            vocab_size=32,
            hidden_size=16,
            intermediate_size=32,
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
            max_position_embeddings=32,
            sliding_window=None,
            use_sliding_window=False,
            _attn_implementation="eager",
        )
        self.backbone = Qwen2Model(self.config).eval()
        self.lm_head = torch.nn.Linear(16, 32, bias=False).eval()
        self.lm_head.weight = self.backbone.embed_tokens.weight
        options = {
            "num_hidden_layers": 2,
            "num_key_value_heads": 2,
            "head_dim": 4,
            "cache_capacity": 8,
        }
        self.prefill = Qwen2Prefill(self.backbone, self.lm_head, **options).eval()
        self.decode = Qwen2Decode(self.backbone, self.lm_head, **options).eval()

    def test_cache_order_is_layer_then_key_value(self):
        self.assertEqual(
            cache_tensor_names(2),
            ["layer_00_key", "layer_00_value", "layer_01_key", "layer_01_value"],
        )

    def test_speaker_conditioning_replaces_only_selected_positions(self):
        tokens = torch.arange(24, dtype=torch.float32).reshape(1, 3, 8)
        speakers = torch.full_like(tokens, -3)
        mask = torch.tensor([[False, True, False]])
        actual = SpeakerConditioning()(tokens, speakers, mask)
        torch.testing.assert_close(actual[:, 0], tokens[:, 0])
        torch.testing.assert_close(actual[:, 1], speakers[:, 1])
        torch.testing.assert_close(actual[:, 2], tokens[:, 2])

    def test_tied_lm_head_uses_embedding_weight(self):
        hidden = torch.randn(1, 16)
        head = TiedLMHead(self.backbone.embed_tokens.weight)
        torch.testing.assert_close(
            head(hidden),
            torch.nn.functional.linear(hidden, self.backbone.embed_tokens.weight),
        )
        self.assertIs(head.weight, self.backbone.embed_tokens.weight)

    def test_full_output_comparison_checks_every_cache(self):
        expected = (torch.ones(1), torch.full((1,), 2.0), torch.full((1,), 3.0))
        result = compare_tuple(
            tuple(value + 1e-6 for value in expected),
            expected,
            label="tiny",
            atol=1e-5,
            rtol=1e-4,
        )
        self.assertEqual(result["outputs"], 3)
        self.assertTrue(result["allclose"])
        with self.assertRaises(AssertionError):
            compare_tuple(
                (*expected[:2], torch.full((1,), 4.0)),
                expected,
                label="tiny",
                atol=1e-5,
                rtol=1e-4,
            )

    def test_pte_comparison_preserves_strict_mismatch_details(self):
        expected = tuple(torch.zeros(1) for _ in range(58))
        actual = (*expected[:57], torch.full((1,), 2e-5))
        result = compare_outputs(actual, expected, atol=1e-5, rtol=1e-4)
        self.assertFalse(result["allclose"])
        self.assertEqual(result["mismatch_count"], 1)
        self.assertEqual(result["output_details"][-1]["name"], "layer_27_value")
        self.assertTrue(result["all_finite"])

    def test_diagnostic_aggregation_weights_means_and_counts_mismatches(self):
        expected = tuple(torch.zeros(2) for _ in range(58))
        actual = list(expected)
        actual[0] = torch.tensor([2e-5, 0.0])
        actual[2] = torch.tensor([3e-5, 3e-5])
        comparison = compare_outputs(tuple(actual), expected, atol=1e-5, rtol=1e-4)
        components = aggregate_details(comparison["output_details"])
        self.assertEqual(components["last_hidden_state"]["mismatch_count"], 1)
        self.assertEqual(components["cache"]["mismatch_count"], 2)
        self.assertEqual(components["cache"]["outputs"], 56)
        self.assertAlmostEqual(
            components["cache"]["mean_abs_error"], 6e-5 / 112, places=12
        )

    def test_non_finite_output_is_rejected(self):
        expected = tuple(torch.zeros(1) for _ in range(58))
        actual = (*expected[:57], torch.tensor([float("nan")]))
        comparison = compare_outputs(actual, expected, atol=1e-5, rtol=1e-4)
        self.assertFalse(comparison["all_finite"])
        self.assertEqual(comparison["mismatch_count"], 1)
        self.assertEqual(comparison["max_abs_error"], float("inf"))
        self.assertFalse(evaluate_acceptance(comparison)["bounded_xnnpack_accepted"])

    def test_bounded_acceptance_preserves_strict_failure(self):
        expected = tuple(torch.zeros(1) for _ in range(58))
        actual = tuple(
            torch.tensor([8e-5 if name != "layer_00_key" else 4.7e-4])
            for name in EXPECTED_NAMES
        )
        comparison = compare_outputs(actual, expected, atol=1e-5, rtol=1e-4)
        # Use realistic large output sizes when checking the aggregate mean cap.
        for detail in comparison["output_details"]:
            detail["mean_abs_error"] = 1e-6
        comparison["mean_abs_error"] = 1e-6
        acceptance = evaluate_acceptance(comparison)
        self.assertFalse(acceptance["strict_accepted"])
        self.assertTrue(acceptance["bounded_xnnpack_accepted"])
        comparison["output_details"][2]["max_abs_error"] = 5.1e-4
        self.assertFalse(evaluate_acceptance(comparison)["bounded_xnnpack_accepted"])

    def test_acceptance_rejects_missing_cache_output(self):
        expected = tuple(torch.zeros(1) for _ in range(58))
        comparison = compare_outputs(expected, expected, atol=1e-5, rtol=1e-4)
        comparison["output_details"].pop()
        self.assertFalse(evaluate_acceptance(comparison)["complete_58_output_abi"])
        self.assertFalse(evaluate_acceptance(comparison)["bounded_xnnpack_accepted"])

    def test_android_decode_control_requires_real_normative_cache_handoff(self):
        capacity = 8
        caches = tuple(torch.zeros(1, 2, capacity, 128) for _ in range(56))
        prefill = {
            "inputs_embeds": torch.zeros(1, 3, 16),
            "attention_mask": torch.tensor([[1, 1, 1, 0, 0, 0, 0, 0]]),
            "post_cache": caches,
        }
        decode = {
            "attention_mask": torch.tensor([[1, 1, 1, 1, 0, 0, 0, 0]]),
            "position_ids": torch.tensor([[3]]),
            "cache_position": torch.tensor([3]),
            "pre_cache": tuple(value.clone() for value in caches),
        }
        self.assertEqual(_validate_control(prefill, decode)["decode_valid_length"], 4)
        decode["pre_cache"] = (*decode["pre_cache"][:-1], torch.ones_like(caches[-1]))
        with self.assertRaisesRegex(ValueError, "ABI index 55"):
            _validate_control(prefill, decode)

    def test_android_decode_control_rejects_invalid_position_mask_and_capacity(self):
        capacity = 4
        caches = tuple(torch.zeros(1, 2, capacity, 128) for _ in range(56))
        prefill = {"inputs_embeds": torch.zeros(1, 3, 16),
                   "attention_mask": torch.tensor([[1, 1, 1, 0]]), "post_cache": caches}
        decode = {"attention_mask": torch.ones(1, capacity, dtype=torch.long),
                  "position_ids": torch.tensor([[2]]), "cache_position": torch.tensor([3]),
                  "pre_cache": caches}
        with self.assertRaisesRegex(ValueError, "position_ids"):
            _validate_control(prefill, decode)
        decode["position_ids"] = torch.tensor([[3]])
        decode["cache_position"] = torch.tensor([4])
        with self.assertRaisesRegex(ValueError, "decode position"):
            _validate_control(prefill, decode)

    def test_prefill_and_decode_match_dynamic_cache_reference(self):
        prefill_embeds = torch.randn(1, 3, 16)
        prefill_mask = torch.tensor([[1, 1, 1, 0, 0, 0, 0, 0]])
        prefill_positions = torch.arange(3).unsqueeze(0)
        prefill_cache_positions = torch.arange(3)

        with torch.no_grad():
            expected_prefill = self.backbone(
                inputs_embeds=prefill_embeds,
                attention_mask=prefill_mask,
                position_ids=prefill_positions,
                cache_position=prefill_cache_positions,
                past_key_values=DynamicCache(),
                use_cache=True,
                return_dict=True,
            )
            actual_prefill = self.prefill(
                prefill_embeds,
                prefill_mask,
                prefill_positions,
                prefill_cache_positions,
            )
        torch.testing.assert_close(
            actual_prefill[0], expected_prefill.last_hidden_state[:, -1:, :]
        )
        torch.testing.assert_close(
            actual_prefill[1],
            self.lm_head(expected_prefill.last_hidden_state[:, -1, :]).float(),
        )
        expected_cache = flatten_cache(expected_prefill.past_key_values, 2)
        for actual, expected in zip(actual_prefill[2:], expected_cache):
            torch.testing.assert_close(actual[:, :, :3], expected)
            self.assertEqual(torch.count_nonzero(actual[:, :, 3:]).item(), 0)

        decode_embeds = torch.randn(1, 1, 16)
        decode_mask = torch.tensor([[1, 1, 1, 1, 0, 0, 0, 0]])
        decode_positions = torch.tensor([[3]])
        decode_cache_positions = torch.tensor([3])
        with torch.no_grad():
            expected_decode = self.backbone(
                inputs_embeds=decode_embeds,
                attention_mask=decode_mask,
                position_ids=decode_positions,
                cache_position=decode_cache_positions,
                past_key_values=expected_prefill.past_key_values,
                use_cache=True,
                return_dict=True,
            )
            actual_decode = self.decode(
                decode_embeds,
                decode_mask,
                decode_positions,
                decode_cache_positions,
                *(value.clone() for value in actual_prefill[2:]),
            )
        torch.testing.assert_close(
            actual_decode[0], expected_decode.last_hidden_state[:, -1:, :]
        )
        torch.testing.assert_close(
            actual_decode[1],
            self.lm_head(expected_decode.last_hidden_state[:, -1, :]).float(),
        )
        expected_cache = flatten_cache(expected_decode.past_key_values, 2)
        for actual, expected in zip(actual_decode[2:], expected_cache):
            torch.testing.assert_close(actual[:, :, :4], expected)
            self.assertEqual(torch.count_nonzero(actual[:, :, 4:]).item(), 0)

    def test_sequential_prefill_boundaries_preserve_exact_eager_result(self):
        embeds = torch.randn(1, 3, 16)
        mask = torch.tensor([[1, 1, 1, 0, 0, 0, 0, 0]])
        positions = torch.arange(3).unsqueeze(0)
        cache_positions = torch.arange(3)
        expected = self.prefill(embeds, mask, positions, cache_positions)
        options = dict(num_hidden_layers=2, num_key_value_heads=2,
                       head_dim=4, cache_capacity=8)
        hidden, causal, cos, sin = Qwen2PrefillPrepare(
            self.backbone, **options
        )(embeds, mask, positions, cache_positions)
        caches = []
        for index, layer in enumerate(self.backbone.layers):
            zero = torch.zeros(1, 2, 8, 4)
            stage = Qwen2PrefillLayer(layer, index)
            stage_inputs = (hidden, causal, cache_positions, cos, sin, zero, zero)
            torch.export.export(stage, stage_inputs, strict=True)
            hidden, key, value = stage(*stage_inputs)
            caches.extend((key, value))
        hidden, logits = Qwen2PrefillFinal(
            self.backbone.norm, self.lm_head
        )(hidden)
        for actual, reference in zip((hidden, logits, *caches), expected):
            torch.testing.assert_close(actual, reference, rtol=0, atol=0)

    def test_prefill_and_decode_are_strict_exportable(self):
        embeds = torch.randn(1, 3, 16)
        mask = torch.tensor([[1, 1, 1, 0, 0, 0, 0, 0]])
        positions = torch.arange(3).unsqueeze(0)
        cache_positions = torch.arange(3)
        exported_prefill = torch.export.export(
            self.prefill, (embeds, mask, positions, cache_positions), strict=True
        )
        with torch.no_grad():
            cache = self.prefill(embeds, mask, positions, cache_positions)[2:]
        decode_args = (
            torch.randn(1, 1, 16),
            torch.tensor([[1, 1, 1, 1, 0, 0, 0, 0]]),
            torch.tensor([[3]]),
            torch.tensor([3]),
            *cache,
        )
        exported_decode = torch.export.export(self.decode, decode_args, strict=True)
        self.assertGreater(len(list(exported_prefill.graph.nodes)), 0)
        self.assertGreater(len(list(exported_decode.graph.nodes)), 0)


if __name__ == "__main__":
    unittest.main()
