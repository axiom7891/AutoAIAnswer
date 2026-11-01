from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "ai_screenshot_assistant" / "web" / "static"


def test_mobile_handles_desktop_scroll_commands() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'event.type === "answer.scroll"' in js
    assert 'event.type === "answer.autopan"' in js
    assert "function applyRemoteScroll(payload)" in js
    assert "function applyRemoteAutoPan(payload)" in js
    assert "function scrollOutputBy(direction, steps)" in js
    assert "function scrollHorizontalBy(direction, steps)" in js
    assert 'scrollOutputBy(-1, steps);' in js
    assert 'scrollHorizontalBy(1, steps);' in js
    assert "pauseCodePan();" in js
    assert "stopAutoPaging();" in js


def test_desktop_sends_scroll_events() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "ai_screenshot_assistant"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert "RemoteAnswerKeyListener(" in source
    assert "def _remote_scroll_answer(self, direction: str)" in source
    assert '"answer.scroll"' in source
    assert '"answer.autopan"' in source
    assert "def _toggle_remote_autopan(self)" in source
    assert "self._setup_remote_answer_keys()" in source


def test_remote_hotkeys_are_documented_in_ui() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "ai_screenshot_assistant"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert "Ctrl+Alt+↑↓←→" in source
    assert "Ctrl+Alt+P" in source
