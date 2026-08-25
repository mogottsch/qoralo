import hashlib
import json
import unittest
from pathlib import Path


EXPERIMENT = Path(__file__).resolve().parents[1]
REVIEW_PATH = EXPERIMENT / "results" / "listening-review-2026-08-25.json"


class ListeningReviewTest(unittest.TestCase):
    def test_both_distinct_phone_wavs_have_exact_hash_acceptance(self):
        review = json.loads(REVIEW_PATH.read_text())
        self.assertEqual(review["reviewer"], "Moritz")
        self.assertEqual(review["verbatim"], "they are good.")
        records = review["reviews"]
        self.assertEqual(len(records), 2)
        self.assertEqual({record["status"] for record in records}, {"accepted"})
        self.assertEqual(
            {record["arm"] for record in records},
            {"source_onnx", "external_epcontext"},
        )

        observed_hashes = set()
        for record in records:
            wav = EXPERIMENT.parents[1] / record["wav_path"]
            self.assertTrue(wav.is_file())
            payload = wav.read_bytes()
            self.assertEqual(len(payload), record["wav_bytes"])
            observed = hashlib.sha256(payload).hexdigest()
            self.assertEqual(observed, record["wav_sha256"])
            observed_hashes.add(observed)
        self.assertEqual(len(observed_hashes), 2)


if __name__ == "__main__":
    unittest.main()
