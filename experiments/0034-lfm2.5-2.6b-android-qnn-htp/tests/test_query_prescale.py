"""Small source/rounding fixtures only; never loads the LFM model or any SDK."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from prescale_ar171_queries import EMBED, rewrite, stage
from verify_query_prescale_cpu import compare, dump_arrays, load_arrays, probe, rankings, round16


def fixture():
    inputs = [helper.make_tensor_value_info(EMBED, TensorProto.FLOAT, [1, 171, 2048]),
              helper.make_tensor_value_info('attention_mask', TensorProto.FLOAT, [1, 1, 171, 4096])]
    nodes, outputs = [], []
    for i in range(8):
        p = f'layer-{i}/htp_chunk'
        inputs += [helper.make_tensor_value_info(p + '/query', TensorProto.FLOAT, [1, 32, 171, 64]),
                   helper.make_tensor_value_info(p + '/key_r', TensorProto.FLOAT, [1, 32, 64, 4096])]
        nodes += [helper.make_node('MatMul', [p + '/query', p + '/key_r'], [p + '/scores'], name=p + '/scores'),
                  helper.make_node('Mul', [p + '/scores', '__attn_scale'], [p + '/scaled_scores'], name=p + '/scaled_scores')]
        outputs += [helper.make_tensor_value_info(p + '/scaled_scores', TensorProto.FLOAT, [1, 32, 171, 4096])]
    return helper.make_model(helper.make_graph(nodes, 'test', inputs, outputs,
                             [numpy_helper.from_array(np.asarray(0.125, np.float32), '__attn_scale')]),
                             opset_imports=[helper.make_opsetid('', 21)], ir_version=10)


class QueryPrescaleTest(unittest.TestCase):
    def test_aot_oom_trace_is_not_a_serialized_context_or_abi_pass(self):
        exp = Path(__file__).resolve().parents[1]
        path = exp / 'results/query-prescale-aot-attempt-1-memory-limit'
        result = json.loads((path / 'result.json').read_text())
        self.assertEqual(result['unit_result'], 'oom-kill')
        self.assertEqual(result['memory_peak_bytes'], 12 << 30)
        self.assertEqual(result['memory_swap_peak_bytes'], 0)
        for field in ('complete_compiled_context', 'context_binary_present', 'context_model_present',
                      'context_metadata_present', 'graph_execution_requested', 'phone_access', 'speedup_claim'):
            self.assertFalse(result[field])
        self.assertIsNone(result['ordered_abi_comparison'])
        self.assertIsNone(result['exact_oom_operation'])
        self.assertEqual(result['framework_trace_summary']['supported_nodes'], 1542)
        self.assertEqual(result['framework_trace_summary']['unsupported_nodes'], 0)
        self.assertEqual(result['framework_query_multiply_mappings'], 8)
        self.assertEqual(result['framework_post_score_multiply_mappings'], 0)
        self.assertTrue(result['immutable_artifacts_after_verified'])
        self.assertTrue(result['process_after_absent'])

    def test_aot_settings_remain_prepare_only_and_resource_bounded(self):
        import ast
        exp = Path(__file__).resolve().parents[1]
        config = json.loads((exp / 'protocol/query-prescale-aot-check.json').read_text())
        self.assertEqual(config['provider_options']['enable_htp_prepare_only'], '1')
        self.assertTrue(config['session_disable_cpu_ep_fallback'])
        self.assertEqual(config['resources']['unit_timeout_seconds'], 900)
        self.assertEqual(config['resources']['memory_max_bytes'], 12 << 30)
        self.assertEqual(config['resources']['swap_max_bytes'], 0)
        text = (exp / 'tools/compile_qnn_part.py').read_text()
        tree = ast.parse(text)
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                             and isinstance(node.func.value, ast.Name) and node.func.value.id == 'session'
                             and node.func.attr in ('run', 'run_with_iobinding', 'run_async') for node in ast.walk(tree)))
        self.assertIn('options.intra_op_num_threads = args.threads', text)
        self.assertIn('options.inter_op_num_threads = 1', text)
        self.assertIn('"enable_htp_prepare_only": "1"', text)
        self.assertIn('"session.disable_cpu_ep_fallback", "1"', text)

    def test_first_attempt_retains_baseline_without_comparison_claim(self):
        exp = Path(__file__).resolve().parents[1]
        path = exp / 'results/query-prescale-cpu-attempt-1-external-path-failure'
        result = json.loads((path / 'result.json').read_text())
        self.assertEqual(result['baseline_outputs'], 60)
        self.assertTrue(result['baseline_all_finite'])
        for field in ('derivative_executions', 'debug_executions', 'fp16_proxy_executions'):
            self.assertEqual(result[field], 0)
        self.assertIsNone(result['all60_comparison'])
        self.assertIsNone(result['logit_ranking_changes'])
        self.assertIn('escapes model directory', (path / 'raw/derivative.stderr').read_text())
        self.assertEqual(len(json.loads((path / 'raw/baseline-manifest.json').read_text())), 60)
        self.assertEqual(len(json.loads((path / 'raw/inputs-manifest.json').read_text())), 41)
        self.assertTrue(all(x['unchanged'] for x in json.loads((path / 'immutable-after.json').read_text())))

    def test_retained_continuation_binds_all60_bytes_rankings_and_copy_identity(self):
        from prescale_ar171_queries import sha
        exp = Path(__file__).resolve().parents[1]
        path = exp / 'results/query-prescale-cpu-attempt-2-numerical-check'
        result = json.loads((path / 'result.json').read_text())
        summary = json.loads((path / 'summary.json').read_text())
        self.assertEqual(sha(path / 'result.json'), summary['result_sha256'])
        self.assertTrue(result['baseline_reused_without_execution'])
        self.assertTrue(result['prepared']['baseline_reuse']['exact_graph_data_input_runtime_options_output_binding_passed'])
        self.assertEqual(len(result['all60']), 60)
        for tensor in result['all60']:
            self.assertTrue(tensor['bitwise_equal'])
            self.assertEqual(tensor['reference']['finite'], tensor['element_count'])
            self.assertEqual(tensor['candidate']['finite'], tensor['element_count'])
            self.assertEqual(tensor['finite_pair_max_abs_delta'], 0)
            self.assertEqual(tensor['finite_pair_mean_abs_delta'], 0)
        manifests = [{x['name']: x for x in json.loads((path / f'raw/{v}-manifest.json').read_text())}
                     for v in ('baseline', 'derivative', 'debug')]
        for name, tensor in manifests[0].items():
            for other in manifests[1:]:
                self.assertEqual(tensor['sha256'], other[name]['sha256'])
        self.assertTrue(result['debug_all60_bitwise_equal'])
        self.assertEqual(result['logit_rankings']['entire_vocab_rank_changed_count'], 0)
        self.assertEqual(result['logit_rankings']['reference_argmax'], 597)
        self.assertEqual(result['logit_rankings']['candidate_argmax'], 597)
        copies = result['prepared']['rewrite']['external_copies']
        self.assertEqual(sum(c['bytes'] for c in copies), 2327207936)
        for c in copies:
            self.assertEqual(c['copy_link_count'], 1)
            self.assertEqual(c['source_before_sha256'], c['copy_sha256'])
            self.assertEqual(c['source_before_sha256'], c['source_after_sha256'])
        self.assertTrue(all(x['unchanged'] for x in result['immutable_after']))
        for field in ('phone_access', 'accelerator_aot', 'qnn_runtime', 'speedup_claim', 'quality_equivalence_claim', 'aot_authorized_by_result'):
            self.assertFalse(result[field])

    def test_retained_fp16_proxy_deltas_do_not_become_htp_or_quality_claims(self):
        exp = Path(__file__).resolve().parents[1]
        path = exp / 'results/query-prescale-cpu-attempt-2-numerical-check'
        result = json.loads((path / 'result.json').read_text())
        probes = result['fp16_same_operand_proxies']
        self.assertEqual(len(probes), 8)
        self.assertEqual(sum(p['scores']['unequal_elements'] for p in probes), 8)
        self.assertEqual(sum(p['causal_unmasked_scores']['unequal_elements'] for p in probes), 5)
        self.assertEqual(max(p['scores']['finite_pair_max_abs_delta'] for p in probes), 0.001953125)
        self.assertEqual(sum(p['casts']['pre_query_scale']['finite_nonzero_rounded_to_zero'] for p in probes), 2)
        self.assertEqual(probes[0]['casts']['query_ingress']['finite_nonzero_rounded_to_zero'], 21888)
        self.assertEqual(probes[0]['casts']['key_ingress']['finite_nonzero_rounded_to_zero'], 21888)
        self.assertEqual(sum(c['finite_rounded_to_infinity'] for p in probes for c in p['casts'].values()), 0)
        summary = json.loads((path / 'summary.json').read_text())
        self.assertIsNone(summary['resource_observations']['cgroup_memory_peak_bytes'])
        self.assertIn('unloaded', summary['resource_observations']['cgroup_memory_peak_missing_reason'])
        self.assertIn('not HTP execution', ' '.join(result['limitations']))

    def test_only_eight_score_pairs_change_and_original_is_immutable(self):
        baseline = fixture()
        before = baseline.SerializeToString()
        derived, changes = rewrite(baseline)
        self.assertEqual(baseline.SerializeToString(), before)
        self.assertEqual(len(changes), 8)
        self.assertEqual(len(derived.graph.node), len(baseline.graph.node))
        self.assertEqual([x.SerializeToString() for x in derived.graph.initializer], [x.SerializeToString() for x in baseline.graph.initializer])
        for i in range(8):
            multiply, matmul = derived.graph.node[2 * i:2 * i + 2]
            self.assertEqual(multiply.op_type, 'Mul')
            self.assertEqual(matmul.op_type, 'MatMul')
            self.assertEqual(matmul.input[0], multiply.output[0])
            self.assertEqual(matmul.output[0], baseline.graph.node[2 * i + 1].output[0])
        onnx.checker.check_model(derived)

    def test_reject_ar1_wrong_scale_and_an_extra_score_consumer(self):
        for case in ('ar1', 'scale', 'fanout'):
            model = fixture()
            if case == 'ar1':
                model.graph.input[0].type.tensor_type.shape.dim[1].dim_value = 1
            elif case == 'scale':
                model.graph.initializer[0].CopyFrom(numpy_helper.from_array(np.asarray(0.25, np.float32), '__attn_scale'))
            else:
                model.graph.node.append(helper.make_node('Identity', ['layer-0/htp_chunk/scores'], ['extra'], name='extra'))
            with self.subTest(case=case), self.assertRaises(ValueError):
                rewrite(model)

    def test_stage_is_exclusive_and_does_not_rewrite_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path / 'source.onnx'
            onnx.save(fixture(), source)
            before = source.read_bytes()
            record = stage(source, path / 'derived/model.onnx')
            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(record['initializers_and_interfaces_unchanged'])
            with self.assertRaises(FileExistsError):
                stage(source, path / 'derived/model.onnx')

    def test_external_data_is_independent_byte_identical_regular_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path / 'source.onnx'
            model = fixture()
            model.graph.initializer.append(numpy_helper.from_array(np.arange(256, dtype=np.float32), 'extra_weight'))
            onnx.save_model(model, source, save_as_external_data=True, all_tensors_to_one_file=True,
                            location='weights.bin', size_threshold=512)
            record = stage(source, path / 'isolated/derived.onnx')
            self.assertEqual(len(record['external_copies']), 1)
            data = record['external_copies'][0]
            target, original = Path(data['copy']), Path(data['source'])
            self.assertFalse(target.is_symlink())
            self.assertFalse(target.samefile(original))
            self.assertEqual(target.stat().st_nlink, 1)
            self.assertEqual(target.read_bytes(), original.read_bytes())
            self.assertEqual(data['source_before_sha256'], data['copy_sha256'])
            self.assertEqual(data['source_before_sha256'], data['source_after_sha256'])
            with self.assertRaises(RuntimeError):
                stage(source, path / 'overbudget/derived.onnx', copy_budget_bytes=0)
            with self.assertRaises(ValueError):
                stage(source, path / 'beside-baseline.onnx')

    def test_storage_amendment_pins_prior_outputs_and_unmodified_criteria(self):
        from prescale_ar171_queries import sha
        exp = Path(__file__).resolve().parents[1]
        amendment = json.loads((exp / 'protocol/query-prescale-storage-amendment.json').read_text())
        self.assertEqual(sha(exp / 'protocol/query-prescale-numerical-check.json'), amendment['original_criteria_sha256'])
        raw = exp / 'results/query-prescale-cpu-attempt-1-external-path-failure/raw'
        for filename, field in [('baseline-manifest.json', 'prior_baseline_output_manifest_sha256'),
                                ('inputs-manifest.json', 'prior_input_manifest_sha256'),
                                ('baseline-runtime.json', 'prior_baseline_runtime_sha256')]:
            self.assertEqual(sha(raw / filename), amendment[field])
        self.assertLessEqual(amendment['resources']['continuation_runtime_max_seconds'] + amendment['resources']['prior_service_runtime_seconds'], 1200)

    def test_rounding_distinguishes_subnormal_zero_underflow_and_overflow(self):
        source = np.asarray([0, 2.0 ** -24, 2.0 ** -27, 1, 70000, np.nan, np.inf], np.float32)
        _, record = round16(source)
        self.assertEqual(record['finite_nonzero_rounded_to_zero'], 1)
        self.assertEqual(record['finite_rounded_to_infinity'], 1)
        self.assertEqual(record['rounded_subnormal_count'], 1)
        self.assertEqual(record['input']['finite'], 5)
        self.assertEqual(record['rounded']['positive_inf'], 2)

    def test_power_of_two_reassociation_can_lose_subnormal_query(self):
        post, pre, record = probe(np.asarray([[2.0 ** -24]], np.float32), np.asarray([[1024]], np.float32))
        self.assertNotEqual(float(post[0, 0]), float(pre[0, 0]))
        self.assertEqual(record['casts']['pre_query_scale']['finite_nonzero_rounded_to_zero'], 1)
        self.assertGreater(record['scores']['finite_pair_max_abs_delta'], 0)

    def test_prescaling_can_avoid_intermediate_overflow_not_equivalence(self):
        post, pre, record = probe(np.asarray([[40000]], np.float32), np.asarray([[2]], np.float32))
        self.assertTrue(np.isinf(post).all())
        self.assertTrue(np.isfinite(pre).all())
        self.assertEqual(record['casts']['post_unscaled_matmul']['finite_rounded_to_infinity'], 1)
        self.assertFalse(record['scores']['tight_allclose'])

    def test_signed_zero_is_not_bitwise_equal_and_nonfinite_is_retained(self):
        record = compare(np.asarray([0, 1, np.inf], np.float32), np.asarray([-0., 2, np.nan], np.float32))
        self.assertFalse(record['bitwise_equal'])
        self.assertEqual(record['finite_pair_count'], 2)
        self.assertEqual(record['finite_pair_max_abs_delta'], 1)
        self.assertEqual(record['reference']['positive_inf'], 1)
        self.assertEqual(record['candidate']['nan'], 1)

    def test_exclusive_arrays_and_integrity_check(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'arrays'
            dump_arrays(path, {'positions': np.arange(171, dtype=np.int64)[None, :]})
            self.assertEqual(load_arrays(path)['positions'].shape, (1, 171))
            with self.assertRaises(FileExistsError):
                dump_arrays(path, {'other': np.ones(1)})
            (path / '000.npy').write_bytes(b'broken')
            with self.assertRaises(ValueError):
                load_arrays(path)

    def test_full_vocabulary_ranking_change_and_stable_ties(self):
        a = np.zeros((1, 1, 128000), np.float32)
        b = a.copy()
        b[0, 0, 3] = 1
        record = rankings({'logits_vocab_0_128000': a}, {'logits_vocab_0_128000': b})
        self.assertEqual(record['reference_argmax'], 0)
        self.assertEqual(record['candidate_argmax'], 3)
        self.assertEqual(record['entire_vocab_rank_changed_count'], 4)
        self.assertEqual(record['maximum_rank_displacement'], 3)


if __name__ == '__main__':
    unittest.main()
