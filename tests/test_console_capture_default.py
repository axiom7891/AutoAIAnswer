from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_console_capture_is_unchecked_on_first_run() -> None:
    source = (ROOT / "ai_screenshot_assistant" / "ui" / "main_window.py").read_text(encoding="utf-8")

    assert 'self._settings_bool("capture/hide_console", False)' in source
    assert 'self._settings_bool("capture/hide_console", sys.platform in {"darwin", "win32"})' not in source