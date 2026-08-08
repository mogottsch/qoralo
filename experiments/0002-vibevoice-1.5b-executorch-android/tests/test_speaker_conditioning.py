#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import torch

EXPORT_DIR = Path(__file__).resolve().parents[1] / "export"
sys.path.insert(0, str(EXPORT_DIR))

from speaker_conditioning import (  # noqa: E402
    SpeakerConditioner,
    SpeakerTransitionState,
    sequence_speaker_ids_from_masks,
)


class SpeakerConditioningTests(unittest.TestCase):
    def fixture(self):
        tokens = torch.arange(1 * 6 * 3, dtype=torch.float32).reshape(1, 6, 3)
        outputs = torch.tensor(
            [[[-1.0] * 3, [-2.0] * 3, [99.0] * 3], [[-3.0] * 3, [99.0] * 3, [99.0] * 3]],
            dtype=torch.float32,
        )
        prompt_mask = torch.tensor([[True, True, False], [True, False, False]])
        speaker_ids = torch.tensor([0, 1], dtype=torch.int64)
        sequence_mask = torch.tensor([[False, True, True, False, True, False]])
        sequence_ids = sequence_speaker_ids_from_masks(sequence_mask, prompt_mask, speaker_ids)
        return tokens, outputs, prompt_mask, speaker_ids, sequence_ids

    def test_selected_position_replacement_matches_reference_and_preserves_tokens(self):
        tokens, outputs, masks, ids, sequence_ids = self.fixture()
        actual = SpeakerConditioner()(tokens, outputs, masks, ids, sequence_ids)
        expected = tokens.clone()
        expected[0, 1] = outputs[0, 0]
        expected[0, 2] = outputs[0, 1]
        expected[0, 4] = outputs[1, 0]
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        torch.testing.assert_close(actual[0, [0, 3, 5]], tokens[0, [0, 3, 5]], rtol=0, atol=0)

    def test_switch_and_reset_are_explicit_controller_state(self):
        state = SpeakerTransitionState()
        self.assertFalse(state.select(0, (0, 1)))
        self.assertFalse(state.select(0, (0, 1)))
        self.assertTrue(state.select(1, (0, 1)))
        self.assertEqual(state.transitions, 1)
        state.reset()
        self.assertIsNone(state.active_speaker_id)
        self.assertEqual(state.transitions, 0)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            state.select(4, (0, 1))

    def test_rejects_malformed_ids_masks_shapes_dtypes_and_values(self):
        tokens, outputs, masks, ids, sequence_ids = self.fixture()
        conditioner = SpeakerConditioner()
        cases = [
            (tokens, outputs, masks, torch.tensor([0, 0]), sequence_ids, "unique"),
            (tokens, outputs, masks, ids, sequence_ids.masked_fill(sequence_ids == 1, 7), "unknown"),
            (tokens, outputs, masks, ids, sequence_ids.masked_fill(sequence_ids == 1, -2), "only use"),
            (tokens, outputs[:, :, :2], masks, ids, sequence_ids, "hidden size"),
            (tokens, outputs, masks[:, :2], ids, sequence_ids, "prompt_mask shape"),
            (tokens, outputs.double(), masks, ids, sequence_ids, "float32"),
        ]
        for token_arg, output_arg, mask_arg, id_arg, sequence_arg, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                conditioner(token_arg, output_arg, mask_arg, id_arg, sequence_arg)
        bad = outputs.clone()
        bad[0, 0, 0] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            conditioner(tokens, bad, masks, ids, sequence_ids)
        wrong_count = sequence_ids.clone()
        wrong_count[0, 2] = -1
        with self.assertRaisesRegex(ValueError, "selects"):
            conditioner(tokens, outputs, masks, ids, wrong_count)

    def test_mask_expansion_rejects_malformed_ids_and_shapes(self):
        _, _, prompt_mask, speaker_ids, _ = self.fixture()
        sequence_mask = torch.tensor([[True, True, True]])
        cases = [
            (sequence_mask, prompt_mask, torch.tensor([0, 0]), "unique"),
            (sequence_mask, prompt_mask, torch.tensor([0, -1]), "non-negative"),
            (sequence_mask.expand(2, -1), prompt_mask, speaker_ids, "batch size 1"),
            (sequence_mask, prompt_mask[:, :1], speaker_ids, "expected"),
        ]
        for sequence_arg, prompt_arg, id_arg, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                sequence_speaker_ids_from_masks(sequence_arg, prompt_arg, id_arg)

    def test_rejects_non_contiguous_boundary_tensor(self):
        tokens, outputs, masks, ids, sequence_ids = self.fixture()
        non_contiguous = tokens.transpose(1, 2).contiguous().transpose(1, 2)
        self.assertFalse(non_contiguous.is_contiguous())
        with self.assertRaisesRegex(ValueError, "contiguous"):
            SpeakerConditioner()(non_contiguous, outputs, masks, ids, sequence_ids)

    def test_deterministic_and_input_tensors_are_not_mutated(self):
        args = self.fixture()
        snapshots = tuple(value.clone() for value in args)
        first = SpeakerConditioner()(*args)
        second = SpeakerConditioner()(*args)
        self.assertTrue(torch.equal(first, second))
        for actual, prior in zip(args, snapshots, strict=True):
            self.assertTrue(torch.equal(actual, prior))


if __name__ == "__main__":
    unittest.main()
