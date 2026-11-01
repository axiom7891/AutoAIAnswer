from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "ai_screenshot_assistant" / "web" / "static"


def test_code_view_controls_exist() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert 'id="code-wrap"' in html
    assert 'id="code-font"' in html
    assert 'id="code-autopan"' in html
    assert "代码自动换行" in html
    assert "自动巡览" in html
    assert 'value="11"' in html
    assert 'value="16"' in html


def test_code_wrap_is_default_and_style_exists() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "style.css").read_text(encoding="utf-8")

    assert 'id="code-wrap" checked' in html
    assert 'id="code-autopan" checked' in html
    assert "body.code-wrap .code-block" in css
    assert "white-space: pre-wrap" in css
    assert "--code-font-size" in css
    assert ".code-view" in css


def test_auto_pan_loop_and_settings_are_wired() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "function applyCodeViewSettings()" in js
    assert "function loadCodeViewSettings()" in js
    assert "function saveCodeViewSettings()" in js
    assert "function panStep()" in js
    assert "function startCodePan()" in js
    assert "function stopCodePan()" in js
    assert "function pauseCodePan()" in js
    assert "setInterval(panStep, 50)" in js
    assert "clearInterval(panTimer)" in js
    assert 'document.body.classList.toggle("code-wrap"' in js
    assert '--code-font-size' in js
    assert "CODE_VIEW_KEY" in js
    assert "panDirection = -1" in js
    assert "panXDirection = -1" in js


def test_auto_pan_pauses_on_user_input_and_conflicts_with_auto_page() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'outputEl.addEventListener("touchstart", pauseCodePan' in js
    assert 'outputEl.addEventListener("wheel", pauseCodePan' in js
    assert 'outputEl.addEventListener("pointerdown", pauseCodePan)' in js
    assert 'document.addEventListener("keydown", pauseCodePan)' in js
    assert "stopCodePan();" in js
    assert "startCodePan();" in js
