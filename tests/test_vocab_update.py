import tempfile
import unittest
from pathlib import Path

from codex_tts_mcp.service import update_vocabulary


class VocabUpdateTests(unittest.TestCase):
    def test_updates_both_targets_and_normalizes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            local = base / "LocalDictionary"
            sync = base / "text_replacements_candidates.tsv"

            local.write_text("Codex\n", encoding="utf-8")
            sync.write_text("Codex\\tCodex\n", encoding="utf-8")

            result = update_vocabulary(
                terms=[" Cielo ", "Samdisha", "Australia@ Pause AI . info", "Codex"],
                local_dict_path=local,
                sync_tsv_path=sync,
            )

            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("added_local"), 3)
            self.assertEqual(result.get("added_synced"), 3)
            self.assertIn("australia@pauseai.info", result.get("normalized_terms", []))

            local_lines = local.read_text(encoding="utf-8").splitlines()
            sync_lines = sync.read_text(encoding="utf-8").splitlines()

            self.assertIn("Cielo", local_lines)
            self.assertIn("Samdisha", local_lines)
            self.assertIn("australia@pauseai.info", local_lines)
            self.assertIn("Codex\tCodex", sync_lines)
            self.assertIn("Cielo\tCielo", sync_lines)
            self.assertIn("australia@pauseai.info\taustralia@pauseai.info", sync_lines)

    def test_rejects_bad_inputs(self) -> None:
        self.assertFalse(update_vocabulary([]).get("ok"))
        self.assertFalse(update_vocabulary([123]).get("ok"))


if __name__ == "__main__":
    unittest.main()
