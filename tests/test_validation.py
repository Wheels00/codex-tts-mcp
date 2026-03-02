import unittest

from codex_tts_mcp.validation import (
    ensure_prefix_codex,
    sanitize_text,
    validate_and_normalize,
)


class ValidationTests(unittest.TestCase):
    def test_prefix_codex_added_when_enabled(self) -> None:
        self.assertEqual(ensure_prefix_codex("task finished", True), "codex task finished")

    def test_prefix_codex_not_duplicated(self) -> None:
        self.assertEqual(
            ensure_prefix_codex("codex task finished", True), "codex task finished"
        )

    def test_sanitize_control_chars(self) -> None:
        self.assertEqual(sanitize_text("hi\x00there\n\tfriend"), "hi there friend")

    def test_validate_and_normalize_happy_path(self) -> None:
        args = validate_and_normalize(
            text="task finished",
            voice="Samantha",
            rate=190,
            interrupt=False,
            prefix_codex=True,
        )
        self.assertEqual(args.text, "task finished")
        self.assertEqual(args.voice, "Samantha")
        self.assertEqual(args.rate, 190)

    def test_validate_and_normalize_rejects_bad_voice(self) -> None:
        with self.assertRaises(ValueError):
            validate_and_normalize(
                text="ok",
                voice="bad/voice",
                rate=190,
                interrupt=False,
                prefix_codex=False,
            )


if __name__ == "__main__":
    unittest.main()
