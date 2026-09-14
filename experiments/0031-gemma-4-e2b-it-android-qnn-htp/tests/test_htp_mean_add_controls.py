import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
p=importlib.import_module('phone_htp_mean_add_discriminator')


class MeanAddControlTests(unittest.TestCase):
    def test_plan_two_single_output_controls_no_power_chain_or_permission(self):
        m,r=p.load_lifecycle({},False);plan=m.plan()
        self.assertFalse(plan['phone_permission_granted_by_plan']);self.assertEqual(plan['adb_calls'],0)
        self.assertEqual(plan['selected_cases'],['mean_edge','epsilon_add']);self.assertEqual(plan['expected_raw_output_bytes'],512)
        self.assertFalse(plan['Power_execution_requested']);self.assertFalse(plan['normalization_chain_execution_requested'])
        self.assertTrue(plan['single_output_each']);self.assertTrue(plan['continuous_single_phone_lease'])
        b,_,_=p.components();manifest=b.verify_stage(b.STAGE,p.DIGEST);self.assertEqual(len(manifest['files']),8)
        self.assertFalse(manifest['Power_graph_included'])

    def test_actual_single_ops_grids_and_scalar_are_frozen(self):
        path=TRACK/'.local/htp-mean-add-controls/prepare-01/result.json'
        if not path.exists():self.skipTest('private prepared controls unavailable')
        r=json.loads(path.read_text());self.assertTrue(r['context_IO_verified']);self.assertEqual(len(r['graphs']),2)
        mean,add=[g['inspection'] for g in r['graphs']]
        self.assertEqual(mean['operator_type'],'Reduce');self.assertEqual(mean['attrs'],{'axes':[2],'keep_dims':True,'reduce_type':'ReduceMean'})
        self.assertEqual(add['operator_type'],'Eltwise_Binary');self.assertEqual(add['attrs'],{'operation':0})
        self.assertEqual(add['tensors']['epsilon']['raw_scalar'],[655])
        self.assertEqual(mean['tensors']['y']['grid'],add['tensors']['x']['grid']);self.assertEqual(add['tensors']['x']['grid'],add['tensors']['y']['grid'])

    def test_full_raw_input_patterns_zero_sparse_and_finite(self):
        root=TRACK/'.local/htp-mean-add-controls/prepare-01'
        if not root.exists():self.skipTest('private inputs unavailable')
        mean=np.fromfile(root/'mean_edge/input.uint16le',dtype='<u2').reshape(1,128,1536)
        for row in range(128):
            values=mean[0,row]
            if row%4==0:self.assertFalse(values.any())
            elif row%4==1:self.assertEqual(np.count_nonzero(values),1);self.assertEqual(values[0],1)
            elif row%4==2:self.assertTrue(np.all(values==1))
            else:self.assertTrue(np.all(values==20))
        add=np.fromfile(root/'epsilon_add/input.uint16le',dtype='<u2');np.testing.assert_array_equal(add,np.resize([0,1,22,434],128))

    def test_selection_shells_and_no_power_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts=p.all_scripts('/data/local/tmp/SYNTHETIC');self.assertEqual(len(scripts),8)
            for name,text in scripts.items():
                path=Path(tmp)/name;path.write_text(text);self.assertEqual(subprocess.run(['/bin/sh','-n',str(path)],capture_output=True).returncode,0)
            for case in p.CASES:
                args=p.case_argv('/data/local/tmp/SYNTHETIC',case);self.assertIn('/data/local/tmp/SYNTHETIC/mean-add-context.bin',args)
                selected=args[args.index('--input_list')+1].split(',');self.assertEqual(len(selected),2);self.assertEqual(sum(x!='__' for x in selected),1)
                self.assertNotIn('power_edge',args[args.index('--input_list')+1])

    def test_actual_two_phase_lease_and_failure_boundary_reused(self):
        import test_htp_chain_selection as shared
        with patch.object(shared,'c',p):
            tester=shared.HTPChainSelectionTests();r,ops=tester.exercise()
            self.assertEqual([x['case'] for x in r['case_results']],list(p.CASES));self.assertEqual(r['process_exit_code'],0)
            self.assertTrue(r['postflight_app_identity']['verified']);self.assertEqual(ops.count('raw.pull'),1)
            r,ops=tester.exercise(first='exit7');self.assertEqual(sum(x.endswith('.process.launch') for x in ops),1)
            self.assertTrue(r['phone_lock_released']);self.assertTrue(r['raw_pull_completed'])


if __name__=='__main__':unittest.main()
