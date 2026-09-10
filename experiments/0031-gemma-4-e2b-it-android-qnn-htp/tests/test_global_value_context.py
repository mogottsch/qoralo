"""Pure metadata/source tests; no SDK execution or model loading."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest

EXP = Path(__file__).resolve().parents[1]
TRACK = EXP / 'improvements/0001-long-collapse-speed-quality'
spec = importlib.util.spec_from_file_location('context_inspector', TRACK / 'tools/inspect_global_value_context.py')
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


def baseline_fixture():
    graphs = []
    for ar in (1, 128):
        graph = {'graphName': f'ar{ar}_cl4096_1_of_1'}
        for side, suffix in [('graphInputs', 'in'), ('graphOutputs', 'out')]:
            graph[side] = []
            for layer in range(15):
                prefix = 'past' if layer in (4, 9, 14) else 'swa'
                for kind in ('key', 'value'):
                    tensor = {'name': f'{prefix}_{kind}_{layer}_h0_{suffix}',
                              'dimensions': [1, 1, 1, 1], 'rank': 4,
                              'dataFormat': inspector.FLAT, 'type': side,
                              'dataType': 'QNN_DATATYPE_UFIXED_POINT_16',
                              'quantizeParams': {'scale': 0.1, 'offset': -32768}}
                    graph[side].append({'info': tensor})
        graphs.append({'info': graph})
    return {'info': {'backendId': 6, 'socModel': 43, 'numGraphs': 2,
                     'buildId': 'test-build', 'graphs': graphs}}


def candidate_fixture(baseline):
    candidate = copy.deepcopy(baseline)
    for graph in candidate['info']['graphs']:
        for side in ('graphInputs', 'graphOutputs'):
            for tensor in graph['info'][side]:
                if tensor['info']['name'] in inspector.SELECTED:
                    tensor['info']['dataType'] = inspector.FLOAT16
                    tensor['info']['quantizeParams'] = {'definition': 'undefined'}
    return candidate


class ContextGateTest(unittest.TestCase):
    def test_fp16_flat_pair_is_compatibility_not_runtime_proof(self):
        baseline = baseline_fixture()
        result = inspector.compare_context(candidate_fixture(baseline), baseline)
        self.assertTrue(result['metadata_gate_passed'])
        self.assertEqual(30, result['cache_count'])
        self.assertFalse(result['physical_execution_proven'])
        self.assertFalse(result['full_cpu_free_execution_proven'])
        self.assertFalse(result['fidelity_proven'])

    def test_native_kv_layout_is_rejected(self):
        baseline = baseline_fixture()
        candidate = candidate_fixture(baseline)
        candidate['info']['graphs'][0]['info']['graphInputs'][0]['info']['dataFormat'] = 'HMX_WEIGHT_LAYOUT'
        result = inspector.compare_context(candidate, baseline)
        self.assertFalse(result['metadata_gate_passed'])
        self.assertTrue(any('NativeKV/non-flat cache forbidden' in issue for issue in result['issues']))

    def test_changed_unselected_scale_is_rejected(self):
        baseline = baseline_fixture()
        candidate = candidate_fixture(baseline)
        candidate['info']['graphs'][0]['info']['graphInputs'][0]['info']['quantizeParams']['scale'] = 0.2
        result = inspector.compare_context(candidate, baseline)
        self.assertFalse(result['metadata_gate_passed'])
        self.assertTrue(any('four-way active cache signature mismatch' in issue for issue in result['issues']))

    def test_float_inactive_union_does_not_create_fake_quant_mismatch(self):
        baseline = baseline_fixture()
        candidate = candidate_fixture(baseline)
        for item in candidate['info']['graphs'][0]['info']['graphInputs']:
            if item['info']['name'] in inspector.SELECTED:
                item['info']['quantizeParams'] = {'unused_union': 'not active for FLOAT16'}
        self.assertTrue(inspector.compare_context(candidate, baseline)['metadata_gate_passed'])

    def test_key_derived_clear_is_negative_zero_not_fidelity_proof(self):
        bits = struct.pack('<H', 1 << 15)
        self.assertEqual(0.0, struct.unpack('<e', bits)[0])
        self.assertEqual(b'\x00\x80', bits)

    def test_retained_context_metadata_and_claim_boundaries(self):
        folder = TRACK / 'results/global-value-fp16-context-attempt-01'
        result = json.loads((folder / 'result.json').read_text())
        candidate = json.loads((folder / 'raw/context-info.json').read_text())
        baseline = json.loads((folder / 'raw/baseline-context-info.json').read_text())
        observed = inspector.compare_context(candidate, baseline)
        for key, value in observed.items():
            self.assertEqual(value, result['metadata_validation'][key])
        self.assertEqual({'QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER': 120}, observed['cache_data_format_counts'])
        self.assertEqual(30, observed['cache_count'])
        for graph in observed['graphs'].values():
            self.assertEqual(38, graph['graphInputs']['count'])
            self.assertEqual(31, graph['graphOutputs']['count'])
            self.assertEqual(3, graph['graphInputs']['datatypes']['QNN_DATATYPE_FLOAT_16'])
            self.assertEqual(3, graph['graphOutputs']['datatypes']['QNN_DATATYPE_FLOAT_16'])
        self.assertEqual('1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8', result['context']['sha256'])
        self.assertEqual(1186430976, result['context']['bytes'])
        self.assertEqual(61440, result['context_size_delta_bytes'])
        config = result['compiler_config']
        self.assertTrue(config['context_custom_configs'][0]['weight_sharing_enabled'])
        self.assertEqual('v73', config['device_custom_configs'][0]['dsp_arch'])
        self.assertTrue(all(g['optimization_type'] == 3 and g['fp16_relaxed_precision'] == 0
                            for g in config['graph_custom_configs']))
        self.assertIsNone(result['unsupported_status']['exhaustive_unsupported_operator_count'])
        self.assertIsNone(result['unmeasured']['host_fidelity'])
        self.assertIsNone(result['unmeasured']['physical_htp_execution'])
        self.assertFalse(result['publication']['registry_eligible'])
        self.assertTrue(result['lifecycle']['scratch_cleanup']['verified_absent'])
        self.assertFalse(result['genie_fp16_source_check']['runtime_validation_performed'])
        for line in (folder / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(digest, hashlib.sha256((folder / name).read_bytes()).hexdigest())

    def test_accepted_compile_recipe_is_unchanged(self):
        path = EXP / 'tools/compile_qairt_cache_aligned.py'
        self.assertEqual('cf997a64ec255d53b51f4b26e42ff426e8a06acce1c8626077be79698272a67b',
                         hashlib.sha256(path.read_bytes()).hexdigest())
        source = (TRACK / 'tools/compile_global_value_fp16_context.py').read_text()
        self.assertIn('legacy.main()', source)
        self.assertIn('options_mutated_by_observer', source)
        self.assertIn('only one native context compilation is authorized', source)


if __name__ == '__main__':
    unittest.main()
