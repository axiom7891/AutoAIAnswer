from ai_screenshot_assistant.ai.models import (
    DEEPSEEK_VISION_MODEL,
    DOUBAO_LITE_MODEL,
    DOUBAO_MINI_MODEL,
    DOUBAO_PRO_MODEL,
    DOUBAO_VISION_MODEL,
    OPENROUTER_GPT_4O,
    OPENROUTER_GPT_4_1,
    OPENROUTER_TIER_MODELS,
    OPENROUTER_QWEN_235B,
    OPENROUTER_QWEN_27B,
    OPENROUTER_QWEN_FLASH,
    OPENROUTER_QWEN_PLUS,
    ROUTE_DEEPSEEK_FLASH,
    ROUTE_DOUBAO_LITE,
    ROUTE_DOUBAO_MINI,
    ROUTE_DOUBAO_PRO,
    ROUTE_DOUBAO_SEED_VISION,
    ROUTE_DOUBAO_TURBO,
    ROUTE_OPENROUTER_GPT_4O,
    ROUTE_OPENROUTER_GPT_4_1,
    ROUTE_OPENROUTER_QWEN_PLUS,
    ROUTE_OPENROUTER_GLM,
    ROUTE_OPENROUTER_MINIMAX,
    ROUTE_OPENROUTER_QWEN_235B,
    ROUTE_OPENROUTER_QWEN_27B,
    ROUTE_OPENROUTER_QWEN_FLASH,
    is_chinese_model,
    normalize_model_tier,
    resolve_model_choice,
    route_options,
)

def test_normalize_model_tier_accepts_chinese_labels() -> None:
    assert normalize_model_tier("好") == ROUTE_OPENROUTER_QWEN_235B
    assert normalize_model_tier("中等") == ROUTE_OPENROUTER_QWEN_27B
    assert normalize_model_tier("简单") == ROUTE_DEEPSEEK_FLASH
    assert normalize_model_tier("unknown") == ROUTE_OPENROUTER_QWEN_235B
    assert normalize_model_tier("good") == ROUTE_OPENROUTER_QWEN_235B
    assert normalize_model_tier("openrouter-qwen-flash") == ROUTE_OPENROUTER_QWEN_FLASH
    assert normalize_model_tier("doubao") == ROUTE_DOUBAO_TURBO
    assert normalize_model_tier("doubao-seed-vision") == ROUTE_DOUBAO_TURBO
    assert normalize_model_tier("doubao-seed-1-6-vision") == ROUTE_DOUBAO_TURBO
    assert normalize_model_tier("doubao-seed-2-1-turbo") == ROUTE_DOUBAO_TURBO
    assert normalize_model_tier("doubao-seed-2-0-mini") == ROUTE_DOUBAO_MINI
    assert normalize_model_tier("doubao-seed-2-0-lite") == ROUTE_DOUBAO_LITE
    assert normalize_model_tier("doubao-seed-2-1-pro") == ROUTE_DOUBAO_PRO
    assert normalize_model_tier("豆包") == ROUTE_DOUBAO_TURBO


def test_only_chinese_models_are_allowed() -> None:
    assert is_chinese_model("qwen/qwen3-vl-235b-a22b-instruct")
    assert is_chinese_model("deepseek-flash")
    assert is_chinese_model(OPENROUTER_QWEN_PLUS)
    assert is_chinese_model(DOUBAO_VISION_MODEL)
    assert is_chinese_model("z-ai/glm-4.5v") is True
    assert is_chinese_model("openai/gpt-4o") is False
    assert is_chinese_model("anthropic/claude-3.5-sonnet") is False
    assert is_chinese_model("google/gemini-2.5-pro") is False
    assert is_chinese_model("meta-llama/llama-3.1-70b") is False


def test_removed_openrouter_routes_migrate_without_removing_other_providers() -> None:
    from ai_screenshot_assistant.ai.models import MODEL_ROUTES

    legacy = {
        "openrouter-qwen-32b": ROUTE_OPENROUTER_QWEN_27B,
        "openrouter-qwen-8b": ROUTE_OPENROUTER_QWEN_FLASH,
        "openrouter-deepseek-flash": ROUTE_OPENROUTER_QWEN_PLUS,
        "deepseek/deepseek-v4.1-flash": ROUTE_OPENROUTER_QWEN_PLUS,
    }
    for old, new in legacy.items():
        assert old not in MODEL_ROUTES
        assert normalize_model_tier(old) == new
        assert resolve_model_choice(old, has_openrouter=True, has_deepseek=False).model == MODEL_ROUTES[new].model
    routes = [r for r in MODEL_ROUTES.values() if r.provider == "openrouter"]
    assert len(routes) == len({r.model for r in routes}) == 8
    foreign = [r for r in routes if not is_chinese_model(r.model)]
    assert {r.route_id for r in foreign} == {ROUTE_OPENROUTER_GPT_4O, ROUTE_OPENROUTER_GPT_4_1}
    assert all(r.allow_foreign for r in foreign)
    assert sum(r.provider == "doubao" for r in MODEL_ROUTES.values()) == 4
    assert MODEL_ROUTES[ROUTE_DEEPSEEK_FLASH].model == DEEPSEEK_VISION_MODEL


def test_good_tier_uses_expensive_qwen_when_openrouter_exists() -> None:
    choice = resolve_model_choice("good", has_deepseek=True, has_openrouter=True)

    assert choice.provider == "openrouter"
    assert choice.route == ROUTE_OPENROUTER_QWEN_235B
    assert choice.model == OPENROUTER_QWEN_235B
    assert "instruct" in choice.model
    assert is_chinese_model(choice.model)
    assert "好" not in choice.label
    assert "好" not in choice.display_name


def test_medium_tier_uses_qwen_32b() -> None:
    choice = resolve_model_choice("medium", has_deepseek=False, has_openrouter=True)

    assert choice.provider == "openrouter"
    assert choice.route == ROUTE_OPENROUTER_QWEN_27B
    assert choice.model == OPENROUTER_QWEN_27B
    assert choice.display_name == f"OpenRouter / {OPENROUTER_QWEN_27B}"


def test_simple_tier_uses_deepseek_flash_when_available() -> None:
    choice = resolve_model_choice("simple", has_deepseek=True, has_openrouter=True)

    assert choice.provider == "deepseek"
    assert choice.route == ROUTE_DEEPSEEK_FLASH
    assert choice.model == DEEPSEEK_VISION_MODEL
    assert choice.display_name == f"DeepSeek / {DEEPSEEK_VISION_MODEL}"


def test_simple_tier_falls_back_to_openrouter_deepseek_without_official_key() -> None:
    choice = resolve_model_choice("simple", has_deepseek=False, has_openrouter=True)

    assert choice.provider == "openrouter"
    assert choice.model == OPENROUTER_QWEN_PLUS


def test_openrouter_deepseek_flash_uses_openrouter_key() -> None:
    missing = resolve_model_choice(
        ROUTE_OPENROUTER_QWEN_PLUS,
        has_deepseek=True,
        has_openrouter=False,
    )
    ready = resolve_model_choice(
        ROUTE_OPENROUTER_QWEN_PLUS,
        has_deepseek=False,
        has_openrouter=True,
    )

    assert missing.provider == "deepseek"
    assert missing.model == DEEPSEEK_VISION_MODEL
    assert ready.provider == "openrouter"
    assert ready.model == OPENROUTER_QWEN_PLUS
    assert ready.openrouter_model == OPENROUTER_QWEN_PLUS
    assert "qwen3.6-plus" in ready.label


def test_explicit_qwen_8b_route() -> None:
    choice = resolve_model_choice(ROUTE_OPENROUTER_QWEN_FLASH, has_deepseek=True, has_openrouter=True)

    assert choice.provider == "openrouter"
    assert choice.model == OPENROUTER_QWEN_FLASH
    assert choice.label == f"OpenRouter · {OPENROUTER_QWEN_FLASH}"


def test_doubao_route_requires_doubao_key() -> None:
    missing = resolve_model_choice(
        ROUTE_DOUBAO_SEED_VISION,
        has_deepseek=True,
        has_openrouter=True,
        has_doubao=False,
    )
    ready = resolve_model_choice(
        ROUTE_DOUBAO_SEED_VISION,
        has_deepseek=True,
        has_openrouter=True,
        has_doubao=True,
    )

    assert missing.provider == "none"
    assert "未配置 Key" in missing.display_name
    assert ready.provider == "doubao"
    assert ready.model == DOUBAO_VISION_MODEL
    assert ready.doubao_model == DOUBAO_VISION_MODEL
    assert ready.display_name == f"豆包 / {DOUBAO_VISION_MODEL}"
    assert ready.label == f"豆包 Turbo · {DOUBAO_VISION_MODEL}"


def test_each_doubao_route_selects_matching_ark_model() -> None:
    mapping = {
        ROUTE_DOUBAO_MINI: DOUBAO_MINI_MODEL,
        ROUTE_DOUBAO_LITE: DOUBAO_LITE_MODEL,
        ROUTE_DOUBAO_TURBO: DOUBAO_VISION_MODEL,
        ROUTE_DOUBAO_PRO: DOUBAO_PRO_MODEL,
    }
    for route_id, model in mapping.items():
        choice = resolve_model_choice(
            route_id,
            has_deepseek=False,
            has_openrouter=False,
            has_doubao=True,
        )
        assert choice.provider == "doubao"
        assert choice.model == model
        assert choice.doubao_model == model
        assert model in choice.label
        assert model in choice.display_name
        assert "（" not in choice.label
        assert "（" not in choice.display_name


def test_gpt_routes_use_openrouter_key_and_real_model() -> None:
    for route_id, model in (
        (ROUTE_OPENROUTER_GPT_4O, OPENROUTER_GPT_4O),
        (ROUTE_OPENROUTER_GPT_4_1, OPENROUTER_GPT_4_1),
    ):
        choice = resolve_model_choice(route_id, has_deepseek=True, has_openrouter=True)
        assert choice.provider == "openrouter"
        assert choice.model == model
        assert choice.openrouter_model == model
        assert choice.display_name == f"OpenRouter / {model}"

    missing = resolve_model_choice(ROUTE_OPENROUTER_GPT_4O, has_deepseek=False, has_openrouter=False)
    assert missing.provider == "none"


def test_route_options_list_explicit_models() -> None:
    options = route_options()
    ids = [item[0] for item in options]
    labels = [item[1] for item in options]
    models = [item[2] for item in options]
    assert ids == [
        ROUTE_DOUBAO_MINI,
        ROUTE_DOUBAO_LITE,
        ROUTE_DOUBAO_TURBO,
        ROUTE_DOUBAO_PRO,
        ROUTE_OPENROUTER_QWEN_235B,
        ROUTE_OPENROUTER_QWEN_27B,
        ROUTE_OPENROUTER_QWEN_FLASH,
        ROUTE_OPENROUTER_QWEN_PLUS,
        ROUTE_OPENROUTER_GLM,
        ROUTE_OPENROUTER_MINIMAX,
        ROUTE_OPENROUTER_GPT_4O,
        ROUTE_OPENROUTER_GPT_4_1,
        ROUTE_DEEPSEEK_FLASH,
    ]
    assert "好" not in labels
    assert "中等" not in labels
    assert "简单" not in labels
    assert "豆包 Mini" in labels
    assert "豆包 Pro" in labels
    assert "OpenRouter Qwen Plus" in labels
    assert "OpenRouter GPT-4o" in labels
    assert "DeepSeek 官方" in labels
    assert OPENROUTER_QWEN_235B in models[4]
    assert OPENROUTER_QWEN_PLUS in models[7]
    assert OPENROUTER_GPT_4O in models[10]
    assert OPENROUTER_GPT_4_1 in models[11]
    assert DEEPSEEK_VISION_MODEL in models[-1]
    assert DOUBAO_MINI_MODEL in models[0]
    assert DOUBAO_VISION_MODEL in models[2]
    assert DOUBAO_PRO_MODEL in models[3]
    assert all("（" not in item[2] and "）" not in item[2] for item in options)


def test_all_configured_openrouter_tiers_are_chinese_qwen_models() -> None:
    for model_id in OPENROUTER_TIER_MODELS.values():
        assert is_chinese_model(model_id)
        assert model_id.startswith("qwen/")
        assert "gpt" not in model_id
        assert "claude" not in model_id
        assert "gemini" not in model_id
    good = resolve_model_choice("good", has_deepseek=True, has_openrouter=False)
    medium = resolve_model_choice("medium", has_deepseek=True, has_openrouter=False)

    assert good.provider == "deepseek"
    assert medium.provider == "deepseek"
    assert good.model == DEEPSEEK_VISION_MODEL
    assert medium.model == DEEPSEEK_VISION_MODEL
