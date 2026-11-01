from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "ai_screenshot_assistant" / "web" / "static"


def test_answer_shortcut_handler_is_wired() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "function handleAnswerShortcut(event)" in js
    assert "function answerShortcutName(event)" in js
    assert "function scrollOutputHorizontal(direction)" in js
    assert "function scrollableCodeBlock()" in js
    assert 'document.addEventListener("keydown", handleAnswerShortcut);' in js
    assert "/^Key[WASD]$/" in js


def test_answer_shortcut_maps_wasd_to_answer_box() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    # W/S 上下翻页复用分页步长；A/D 左右滚动当前代码块
    assert 'scrollOutputPage(name === "w" ? -1 : 1);' in js
    assert 'scrollOutputHorizontal(name === "a" ? -1 : 1);' in js
    assert "stopAutoPaging();" in js
    assert "event.preventDefault();" in js


def test_answer_shortcut_ignores_typing_targets() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "target.isContentEditable" in js
    assert 'tag === "input"' in js
    assert 'tag === "textarea"' in js
    assert 'tag === "select"' in js


def test_answer_shortcut_hint_is_visible() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "style.css").read_text(encoding="utf-8")

    assert "Shift+W" in html
    assert "Shift+S" in html
    assert "Shift+A" in html
    assert "Shift+D" in html
    assert ".answer-shortcut-hint" in css
    assert "scroll-behavior: smooth" in css


def test_mobile_page_lists_gpt_routes() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert 'value="openrouter-gpt-4o"' in html
    assert 'value="openrouter-gpt-4-1"' in html
