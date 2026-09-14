import importlib.util
from pathlib import Path
import struct
import unittest

path = Path(__file__).resolve().parents[1] / 'profile_verifier_cache.py'
spec = importlib.util.spec_from_file_location('profile_verifier_cache', path)
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class ProfileVerifierCacheTest(unittest.TestCase):
    def raw(self, schema=1, result=327680, updated=1000, size=0):
        return struct.pack('>iiqq', schema, result, updated, size)

    def test_exact_format_and_known_version(self):
        value = cache.decode(self.raw(), library_version='1.4.0', package_last_update_ms=1000)
        self.assertEqual(24, value['bytes'])
        self.assertEqual(327680, value['resultCode'])
        self.assertEqual(1000, value['packageLastUpdateTimeMs'])

    def test_rejects_unknown_versions_lengths_schema_and_non_writer_results(self):
        for raw, version in [(b'', '1.4.0'), (self.raw() + b'x', '1.4.0'), (self.raw(schema=2), '1.4.0'),
                             (self.raw(result=65536), '1.4.0'), (self.raw(), '1.5.0')]:
            with self.assertRaises(ValueError):
                cache.decode(raw, library_version=version, package_last_update_ms=1000)

    def test_rejects_wrong_package_timestamp_and_impossible_sizes(self):
        for raw in (self.raw(updated=2000), self.raw(size=-1), self.raw(size=64 * 1024**2 + 1)):
            with self.assertRaises(ValueError):
                cache.decode(raw, library_version='1.4.0', package_last_update_ms=1000)

    def test_only_explicit_format_bounded_framework_update_is_classified(self):
        value = cache.classify(self.raw(), self.raw(updated=2000), library_version='1.4.0',
                               before_package_last_update_ms=1000, after_package_last_update_ms=2000,
                               app_apk_changed=True)
        self.assertEqual(['packageLastUpdateTimeMs'], value['changedFields'])
        self.assertTrue(value['expectedFrameworkMetadataChange'])
        self.assertFalse(value['blanketExclusion'])
        self.assertFalse(value['cacheRestoredOrDeleted'])

    def test_same_app_cannot_import_test_apk_update_time(self):
        with self.assertRaises(ValueError):
            cache.classify(self.raw(), self.raw(updated=2000), library_version='1.4.0',
                           before_package_last_update_ms=1000, after_package_last_update_ms=2000,
                           app_apk_changed=False)

    def test_same_app_can_change_only_its_measured_profile_state_size(self):
        value = cache.classify(self.raw(result=2, size=100), self.raw(result=1, size=120), library_version='1.4.0',
                               before_package_last_update_ms=1000, after_package_last_update_ms=1000,
                               app_apk_changed=False)
        self.assertEqual(['resultCode', 'installedCurrentProfileBytes'], value['changedFields'])
        self.assertEqual(value['before']['packageLastUpdateTimeMs'], value['after']['packageLastUpdateTimeMs'])

    def test_missing_after_cache_cannot_be_excused(self):
        with self.assertRaises(ValueError):
            cache.classify(self.raw(), None, library_version='1.4.0', before_package_last_update_ms=1000,
                           after_package_last_update_ms=1000, app_apk_changed=False)


if __name__ == '__main__':
    unittest.main()
