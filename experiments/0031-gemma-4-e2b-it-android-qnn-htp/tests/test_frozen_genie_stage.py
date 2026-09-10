"""Tiny-file tests only: never load SDK/runtime/model or use a phone."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

EXP = Path(__file__).resolve().parents[1]
TRACK = EXP / 'improvements/0001-long-collapse-speed-quality'
spec = importlib.util.spec_from_file_location('frozen_stage', TRACK / 'tools/prepare_frozen_genie_stage.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def tiny_stage(root):
    payload = root / 'bin/genie-app'
    payload.parent.mkdir()
    payload.write_bytes(b'abc')
    payload.chmod(0o555)
    files = {'bin/genie-app': {'bytes': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}}
    manifest = root / 'frozen-manifest.json'
    manifest.write_text(json.dumps({'files': files}) + '\n')
    manifest.chmod(0o400)
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    sums = root / 'SHA256SUMS'
    sums.write_text(f'{files["bin/genie-app"]["sha256"]}  bin/genie-app\n{digest}  frozen-manifest.json\n')
    sums.chmod(0o400)
    return digest


class FrozenStageTest(unittest.TestCase):
    def test_copy_is_independent_read_only_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src, dest = root / 'source', root / 'stage/bin/genie-app'
            src.write_bytes(b'abc')
            src.chmod(0o700)
            identity = {'bytes': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}
            self.assertEqual(identity, module.copy_bound(src, dest, identity))
            self.assertFalse(os.path.samefile(src, dest))
            self.assertEqual(0o700, stat.S_IMODE(src.stat().st_mode))
            self.assertEqual(0o555, stat.S_IMODE(dest.stat().st_mode))

    def test_wrong_payload_hash_keeps_partial_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / 'source'
            src.write_bytes(b'abc')
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                module.copy_bound(src, root / 'partial', {'bytes': 3, 'sha256': '0' * 64})
            self.assertEqual(b'abc', src.read_bytes())
            self.assertTrue((root / 'partial').exists())
            with self.assertRaises(FileExistsError):
                module.copy_bound(src, root / 'partial', {'bytes': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()})

    def test_existing_frozen_stage_is_never_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileExistsError, 'never overwrite'):
                module.prepare(Path(directory))

    def test_verifier_requires_external_hash_and_executable_bits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            digest = tiny_stage(root)
            module.verify(root, digest)
            with self.assertRaisesRegex(RuntimeError, 'external frozen-manifest hash mismatch'):
                module.verify(root, '0' * 64)
            (root / 'bin/genie-app').chmod(0o400)
            with self.assertRaisesRegex(RuntimeError, 'executable mode0555'):
                module.verify(root, digest)

    def test_verifier_rejects_extra_files_and_payload_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            digest = tiny_stage(root)
            extra = root / 'libQnnCpu.so'
            extra.write_bytes(b'not-a-library')
            with self.assertRaisesRegex(RuntimeError, 'unexpected/missing'):
                module.verify(root, digest)
            extra.unlink()
            payload = root / 'bin/genie-app'
            payload.chmod(0o700)
            payload.write_bytes(b'xyz')
            payload.chmod(0o555)
            with self.assertRaisesRegex(RuntimeError, 'frozen input mismatch'):
                module.verify(root, digest)

    def test_script_is_one_short_noncanonical_query_without_export_or_long(self):
        lines = module.SCRIPT.splitlines()
        queries = [x for x in lines if x.startswith('dialog query ')]
        self.assertEqual(['dialog query dialog1 prompts/short.txt evidence/short-output.txt'], queries)
        self.assertIn('dialog setMaxNumTokens dialog1 16', lines)
        self.assertEqual(1, sum(x.startswith('dialog create ') for x in lines))
        self.assertTrue(lines[0].startswith('log create '))
        self.assertLess(lines.index(queries[0]), lines.index('profile save profile1 evidence/short-profile.json'))
        self.assertNotIn('long.txt', module.SCRIPT)
        self.assertNotIn('export', module.SCRIPT)
        self.assertNotIn('import', module.SCRIPT)

    def test_preparation_imports_no_runtime_or_device_library(self):
        tree = ast.parse((TRACK / 'tools/prepare_frozen_genie_stage.py').read_text())
        imports = {a.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names}
        imports |= {node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertTrue(imports <= {'argparse', 'hashlib', 'json', 'os', 'pathlib', 'stat', 'struct'})

    def test_retained_readiness_is_not_phone_or_model_evidence(self):
        folder = TRACK / 'results/frozen-genie-stage-readiness'
        result = json.loads((folder / 'result.json').read_text())
        control = folder / 'raw/control-inputs'
        self.assertEqual('584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25',
                         hashlib.sha256((control / 'frozen-manifest.json').read_bytes()).hexdigest())
        self.assertEqual('0555', result['stage']['runner_mode'])
        self.assertEqual(16, result['first_short_plan']['output_ceiling'])
        self.assertFalse(result['first_short_plan']['canonical_campaign'])
        self.assertEqual(1, result['first_short_plan']['queries'])
        self.assertFalse(result['later_long_plan']['script_present'])
        self.assertFalse(result['later_long_plan']['authorized'])
        self.assertEqual(2048, result['later_long_plan']['output_ceiling_if_separately_reviewed'])
        config = json.loads((control / 'gemma4-e2b-htp-cl4096-greedy.json').read_text())
        self.assertEqual(-1, config['dialog']['context']['bos-token'])
        self.assertEqual(2048, config['dialog']['max-num-tokens'])
        self.assertEqual(module.SCRIPT, (control / 'first-short.script').read_text())
        self.assertTrue(all(value is False for value in result['requested'].values()))
        self.assertFalse(result['publication']['registry_eligible'])
        self.assertFalse(result['publication']['completed_baseline_modified'])
        self.assertEqual(170, result['input_identities']['short']['tokens'])
        self.assertEqual(1929, result['input_identities']['long']['tokens'])
        self.assertTrue(result['source_bound_capture']['response_chunks_flushed'])
        self.assertEqual(result['preparation']['final_tool_sha256'],
                         hashlib.sha256((TRACK / 'tools/prepare_frozen_genie_stage.py').read_bytes()).hexdigest())
        self.assertEqual(result['preparation']['plan_sha256'],
                         hashlib.sha256((TRACK / 'PHONE-RETURN-DIAGNOSTIC-PLAN.md').read_bytes()).hexdigest())
        self.assertEqual(result['stage']['checksum_manifest_sha256'],
                         hashlib.sha256((control / 'SHA256SUMS').read_bytes()).hexdigest())
        for line in (folder / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(digest, hashlib.sha256((folder / name).read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
