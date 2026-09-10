"""Small synthetic tensors only. No checkpoint, PT2, QNN, or phone is loaded."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import signal
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import torch

torch.set_num_threads(1)
EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "tools"))
import replay_saved_qdq as replay

IDS = EXP / "protocol/token-ids/short.int32le"


def config():
    return SimpleNamespace(
        n_layers=2, layer_types=["linear_attention", "full_attention"],
        linear_num_value_heads=1, linear_num_key_heads=1,
        linear_key_head_dim=2, linear_value_head_dim=2,
        linear_conv_kernel_dim=2, n_kv_heads=1, head_dim=2,
    )


class SyntheticGraph:
    def __init__(self, ids, context, offset=0, fail_at=None, failure=None):
        self.ids, self.context, self.offset = ids, context, offset
        self.fail_at, self.failure = fail_at, failure
        self.calls = 0

    def __call__(self, token, mask, position, *states):
        p = self.calls
        assert token.dtype == position.dtype == torch.int32
        assert token.shape == position.shape == (1, 1)
        assert int(token.item()) == self.ids[p]
        assert int(position.item()) == p
        assert mask.shape == (1, 1, 1, self.context)
        expected_mask = torch.full_like(mask, -65504.0)
        expected_mask[..., :p] = 0
        expected_mask[..., -1] = 0
        torch.testing.assert_close(mask, expected_mask, rtol=0, atol=0)
        recurrent, key, convolution, value = states
        assert recurrent.shape == (1, 1, 2, 2)
        assert convolution.shape == (1, 6, 1, 2)
        assert key.shape == (1, 1, 2, self.context - 1)
        assert value.shape == (1, 1, self.context - 1, 2)
        assert bool((recurrent == p).all())
        assert bool((convolution == (0 if p == 0 else 100 + p)).all())
        for j in range(p):
            assert bool((key[..., j] == 10 + j).all())
            assert bool((value[:, :, j, :] == 20 + j).all())
        assert bool((key[..., p:] == 0).all())
        assert bool((value[:, :, p:, :] == 0).all())
        if p == self.fail_at:
            if callable(self.failure):
                self.failure()
            raise self.failure
        self.calls += 1
        logits = torch.full((1, 1, 7), -50.0)
        logits[..., (self.ids[p] + p + self.offset) % 7] = p + 0.25
        return (
            logits, recurrent + 1, torch.full_like(key[..., :1], 10 + p),
            torch.full_like(convolution, 101 + p),
            torch.full_like(value[:, :, :1, :], 20 + p),
            torch.tensor([-999.0]),  # Diagnostic extra must not become state.
        )


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.args = SimpleNamespace(
            params=root / "params.json", token_ids=root / "short.int32le",
            qdq_file=root / "synthetic-not-a-model.pt2",
            artifact_manifest=root / "artifacts.json", output=root / "result.json",
            logits=root / "final.pt", progress=root / "progress.jsonl", context=4096,
        )
        self.args.params.write_text('{}\n')
        self.args.token_ids.write_bytes(IDS.read_bytes())
        self.args.qdq_file.write_bytes(b'synthetic bytes; never deserialize')
        self.manifest = {"files": {
            k: replay.artifact(p) for k, p in (
                ("params", self.args.params), ("input_ids", self.args.token_ids),
                ("histogram_qdq", self.args.qdq_file),
            )
        }}
        self.args.artifact_manifest.write_text(json.dumps(self.manifest))
        self.ids = list(struct.unpack('<174i', IDS.read_bytes()))
        self.real_load = mock.patch.object(torch.export, "load", side_effect=AssertionError("Real model loading forbidden in synthetic tests"))
        self.real_load.start()
        self.addCleanup(self.real_load.stop)

    def run_graph(self, graph):
        loader = mock.Mock(return_value=(graph, config()))
        with contextlib.redirect_stdout(io.StringIO()):
            result = replay.run_replay(self.args, runtime_loader=loader)
        return result

    def persisted(self):
        return json.loads(self.args.output.read_text())

    def journal(self):
        return [json.loads(s) for s in self.args.progress.read_text().splitlines()]

    def test_complete_174_inputs_masks_states_and_computed_argmax(self):
        graph = SyntheticGraph(self.ids, self.args.context)
        result = self.run_graph(graph)
        self.assertEqual(174, graph.calls)
        self.assertEqual("completed", result["status"])
        self.assertEqual(174, result["evaluated_tokens"])
        self.assertEqual(174, result["state_updates_completed"])
        self.assertEqual(173, result["last_input_position"])
        expected = (self.ids[-1] + 173) % 7
        self.assertEqual(expected, result["final_logits"]["argmax"])
        self.assertEqual(173.25, result["final_logits"]["top_logits"][0])
        final = torch.load(self.args.logits, weights_only=True)
        self.assertEqual(expected, int(final.argmax()))
        self.assertEqual(result["final_logits_artifact"], replay.artifact(self.args.logits))
        self.assertEqual(list(range(174)), [r['position'] for r in self.journal()])
        self.assertEqual(self.ids, [r['input_token'] for r in self.journal()])
        for row in self.journal():
            self.assertEqual(row['artifact'], replay.artifact(Path(row['artifact']['path'])))
        self.assertFalse(result['physical_execution'])
        self.assertFalse(result['automatic_retry'])
        self.assertNotIn('physical_observation', result)

    def test_different_computed_logits_change_report_not_hardcoded(self):
        graph = SyntheticGraph(self.ids, self.args.context, offset=2)
        result = self.run_graph(graph)
        self.assertEqual((self.ids[-1] + 175) % 7, result['final_logits']['argmax'])

    def test_argmax_ties_use_first_index_not_topk_order(self):
        s = replay.summarize_logits(torch.tensor([1.0, 9.0, 9.0, -1.0]))
        self.assertEqual(1, s['argmax'])
        self.assertEqual(2, s['max_count'])
        self.assertEqual(4, len(s['top_ids']))

    def test_input_length_malformed_truncated_or_extended_rejected(self):
        for raw in (IDS.read_bytes()[:-4], IDS.read_bytes() + b'\x00', IDS.read_bytes() + b'\x00'*4):
            with self.subTest(length=len(raw)):
                self.args.token_ids.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, '174'):
                    replay.read_short_ids(self.args.token_ids, 4096)

    def test_same_length_wrong_hash_and_wrong_endian_rejected(self):
        wrong = bytearray(IDS.read_bytes()); wrong[0] ^= 1
        for raw in (bytes(wrong), struct.pack('>174i', *self.ids)):
            self.args.token_ids.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                replay.read_short_ids(self.args.token_ids, 4096)

    def test_context_includes_canonical_output_ceiling(self):
        with self.assertRaisesRegex(ValueError, 'ceiling'):
            replay.read_short_ids(self.args.token_ids, 2221)
        self.assertEqual(self.ids, replay.read_short_ids(self.args.token_ids, 2222))

    def test_bad_tokens_never_invoke_loader_and_error_is_retained(self):
        raw = bytearray(IDS.read_bytes()); raw[-1] ^= 1
        self.args.token_ids.write_bytes(raw)
        loader = mock.Mock()
        with self.assertRaises(ValueError):
            replay.run_replay(self.args, runtime_loader=loader)
        loader.assert_not_called()
        result = self.persisted()
        self.assertEqual('error', result['status'])
        self.assertEqual('preflight', result['phase'])
        self.assertEqual(0, result['evaluated_tokens'])

    def test_manifest_mismatch_never_loads_model(self):
        self.args.qdq_file.write_bytes(b'different archive bytes')
        loader = mock.Mock()
        with self.assertRaisesRegex(ValueError, 'qdq_file'):
            replay.run_replay(self.args, runtime_loader=loader)
        loader.assert_not_called()
        self.assertEqual(replay.artifact(self.args.qdq_file), self.persisted()['input_artifacts']['qdq_file'])

    def test_bad_params_hash_rejected_before_load(self):
        self.args.params.write_text('{"wrong":true}')
        loader = mock.Mock()
        with self.assertRaisesRegex(ValueError, 'params'):
            replay.run_replay(self.args, runtime_loader=loader)
        loader.assert_not_called()

    def test_load_error_is_retained_without_final_output(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic load failure'):
            replay.run_replay(self.args, runtime_loader=mock.Mock(side_effect=RuntimeError('synthetic load failure')))
        result = self.persisted()
        self.assertEqual('error', result['status'])
        self.assertEqual('load', result['phase'])
        self.assertIsNone(result['final_logits'])
        self.assertEqual([], self.journal())
        self.assertEqual(0, self.args.logits.stat().st_size)

    def test_mid_replay_error_retains_three_raw_outputs_and_partial_counts(self):
        graph = SyntheticGraph(self.ids, self.args.context, fail_at=3, failure=RuntimeError('synthetic graph failure'))
        with self.assertRaisesRegex(RuntimeError, 'synthetic graph failure'):
            self.run_graph(graph)
        result = self.persisted()
        self.assertEqual('error', result['status'])
        self.assertEqual(3, result['evaluated_tokens'])
        self.assertEqual(3, result['state_updates_completed'])
        self.assertEqual(2, result['last_input_position'])
        self.assertEqual(3, len(self.journal()))
        self.assertEqual(result['logits_artifact'], replay.artifact(Path(result['logits_artifact']['path'])))
        self.assertIsNone(result['final_logits'])
        self.assertEqual(0, self.args.logits.stat().st_size)

    def test_sigterm_retains_partial_and_restores_signal_handlers(self):
        previous = signal.getsignal(signal.SIGTERM)
        graph = SyntheticGraph(self.ids, self.args.context, fail_at=2, failure=lambda: signal.raise_signal(signal.SIGTERM))
        with replay.interruption_signals():
            with self.assertRaises(replay.ReplayInterrupted):
                self.run_graph(graph)
        self.assertEqual(previous, signal.getsignal(signal.SIGTERM))
        result = self.persisted()
        self.assertEqual('interrupted', result['status'])
        self.assertEqual(2, result['evaluated_tokens'])
        self.assertEqual(2, len(self.journal()))
        self.assertIsNone(result['final_logits_artifact'])

    def test_nonfinite_raw_logits_retained_with_null_argmax(self):
        graph = SyntheticGraph(self.ids, self.args.context)
        def nonfinite(*args):
            outputs = list(graph(*args)); outputs[0][..., 0] = float('nan'); return outputs
        with self.assertRaises(FloatingPointError):
            self.run_graph(nonfinite)
        result = self.persisted()
        self.assertFalse(result['last_logits']['finite'])
        self.assertIsNone(result['last_logits']['argmax'])
        self.assertIsNone(result['final_logits'])
        tensor = torch.load(result['logits_artifact']['path'], weights_only=True)
        self.assertTrue(bool(torch.isnan(tensor).any()))
        self.assertNotIn(': NaN', self.args.output.read_text())
        self.assertEqual(1, len(self.journal()))

    def test_invalid_logits_do_not_reuse_previous_summary(self):
        graph = SyntheticGraph(self.ids, self.args.context)
        def empty_at_second_step(*args):
            outputs = list(graph(*args))
            if graph.calls == 2:
                outputs[0] = torch.empty((1, 1, 0))
            return outputs
        with self.assertRaisesRegex(ValueError, 'Empty next-token'):
            self.run_graph(empty_at_second_step)
        result = self.persisted()
        self.assertEqual(2, result['evaluated_tokens'])
        self.assertEqual(1, result['state_updates_completed'])
        self.assertIsNone(result['last_logits'])
        self.assertEqual(0, torch.load(result['logits_artifact']['path'], weights_only=True).numel())
        self.assertEqual(1, len(self.journal()))

    def test_missing_states_keeps_logits_but_does_not_claim_state_readiness(self):
        graph = SyntheticGraph(self.ids, self.args.context)
        with self.assertRaisesRegex(ValueError, 'state outputs'):
            self.run_graph(lambda *args: graph(*args)[:1])
        result = self.persisted()
        self.assertEqual(1, result['evaluated_tokens'])
        self.assertEqual(0, result['state_updates_completed'])
        self.assertIsNotNone(result['logits_artifact'])
        self.assertIsNone(result['final_logits'])

    def test_state_shape_mismatch_does_not_silently_broadcast(self):
        graph = SyntheticGraph(self.ids, self.args.context)
        def wrong_shape(*args):
            outputs = list(graph(*args)); outputs[2] = torch.ones((1,)); return outputs
        with self.assertRaisesRegex(ValueError, 'KV update geometry'):
            self.run_graph(wrong_shape)
        self.assertEqual(0, self.persisted()['state_updates_completed'])
        self.assertEqual(1, len(self.journal()))

    def test_recurrent_and_conv_outputs_are_cloned_not_aliased(self):
        from diagnose_quantized_output import make_state_templates
        c = config(); states = make_state_templates(c, 4096)
        graph = SyntheticGraph(self.ids, 4096)
        mask = torch.full((1, 1, 1, 4096), -65504.); mask[..., -1] = 0
        outputs = graph(torch.tensor([[self.ids[0]]], dtype=torch.int32), mask, torch.tensor([[0]], dtype=torch.int32), *states)
        replay.advance_state(c, states, outputs, 0)
        outputs[1].fill_(999); outputs[3].fill_(999)
        self.assertTrue(bool((states[0] == 1).all()))
        self.assertTrue(bool((states[2] == 101).all()))

    def test_each_existing_destination_is_preserved(self):
        for attr in ('output', 'logits', 'progress'):
            with self.subTest(attr=attr):
                path = getattr(self.args, attr); path.write_bytes(b'prior evidence')
                with self.assertRaises(FileExistsError):
                    replay.run_replay(self.args, runtime_loader=mock.Mock())
                self.assertEqual(b'prior evidence', path.read_bytes())
                path.unlink()

    def test_existing_checkpoint_directory_is_not_reused(self):
        directory = Path(str(self.args.logits) + '.steps'); directory.mkdir()
        (directory / 'old.pt').write_bytes(b'prior tensor')
        with self.assertRaises(FileExistsError):
            replay.run_replay(self.args, runtime_loader=mock.Mock())
        self.assertFalse(self.args.output.exists())
        self.assertEqual(b'prior tensor', (directory / 'old.pt').read_bytes())

    def test_dangling_output_symlink_is_not_overwritten(self):
        self.args.output.symlink_to(self.args.output.parent / 'missing')
        with self.assertRaises(FileExistsError):
            replay.run_replay(self.args, runtime_loader=mock.Mock())
        self.assertTrue(self.args.output.is_symlink())

    def test_output_cannot_alias_input_or_other_output(self):
        self.args.output = self.args.token_ids
        with self.assertRaisesRegex(ValueError, 'alias'):
            replay.run_replay(self.args, runtime_loader=mock.Mock())
        self.assertEqual(IDS.read_bytes(), self.args.token_ids.read_bytes())
        self.args.output = self.args.logits
        with self.assertRaisesRegex(ValueError, 'distinct'):
            replay.run_replay(self.args, runtime_loader=mock.Mock())

    def test_completed_or_partial_attempt_cannot_be_overwritten(self):
        graph = SyntheticGraph(self.ids, self.args.context, fail_at=1, failure=RuntimeError('stop'))
        with self.assertRaises(RuntimeError): self.run_graph(graph)
        original = self.args.output.read_bytes()
        with self.assertRaises(FileExistsError):
            self.run_graph(SyntheticGraph(self.ids, self.args.context))
        self.assertEqual(original, self.args.output.read_bytes())

    def test_final_save_error_does_not_mark_completed(self):
        with mock.patch.object(replay.Evidence, 'save_final_logits', side_effect=OSError('synthetic disk error')):
            with self.assertRaises(OSError): self.run_graph(SyntheticGraph(self.ids, self.args.context))
        result = self.persisted()
        self.assertEqual('error', result['status'])
        self.assertEqual(174, result['state_updates_completed'])
        self.assertEqual(174, len(self.journal()))
        self.assertIsNone(result['final_logits'])
        self.assertIsNone(result['final_logits_artifact'])

    def test_failed_atomic_write_preserves_previous_checkpoint(self):
        p = self.args.output; p.write_bytes(b'old')
        def broken(f):
            f.write(b'partial'); raise OSError('failed temporary write')
        with self.assertRaises(OSError): replay._atomic_write(p, broken)
        self.assertEqual(b'old', p.read_bytes())
        self.assertEqual([], list(p.parent.glob('.result.json.*')))


if __name__ == '__main__':
    unittest.main()
