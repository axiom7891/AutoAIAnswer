from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_main_window_wires_capture_guard_and_blackout() -> None:
    source = (ROOT / "ai_screenshot_assistant" / "ui" / "main_window.py").read_text(encoding="utf-8")

    assert "CaptureExclusionGuard(self._capture_guard_targets)" in source
    assert "self.capture_guard.start()" in source
    assert "self.capture_guard.reassert_now()" in source
    assert "BlackoutSession(" in source
    assert "_toggle_blackout" in source
    assert "让目标窗口持续可见（解决黑屏）" in source
    assert "查看所有热键" in source
    assert "_show_hotkey_help" in source
    assert "已开启：目标窗口可见（点击还原）" in source
    assert "Alt+F" in source


def test_guard_reports_external_clear() -> None:
    guard_source = (ROOT / "ai_screenshot_assistant" / "ui" / "capture_guard.py").read_text(encoding="utf-8")

    assert "WDA_EXCLUDEFROMCAPTURE" in guard_source or "apply_capture_exclusion" in guard_source
    assert "hijacked" in guard_source