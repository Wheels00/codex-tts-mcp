import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_tts_mcp import service


class SpeakQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.mute_state_path = Path(self._tmp.name) / "mute_state.json"
        service.set_mute(False, state_path=self.mute_state_path)
        with service.QUEUE_LOCK:
            for timer in service.QUEUE_TIMERS.values():
                timer.cancel()
            service.QUEUE_TIMERS.clear()
            service.QUEUE_PAYLOADS.clear()

    def tearDown(self) -> None:
        self.setUp()

    def test_debounce_queues_without_speaking_immediately(self) -> None:
        with patch("codex_tts_mcp.service._speak_now") as speak_now:
            result = service.speak(
                text="task one finished",
                prefix_codex=True,
                queue_mode="debounce",
                queue_key="batch-a",
                debounce_ms=20000,
                mute_state_path=self.mute_state_path,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("method"), "debounced_queue")
            self.assertTrue(result.get("queued"))
            speak_now.assert_not_called()
            self.assertIn("batch-a", service.QUEUE_PAYLOADS)

    def test_flush_speaks_once_with_summary_text(self) -> None:
        with patch("codex_tts_mcp.service._speak_now") as speak_now:
            speak_now.return_value = {
                "ok": True,
                "method": "helper_launchagent_say",
                "spoken_text": "codex all queued tasks complete",
                "voice": "Samantha",
                "rate": 190,
                "error": None,
            }
            service.speak(
                text="task one finished",
                prefix_codex=True,
                queue_mode="debounce",
                queue_key="batch-b",
                debounce_ms=20000,
                mute_state_path=self.mute_state_path,
            )
            result = service.speak(
                text="all queued tasks complete",
                prefix_codex=True,
                queue_mode="flush",
                queue_key="batch-b",
                mute_state_path=self.mute_state_path,
            )
            self.assertTrue(result.get("ok"))
            speak_now.assert_called_once()
            self.assertNotIn("batch-b", service.QUEUE_PAYLOADS)


if __name__ == "__main__":
    unittest.main()
