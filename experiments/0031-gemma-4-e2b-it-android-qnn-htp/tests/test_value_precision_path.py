import importlib.util
from pathlib import Path
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'improvements/0001-long-collapse-speed-quality/tools/value_precision_path.py'
spec = importlib.util.spec_from_file_location('value_precision_path', TOOL)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def t(name, dtype):
    return {'name': name, 'datatype': dtype, 'tensor_type': 'NATIVE', 'dimensions': '1,1,1,32'}


def op(n, kind, inputs, outputs):
    return {'id': n, 'name': f'op{n}', 'type': kind, 'inputs': inputs, 'outputs': outputs}


class ValuePrecisionTests(unittest.TestCase):
    def test_scoped_float_overrides_leave_original_other_activations_and_parameters(self):
        old = {'version': '1.0.0', 'activation_encodings': [
            {'name': 'keep', 'dtype': 'INT', 'bw': 16, 'scale': [1]},
            {'name': 'change', 'dtype': 'INT', 'bw': 16, 'scale': [2]}],
            'param_encodings': [{'name': 'weights', 'dtype': 'INT', 'bw': 4}]}
        new, changes = m.override_float16(old, {'change', 'insert'})
        self.assertEqual(new['activation_encodings'][0], old['activation_encodings'][0])
        self.assertEqual(new['param_encodings'], old['param_encodings'])
        self.assertEqual(old['activation_encodings'][1]['dtype'], 'INT')
        self.assertEqual(new['activation_encodings'][1], m.float16_encoding('change'))
        self.assertEqual([e['name'] for e in changes], ['change', 'insert'])
        self.assertIsNone(changes[1]['before'])
        self.assertNotIn('scale', new['activation_encodings'][1])

    def test_v2_cannot_silently_discard_float_overrides(self):
        with self.assertRaises(ValueError):
            m.override_float16({'version': '2.0.0'}, {'x'})

    def test_duplicate_or_unspecified_scope_rejected(self):
        enc = {'version': '1.0.0', 'activation_encodings': [{'name': 'a'}, {'name': 'a'}]}
        with self.assertRaises(ValueError):
            m.override_float16(enc, {'a'})
        with self.assertRaises(ValueError):
            m.override_float16(enc, set())

    def graph(self, quant_export=False, quant_read=False):
        f, q = 'Float_16', 'uFxp_16'
        ops = [op(0, 'RmsNorm', [t('v_projected', f)], [t('normal', f)])]
        exported = 'normal'
        if quant_export:
            ops += [op(1, 'Convert', [t('normal', f)], [t('quant', q)]),
                    op(2, 'Dequantize', [t('quant', q)], [t('dequant', f)])]
            exported = 'dequant'
        ops += [op(3, 'Cast', [t(exported, f)], [t('cache_out', f)]),
                op(4, 'Concat', [t('cache_in', f), t(exported, f)], [t('joined', f)])]
        dtype = q if quant_read else f
        if quant_read:
            ops += [op(5, 'Convert', [t('joined', f)], [t('read_values', q)])]
        ops += [op(6, 'MatMul', [t('p', dtype), t('read_values' if quant_read else 'joined', dtype)], [t('y', dtype)])]
        return {'operators': ops, 'io': {'output': {'cache_out': {'datatype': f}}}}

    def test_fp16_cache_io_not_enough_for_precision_gate(self):
        self.assertFalse(m.fixture_gate(self.graph(quant_export=True), True)['passed'])
        self.assertFalse(m.fixture_gate(self.graph(quant_read=True), True)['passed'])

    def test_coupled_probability_input_is_required(self):
        graph = self.graph()
        graph['operators'][-1]['inputs'][0]['datatype'] = 'uFxp_16'
        self.assertFalse(m.fixture_gate(graph, True)['passed'])

    def test_expected_precision_and_control_pass(self):
        self.assertTrue(m.fixture_gate(self.graph(), True)['passed'])
        self.assertTrue(m.fixture_gate(self.graph(True, True), False)['passed'])

    def test_control_must_actually_demonstrate_quantization(self):
        self.assertFalse(m.fixture_gate(self.graph(), False)['passed'])

    def test_synthetic_retained_quantization_pattern_fails_precision_gate(self):
        # Synthetic counterexample; this helper is not a full-model validator.
        graph = self.graph(True, True)
        result = m.fixture_gate(graph, True)
        self.assertTrue(any('export' in x for x in result['issues']))
        self.assertTrue(any('MatMul' in x for x in result['issues']))

    def full_case(self):
        prior = self.graph(False, True)
        candidate = self.graph()
        candidate['operators'].append(op(7, 'Convert', [t('p', 'uFxp_16')], [t('p_float', 'Float_16')]))
        next(o for o in candidate['operators'] if o['type'] == 'MatMul')['inputs'][0]['name'] = 'p_float'
        for graph in (prior, candidate):
            graph['operators'].extend([
                op(8, 'Conv2d', [t('hidden', 'uFxp_16')], [t('v_projected', 'uFxp_16')]),
                op(9, 'Softmax', [t('scores', 'uFxp_16')], [t('p', 'uFxp_16')]),
                op(10, 'Convert', [t('v_projected', 'uFxp_16')], [t('v_float', 'Float_16')]),
            ])
            graph['operators'][0]['inputs'][0]['name'] = 'v_float'
        plan = [{'layer': 4, 'concat': 'joined', 'consumer_nodes': ['op6'],
                 'cache_output': 'cache_out', 'v_projection_boundary': 'v_projected'}]
        return prior, candidate, plan

    def test_full_gate_preserves_interface_probability_and_projection_boundaries(self):
        prior, candidate, plan = self.full_case()
        self.assertTrue(m.full_dlc_gate(candidate, prior, plan)['passed'])
        self.assertFalse(m.full_dlc_gate(prior, prior, plan)['passed'])

    def test_full_gate_catches_hidden_probability_scope_expansion(self):
        prior, candidate, plan = self.full_case()
        next(o for o in candidate['operators'] if o['id'] == 7)['inputs'][0]['datatype'] = 'Float_16'
        result = m.full_dlc_gate(candidate, prior, plan)
        self.assertFalse(result['passed'])
        self.assertTrue(any('probability boundary' in x for x in result['issues']))

    def test_full_gate_catches_projection_or_probability_quantization_change(self):
        prior, candidate, plan = self.full_case()
        next(o for o in candidate['operators'] if o['id'] == 8)['outputs'][0]['datatype'] = 'Float_16'
        self.assertFalse(m.full_dlc_gate(candidate, prior, plan)['passed'])
        prior, candidate, plan = self.full_case()
        next(o for o in candidate['operators'] if o['id'] == 9)['parameters'] = ['p encoding : changed grid']
        self.assertFalse(m.full_dlc_gate(candidate, prior, plan)['passed'])

    def test_full_gate_catches_unselected_interface_change(self):
        prior, candidate, plan = self.full_case()
        candidate['io']['output']['other'] = {'datatype': 'Float_16'}
        self.assertFalse(m.full_dlc_gate(candidate, prior, plan)['passed'])

    def test_selected_float_placeholder_changes_are_retained_not_treated_as_integer_grids(self):
        prior, candidate, plan = self.full_case()
        prior['io']['output']['cache_out']['encoding'] = 'No encoding info for this tensor'
        candidate['io']['output']['cache_out']['encoding'] = 'bitwidth 16, min 0, max 0, scale 0, offset 0'
        result = m.full_dlc_gate(candidate, prior, plan)
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['selected_float_encoding_annotation_changes']), 1)
        candidate['io']['output']['cache_out']['dimensions'] = 'wrong'
        self.assertFalse(m.full_dlc_gate(candidate, prior, plan)['passed'])

    def test_active_integer_encoding_changes_still_rejected(self):
        prior, candidate, plan = self.full_case()
        prior['io']['input'] = {'key': {'datatype': 'uFxp_16', 'encoding': 'scale1'}}
        candidate['io']['input'] = {'key': {'datatype': 'uFxp_16', 'encoding': 'scale2'}}
        self.assertFalse(m.full_dlc_gate(candidate, prior, plan)['passed'])


class ExitBoundaryTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('value_precision_exits', TOOL.with_name('value_precision_exits.py'))
        self.exits = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.exits)

    def pair(self):
        def make(floating):
            dtype = 'Float_16' if floating else 'uFxp_16'
            mm = op(0, 'MatMul', [t('p', dtype), t('v', dtype)], [t('m', dtype)])
            cat = op(1, 'Concat', [t('m', dtype)], [t('joined', dtype)])
            cat['parameters'] = ['joined encoding : grid-a']
            proj = op(2, 'Conv2d', [t('joined_q' if floating else 'joined', 'uFxp_16')], [t('output', 'uFxp_16')])
            proj['parameters'] = ['output encoding : grid-b']
            ops = [mm, cat, proj]
            if floating:
                cvt = op(3, 'Convert', [t('joined', 'Float_16')], [t('joined_q', 'uFxp_16')])
                cvt['parameters'] = ['joined_q encoding : grid-a']
                ops.append(cvt)
            return {'operators': ops}
        return make(True), make(False), [{'consumer_nodes': ['op0']}]

    def test_head_reassembly_and_return_grid_are_verified(self):
        current, prior, plan = self.pair()
        result = self.exits.exit_gate(current, prior, plan)
        self.assertTrue(result['passed'])
        self.assertEqual(result['head_group_count'], 1)
        current['operators'][-1]['parameters'] = ['joined_q encoding : changed']
        self.assertFalse(self.exits.exit_gate(current, prior, plan)['passed'])

    def test_projection_or_extra_arithmetic_cannot_pass_silently(self):
        current, prior, plan = self.pair()
        current['operators'][2]['outputs'][0]['datatype'] = 'Float_16'
        self.assertFalse(self.exits.exit_gate(current, prior, plan)['passed'])
        current, prior, plan = self.pair()
        current['operators'][1]['type'] = 'Eltwise_Binary'
        self.assertFalse(self.exits.exit_gate(current, prior, plan)['passed'])
        self.assertFalse(self.exits.exit_gate(current, prior, [])['passed'])


class PairContractTests(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(TOOL.parent))
        try:
            spec = importlib.util.spec_from_file_location('value_context', TOOL.with_name('compile_value_precision_context.py'))
            self.compiler = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.compiler)
        finally:
            sys.path.pop(0)

    def pair(self):
        graphs = {}
        for ar in (1, 128):
            io = {'input': {}, 'output': {}}
            for layer in range(15):
                for kind in ('key', 'value'):
                    dtype = 'Float_16' if kind == 'value' and layer in (4, 9, 14) else 'uFxp_16'
                    for role, suffix in (('input', 'in'), ('output', 'out')):
                        prefix = 'past' if layer in (4, 9, 14) else 'swa'
                        io[role][f'{prefix}_{kind}_{layer}_h0_{suffix}'] = {'datatype': dtype, 'encoding': 'grid' if dtype == 'uFxp_16' else f'placeholder-{ar}-{role}'}
            graphs[ar] = {'io': io}
        return graphs

    def test_active_grid_contract_ignores_only_float_placeholders(self):
        graphs = self.pair()
        self.assertTrue(self.compiler.pair_contract(graphs)['active_four_way_contract_passed'])
        graphs[128]['io']['input']['past_key_4_h0_in']['encoding'] = 'different'
        with self.assertRaises(ValueError):
            self.compiler.pair_contract(graphs)

    def test_missing_or_extra_cache_name_rejected(self):
        graphs = self.pair()
        graphs[128]['io']['output']['past_value_extra_out'] = {'datatype': 'Float_16', 'encoding': 'none'}
        with self.assertRaises(ValueError):
            self.compiler.pair_contract(graphs)

    def test_global_only_enumeration_cannot_omit_the_24_swa_boundaries(self):
        graphs = self.pair()
        for graph in graphs.values():
            graph['io']['output'] = {n: v for n, v in graph['io']['output'].items() if n.startswith('past_')}
        with self.assertRaises(ValueError):
            self.compiler.pair_contract(graphs)


class ResourceGuardTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('value_precision_guard', TOOL.with_name('run_value_precision_guard.py'))
        self.guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.guard)

    def test_actual_headroom_and_known_peak_both_required(self):
        g = 1024**3
        good = {'MemAvailable_bytes': 22*g, 'SwapFree_bytes': 31*g}
        self.assertTrue(self.guard.capacity_ok(good, 17*g, 16*g))
        self.assertFalse(self.guard.capacity_ok({'MemAvailable_bytes': 20*g, 'SwapFree_bytes': 31*g}, 17*g, 16*g))
        self.assertFalse(self.guard.capacity_ok({'MemAvailable_bytes': 22*g, 'SwapFree_bytes': 23*g}, 17*g, 16*g))
        self.assertFalse(self.guard.capacity_ok(good, 12*g, 12*g))


if __name__ == '__main__':
    unittest.main()
