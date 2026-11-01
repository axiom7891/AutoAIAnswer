from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "ai_screenshot_assistant" / "web" / "static"


def test_code_blocks_get_their_own_copy_button() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'shell.className = "code-shell"' in js
    assert 'copyButton.className = "code-copy"' in js
    assert 'copyButton.textContent = "复制代码"' in js
    assert 'copyAnswer(code.textContent, copyButton, "复制代码")' in js


def test_copy_answer_supports_custom_label() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "async function copyAnswer(text, button, label)" in js
    assert "const restoreLabel = label ||" in js
    assert "button.textContent = restoreLabel" in js
    assert "return copied;" in js


def test_chunk_copy_controls_are_wired() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "function answerChunks()" in js
    assert "function updateChunkStatus()" in js
    assert "function copyNextChunk()" in js
    assert "function chunkSizeValue()" in js
    assert "let chunkIndex = 0;" in js
    assert "chunkIndex += 1;" in js
    assert 'localStorage.setItem(chunkSizeKey' in js
    assert 'chunkProgress.textContent' in js

    assert 'id="chunk-size"' in html
    assert 'id="chunk-copy-button"' in html
    assert 'id="chunk-progress"' in html
    assert 'id="chunk-reset"' in html
    assert "分段复制" in html
    assert "复制下一段" in html
    assert 'min="20"' in html
    assert 'max="2000"' in html


def test_new_answer_resets_chunk_progress() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "if (!nextText.startsWith(chunkSourceText))" in js
    assert "chunkIndex = 0;" in js
    assert "chunkSourceText = nextText;" in js
    assert "updateChunkStatus();" in js


def test_code_and_chunk_styles_exist() -> None:
    css = (STATIC / "style.css").read_text(encoding="utf-8")

    for selector in (".code-shell", ".code-toolbar", ".code-copy", ".chunk-copy", ".chunk-progress"):
        assert selector in css
