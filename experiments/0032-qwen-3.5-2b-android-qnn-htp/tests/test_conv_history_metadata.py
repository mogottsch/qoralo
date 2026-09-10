"""Pure stdlib metadata/scalar tests; no torch import or model runtime."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

EXP=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('conv_audit',EXP/'tools/audit_conv_history_metadata.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class MetadataAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace=json.loads((EXP/'results/conv-history-encoding-audit-20260910/qdq-metadata-trace.json').read_text())

    def program(self):
        inputs=['tokens','mask','position']+[f'states_{i}' for i in range(48)]
        outputs=[{'as_tensor':{'name':f'other_{i}'}} for i in range(73)]
        outputs[25]={'as_tensor':{'name':'dequantize_per_tensor_221'}}
        return {'torch_version':'synthetic-metadata-only','graph_module':{
            'signature':{'input_specs':[{'user_input':{'arg':{'as_tensor':{'name':n}}}} for n in inputs]},
            'graph':{'nodes':copy.deepcopy(list(self.trace['selected_nodes'].values())), 'outputs':outputs,
                     'tensor_values':{'states_24':self.trace['input_tensor_metadata'],
                                      'dequantize_per_tensor_221':self.trace['output_tensor_metadata']}}}}

    def test_scalar_chain_exactly_reproduces_observed_qdq(self):
        r=audit.inspect_program(self.program(),23.721895217895508)
        self.assertEqual(22.131549835205078,r['scalar_result_fp32'])
        self.assertEqual(67539,r['scalar_trace'][0]['unclamped_code'])
        self.assertEqual(65535,r['scalar_trace'][0]['clamped_code'])
        self.assertTrue(r['scalar_trace'][0]['clipped'])
        self.assertFalse(r['scalar_trace'][1]['clipped'])
        self.assertFalse(r['scalar_trace'][2]['clipped'])

    def test_observation_is_not_final_output_ceiling(self):
        r=audit.inspect_program(self.program(),23.721895217895508)
        self.assertEqual(23.721895217895508,r['scalar_trace'][2]['representable_max_fp32'])
        self.assertEqual(63590,r['scalar_trace'][2]['clamped_code'])
        self.assertLess(r['scalar_result_fp32'],r['scalar_trace'][2]['representable_max_fp32'])

    def test_output_only_hypothesis_is_not_exact_observed_qnn_path(self):
        r=audit.inspect_program(self.program(),23.721895217895508)
        predicted=r['output_only_hypothesis']['output_fp32']
        self.assertNotEqual(23.72189712524414,predicted)
        self.assertLess(abs(23.72189712524414-predicted),2e-6)

    def test_lineage_change_is_rejected(self):
        p=self.program();p['graph_module']['graph']['nodes'][0]['inputs'][0]['arg']['as_tensor']['name']='states_23'
        with self.assertRaisesRegex(ValueError,'lineage'):audit.inspect_program(p,23.7)

    def test_mismatching_pair_encoding_is_rejected(self):
        p=self.program()
        n=next(n for n in p['graph_module']['graph']['nodes'] if n['name']=='dequantize_per_tensor_148')
        next(i for i in n['inputs'] if i['name']=='scale')['arg']['as_float']=0.5
        with self.assertRaisesRegex(ValueError,'encoding'):audit.inspect_program(p,23.7)

    def test_fp32_rounding_ties_are_even(self):
        e={'scale':1.,'zero_point':0,'quant_min':0,'quant_max':65535}
        self.assertEqual(0,audit.scalar_qdq(0.5,e)['clamped_code'])
        self.assertEqual(2,audit.scalar_qdq(1.5,e)['clamped_code'])
        self.assertEqual(2,audit.scalar_qdq(2.5,e)['clamped_code'])

    def test_archive_reader_never_reads_weights_constants_or_sample_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fake.pt2'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('fake/models/model.json',json.dumps(self.program()))
                z.writestr('fake/data/weights/secret','do not read')
                z.writestr('fake/data/constants/secret','do not read')
                z.writestr('fake/data/sample_inputs/model.pt','do not read')
            original=zipfile.ZipFile.read;seen=[]
            def checked(self,name,*args,**kwargs):
                seen.append(name)
                if name!='fake/models/model.json':raise AssertionError('Forbidden payload read')
                return original(self,name,*args,**kwargs)
            with mock.patch.object(zipfile.ZipFile,'read',checked):
                r=audit.audit(path,Path(tmp)/'out',23.721895217895508)
            self.assertEqual(['fake/models/model.json'],seen)
            self.assertEqual(0,r['archive_metadata']['weight_constant_or_sample_input_members_read'])
            self.assertFalse(r['archive_metadata']['archive_sha256_recomputed'])


if __name__=='__main__':unittest.main()
