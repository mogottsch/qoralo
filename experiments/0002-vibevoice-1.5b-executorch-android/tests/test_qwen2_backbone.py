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
    SpeakerConditioning,
    cache_tensor_names,
    flatten_cache,
)


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
            actual_prefill[1], self.lm_head(expected_prefill.last_hidden_state[:, -1, :]).float()
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
            actual_decode[1], self.lm_head(expected_decode.last_hidden_state[:, -1, :]).float()
        )
        expected_cache = flatten_cache(expected_decode.past_key_values, 2)
        for actual, expected in zip(actual_decode[2:], expected_cache):
            torch.testing.assert_close(actual[:, :, :4], expected)
            self.assertEqual(torch.count_nonzero(actual[:, :, 4:]).item(), 0)

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
