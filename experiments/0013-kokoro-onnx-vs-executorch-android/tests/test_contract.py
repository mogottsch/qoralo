from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import kokoro_contract as contract


class FrontendTests(unittest.TestCase):
    def assets(self, directory: Path) -> tuple[Path, Path]:
        tokens = directory / "tokens.txt"
        tokens.write_text(". 4\n  16\nw 65\nɜ 87\nd 46\n", encoding="utf-8")
        lexicon = directory / "lexicon.txt"
        lexicon.write_text("word w ɜ d\n", encoding="utf-8")
        return tokens, lexicon

    def test_runtime_lexicon_path_and_style_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tokens, lexicon = self.assets(Path(temporary))
            result = contract.frontend("Word.", tokens, lexicon)
            self.assertEqual(result.segments, ((0, 65, 87, 46, 16, 4, 0),))
            self.assertEqual(result.style_indices, (5,))
            self.assertEqual(result.lexicon_words, ("word",))

    def test_oov_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tokens, lexicon = self.assets(Path(temporary))
            with self.assertRaisesRegex(contract.ContractError, "not fully covered"):
                contract.frontend("Other.", tokens, lexicon)

    def test_audio_validation(self) -> None:
        samples = [0.1] * 2400
        result = contract.validate_audio(samples)
        self.assertTrue(result["valid"])
        self.assertEqual(result["sample_count"], 2400)
        with self.assertRaisesRegex(contract.ContractError, "non-finite"):
            contract.validate_audio([float("nan")] * 2400)


class StftTests(unittest.TestCase):
    def test_real_decomposition_matches_torch_stft_istft(self) -> None:
        try:
            import torch
            from exact_stft import ExactRealSTFT
        except ImportError as exc:
            self.skipTest(str(exc))
        torch.manual_seed(7)
        module = ExactRealSTFT(20, 5, 20)
        source = torch.randn(2, 1000)
        window = torch.hann_window(20)
        value = torch.stft(source, 20, 5, 20, window=window, return_complex=True)
        reconstructed = torch.istft(value, 20, 5, 20, window=window).unsqueeze(1)
        actual = module.inverse(value.abs(), torch.angle(value))
        self.assertEqual(tuple(actual.shape), tuple(reconstructed.shape))
        self.assertLess(float((actual - reconstructed).abs().max()), 2.0e-6)


if __name__ == "__main__":
    unittest.main()
