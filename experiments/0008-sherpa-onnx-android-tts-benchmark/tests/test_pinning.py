import hashlib
import importlib.util
import io
import json
import os
import stat
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pinning", ROOT / "tools" / "pinning.py")
pinning = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(pinning)
PinError = pinning.PinError


def pin_for(path: Path, roots=("model",)):
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "allowed_top_level": list(roots)}


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "pins" / "assets.json"
        self.data = json.loads(self.path.read_text())

    def test_committed_manifest_is_complete(self):
        pinning.validate_manifest(self.data)
        self.assertEqual([98336520, 349418188, 128774318], [pinning.find_asset(self.data, x)["bytes"] for x in ("pocket", "kokoro", "supertonic-3")])

    def test_missing_license_or_provenance_fails(self):
        for field in ("licenses", "conversion_provenance", "asset_updated_at"):
            changed = json.loads(json.dumps(self.data))
            del changed["assets"][1][field]
            with self.assertRaises(PinError): pinning.validate_manifest(changed)

    def test_malformed_or_duplicate_manifest_entries_fail_closed(self):
        with self.assertRaises(PinError): pinning.validate_manifest([])
        changed = json.loads(json.dumps(self.data))
        changed["assets"].append(json.loads(json.dumps(changed["assets"][0])))
        with self.assertRaises(PinError): pinning.validate_manifest(changed)
        changed = json.loads(json.dumps(self.data))
        changed["assets"][0]["asset_created_at"] = "not-a-timestamp"
        with self.assertRaises(PinError): pinning.validate_manifest(changed)

    def test_unpinned_host_runtime_fails(self):
        changed = json.loads(json.dumps(self.data))
        changed["host_runtime"]["runtime_versions"]["sherpa-onnx"] = "1.13.6"
        with self.assertRaises(PinError): pinning.validate_manifest(changed)

    def test_release_metadata_drift_fails(self):
        asset = self.data["assets"][0]
        observed = {"tag_name": asset["release_tag"], "published_at": asset["release_published_at"], "assets": [{"name": asset["filename"], "size": asset["bytes"], "created_at": asset["asset_created_at"], "updated_at": asset["asset_updated_at"], "browser_download_url": asset["url"], "digest": "sha256:" + asset["sha256"]}]}
        pinning.verify_release_metadata(asset, observed)
        observed["assets"][0]["updated_at"] = "2099-01-01T00:00:00Z"
        with self.assertRaises(PinError): pinning.verify_release_metadata(asset, observed)


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def make_tar(self, entries):
        archive = self.root / f"input-{len(list(self.root.glob('input-*')))}.tar"
        with tarfile.open(archive, "w") as output:
            for name, kind, payload in entries:
                info = tarfile.TarInfo(name)
                if kind == "file":
                    info.size = len(payload); output.addfile(info, io.BytesIO(payload))
                elif kind == "symlink":
                    info.type = tarfile.SYMTYPE; info.linkname = payload; output.addfile(info)
                elif kind == "hardlink":
                    info.type = tarfile.LNKTYPE; info.linkname = payload; output.addfile(info)
        return archive

    def assert_rejected(self, entries):
        archive = self.make_tar(entries)
        with self.assertRaises((PinError, tarfile.TarError)):
            pinning.safe_extract(archive, self.root / "out", pin_for(archive))
        self.assertFalse((self.root / "out").exists())

    def test_extracts_regular_pinned_archive(self):
        archive = self.make_tar([("model/file.bin", "file", b"abc")])
        pinning.safe_extract(archive, self.root / "out", pin_for(archive))
        self.assertEqual((self.root / "out/model/file.bin").read_bytes(), b"abc")

    def test_rejects_traversal_absolute_backslash_and_wrong_layout(self):
        for name in ("../escape", "/absolute", "model/../../escape", "model\\escape", "other/file"):
            self.assert_rejected([(name, "file", b"x")])

    def test_rejects_links(self):
        for kind, target in (("symlink", "../../escape"), ("hardlink", "model/file")):
            self.assert_rejected([("model/link", kind, target)])

    def test_rejects_duplicate_paths(self):
        self.assert_rejected([("model/file", "file", b"one"), ("model/file", "file", b"two")])

    def test_rejects_archive_hash_or_size_drift(self):
        archive = self.make_tar([("model/file", "file", b"abc")])
        bad = pin_for(archive); bad["sha256"] = "0" * 64
        with self.assertRaises(PinError): pinning.safe_extract(archive, self.root / "out", bad)

    def test_rejects_zip_symlink_and_special_file(self):
        for file_type in (stat.S_IFLNK, stat.S_IFCHR):
            archive = self.root / f"input-{file_type}.zip"
            with zipfile.ZipFile(archive, "w") as output:
                item = zipfile.ZipInfo("model/unsafe"); item.create_system = 3; item.external_attr = (file_type | 0o777) << 16
                output.writestr(item, "../../escape")
            with self.assertRaises(PinError):
                pinning.safe_extract(archive, self.root / "out", pin_for(archive))

    def test_extract_creates_missing_parent_without_weakening_layout(self):
        archive = self.make_tar([("model/file.bin", "file", b"abc")])
        destination = self.root / "new-parent" / "out"
        pinning.safe_extract(archive, destination, pin_for(archive))
        self.assertEqual((destination / "model/file.bin").read_bytes(), b"abc")


class InventoryAndRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def test_inventory_is_deterministic_and_hashes_files(self):
        deployed = self.root / "deployed"; (deployed / "z").mkdir(parents=True)
        (deployed / "z/b").write_bytes(b"b"); (deployed / "a").write_bytes(b"a")
        first = pinning.inventory(deployed); second = pinning.inventory(deployed)
        self.assertEqual(first, second)
        self.assertEqual(["a", "z/b"], [x["path"] for x in first["files"]])
        self.assertEqual(2, first["total_bytes"])

    def test_inventory_rejects_symlink(self):
        deployed = self.root / "deployed"; deployed.mkdir(); (deployed / "file").write_bytes(b"x")
        os.symlink("file", deployed / "alias")
        with self.assertRaises(PinError): pinning.inventory(deployed)

    def test_host_runtime_requires_exact_set_hashes_and_platform(self):
        wheels = self.root / "wheels"; wheels.mkdir()
        names = ("api.whl", "core.whl")
        manifest = json.loads((ROOT / "pins" / "assets.json").read_text())
        for index, (name, wheel) in enumerate(zip(names, manifest["host_runtime"]["wheels"])):
            path = wheels / name; path.write_bytes(bytes([index]))
            wheel.update({"filename": name, "bytes": 1, "sha256": hashlib.sha256(bytes([index])).hexdigest()})
        pinning.verify_host_runtime(wheels, manifest, system="Linux", machine="x86_64", python_version=(3, 11, 9))
        (wheels / "local-build.whl").write_bytes(b"")
        with self.assertRaises(PinError): pinning.verify_host_runtime(wheels, manifest, system="Linux", machine="x86_64", python_version=(3, 11, 9))
        (wheels / "local-build.whl").unlink()
        with self.assertRaises(PinError): pinning.verify_host_runtime(wheels, manifest, system="Darwin", machine="x86_64", python_version=(3, 11, 9))
        with self.assertRaises(PinError): pinning.verify_host_runtime(wheels, manifest, system="Linux", machine="x86_64", python_version=(3, 11, 10))


if __name__ == "__main__": unittest.main()
