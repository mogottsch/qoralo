import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
fix=importlib.import_module('declared_dlc_reference_fp16')


class FP16StorageTests(unittest.TestCase):
    def test_native_strided_endian_special_words_preserve_bits(self):
        words=np.array([0,0x8000,0x3c00,0xc000,1,0x7c00,0xfc00,0x7e01,0x7d55],dtype=np.uint16)
        for value in [words,words[::2],words.astype('>u2'),words.view(np.float16),words.astype('>u2').view('>f2')]:
            half=fix.storage_view(value,'Float_16')
            expected=words[::2] if value.shape==words[::2].shape else words
            self.assertEqual(half.dtype,np.float16);np.testing.assert_array_equal(half.view(np.uint16),expected)
        words.setflags(write=False);half=fix.storage_view(words,'Float_16')
        self.assertFalse(half.flags.writeable);self.assertTrue(np.shares_memory(words,half))
        self.assertIs(fix.storage_view(half,'Float_16'),half)
        with self.assertRaises(ValueError):fix.storage_view(words.astype(np.uint32),'Float_16')

    def test_true_UF16_and_BW4_decode_are_unchanged(self):
        runtime,_=fix.load_runtime();words=np.array([0,32768,65535],dtype=np.uint16)
        self.assertIs(fix.storage_view(words,'uFxp_16'),words)
        q={'datatype':'uFxp_16','dimensions':[3],'grid':{'axis':None,'bitwidths':[16],'scale':[.5],'offset':[-32768]}}
        np.testing.assert_array_equal(runtime.decode(words,q),(words.astype(np.float32)-32768)*.5)
        s={'datatype':'sFxp_8','dimensions':[2],'grid':{'axis':None,'bitwidths':[4],'scale':[1.0],'offset':[0]}}
        np.testing.assert_array_equal(runtime.decode(np.array([13,-3],dtype=np.int8),s),[-3,-3])

    def test_all30_actual_static_FP16_tensors_against_independent_IEEE_decoder(self):
        policy=TRACK/'.local/matched-prefill-reference/policy-01/policy.json'
        if not policy.exists():self.skipTest('private static policy unavailable')
        p=json.loads(policy.read_text());runtime,_=fix.load_runtime();count=0;changed=0
        for spec in p['tensors'].values():
            if spec['datatype']!='Float_16' or 'static' not in spec:continue
            raw=np.load(policy.parent/spec['static']['file'],mmap_mode='r',allow_pickle=False)
            half=fix.storage_view(raw,spec['datatype']);decoded=runtime.decode(raw,spec)
            expected=np.array([struct.unpack('<e',struct.pack('<H',int(v)))[0] for v in raw.reshape(-1)],dtype=np.float32).reshape(raw.shape)
            np.testing.assert_array_equal(decoded.view(np.uint32),expected.view(np.uint32));self.assertFalse(half.flags.writeable)
            changed+=int(np.count_nonzero(raw.astype(np.float32)!=decoded));count+=1
        self.assertEqual(count,30);self.assertEqual(changed,4608)

    def test_actual_loader_preserved_reshape_first_RMS_and_Cast_fixture(self):
        root=TRACK/'.local/declared-reference-static-audit/fp16-transport-01/synthetic';path=root/'policy.json'
        if not path.exists():self.skipTest('retained authored synthetic fixture unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            runtime,receipt=fix.load_runtime(Path(tmp)/'nonfinite.json');reference=runtime.DeclaredDlcReference(path)
            x=np.array([1,2,3,4],dtype=np.float16).reshape(1,1,1,4)
            out=reference.run_encoded({'x':x})['z']
            expected=(x.astype(np.float32)/np.sqrt(np.mean(x.astype(np.float32)**2,axis=3,keepdims=True)+np.float32(1e-6))).astype(np.float16)
            np.testing.assert_array_equal(out.view(np.uint16),expected.view(np.uint16));self.assertIsNone(runtime.finite_observer.first)
            self.assertTrue(receipt['true_UFIXED16_and_BW4_unchanged'])

    def test_nonfinite_integer_encode_stops_before_round_clip_cast(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'first.json';runtime,_=fix.load_runtime(path);runtime.finite_observer.set_context({'index':17,'name':'test'},3)
            q={'name':'output','datatype':'uFxp_16','dimensions':[2],'grid':{'axis':None,'bitwidths':[16],'scale':[1.0],'offset':[0]}}
            with self.assertRaises(fix.NonFiniteIntermediate):runtime.encode(np.array([np.nan,np.inf],dtype=np.float32),q)
            first=path.read_bytes();row=json.loads(first);self.assertEqual(row['operator_index'],17);self.assertEqual(row['chunk'],3)
            self.assertEqual(row['phase'],'encode_input');self.assertFalse(row['arithmetic_repaired_or_clipped_by_observer'])
            self.assertEqual(os.stat(path).st_mode&0o777,0o600)
            with self.assertRaises(fix.NonFiniteIntermediate):runtime.encode(np.array([np.nan,0],dtype=np.float32),q)
            self.assertEqual(path.read_bytes(),first)

    def test_hidden_RMS_overflow_and_FP16_encode_overflow_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime,_=fix.load_runtime(Path(tmp)/'rms.json');runtime.finite_observer.set_context({'index':52,'name':'synthetic_RMS'},0)
            with self.assertRaises(fix.NonFiniteIntermediate):runtime.logical_op({'type':'RmsNorm','attrs':{'axes':[0],'epsilon':1e-6}},[np.array([1e30],dtype=np.float32)],[1])
            row=json.loads((Path(tmp)/'rms.json').read_text());self.assertEqual(row['operator_index'],52);self.assertEqual(row['phase'],'logical_op')
            runtime,_=fix.load_runtime(Path(tmp)/'half.json')
            with self.assertRaises(fix.NonFiniteIntermediate):runtime.encode(np.array([70000],dtype=np.float32),{'datatype':'Float_16','name':'half'})
            self.assertTrue((Path(tmp)/'half.json').exists())

    def test_finite_declared_clipping_and_underflow_are_not_repaired(self):
        runtime,_=fix.load_runtime();q={'datatype':'uFxp_16','dimensions':[3],'grid':{'axis':None,'bitwidths':[16],'scale':[1.0],'offset':[0]}}
        np.testing.assert_array_equal(runtime.encode(np.array([-10,2.5,100000],dtype=np.float32),q),[0,2,65535])
        half=runtime.encode(np.array([1e-30],dtype=np.float32),{'datatype':'Float_16'});self.assertEqual(half[0],0)
        self.assertIsNone(runtime.finite_observer.first)

    def test_corrected_host_new_grant_and_unchanged_limits(self):
        tool=importlib.import_module('run_corrected_paired_prefill_host');module,binding=tool.load_adapter()
        sources=module.assert_host_sources();self.assertEqual(sources[str(TRACK/'tools/declared_dlc_reference_fp16.py')],tool.CORRECTED_REFERENCE_SHA)
        self.assertTrue(binding['same_model_policy_actual_inputs_own30caches_and_limits']);self.assertFalse(binding['phone_access'])
        output=io.StringIO()
        with patch.object(sys,'argv',['plan']),contextlib.redirect_stdout(output):self.assertEqual(module.main(),0)
        self.assertEqual(json.loads(output.getvalue())['limits'],{'memory_max_GiB':12,'swap_max_GiB':2,'CPU_cores':2,'total_seconds':1800,'work_seconds':1770,'new_output_disk_GiB':1,'trace_cap_MiB':64})
        with patch.object(sys,'argv',['test','--execute','--pi-grant','pi-gemma-legacy-prefill-20260913T125558Z-01-host']):
            with self.assertRaises(PermissionError):module.main()

    def test_noncontiguous_nonfinite_scan_and_exclusive_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'first.json';path.write_text('prior immutable receipt')
            observer=fix.FiniteObserver(path);value=np.array([0,np.inf,0,np.nan],dtype=np.float32)[1::2]
            with self.assertRaises(fix.NonFiniteIntermediate):observer.check(value,'test')
            self.assertEqual(path.read_text(),'prior immutable receipt');self.assertEqual(observer.first['block_nan_count'],1)
            self.assertEqual(observer.first['block_positive_infinity_count'],1)


if __name__=='__main__':unittest.main()
