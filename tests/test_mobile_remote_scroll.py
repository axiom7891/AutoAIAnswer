from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "ai_screenshot_assistant" / "web" / "static"


def test_mobile_handles_desktop_scroll_commands() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'event.type === "answer.scroll"' in js
    assert 'event.type === "answer.autopan"' in js
    assert "function applyRemoteScroll(payload)" in js
    assert "function applyRemoteAutoPan(payload)" in js
    assert "function scrollOutputBy(direction, steps)" in js
    assert "function scrollHorizontalBy(direction, steps)" in js


def test_mobile_polls_http_scroll_queue() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "function pollScrollCommands()" in js
    assert "/scroll/${encodeURIComponent(sessionId)}" in js
    assert "setInterval(pollScrollCommands, 700);" in js
    assert "scrollCursor" in js


def test_backend_exposes_scroll_queue() -> None:
    source = (ROOT / "ai_screenshot_assistant" / "backend" / "app.py").read_text(encoding="utf-8")

    assert '@app.post("/scroll/{session_id}")' in source
    assert '@app.get("/scroll/{session_id}")' in source
    assert "session.scroll_events.append(event)" in source
    assert "session.next_scroll_id" in source


def test_desktop_sends_plain_arrow_scroll() -> None:
    source = (ROOT / "ai_screenshot_assistant" / "ui" / "main_window.py").read_text(encoding="utf-8")

    assert "RemoteAnswerKeyListener(" in source
    assert "def _remote_scroll_answer(self, direction: str)" in source
    assert "/scroll/" in source
    assert "def _post_scroll_command(self, direction: str)" in source
    assert "set_remote_arrows_enabled" in source
    assert "方向键 ↑ ↓ ← → 直接遥控手机答案框" in source


def test_no_modifier_chords_left_in_ui_text() -> None:
    source = (ROOT / "ai_screenshot_assistant" / "ui" / "main_window.py").read_text(encoding="utf-8")

    assert "Ctrl+Alt+↑↓←→" not in source
    assert "Ctrl+Alt+P" not in source
