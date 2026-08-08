#!/usr/bin/env python3

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import torch

EXPORT_DIR = Path(__file__).resolve().parents[1] / "export"
sys.path.insert(0, str(EXPORT_DIR))

from acoustic_decoder import (  # noqa: E402
    NonStreamingDecoderProbe,
    build_decoder_config,
)
from fixture_utils import snapshot_cache, tensor_metadata, tensor_sha256  # noqa: E402


class SConv1d(torch.nn.Module):
    def __init__(self, layer_id: str):
        super().__init__()
        self._layer_id = layer_id

    @property
    def layer_id(self) -> str:
        return self._layer_id


class FakeDecoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.stem = SConv1d("runtime-123")

    def forward(self, value, **kwargs):
        return value * 2


class FakeCache:
    def __init__(self):
        self.cache = {("runtime-123", 0): torch.tensor([[1.0, 2.0]])}


class ExportHelperTests(unittest.TestCase):
    def test_tensor_hash_uses_exact_bytes(self):
        value = torch.tensor([1.0, 2.0], dtype=torch.float32)
        self.assertEqual(tensor_sha256(value), tensor_metadata(value)["sha256"])
        self.assertNotEqual(tensor_sha256(value), tensor_sha256(value + 1))
        singleton_stride = torch.ones(1, 1, 64).permute(0, 2, 1)
        self.assertEqual(len(tensor_sha256(singleton_stride)), 64)

    def test_cache_snapshot_uses_stable_module_name(self):
        tensors, entries = snapshot_cache(FakeDecoder(), FakeCache())
        self.assertEqual(list(tensors), ["stem/sample_0"])
        self.assertEqual(entries[0]["module"], "stem")
        self.assertEqual(entries[0]["shape"], [1, 2])

    def test_decoder_config_reverses_encoder_depths(self):
        config = SimpleNamespace(
            encoder_depths="3-3-8",
            decoder_depths=None,
            vae_dim=64,
            decoder_n_filters=32,
            decoder_ratios=[8, 5],
            conv_norm="none",
            pad_mode="constant",
            conv_bias=True,
            layernorm_eps=1e-5,
            layernorm_elementwise_affine=True,
            mixer_layer="depthwise_conv",
            layer_scale_init_value=1e-6,
            disable_last_norm=True,
        )
        derived = build_decoder_config(copy.deepcopy(config))
        self.assertEqual(derived.depths, [8, 3, 3])
        self.assertEqual(derived.dimension, 64)

    def test_nonstreaming_wrapper_has_tensor_only_call(self):
        value = torch.ones(1, 64, 1)
        result = NonStreamingDecoderProbe(FakeDecoder())(value)
        torch.testing.assert_close(result, value * 2)


if __name__ == "__main__":
    unittest.main()
