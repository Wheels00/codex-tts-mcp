import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_tts_mcp import service


class SpeechSettingsTests(unittest.TestCase):
    def test_set_and_get_speech_settings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            settings_path = Path(td) / "speech_settings.json"

            initial = service.get_speech_settings(settings_path=settings_path)
            self.assertTrue(initial.get("ok"))

            updated = service.set_speech_settings(
                voice="Alex", rate=210, settings_path=settings_path
            )
            self.assertTrue(updated.get("ok"))
            self.assertEqual(updated.get("voice"), "Alex")
            self.assertEqual(updated.get("rate"), 210)

            final = service.get_speech_settings(settings_path=settings_path)
            self.assertEqual(final.get("voice"), "Alex")
            self.assertEqual(final.get("rate"), 210)

    def test_speak_uses_persisted_settings_when_unset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            settings_path = Path(td) / "speech_settings.json"
            mute_path = Path(td) / "mute_state.json"
            service.set_mute(False, state_path=mute_path)
            service.set_speech_settings(
                voice="Alex", rate=205, settings_path=settings_path
            )

            with patch("codex_tts_mcp.service.helper_speak") as helper_mock:
                helper_mock.return_value = {"ok": True, "method": "helper_launchagent_say"}
                result = service.speak(
                    text="task finished",
                    prefix_codex=True,
                    mute_state_path=mute_path,
                    settings_path=settings_path,
                )

                self.assertTrue(result.get("ok"))
                kwargs = helper_mock.call_args.kwargs
                self.assertEqual(kwargs["voice"], "Alex")
                self.assertEqual(kwargs["rate"], 205)


if __name__ == "__main__":
    unittest.main()
