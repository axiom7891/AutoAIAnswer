from __future__ import annotations

from ai_screenshot_assistant.ai.models import (
    MODEL_ROUTES,
    OPENROUTER_GEMINI_31_PRO,
    ROUTE_OPENROUTER_GEMINI_31_PRO,
    normalize_model_tier,
    resolve_model_choice,
    route_options,
)


def test_gemini_route_registered() -> None:
    route = MODEL_ROUTES[ROUTE_OPENROUTER_GEMINI_31_PRO]

    assert route.provider == "openrouter"
    assert route.model == OPENROUTER_GEMINI_31_PRO
    assert "gemini" in route.model


def test_gemini_appears_in_options() -> None:
    ids = [item[0] for item in route_options()]

    assert ROUTE_OPENROUTER_GEMINI_31_PRO in ids


def test_gemini_alias_resolves() -> None:
    assert normalize_model_tier("google/gemini-3.1-pro") == ROUTE_OPENROUTER_GEMINI_31_PRO
    assert normalize_model_tier("gemini-3.1-pro") == ROUTE_OPENROUTER_GEMINI_31_PRO


def test_gemini_uses_openrouter_key() -> None:
    choice = resolve_model_choice(
        ROUTE_OPENROUTER_GEMINI_31_PRO, has_deepseek=False, has_openrouter=True
    )

    assert choice.provider == "openrouter"
    assert choice.model == OPENROUTER_GEMINI_31_PRO


def test_gemini_without_key_reports_missing() -> None:
    choice = resolve_model_choice(
        ROUTE_OPENROUTER_GEMINI_31_PRO, has_deepseek=False, has_openrouter=False
    )

    assert choice.provider == "none"
