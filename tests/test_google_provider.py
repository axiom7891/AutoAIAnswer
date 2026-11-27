from __future__ import annotations

import base64

from ai_screenshot_assistant.ai.client import ProviderConfig, VisionClient, _extract_google_text
from ai_screenshot_assistant.ai.models import (
    GOOGLE_GEMINI_PRO_MODEL,
    ROUTE_GOOGLE_GEMINI_PRO,
    ROUTE_OPENROUTER_CUSTOM,
    resolve_model_choice,
)


def test_google_route_uses_google_key() -> None:
    choice = resolve_model_choice(
        ROUTE_GOOGLE_GEMINI_PRO,
        has_deepseek=False,
        has_openrouter=False,
        has_google=True,
    )

    assert choice.provider == "google"
    assert choice.model == GOOGLE_GEMINI_PRO_MODEL


def test_google_route_without_key() -> None:
    choice = resolve_model_choice(
        ROUTE_GOOGLE_GEMINI_PRO,
        has_deepseek=False,
        has_openrouter=False,
        has_google=False,
    )

    assert choice.provider == "none"


def test_custom_model_uses_entered_slug() -> None:
    choice = resolve_model_choice(
        ROUTE_OPENROUTER_CUSTOM,
        has_deepseek=False,
        has_openrouter=True,
        custom_model="deepseek/deepseek-v4.1-flash-1017",
    )

    assert choice.provider == "openrouter"
    assert choice.model == "deepseek/deepseek-v4.1-flash-1017"
    assert "deepseek/deepseek-v4.1-flash-1017" in choice.display_name


def test_custom_model_empty_reports_missing() -> None:
    choice = resolve_model_choice(
        ROUTE_OPENROUTER_CUSTOM,
        has_deepseek=False,
        has_openrouter=True,
        custom_model="  ",
    )

    assert choice.provider == "none"
    assert "未填写" in choice.display_name


def test_google_payload_contains_inline_image() -> None:
    client = VisionClient(
        ProviderConfig(
            name="Google",
            api_key="test-key",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model=GOOGLE_GEMINI_PRO_MODEL,
        )
    )
    payload = client._google_payload("看图作答", [(b"png-bytes", "image/png")])

    parts = payload["contents"][0]["parts"]
    assert parts[0]["text"] == "看图作答"
    assert parts[1]["inline_data"]["mime_type"] == "image/png"
    assert base64.b64decode(parts[1]["inline_data"]["data"]) == b"png-bytes"


def test_google_stream_url_uses_stream_action() -> None:
    client = VisionClient(
        ProviderConfig(
            name="Google",
            api_key="abc123",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model=GOOGLE_GEMINI_PRO_MODEL,
        )
    )

    url = client._google_url(True)

    assert ":streamGenerateContent" in url
    assert "alt=sse" in url
    assert GOOGLE_GEMINI_PRO_MODEL in url
    assert url.endswith("abc123")


def test_extract_google_text() -> None:
    data = '{"candidates":[{"content":{"parts":[{"text":"答案：D"}]}}]}'

    assert _extract_google_text(data) == "答案：D"
    assert _extract_google_text("not-json") == ""
