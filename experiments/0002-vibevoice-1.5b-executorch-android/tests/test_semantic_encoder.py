#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import torch

EXPORT_DIR = Path(__file__).resolve().parents[1] / "export"
sys.path.insert(0, str(EXPORT_DIR))

from semantic_encoder import (  # noqa: E402
    AUDIO_SHAPE,
    ExplicitTensorCache,
    FunctionalSemanticEncoder,
    validate_call_inputs,
)
from validate_semantic_encoder import CACHE_ACCEPTANCE_ATOL, compare  # noqa: E402


class FakeCacheLayer(torch.nn.Module):
    def __init__(self, layer_id: str):
        super().__init__()
        self.layer_id = layer_id


class FakeStreamingEncoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.alpha = FakeCacheLayer("alpha-id")
        self.zeta = FakeCacheLayer("zeta-id")

    def forward(self, audio, cache, sample_indices, use_cache, debug):
        assert use_cache and not debug
        prior_alpha = cache.get("alpha-id", sample_indices)
        prior_zeta = cache.get("zeta-id", sample_indices)
        if prior_alpha is None:
            prior_alpha = audio.new_zeros((1, 1, 2))
            prior_zeta = audio.new_zeros((1, 1, 3))
        cache.set("alpha-id", sample_indices, audio[..., -2:])
        cache.set("zeta-id", sample_indices, audio[..., -3:])
        return (audio[..., :1] + prior_alpha[..., -1:]).expand(1, 128, 1)


class SemanticEncoderTests(unittest.TestCase):
    def test_explicit_cache_preserves_declared_order_and_clones(self):
        cache = ExplicitTensorCache({"zeta": 1, "alpha": 0}, None)
        sample = torch.zeros(1, dtype=torch.int64)
        first = torch.tensor([1.0])
        second = torch.tensor([2.0])
        cache.set("zeta", sample, second)
        cache.set("alpha", sample, first)
        outputs = cache.result()
        self.assertEqual([value.item() for value in outputs], [1.0, 2.0])
        first.add_(5)
        self.assertEqual(outputs[0].item(), 1.0)

    def test_call_two_consumes_actual_call_one_caches_and_reset_is_stateless(self):
        encoder = FakeStreamingEncoder()
        names = ("alpha", "zeta")
        first = FunctionalSemanticEncoder(encoder, names, cached=False)
        cached = FunctionalSemanticEncoder(encoder, names, cached=True)
        audio_1 = torch.zeros(AUDIO_SHAPE)
        audio_1[..., -1] = 3
        audio_2 = torch.ones(AUDIO_SHAPE)
        call_1 = first(audio_1)
        call_2 = cached(audio_2, *call_1[1:])
        self.assertEqual(call_2[0][0, 0, 0].item(), 4.0)
        reset = first(audio_1)
        for actual, expected in zip(reset, call_1, strict=True):
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)

    def test_fixed_abi_rejects_count_shape_dtype_nonfinite_and_noncontiguous(self):
        audio = torch.ones(AUDIO_SHAPE)
        shapes = ((1, 2, 3), (1, 4, 5))
        caches = (torch.ones(shapes[0]), torch.ones(shapes[1]))
        self.assertEqual(len(validate_call_inputs(audio, caches, shapes, cached=True)), 3)
        with self.assertRaisesRegex(ValueError, "Expected 2 cache"):
            validate_call_inputs(audio, caches[:1], shapes, cached=True)
        with self.assertRaisesRegex(ValueError, r"cache\[0\]"):
            validate_call_inputs(audio, (torch.ones(1), caches[1]), shapes, cached=True)
        with self.assertRaisesRegex(ValueError, r"cache\[0\]"):
            validate_call_inputs(audio, tuple(reversed(caches)), shapes, cached=True)
        noncontiguous = torch.ones((1, 3, 2)).transpose(1, 2)
        self.assertEqual(tuple(noncontiguous.shape), shapes[0])
        with self.assertRaisesRegex(ValueError, r"cache\[0\].*contiguous"):
            validate_call_inputs(audio, (noncontiguous, caches[1]), shapes, cached=True)
        nonfinite_cache = caches[0].clone()
        nonfinite_cache[0, 0, 0] = float("inf")
        with self.assertRaisesRegex(ValueError, r"cache\[0\].*finite"):
            validate_call_inputs(audio, (nonfinite_cache, caches[1]), shapes, cached=True)
        with self.assertRaisesRegex(ValueError, "audio must be"):
            validate_call_inputs(audio.double(), (), shapes, cached=False)
        bad = audio.clone()
        bad[0, 0, 0] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            validate_call_inputs(bad, (), shapes, cached=False)

    def test_runtime_comparison_preserves_strict_failure_and_cache_bound(self):
        expected = torch.tensor([0.0, 2.0])
        actual = expected + CACHE_ACCEPTANCE_ATOL * 0.9
        metrics = compare(actual, expected)
        self.assertFalse(metrics["allclose"])
        self.assertGreater(metrics["mismatch_count"], 0)
        self.assertTrue(metrics["bounded_cache_allclose"])
        rejected = compare(expected + CACHE_ACCEPTANCE_ATOL * 1.1, expected)
        self.assertFalse(rejected["bounded_cache_allclose"])


if __name__ == "__main__":
    unittest.main()
