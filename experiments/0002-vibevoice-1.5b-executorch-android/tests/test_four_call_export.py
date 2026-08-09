from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "export"))

from four_call_abi import (  # noqa: E402
    AtomicFourCallController,
    canonical_cache,
    validate_state,
)

CONTRACT = json.loads((ROOT / "fixtures/four-call-cache-abi.json").read_text())


def outputs(controller: AtomicFourCallController, domain: str, primary: torch.Tensor):
    transition = CONTRACT["call_transitions"][controller.phase]
    state = controller.decoder if domain == "decoder" else controller.semantic
    shape = (1, 1, 3200) if domain == "decoder" else (1, 1, 128)
    value = torch.zeros(shape, dtype=torch.float32)
    lengths = torch.tensor(transition[f"{domain}_post_valid_lengths"], dtype=torch.int32)
    caches = []
    method = CONTRACT["methods"]["acoustic_decode" if domain == "decoder" else "semantic_encode"]
    for spec, valid in zip(method["caches"], lengths.tolist(), strict=True):
        cache = torch.zeros(tuple(spec["capacity_shape"]), dtype=torch.float32)
        cache[..., :valid] = controller.phase + 1
        caches.append(cache)
    return (value, lengths, *caches)


def test_canonical_cache_is_left_aligned_and_zero_padded():
    value = torch.tensor([[1.0, 2.0]], dtype=torch.float32)
    result = canonical_cache(value, (1, 4))
    assert result.tolist() == [[1.0, 2.0, 0.0, 0.0]]
    assert result.is_contiguous()


def test_reset_transition_exclusion_and_boundary():
    controller = AtomicFourCallController(CONTRACT)
    assert controller.phase == 0
    assert all(torch.count_nonzero(value) == 0 for value in (*controller.decoder.caches, *controller.semantic.caches))
    for expected_phase in range(4):
        pcm, semantic = controller.execute(
            torch.zeros(1, 1, 64),
            lambda *args: outputs(controller, "decoder", args[0]),
            lambda *args: outputs(controller, "semantic", args[0]),
        )
        assert tuple(pcm.shape) == (1, 1, 3200)
        assert tuple(semantic.shape) == (1, 1, 128)
        assert controller.phase == expected_phase + 1
    with pytest.raises(ValueError, match="validation boundary"):
        controller.execute(torch.zeros(1, 1, 64), lambda *args: (), lambda *args: ())


def test_wrong_transition_and_nonzero_padding_are_rejected():
    controller = AtomicFourCallController(CONTRACT)
    bad_lengths = controller.decoder.lengths.clone()
    bad_lengths[0] = 1
    with pytest.raises(ValueError, match="valid lengths"):
        validate_state(CONTRACT, "decoder", 0, bad_lengths, controller.decoder.caches)
    bad_caches = list(controller.decoder.caches)
    bad_caches[0] = bad_caches[0].clone()
    bad_caches[0][..., -1] = 1
    with pytest.raises(ValueError, match="non-zero padding"):
        validate_state(CONTRACT, "decoder", 0, controller.decoder.lengths, bad_caches)


def test_partial_failure_does_not_commit_and_input_mutation_is_detected():
    controller = AtomicFourCallController(CONTRACT)
    before = copy.deepcopy(controller.decoder)

    def fail_semantic(*args):
        raise RuntimeError("injected")

    with pytest.raises(RuntimeError, match="injected"):
        controller.execute(torch.zeros(1, 1, 64), lambda *args: outputs(controller, "decoder", args[0]), fail_semantic)
    assert controller.phase == 0
    assert torch.equal(controller.decoder.lengths, before.lengths)
    assert all(torch.equal(a, b) for a, b in zip(controller.decoder.caches, before.caches, strict=True))

    def mutate(*args):
        args[3].add_(1)
        return outputs(controller, "decoder", args[0])

    with pytest.raises(ValueError, match="mutated input"):
        controller.execute(torch.zeros(1, 1, 64), mutate, lambda *args: outputs(controller, "semantic", args[0]))
    assert controller.phase == 0


def test_reset_after_progress_restores_canonical_state():
    controller = AtomicFourCallController(CONTRACT)
    controller.execute(torch.zeros(1, 1, 64), lambda *args: outputs(controller, "decoder", args[0]), lambda *args: outputs(controller, "semantic", args[0]))
    assert controller.phase == 1
    controller.reset()
    assert controller.phase == 0
    assert controller.decoder.lengths.tolist() == [0] * 34
    assert controller.semantic.lengths.tolist() == [0] * 34
    assert all(torch.count_nonzero(value) == 0 for value in (*controller.decoder.caches, *controller.semantic.caches))
