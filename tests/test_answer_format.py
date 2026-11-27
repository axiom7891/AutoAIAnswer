from __future__ import annotations

from ai_screenshot_assistant.ai.prompt import (
    ANSWER_FORMAT_ANSWER_ONLY,
    ANSWER_FORMAT_FULL,
    ANSWER_FORMAT_INDEX_ONLY,
    ANSWER_FORMAT_LABELS,
    ANSWER_FORMAT_LETTER_ONLY,
    answer_format_suffix,
    set_answer_format,
)


def test_all_formats_have_labels() -> None:
    assert set(ANSWER_FORMAT_LABELS) == {
        ANSWER_FORMAT_FULL,
        ANSWER_FORMAT_ANSWER_ONLY,
        ANSWER_FORMAT_LETTER_ONLY,
        ANSWER_FORMAT_INDEX_ONLY,
    }


def test_full_format_adds_nothing() -> None:
    set_answer_format(ANSWER_FORMAT_FULL)

    assert answer_format_suffix() == ""


def test_answer_only_instruction() -> None:
    set_answer_format(ANSWER_FORMAT_ANSWER_ONLY)
    suffix = answer_format_suffix()

    assert "只要答案" in suffix or "只输出一行" in suffix
    assert "解析" in suffix


def test_letter_only_instruction() -> None:
    set_answer_format(ANSWER_FORMAT_LETTER_ONLY)
    suffix = answer_format_suffix()

    assert "选项字母" in suffix


def test_index_only_instruction() -> None:
    set_answer_format(ANSWER_FORMAT_INDEX_ONLY)
    suffix = answer_format_suffix()

    assert "第 N 个" in suffix


def test_unknown_format_falls_back_to_full() -> None:
    set_answer_format("something-else")

    assert answer_format_suffix() == ""


def test_client_prompt_includes_format_suffix() -> None:
    from ai_screenshot_assistant.ai.client import _build_user_prompt

    set_answer_format(ANSWER_FORMAT_LETTER_ONLY)
    prompt = _build_user_prompt("看图作答", [])
    set_answer_format(ANSWER_FORMAT_FULL)

    assert "选项字母" in prompt
