import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("verify_gemma_pack", Path(__file__).resolve().parents[1] / "verify_gemma_pack.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class VerifyGemmaPackTest(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"role": role, "path": path, "bytes": 8, "sha256": hashlib.sha256(role.encode()).hexdigest()}
            for role, path in verifier.FILES.items()
        ]
        self.manifest = {"schemaVersion": 2, "id": "gemma-4-e2b", "route": "GEMMA_4_E2B_LITERT_GPU", "files": self.entries}
        self.corrupt_hash = False
        self.wrong_size = False
        self.extra_file = False

    def raw_and_pin(self):
        raw = json.dumps(self.manifest).encode()
        return raw, hashlib.sha256(raw).hexdigest()

    def fake_adb(self, args, timeout):
        raw, _ = self.raw_and_pin()
        if "cat" in args:
            return raw
        if "sh" in args:
            inventory = ["./manifest.json"] + ["./" + e["path"] for e in self.entries]
            if self.extra_file:
                inventory.append("./injected.bin")
            return ("\n".join(inventory) + "\n").encode()
        if "stat" in args:
            return b"9\n" if self.wrong_size else b"8\n"
        if "sha256sum" in args:
            entry = next(e for e in self.entries if args[-1].endswith(e["path"]))
            sha = "0" * 64 if self.corrupt_hash else entry["sha256"]
            return (sha + "  " + args[-1] + "\n").encode()
        self.fail("Unexpected ADB operation: " + str(args))

    def verify_device(self):
        _, pin = self.raw_and_pin()
        with patch.object(verifier.subprocess, "check_output", side_effect=self.fake_adb) as adb:
            result = verifier.verify_installed_pack("adb", "phone", "dev.qoralo.podcast.internal", pin)
        return result, adb

    def test_hashes_both_installed_payloads_without_inference_or_install(self):
        result, adb = self.verify_device()
        self.assertEqual("fully_verified", result["result"])
        self.assertFalse(result["inference"])
        self.assertEqual(2, len(result["files"]))
        calls = [call.args[0] for call in adb.call_args_list]
        self.assertEqual(2, sum("sha256sum" in args for args in calls))
        self.assertTrue(all("install" not in args and "instrument" not in args and "force-stop" not in args for args in calls))

    def test_rejects_untrusted_manifest_before_device_payload_access(self):
        raw, _ = self.raw_and_pin()
        with patch.object(verifier.subprocess, "check_output", return_value=raw) as adb:
            with self.assertRaisesRegex(ValueError, "trusted pin"):
                verifier.verify_installed_pack("adb", "phone", "dev.qoralo.podcast.internal", "0" * 64)
            self.assertEqual(1, adb.call_count)

    def test_rejects_same_size_payload_corruption(self):
        self.corrupt_hash = True
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.verify_device()

    def test_rejects_size_mismatch(self):
        self.wrong_size = True
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            self.verify_device()

    def test_rejects_unlisted_file(self):
        self.extra_file = True
        with self.assertRaisesRegex(ValueError, "inventory"):
            self.verify_device()

    def test_rejects_unsafe_or_wrong_inventory_paths(self):
        self.entries[0]["path"] = "../escape"
        raw, pin = self.raw_and_pin()
        with self.assertRaisesRegex(ValueError, "payload path"):
            verifier.checked_manifest(raw, pin)

    def test_rejects_duplicate_roles(self):
        self.entries[1] = dict(self.entries[0])
        raw, pin = self.raw_and_pin()
        with self.assertRaisesRegex(ValueError, "exactly one"):
            verifier.checked_manifest(raw, pin)

    def test_rejects_wrong_model_route(self):
        self.manifest["route"] = "SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP"
        raw, pin = self.raw_and_pin()
        with self.assertRaisesRegex(ValueError, "expected Gemma"):
            verifier.checked_manifest(raw, pin)


if __name__ == "__main__":
    unittest.main()
