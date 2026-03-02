import os
import stat
import subprocess
import sys
import time
import unittest
from pathlib import Path

from codex_tts_mcp.helper_client import helper_health


def _wait_for_socket(path: Path, timeout_s: float = 5.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.exists() and stat.S_ISSOCK(path.stat().st_mode):
            return True
        time.sleep(0.1)
    return False


@unittest.skipUnless(sys.platform == "darwin", "macOS integration test")
class HelperPathIntegrationTests(unittest.TestCase):
    def test_helper_path_callable(self) -> None:
        root = Path(__file__).resolve().parents[1]
        helper = root / "src/codex_tts_mcp/helper_daemon.py"

        runtime_dir = root / ".tmp-test-runtime"
        runtime_dir.mkdir(exist_ok=True)
        socket_path = runtime_dir / "tts.sock"
        socket_path.unlink(missing_ok=True)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(root / "src")

        proc = subprocess.Popen(
            [sys.executable, str(helper), "--socket", str(socket_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            if not _wait_for_socket(socket_path):
                stderr = (proc.stderr.read() or "").strip() if proc.stderr else ""
                if "PermissionError" in stderr and "Operation not permitted" in stderr:
                    self.skipTest("runtime sandbox blocks unix socket bind")
                self.fail(f"helper socket did not start: {stderr}")
            health = helper_health(socket_path)
            self.assertTrue(health.get("ok"))
            self.assertEqual(health.get("method"), "helper_launchagent_say")
        finally:
            proc.terminate()
            proc.wait(timeout=5)
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            socket_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
