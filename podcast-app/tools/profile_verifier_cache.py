"""Narrow validation of APK-pinned AndroidX ProfileVerifier's own cache, not user data.

Binding: androidx.profileinstaller:profileinstaller:1.4.0, ProfileVerifier$Cache.
Its writeOnFile uses DataOutputStream: int schema, int resultCode, long package
last-update time, long installed-current-profile size. ProfileVerifier rewrites
that 24-byte cache when those values differ. No broad file exclusion is allowed.
"""
import hashlib
import struct

VERSION = '1.4.0'
PATH = 'files/profileInstalled'
WRITABLE_RESULTS = {0, 1, 2, 3, 327680}  # No profile, compiled, queued, non-matching, no embedded profile.
MAX_CURRENT_PROFILE_BYTES = 64 * 1024 * 1024


def decode(raw, *, library_version, package_last_update_ms):
    if library_version != VERSION:
        raise ValueError('Unverified ProfileVerifier library version')
    if len(raw) != 24:
        raise ValueError('ProfileVerifier cache is not the pinned 24-byte format')
    schema, result, updated, size = struct.unpack('>iiqq', raw)
    if schema != 1 or result not in WRITABLE_RESULTS:
        raise ValueError('Unknown ProfileVerifier schema/result')
    if updated <= 0 or updated != package_last_update_ms:
        raise ValueError('ProfileVerifier cache does not match target APP PackageInfo.lastUpdateTime')
    if not 0 <= size <= MAX_CURRENT_PROFILE_BYTES:
        raise ValueError('Unknown ProfileVerifier profile size')
    return {'schema': schema, 'resultCode': result, 'packageLastUpdateTimeMs': updated,
            'installedCurrentProfileBytes': size, 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def classify(before, after, *, library_version, before_package_last_update_ms,
             after_package_last_update_ms, app_apk_changed):
    """Caller must retain both byte artifacts and bind actual target-app PackageInfo values.

    This does not authorize changing/removing any other file or restoring the cache
    to its prior bytes. Test-APK timestamps must not be substituted for app times.
    """
    if after is None:
        raise ValueError('Expected framework cache was removed/missing')
    if not app_apk_changed and before_package_last_update_ms != after_package_last_update_ms:
        raise ValueError('App update timestamp changed despite unchanged app APK')
    old = None if before is None else decode(before, library_version=library_version,
                                            package_last_update_ms=before_package_last_update_ms)
    new = decode(after, library_version=library_version, package_last_update_ms=after_package_last_update_ms)
    fields = ('resultCode', 'packageLastUpdateTimeMs', 'installedCurrentProfileBytes')
    changes = list(fields) if old is None else [key for key in fields if old[key] != new[key]]
    return {'path': PATH, 'writer': 'androidx.profileinstaller.ProfileVerifier$Cache',
            'libraryVersion': library_version, 'before': old, 'after': new,
            'expectedFrameworkMetadataChange': bool(changes), 'changedFields': changes,
            'basis': 'APK-pinned cache format, allowed writer result codes, actual target-app PackageInfo timestamp, bounded profile size',
            'notUserEpisodeData': True, 'blanketExclusion': False, 'cacheRestoredOrDeleted': False}
