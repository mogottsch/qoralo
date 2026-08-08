#!/usr/bin/env python3

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import torch
import torch.nn.functional as F

EXPORT_DIR = Path(__file__).resolve().parents[1] / "export"
sys.path.insert(0, str(EXPORT_DIR))

from acoustic_decoder import (  # noqa: E402
    CausalPaddedSConv1d,
    NonStreamingDecoderProbe,
    build_decoder_config,
    replace_constant_pad_modules,
)
from android_io import read_float32_le, write_float32_le  # noqa: E402
from diagnose_decoder import collect_probes  # noqa: E402
from fixture_utils import snapshot_cache, tensor_metadata, tensor_sha256  # noqa: E402


class SConv1d(torch.nn.Module):
    def __init__(self, layer_id: str):
        super().__init__()
        self._layer_id = layer_id
        self.conv = torch.nn.Conv1d(2, 3, 3, bias=False)
        self.causal = True
        self.pad_mode = "constant"
        self.kernel_size = 3
        self.stride = 1
        self.dilation = 1
        self.padding_total = 2

    @property
    def layer_id(self) -> str:
        return self._layer_id

    def forward(self, value):
        return self.conv(F.pad(value, (self.padding_total, 0)))


class FakeDecoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.stem = SConv1d("runtime-123")

    def forward(self, value, **kwargs):
        return value * 2


class FakeCache:
    def __init__(self):
        self.cache = {("runtime-123", 0): torch.tensor([[1.0, 2.0]])}


class Scale(torch.nn.Module):
    def __init__(self, factor: float):
        super().__init__()
        self.factor = factor

    def forward(self, value):
        return value * self.factor


class FakeComponentDecoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.upsample_layers = torch.nn.ModuleList([Scale(2), Scale(3)])
        self.stages = torch.nn.ModuleList([Scale(5), Scale(7)])
        self.norm = Scale(11)
        self.head = Scale(13)

    def forward(self, value):
        for upsample, stage in zip(self.upsample_layers, self.stages):
            value = stage(upsample(value))
        return self.head(self.norm(value))


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

    def test_android_float32_little_endian_round_trip(self):
        value = torch.tensor([[[-2.5], [0.25]]], dtype=torch.float32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.f32le"
            write_float32_le(path, value)
            result = read_float32_le(path, (1, 2, 1))
        torch.testing.assert_close(result, value, rtol=0, atol=0)

    def test_android_float32_reader_rejects_wrong_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.f32le"
            path.write_bytes(b"short")
            with self.assertRaisesRegex(ValueError, "Expected 8 bytes"):
                read_float32_le(path, (2,))

    def test_internal_conv_padding_matches_causal_constant_padding(self):
        original = SConv1d("pad-test")
        value = torch.randn(1, 2, 5)
        expected = original(value)
        replacement = CausalPaddedSConv1d(original)
        torch.testing.assert_close(replacement(value), expected)
        container = torch.nn.Sequential(SConv1d("nested"))
        self.assertEqual(replace_constant_pad_modules(container), ["0"])
        self.assertIsInstance(container[0], CausalPaddedSConv1d)

    def test_microprobes_follow_decoder_component_boundaries(self):
        decoder = FakeComponentDecoder()
        probes = collect_probes(decoder, torch.ones(1, 1, 1))
        self.assertEqual(
            list(probes),
            [
                "stem",
                "stage-0",
                "upsample-1",
                "stage-1",
                "norm",
                "head",
                "stage-0-upsample-1",
                "initial-through-upsample-1",
            ],
        )
        torch.testing.assert_close(probes["stem"].output, torch.tensor([[[2.0]]]))
        torch.testing.assert_close(probes["head"].output, decoder(torch.ones(1, 1, 1)))


if __name__ == "__main__":
    unittest.main()
