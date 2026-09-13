import contextlib
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))


class LegacyLogitTests(unittest.TestCase):
    def test_real_PLE_dispatch_integration_with_synthetic_backend(self):
        fixture=importlib.import_module('run_legacy_logits_fixture')
        if not (fixture.BASE/fixture.REL).is_file():self.skipTest('private bound SDK source unavailable')
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            out=Path(tmp)/'fixture';fixture.build_fixture(out);x=json.loads((out/'result.json').read_text())
            self.assertTrue(x['actual_engine_dispatch_and_getDequant_source_compiled'])
            self.assertTrue(x['original_and_relocated_dequant_bit_identical'])
            self.assertEqual(x['original_dequant_call_count'],1);self.assertEqual(x['request_sampler_calls'],1)
            self.assertFalse(x['full_QNN_loop_or_model_executed']);self.assertFalse(x['real_sampler_executed'])
            new=x['variants']['relocated'];self.assertEqual(new['raw_values_verified'],262144)
            self.assertTrue(new['row8_selected_once']);self.assertTrue(new['capture_before_original_dequant'])
            self.assertEqual(x['variants']['original']['capture_records'],0);self.assertEqual(new['capture_records'],2)

    def test_patch_relocates_observation_without_second_offset(self):
        m=importlib.import_module('prepare_legacy_prefill_logits');old,new=m.hooks()
        first='  __TRACE("qnn-htp: getDequantLogits Returning {}*{} from [{}]", count, m_vocab_size, step.str());\n'
        second='  __TRACE("qnn-htp: getLogits Returning {}*{} from [{}]", count, m_vocab_size, step.str());\n'
        source=first+'original_dequant();\n'+second+old+'original_Tensor();\n';changed=m.patch(source)
        self.assertEqual(changed.replace(new,'').replace(second,second+old),source)
        self.assertLess(changed.index(new),changed.index('original_dequant();'))
        self.assertIn('"logits", logit_buffer,\n                                  size * bitwidth',new)
        self.assertNotIn('logit_buffer +',new)
        with self.assertRaises(ValueError):m.patch('unbound source')

    def test_row_distinct_sentinels_detect_double_offset(self):
        for i in range(262144):self.assertNotEqual(8*512+i%512,16*512+i%512)

    def test_new_controller_keeps_AS12_and_all_materialized_scripts(self):
        old=importlib.import_module('phone_mapping_as12_capture');new=importlib.import_module('phone_legacy_prefill_capture')
        m0,_=old.load_adapter();c0,r0=m0.load_lifecycle({},False);m1,b=new.load_adapter();c1,r1=m1.load_lifecycle({},False)
        self.assertEqual(c0.scripts('/data/local/tmp/SAME_SYNTHETIC_ROOT'),c1.scripts('/data/local/tmp/SAME_SYNTHETIC_ROOT'))
        p=c1.plan();self.assertEqual(p['phone_address_space_limit_bytes'],12884901888);self.assertEqual(p['process_deadline_seconds'],300)
        self.assertEqual(p['reviewed_stage_digest'],new.DIGEST);self.assertFalse(p['phone_permission_granted_by_plan'])
        self.assertFalse(b['AS12_model_LUT_input_caps_time_capture_cleanup_changed']);self.assertIn('_finish_remote',c1.Controller.__dict__)

    def test_AS12_success_is_not_a_complete_capture_or_unique_AS_cause(self):
        root=TRACK/'results/paired-mapping-as12-discriminator-01';r=json.loads((root/'result.json').read_text());a=json.loads((root/'analysis.json').read_text())
        self.assertEqual(r['AR128_status0'],16);self.assertEqual(r['complete_noncache_inputs'],128);self.assertEqual(r['final_logit_payloads'],0)
        self.assertFalse(r['complete_paired_capture']);self.assertFalse(r['host_reference_started'])
        self.assertTrue(a['kernel_VmPeak_below_old8GiB_cap']);self.assertFalse(a['AS12_uniquely_necessary_or_sole_cause_proven'])
        self.assertEqual(a['actual_PLE_path'],'getDequantLogits(std::span<float>, finalstep, count1)')
        rejection=json.loads((root/'binding-rejection.json').read_text());self.assertTrue(rejection['binding_rejected']);self.assertFalse(rejection['model_executed'])


if __name__=='__main__':unittest.main()
