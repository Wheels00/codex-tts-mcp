import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_tts_mcp import service


class MuteTests(unittest.TestCase):
    def test_set_and_get_mute_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "mute_state.json"

            initial = service.get_mute_status(state_path=state_path)
            self.assertTrue(initial.get("ok"))
            self.assertFalse(initial.get("muted"))

            updated = service.set_mute(True, state_path=state_path)
            self.assertTrue(updated.get("ok"))
            self.assertTrue(updated.get("muted"))

            final = service.get_mute_status(state_path=state_path)
            self.assertTrue(final.get("muted"))

    def test_speak_short_circuits_when_muted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "mute_state.json"
            service.set_mute(True, state_path=state_path)

            with patch("codex_tts_mcp.service.helper_speak") as helper_mock, patch(
                "codex_tts_mcp.service.run_osascript_say"
            ) as osa_mock, patch("codex_tts_mcp.service.run_say") as say_mock:
                result = service.speak(
                    text="task finished",
                    prefix_codex=True,
                    mute_state_path=state_path,
                )

                self.assertTrue(result.get("ok"))
                self.assertEqual(result.get("method"), "muted")
                self.assertEqual(result.get("spoken_text"), "task finished")
                helper_mock.assert_not_called()
                osa_mock.assert_not_called()
                say_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
