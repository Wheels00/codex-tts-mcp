import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from codex_tts_mcp import helper_daemon


class HelperSerializationTests(unittest.TestCase):
    def test_speak_requests_are_serialized(self) -> None:
        max_parallel = 0
        active = 0
        lock = threading.Lock()

        def fake_run_say(text: str, voice: str, rate: int, interrupt: bool):
            nonlocal active, max_parallel
            with lock:
                active += 1
                max_parallel = max(max_parallel, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return SimpleNamespace(ok=True, error=None)

        payload = {
            "action": "speak",
            "text": "task finished",
            "voice": "Samantha",
            "rate": 190,
            "interrupt": False,
        }

        with patch("codex_tts_mcp.helper_daemon.run_say", side_effect=fake_run_say):
            threads = [
                threading.Thread(target=helper_daemon._handle_request, args=(payload,))
                for _ in range(4)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(max_parallel, 1)


if __name__ == "__main__":
    unittest.main()
