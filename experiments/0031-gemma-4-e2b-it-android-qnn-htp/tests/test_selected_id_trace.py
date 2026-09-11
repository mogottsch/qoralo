"""Source/observer fixtures only. No model, SDK runtime or ADB execution."""
import importlib
import re
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a=importlib.import_module('prepare_selected_id_trace')


class SelectedTraceTests(unittest.TestCase):
    def test_source_patch_is_three_observers_and_exactly_invertible(self):
        source=(a.SDK/'examples/Genie/Genie/src/qualla/dialogs/basic.cpp').read_text()
        patched=a.patch_source(source)
        self.assertEqual(patched.count('gemma_trace_selected_id('),3)
        self.assertEqual(patched.removeprefix('#include "selected_id_trace.hpp"\n').replace(a.NEEDLE+a.OBSERVER,a.NEEDLE),source)
        with self.assertRaises(ValueError):a.patch_source(source+'\n')

    def test_android_recipe_completes_exact_non_windows_source_inventory(self):
        src=a.SDK/'examples/Genie/Genie'
        original=(src/'make/Android.mk').read_text()
        patched=a.patch_android_recipe(original)
        selected=set()
        for pattern in re.findall(r'\$\(wildcard \$\(LOCAL_PATH\)/\.\./(src/[^)]*)\)',patched):
            selected.update(src.glob(pattern))
        selected.update(src/p for p in a.EXTRA_CPP)
        selected={p for p in selected if p.name not in ('DxAllocator.cpp','DxRegs.cpp')}
        expected={p for p in (src/'src').rglob('*.cpp') if '/PAL/windows/' not in str(p) and p.name not in ('DxAllocator.cpp','DxRegs.cpp')}
        self.assertEqual(selected,expected)
        self.assertEqual(len(selected),132)
        self.assertIn('-I $(LOCAL_PATH)/../src/qualla/engines\n',patched)
        with self.assertRaises(ValueError):a.patch_android_recipe(patched)

    def test_observer_reports_real_fixture_ids_without_replacing_or_stopping_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            cpp=root/'fixture.cpp';exe=root/'fixture'
            cpp.write_text('#include "selected_id_trace.hpp"\n#include <cstdio>\n'
                'int main(){int ids[]={8291,50,7,106}; for(unsigned i=0;i<4;++i){'
                'const int selected=ids[i]; gemma_trace_selected_id(i,selected,selected==1||selected==106,1929+i);'
                'if(selected!=ids[i])return 2; std::printf("%d ",selected); } return 0;}\n')
            subprocess.run(['c++','-std=c++20','-O2','-I',str(TRACK/'tools'),str(cpp),'-o',str(exe)],check=True,capture_output=True,timeout=30)
            out=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=5)
            self.assertEqual(out.stdout,'8291 50 7 106 ')
            self.assertIn('ordinal=1 token=50 configured_eos=0',out.stderr)
            self.assertIn('ordinal=2 token=7 configured_eos=0',out.stderr)
            self.assertIn('ordinal=3 token=106 configured_eos=1',out.stderr)


class TraceStageTests(unittest.TestCase):
    def test_controller_changes_only_frozen_scope_and_retains_full_lock_lifecycle(self):
        adapter=importlib.import_module('phone_selected_id_long')
        source,shell,changes,_=adapter.materialize_sources()
        original,old_shell,_,_=adapter.base.materialize_sources()
        for before,after,count in reversed(changes):
            self.assertEqual(source.count(after),count)
            source=source.replace(after,before)
        self.assertEqual(source,original)
        self.assertEqual(shell,old_shell)
        module,receipt=adapter.load_lifecycle()
        self.assertEqual(module.DIGEST,adapter.STAGE_DIGEST)
        self.assertEqual(module.STAGE.name,adapter.STAGE_NAME)
        self.assertFalse(receipt['runtime_binary_equivalence_assumed'])
        self.assertFalse(receipt['signal_guard_atomic'])

    def test_tokenizer_observation_occurs_after_unchanged_query_and_profile(self):
        stage=importlib.import_module('prepare_selected_id_stage')
        original=(stage.SOURCE/'exact-long.script').read_text()
        changed=stage.script_with_tokenizer_observation(original)
        self.assertEqual(changed.replace(stage.POST_QUERY,''),original)
        self.assertGreater(changed.index('tokenizer encodeFromFile'),changed.index('profile save profile1 evidence/long-profile.json'))
        self.assertEqual(changed.count('dialog query '),1)


class TraceAnalysisTests(unittest.TestCase):
    def line(self,n,token,eos=0):
        return f'GEMMA_SELECTED_ID_V1 ordinal={n} token={token} configured_eos={eos} n_past={1929+n}\n'

    def test_actual_50_and_later_sampling_are_separate_from_stop_decision(self):
        parser=importlib.import_module('analyze_selected_id_trace')
        result=parser.summarize(self.line(0,50)+self.line(1,7),2)
        self.assertTrue(result['id50_observed'])
        self.assertTrue(result['id50_occurrences'][0]['subsequent_sampling_observed'])
        self.assertIsNone(result['internal_stop_decision'])
        final=parser.summarize(self.line(0,7)+self.line(1,50),2)
        self.assertIsNone(final['id50_occurrences'][0]['subsequent_sampling_observed'])

    def test_missing_ids_cannot_establish_absence(self):
        parser=importlib.import_module('analyze_selected_id_trace')
        partial=parser.summarize(self.line(0,7)+self.line(2,8),3)
        self.assertFalse(partial['coverage_complete_against_profile'])
        self.assertIsNone(partial['id50_observed'])
        full=parser.summarize(self.line(0,7)+self.line(1,106,1),2)
        self.assertFalse(full['id50_observed'])
        self.assertIsNone(full['internal_stop_decision'])

    def test_full_input_parity_and_malformed_trace(self):
        parser=importlib.import_module('analyze_selected_id_trace')
        self.assertTrue(parser.input_parity('2 105 7\n',struct.pack('<3i',2,105,7))['exact_frozen_input_ids_equal'])
        self.assertFalse(parser.input_parity('2 2 105 7\n',struct.pack('<3i',2,105,7))['exact_frozen_input_ids_equal'])
        malformed=parser.summarize(self.line(0,7).rstrip()+'junk\n',1)
        self.assertTrue(malformed['trace_errors'])
        self.assertIsNone(malformed['id50_observed'])

    def test_membership_mismatch_and_unknown_count_withhold_absence(self):
        parser=importlib.import_module('analyze_selected_id_trace')
        bad=parser.summarize(self.line(0,106,0),1)
        self.assertTrue(bad['trace_errors'])
        self.assertIsNone(bad['id50_observed'])
        self.assertIsNone(parser.summarize(self.line(0,7))['id50_observed'])


if __name__=='__main__':unittest.main()
