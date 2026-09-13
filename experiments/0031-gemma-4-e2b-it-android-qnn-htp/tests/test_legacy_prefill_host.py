import contextlib
import copy
import importlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))


class LegacyHostBindingTests(unittest.TestCase):
    def test_unchanged_reference_limits_and_original_math_bindings(self):
        tool=importlib.import_module('run_legacy_prefill_host');module,binding=tool.load_adapter()
        self.assertTrue(binding['original_computation_cache_flow_and_limits_unchanged']);self.assertTrue(binding['own30caches'])
        self.assertFalse(binding['HTP_caches_imported']);self.assertEqual(len(binding['source_changes']),3)
        sources=module.assert_host_sources()
        for artifact,expected in tool.REFERENCE_ARTIFACTS.items():self.assertEqual(sources[artifact],expected)
        self.assertEqual(sources[str(TRACK/'tools/run_paired_prefill_host.py')],tool.BASE_SHA)
        self.assertEqual(sources[str(TRACK/'tools/matched_prefill_inputs.py')],'453221b8ee4a9c81d7dc5248e6acf7e2d72dc99b96498a7b52966ac09a0b55cf')
        self.assertEqual(sources[str(TRACK/'tools/declared_dlc_reference.py')],'06f108e24d5370d94e57b24cb8e285106deeef8be0d03d9f29b28187b4cd2045')
        output=io.StringIO()
        with patch.object(sys,'argv',['plan']),contextlib.redirect_stdout(output):self.assertEqual(module.main(),0)
        p=json.loads(output.getvalue());self.assertFalse(p['model_executed']);self.assertFalse(p['phone_access'])
        self.assertEqual(p['limits'],{'memory_max_GiB':12,'swap_max_GiB':2,'CPU_cores':2,'total_seconds':1800,'work_seconds':1770,'new_output_disk_GiB':1,'trace_cap_MiB':64})

    def test_wrong_grant_or_changed_validator_is_rejected_without_launch(self):
        tool=importlib.import_module('run_legacy_prefill_host');module,_=tool.load_adapter()
        with patch.object(sys,'argv',['test','--execute','--pi-grant','wrong-grant']):
            with self.assertRaises(PermissionError):module.main()
        original_sha=tool.sha;policy=next(iter(tool.REFERENCE_ARTIFACTS))
        with patch.object(tool,'sha',side_effect=lambda p:'changed' if str(p)==policy else original_sha(p)):
            with self.assertRaises(ValueError):module.assert_host_sources()
        with patch.object(tool,'sha',return_value='changed'):
            with self.assertRaises(ValueError):tool.load_adapter()

    def test_independent_postflight_and_AS_stage_scope_required(self):
        check=importlib.import_module('validate_legacy_prefill_capture');spec=check.specification()
        x={'run_id':spec['run_id'],'pi_slot':spec['pi_slot'],'reviewed_stage_digest':spec['stage_digest'],'process_exit_code':0,'raw_pull_completed':True,'phone_lock_released':True,'cleanup':'verified_absent','process_cleanup':{'all_absent':True},'current_app_preflight':{'current_apks':spec['expected_APKs'],'generation_and_test_absent':True},'postflight_app_identity':{'current_apks':spec['expected_APKs'],'generation_and_test_absent':True,'verified':True},'scope_adapter':{**spec['scope_bound_fields'],'actual_user_job_quiescence_attested':True}}
        for key in ['preflight.actual_user_job_playback_v2','prelaunch.actual_user_job_playback_v2']:x[key]={'playback_quiescence_observed':True}
        check.check_observations(x,spec)
        for mutate in [lambda v:v['postflight_app_identity'].update(verified=False),lambda v:v.update(phone_lock_released=False),lambda v:v['scope_adapter'].update(address_space_limit_bytes=8589934592),lambda v:v.update(reviewed_stage_digest='old-observer')]:
            bad=copy.deepcopy(x);mutate(bad)
            with self.assertRaises(ValueError):check.check_observations(bad,spec)

    def test_full_same_run_row8_journal_not_partial_or_reoffset(self):
        check=importlib.import_module('validate_legacy_prefill_capture');rows=[]
        for step in range(16):
            for name in check.NONCACHE:
                for event in ['begin','complete']:rows.append({'phase':'input','step':step,'name':name,'event':event,'cache_tensor':False})
        out={'phase':'output','step':15,'name':'logits','cache_tensor':False,'variant':128,'context':4096,'n_past':1920,'n_process':9,'final_valid_row':8,'shape':[1,1,262144],'datatype':'QNN_DATATYPE_UFIXED_POINT_16','scale':0.0008891067700460553,'offset':-31869,'before_sampler_access':True,'before_original_dequantization':True,'row_view_already_offset':True,'source_path':'PLE_legacy_getDequantLogits','file':'15-output-logits.raw','bytes':524288,'completed_payloads':129,'total_payload_bytes':66060288}
        rows += [{**out,'event':'begin'},{**out,'event':'complete'}];check.check_journal(rows)
        for key,value in [('final_valid_row',16),('before_original_dequantization',False),('bytes',262144),('datatype','QNN_DATATYPE_FLOAT_32')]:
            bad=copy.deepcopy(rows);bad[-1][key]=value
            with self.assertRaises(ValueError):check.check_journal(bad)
        with self.assertRaises(ValueError):check.check_journal(rows[:-2])
        with self.assertRaises(ValueError):check.check_journal(rows+[rows[-1]])

    def test_actual_saved_capture_binding_has_no_model_or_phone_side_effect(self):
        check=importlib.import_module('validate_legacy_prefill_capture');spec=check.specification();path=Path(spec['phone_collection'])
        if not path.exists():self.skipTest('private completed capture unavailable')
        result=check.validate(path);self.assertEqual(result['raw_payloads'],129);self.assertEqual(result['raw_payload_bytes'],66060288)
        self.assertTrue(result['actual_AS_readback']['matches_expected']);self.assertTrue(result['phone_released']);self.assertFalse(result['model_executed_by_validation'])


if __name__=='__main__':unittest.main()
