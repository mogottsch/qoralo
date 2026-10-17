import contextlib
import io
import unittest

from summarize import main, measure


def chapters(*texts):
    return [{"title": "Welcome to a title", "text": text} for text in texts]


class SavedRunSummaryTest(unittest.TestCase):
    def test_counts_narration_characters_and_repeated_first_words(self):
        result = measure(chapters("So, a.", "SO, another.", "First."))
        self.assertEqual(3, result["chapters"])
        self.assertEqual(len("So, a.SO, another.First."), result["chars"])
        self.assertEqual(1, result["duplicate_first_words"])
        self.assertAlmostEqual(len("SO, another.") / len("First."), result["length_spread"])

    def test_greeting_check_ignores_titles_and_has_word_boundaries(self):
        result = measure(chapters("Welcome!", "  HELLO there.", "History follows.", "No greeting."))
        self.assertEqual(2, result["literal_greeting_starts"])

    def test_overlap_is_descriptive_jaccard_not_a_score(self):
        self.assertEqual(1.0, measure(chapters("Alpha beta.", "Beta alpha."))["mean_vocabulary_overlap"])
        self.assertEqual(0.0, measure(chapters("Alpha beta.", "Gamma delta."))["mean_vocabulary_overlap"])
        self.assertIsNone(measure(chapters("Only one."))["mean_vocabulary_overlap"])

    def test_lengths_are_unicode_characters_not_utf8_bytes(self):
        result = measure(chapters("Éire.", "Éire!"))
        self.assertEqual(10, result["chars"])
        self.assertEqual(1, result["duplicate_first_words"])

    def test_saved_bundle_validates_offline(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main()
        for name in ("bench-round1c", "bench-round2", "bench-round3", "bench-round3b"):
            self.assertIn(name, output.getvalue())


if __name__ == "__main__":
    unittest.main()
