"""Host/saved-only tests. No model, GPU or ADB execution."""
import importlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
b=importlib.import_module('build_aligned_litert_reference')
p=importlib.import_module('phone_aligned_litert_reference')
s=importlib.import_module('prepare_aligned_litert_stage')


class AlignedReferenceBuildTests(unittest.TestCase):
    def test_saved_native_receipts_and_runtime_binding(self):
        result=json.loads((s.BUILD/'build-result.json').read_text())
        self.assertTrue(result['actual_success'])
        for phase in ('compile','link'):
            self.assertEqual(json.loads((s.BUILD/(phase+'-exit.json')).read_text())['actual_exit_code'],0)
        self.assertEqual(b.sha(s.BUILD/'work/bin/litert_lm_aligned_reference'),s.BINARY_SHA)
        self.assertEqual(b.sha(s.BUILD/'work/lib/libLiteRt.so'),b.LIB_SHA)
        self.assertFalse(result['historical_gpu_executable_equivalence_proven'])

    def test_exact_private_stage_and_request_scope(self):
        m=s.verify(TRACK/'.local/frozen-stages'/p.STAGE_NAME,p.STAGE_DIGEST)
        self.assertEqual(len(m['files']),13)
        self.assertEqual(m['scope']['requests'],1)
        self.assertEqual(m['scope']['effective_input_tokens'],1929)
        self.assertEqual(m['scope']['max_output_tokens'],2048)

    def test_link_replaces_only_frontend_and_output_plus_runpath(self):
        old=(b.CACHE/b.PARAM).read_text().splitlines();new=b.link_arguments(old)
        self.assertNotIn(b.OLDOBJ,new)
        self.assertEqual(new.count('aligned-reference.o'),1)
        reconstructed=[b.OLDOBJ if x=='aligned-reference.o' else b.OLDOUT if x=='bin/litert_lm_aligned_reference' else x for x in new[:-1]]
        self.assertEqual(reconstructed,old)
        with self.assertRaises(ValueError):b.link_arguments(old+[b.OLDOBJ])

    def test_lifecycle_plan_and_all_shell_syntax(self):
        module,receipt=p.load_lifecycle()
        self.assertTrue(receipt['inverse_reconstruction_exact'])
        self.assertEqual(module.plan()['adb_calls'],0)
        self.assertEqual(module.DIGEST,p.STAGE_DIGEST)
        remote='/data/local/tmp/vibevoice-0031-aligned-test-01'
        for name,text in module.scripts(remote).items():
            process=subprocess.run(['/bin/sh','-n'],input=text,text=True,capture_output=True)
            self.assertEqual(process.returncode,0,(name,process.stderr))
        self.assertNotIn('genie-app',module.scripts(remote)['model-entry.sh'])
        self.assertNotIn('first-short.script',module.common(remote))
        self.assertIn('expected_fields=12',module.common(remote))

    def test_host_probe_exact_nul_argv_and_no_extra_empty_argument(self):
        module,_=p.load_lifecycle();c=module.Controller();c.remote='/data/local/tmp/vibevoice-0031-aligned-test-02'
        c._record=lambda role,deadline:(12345,'777')
        stat=b'12345 (litert_lm) S '+b'0 '*18+b'777 0\n'
        argv=b'\0'.join(x.encode() for x in p.native_argv(c.remote))+b'\0'
        def body(cmd):return stat+b'\nEXE\n'+p.native_argv(c.remote)[0].encode()+b'\nCMD\n'+cmd
        c._shell=lambda *args,**kwargs:module.Reply(0,body(argv))
        self.assertEqual(c._probe('model',10)[0],'verified')
        self.assertTrue(c.result['native_process_observed'])
        for bad in (argv+b'\0',argv.replace(b'--backend=gpu',b'--backend=cpu')):
            c._shell=lambda *args,**kwargs:module.Reply(0,body(bad))
            with self.assertRaises(module.UnsafePID):c._probe('model',10)

    def test_shell_expected_argv_equals_host_guard(self):
        module,_=p.load_lifecycle();remote='/data/local/tmp/vibevoice-0031-aligned-test-03'
        text=module.common(remote)
        line=next(x.strip() for x in text.splitlines() if "expected=$(printf '%s" in x)
        script='REMOTE='+shlex.quote(remote)+'\n'+line+'\nprintf "%s" "$expected"\n'
        observed=subprocess.check_output(['/bin/sh','-c',script])
        self.assertEqual(observed,b'\n'.join(x.encode() for x in p.native_argv(remote)))


if __name__=='__main__':unittest.main()
