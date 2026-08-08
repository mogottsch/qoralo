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
from diffusion_head import DiffusionHeadStep  # noqa: E402
from diffusion_scheduler import DpmSolverState, ten_step_schedule  # noqa: E402
from export_diffusion_step import validated_inputs  # noqa: E402
from fixture_utils import snapshot_cache, tensor_metadata, tensor_sha256  # noqa: E402
from speech_connectors import ConnectorRMSNorm, SpeechConnectorJoin  # noqa: E402
from streaming_android_io import (  # noqa: E402
    compare_tensor,
    read_tensor_le,
    write_tensor_le,
)
from streaming_decoder import (  # noqa: E402
    StaticTensorCache,
    cache_module_names,
    segment_cache_names,
)
from validate_streaming_sequence import compare_outputs  # noqa: E402


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


class FakePredictionHead(torch.nn.Module):
    def forward(self, noisy_latent, timestep, condition):
        return noisy_latent + timestep[:, None] + condition[:, :64]


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

    def test_diffusion_step_uses_documented_cfg_order(self):
        wrapper = DiffusionHeadStep(FakePredictionHead(), cfg_scale=1.3)
        noisy = torch.ones(1, 64)
        timestep = torch.tensor([999.0])
        positive = torch.full((1, 1536), 2.0)
        negative = torch.full((1, 1536), -3.0)
        result = wrapper(noisy, timestep, positive, negative)
        expected_positive = noisy + timestep[:, None] + positive[:, :64]
        expected_negative = noisy + timestep[:, None] + negative[:, :64]
        torch.testing.assert_close(
            result, expected_negative + 1.3 * (expected_positive - expected_negative)
        )

    def test_diffusion_fixture_input_validation_is_fixed_shape_fp32(self):
        fixture = {
            "noisy_latent": torch.ones(1, 64, dtype=torch.float64),
            "timestep": torch.ones(1, dtype=torch.int64),
            "positive_condition": torch.ones(1, 1536),
            "negative_condition": torch.ones(1, 1536),
        }
        inputs = validated_inputs(fixture)
        self.assertTrue(all(value.dtype == torch.float32 for value in inputs))
        with self.assertRaisesRegex(SystemExit, "positive_condition shape"):
            validated_inputs({**fixture, "positive_condition": torch.ones(2, 1536)})

    def test_diffusion_schedule_matches_locked_ten_step_values(self):
        timesteps, sigmas = ten_step_schedule()
        self.assertEqual(
            timesteps.tolist(), [999, 899, 799, 699, 599, 500, 400, 300, 200, 100]
        )
        self.assertEqual(sigmas.dtype, torch.float32)
        self.assertEqual(len(sigmas), 11)
        self.assertEqual(sigmas[-1].item(), 0.0)
        self.assertAlmostEqual(sigmas[0].item(), 20291.302734375)

    def test_diffusion_scheduler_runs_first_second_and_final_order(self):
        _, sigmas = ten_step_schedule()
        scheduler = DpmSolverState(sigmas)
        sample = torch.linspace(-1, 1, 64).reshape(1, 64)
        for index in range(10):
            prediction = torch.full((1, 64), index / 10)
            sample = scheduler.step(prediction, sample)
        self.assertTrue(torch.isfinite(sample).all())
        self.assertEqual(scheduler.step_index, 10)
        self.assertAlmostEqual(sample[0, 0].item(), -1.7456469536, places=6)
        self.assertAlmostEqual(sample[0, -1].item(), 0.2078655511, places=6)

    def test_connector_join_has_tensor_only_additive_abi(self):
        join = SpeechConnectorJoin(Scale(2), Scale(3))
        acoustic = torch.ones(1, 64)
        semantic = torch.ones(1, 64)
        torch.testing.assert_close(join(acoustic, semantic), torch.full((1, 64), 5.0))

    def test_connector_rms_norm_upcasts_variance(self):
        norm = ConnectorRMSNorm(2, eps=1e-6)
        value = torch.tensor([[3.0, 4.0]], dtype=torch.float32)
        expected = value * torch.rsqrt(value.pow(2).mean(-1, keepdim=True) + 1e-6)
        torch.testing.assert_close(norm(value), expected)

    def test_streaming_cache_abi_uses_stable_sorted_module_names(self):
        fixture = {
            "post_cache": {
                "upsample_layers.1.0/sample_0": torch.ones(1),
                "stages.0.0.mixer.conv/sample_0": torch.ones(1),
                "head/sample_0": torch.ones(1),
            }
        }
        names = cache_module_names(fixture, "post_cache")
        self.assertEqual(
            names,
            ["head", "stages.0.0.mixer.conv", "upsample_layers.1.0"],
        )
        self.assertEqual(segment_cache_names(names, 0), ["stages.0.0.mixer.conv"])
        self.assertEqual(segment_cache_names(names, 1), ["upsample_layers.1.0"])
        self.assertEqual(segment_cache_names(names, 7), ["head"])

    def test_static_tensor_cache_preserves_declared_output_order(self):
        inputs = (torch.tensor([[[1.0]]]), torch.tensor([[[2.0]]]))
        cache = StaticTensorCache({"layer-a": 0, "layer-b": 1}, inputs)
        sample = torch.zeros(1, dtype=torch.int64)
        torch.testing.assert_close(cache.get("layer-b", sample), inputs[1])
        first = torch.tensor([[[3.0]]])
        second = torch.tensor([[[4.0]]])
        cache.set("layer-b", sample, second)
        cache.set("layer-a", sample, first)
        outputs = cache.result()
        torch.testing.assert_close(outputs[0], first)
        torch.testing.assert_close(outputs[1], second)
        first.add_(10)
        self.assertEqual(outputs[0].item(), 3.0)

    def test_android_float16_little_endian_round_trip(self):
        value = torch.tensor([[[-2.5], [0.25]]], dtype=torch.float32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.f16le"
            write_tensor_le(path, value, "fp16")
            result = read_tensor_le(path, (1, 2, 1), "fp16")
        self.assertEqual(path.suffix, ".f16le")
        self.assertEqual(result.dtype, torch.float16)
        torch.testing.assert_close(result.float(), value, rtol=0, atol=0)

    def test_streaming_android_comparison_checks_fp16_against_fp32(self):
        expected = torch.tensor([0.123456], dtype=torch.float32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actual.f16le"
            write_tensor_le(path, expected, "fp16")
            result = compare_tensor(
                path, expected, atol=2e-3, rtol=2e-3, precision="fp16"
            )
        self.assertTrue(result["allclose"])
        self.assertGreater(result["max_abs_error"], 0)

    def test_streaming_android_comparison_checks_raw_tensor(self):
        expected = torch.tensor([[[1.0, -2.0]]], dtype=torch.float32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actual.f32le"
            write_float32_le(path, expected + 1e-6)
            result = compare_tensor(path, expected, atol=2e-5, rtol=1e-5)
        self.assertEqual(result["shape"], [1, 1, 2])
        self.assertTrue(result["allclose"])
        self.assertTrue(result["accepted"])
        self.assertLess(result["max_abs_error"], 2e-5)

    def test_streaming_android_cache_acceptance_preserves_strict_failure(self):
        expected = torch.tensor([0.732095], dtype=torch.float32)
        actual = torch.tensor([0.7321286], dtype=torch.float32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actual.f32le"
            write_float32_le(path, actual)
            result = compare_tensor(
                path, expected, atol=2e-5, rtol=1e-5, acceptance_atol=6e-5
            )
        self.assertFalse(result["allclose"])
        self.assertEqual(result["strict_mismatch_count"], 1)
        self.assertTrue(result["accepted"])

    def test_streaming_sequence_comparison_checks_pcm_and_caches(self):
        expected = (torch.tensor([1.0]), torch.tensor([2.0]))
        actual = (torch.tensor([1.000001]), torch.tensor([2.000001]))
        pcm_error, cache_error = compare_outputs(
            actual, expected, atol=2e-5, rtol=1e-5, label="test"
        )
        self.assertLess(pcm_error, 2e-5)
        self.assertLess(cache_error, 2e-5)
        with self.assertRaisesRegex(SystemExit, "expected 2 outputs"):
            compare_outputs(actual[:1], expected, 2e-5, 1e-5, "test")


if __name__ == "__main__":
    unittest.main()
