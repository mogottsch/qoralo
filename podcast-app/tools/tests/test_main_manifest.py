from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


MAIN_MANIFEST = Path(__file__).resolve().parents[2] / 'app/src/main/AndroidManifest.xml'
ANDROID = '{http://schemas.android.com/apk/res/android}'


class MainManifestTests(unittest.TestCase):
    def test_normal_app_imports_fastrpc_and_existing_public_libraries_once_as_optional(self):
        application = ET.parse(MAIN_MANIFEST).getroot().find('application')
        self.assertIsNotNone(application)
        declarations = application.findall('uses-native-library')
        self.assertCountEqual(
            [
                {ANDROID + 'name': name, ANDROID + 'required': 'false'}
                for name in ('libvndksupport.so', 'libOpenCL.so', 'libcdsprpc.so')
            ],
            [node.attrib for node in declarations],
        )


if __name__ == '__main__':
    unittest.main()
