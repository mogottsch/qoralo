from copy import deepcopy
from pathlib import Path
import hashlib
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from duration_manifest_overlay import LIBRARY, declaration, patch_manifest, tree

FIXTURE=Path(__file__).parent/'fixtures/duration-baseline-manifest.axml'


class DurationManifestOverlayTests(unittest.TestCase):
    def test_exact_frozen_manifest_gets_only_optional_public_library_declaration(self):
        data=FIXTURE.read_bytes()
        self.assertEqual('293221fb7189018607b2424216d84c811c0c00d4f935c3d05d876ada31b5efd8',hashlib.sha256(data).hexdigest())
        changed,proof=patch_manifest(data)
        after=deepcopy(tree(changed));app=next(n for n in after['children'] if n['name']=='application')
        added=declaration(app,LIBRARY);self.assertEqual(1,len(added));app['children'].remove(added[0])
        self.assertEqual(tree(data),after);self.assertFalse(proof['required'])
        self.assertEqual(data,FIXTURE.read_bytes())

    def test_duplicate_is_rejected_not_silently_added(self):
        changed,_=patch_manifest(FIXTURE.read_bytes())
        with self.assertRaisesRegex(ValueError,'already declared'):patch_manifest(changed)

    def test_unknown_pool_encoding_and_truncated_xml_fail_closed(self):
        data=bytearray(FIXTURE.read_bytes());struct.pack_into('<I',data,8+16,0x100)
        with self.assertRaises(ValueError):patch_manifest(bytes(data))
        with self.assertRaises(ValueError):patch_manifest(FIXTURE.read_bytes()[:-1])


if __name__=='__main__':unittest.main()
