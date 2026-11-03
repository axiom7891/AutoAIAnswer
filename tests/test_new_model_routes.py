from __future__ import annotations

from pathlib import Path

import requests

from ai_screenshot_assistant.ai.client import (
    FailoverVisionClient,
    ModelUnavailableError,
    ProviderConfig,
    VisionClient,
)
from ai_screenshot_assistant.ai.models import (
    DEFAULT_MODEL_TIER,
    MODEL_ROUTES,
    OPENROUTER_CLAUDE_OPUS_55,
    OPENROUTER_DEEPSEEK_V41,
    OPENROUTER_GPT_6_LUNA,
    ROUTE_OPENROUTER_CLAUDE_OPUS_55,
    ROUTE_OPENROUTER_DEEPSEEK_V41,
    ROUTE_OPENROUTER_GPT_6_LUNA,
    resolve_model_choice,
)

ROOT = Path(__file__).resolve().parents[1]


def test_new_routes_are_registered_with_exact_model_ids() -> None:
    assert MODEL_ROUTES[ROUTE_OPENROUTER_DEEPSEEK_V41].model == "deepseek/deepseek-v4.1-flash-1017"
    assert MODEL_ROUTES[ROUTE_OPENROUTER_CLAUDE_OPUS_55].model == "anthropic/claude-opus-5.5"
    assert MODEL_ROUTES[ROUTE_OPENROUTER_GPT_6_LUNA].model == "openai/gpt-6-luna"
    assert OPENROUTER_DEEPSEEK_V41 == "deepseek/deepseek-v4.1-flash-1017"
    assert OPENROUTER_CLAUDE_OPUS_55 == "anthropic/claude-opus-5.5"
    assert OPENROUTER_GPT_6_LUNA == "openai/gpt-6-luna"


def test_foreign_routes_are_allowed_but_deepseek_is_domestic() -> None:
    assert MODEL_ROUTES[ROUTE_OPENROUTER_CLAUDE_OPUS_55].allow_foreign is True
    assert MODEL_ROUTES[ROUTE_OPENROUTER_GPT_6_LUNA].allow_foreign is True
    assert MODEL_ROUTES[ROUTE_OPENROUTER_DEEPSEEK_V41].allow_foreign is False
    assert MODEL_ROUTES[ROUTE_OPENROUTER_DEEPSEEK_V41].provider == "openrouter"


def test_new_routes_resolve_to_openrouter_models() -> None:
    choice = resolve_model_choice(ROUTE_OPENROUTER_GPT_6_LUNA, has_openrouter=True, has_deepseek=False)
    assert choice.provider == "openrouter"
    assert choice.route == ROUTE_OPENROUTER_GPT_6_LUNA

    choice = resolve_model_choice(ROUTE_OPENROUTER_CLAUDE_OPUS_55, has_openrouter=True, has_deepseek=False)
    assert choice.provider == "openrouter"

    choice = resolve_model_choice(ROUTE_OPENROUTER_DEEPSEEK_V41, has_openrouter=True, has_deepseek=False)
    assert choice.provider == "openrouter"


def test_model_not_found_falls_back_to_default_route() -> None:
    client = FailoverVisionClient(
        ProviderConfig(name="DeepSeek", api_key="k", base_url="https://example.test", model="vision"),
        ProviderConfig(name="OpenRouter", api_key="k", base_url="https://openrouter.ai/api/v1", model="vision"),
        model_tier=ROUTE_OPENROUTER_GPT_6_LUNA,
    )

    assert client._requested_tier == ROUTE_OPENROUTER_GPT_6_LUNA
    assert client._switch_to_default_route() is True
    assert client._requested_tier == DEFAULT_MODEL_TIER
    assert client._switch_to_default_route() is False


def test_openrouter_404_becomes_model_unavailable_error() -> None:
    vision = VisionClient(
        ProviderConfig(
            name="OpenRouter",
            api_key="k",
            base_url="https://openrouter.ai/api/v1",
            model="openai/gpt-6-luna",
        )
    )
    response = requests.Response()
    response.status_code = 404
    response._content = b'{"error":{"message":"No such model"}}'

    error = vision._friendly_http_error(requests.HTTPError("404", response=response))

    assert isinstance(error, ModelUnavailableError)
    assert error.status_code == 404
    assert "gpt-6-luna" in str(error)


def test_mobile_page_lists_new_routes() -> None:
    html = (ROOT / "ai_screenshot_assistant" / "web" / "static" / "index.html").read_text(encoding="utf-8")

    assert 'value="openrouter-deepseek-v41"' in html
    assert 'value="openrouter-claude-opus-55"' in html
    assert 'value="openrouter-gpt-6-luna"' in html
    assert "deepseek/deepseek-v4.1-flash-1017" in html
    assert "anthropic/claude-opus-5.5" in html


def test_overlay_opacity_allows_full_transparency() -> None:
    main_source = (ROOT / "ai_screenshot_assistant" / "ui" / "main_window.py").read_text(encoding="utf-8")
    overlay_source = (ROOT / "ai_screenshot_assistant" / "ui" / "streaming_overlay.py").read_text(encoding="utf-8")

    assert "self.opacity_slider.setRange(0, 100)" in main_source
    assert "opacity_percent = max(0, min(100, opacity_percent))" in main_source
    assert "self._opacity_percent = max(0, min(100, int(percent)))" in overlay_source
