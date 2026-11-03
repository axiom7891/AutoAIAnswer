from __future__ import annotations

from dataclasses import dataclass

TIER_GOOD = "good"
TIER_MEDIUM = "medium"
TIER_SIMPLE = "simple"

ROUTE_DOUBAO_MINI = "doubao-seed-2-0-mini"
ROUTE_DOUBAO_LITE = "doubao-seed-2-0-lite"
ROUTE_DOUBAO_TURBO = "doubao-seed-2-1-turbo"
ROUTE_DOUBAO_PRO = "doubao-seed-2-1-pro"
ROUTE_DOUBAO_SEED_VISION = ROUTE_DOUBAO_TURBO
ROUTE_OPENROUTER_QWEN_235B = "openrouter-qwen-235b"
ROUTE_OPENROUTER_QWEN_27B = "openrouter-qwen-27b"
ROUTE_OPENROUTER_QWEN_FLASH = "openrouter-qwen-flash"
ROUTE_OPENROUTER_QWEN_PLUS = "openrouter-qwen-plus"
ROUTE_OPENROUTER_GLM = "openrouter-glm"
ROUTE_OPENROUTER_MINIMAX = "openrouter-minimax"
ROUTE_OPENROUTER_GPT_4O = "openrouter-gpt-4o"
ROUTE_OPENROUTER_GPT_4_1 = "openrouter-gpt-4-1"
ROUTE_OPENROUTER_DEEPSEEK_V41 = "openrouter-deepseek-v41"
ROUTE_OPENROUTER_CLAUDE_OPUS_55 = "openrouter-claude-opus-55"
ROUTE_OPENROUTER_GPT_6_LUNA = "openrouter-gpt-6-luna"
ROUTE_DEEPSEEK_FLASH = "deepseek-flash"
DEFAULT_MODEL_TIER = ROUTE_OPENROUTER_QWEN_235B

DEEPSEEK_VISION_MODEL = "deepseek-flash"
DOUBAO_MINI_MODEL = "doubao-seed-2-0-mini-260428"
DOUBAO_LITE_MODEL = "doubao-seed-2-0-lite-260428"
DOUBAO_TURBO_MODEL = "doubao-seed-2-1-turbo-260628"
DOUBAO_PRO_MODEL = "doubao-seed-2-1-pro-260915"
DOUBAO_VISION_MODEL = DOUBAO_TURBO_MODEL
DOUBAO_CHAT_COMPLETIONS_MODELS = frozenset({DOUBAO_TURBO_MODEL})
OPENROUTER_QWEN_235B = "qwen/qwen3-vl-235b-a22b-instruct"
OPENROUTER_QWEN_27B = "qwen/qwen3.8-27b"
OPENROUTER_QWEN_FLASH = "qwen/qwen3.8-flash"
OPENROUTER_QWEN_PLUS = "qwen/qwen3.6-plus"
OPENROUTER_GLM = "z-ai/glm-4.6v"
OPENROUTER_MINIMAX = "minimax/minimax-m3"
OPENROUTER_GPT_4O = "openai/gpt-4o"
OPENROUTER_GPT_4_1 = "openai/gpt-4.1"
OPENROUTER_DEEPSEEK_V41 = "deepseek/deepseek-v4.1-flash-1017"
OPENROUTER_CLAUDE_OPUS_55 = "anthropic/claude-opus-5.5"
OPENROUTER_GPT_6_LUNA = "openai/gpt-6-luna"

OPENROUTER_TIER_MODELS = {
    TIER_GOOD: OPENROUTER_QWEN_235B,
    TIER_MEDIUM: OPENROUTER_QWEN_27B,
    TIER_SIMPLE: OPENROUTER_QWEN_FLASH,
}

PROVIDER_LABELS = {
    "doubao": "豆包",
    "openrouter": "OpenRouter",
    "deepseek": "DeepSeek",
}


@dataclass(frozen=True)
class ModelRoute:
    route_id: str
    vendor: str
    provider: str
    model: str
    trait: str = ""
    allow_foreign: bool = False


MODEL_ROUTES: dict[str, ModelRoute] = {
    ROUTE_DOUBAO_MINI: ModelRoute(ROUTE_DOUBAO_MINI, "豆包 Mini", "doubao", DOUBAO_MINI_MODEL),
    ROUTE_DOUBAO_LITE: ModelRoute(ROUTE_DOUBAO_LITE, "豆包 Lite", "doubao", DOUBAO_LITE_MODEL),
    ROUTE_DOUBAO_TURBO: ModelRoute(ROUTE_DOUBAO_TURBO, "豆包 Turbo", "doubao", DOUBAO_TURBO_MODEL),
    ROUTE_DOUBAO_PRO: ModelRoute(ROUTE_DOUBAO_PRO, "豆包 Pro", "doubao", DOUBAO_PRO_MODEL),
    ROUTE_OPENROUTER_QWEN_235B: ModelRoute(
        ROUTE_OPENROUTER_QWEN_235B, "OpenRouter", "openrouter", OPENROUTER_QWEN_235B
    ),
    ROUTE_OPENROUTER_QWEN_27B: ModelRoute(
        ROUTE_OPENROUTER_QWEN_27B, "OpenRouter", "openrouter", OPENROUTER_QWEN_27B
    ),
    ROUTE_OPENROUTER_QWEN_FLASH: ModelRoute(
        ROUTE_OPENROUTER_QWEN_FLASH, "OpenRouter", "openrouter", OPENROUTER_QWEN_FLASH
    ),
    ROUTE_OPENROUTER_QWEN_PLUS: ModelRoute(
        ROUTE_OPENROUTER_QWEN_PLUS, "OpenRouter Qwen Plus", "openrouter", OPENROUTER_QWEN_PLUS
    ),
    ROUTE_OPENROUTER_GLM: ModelRoute(ROUTE_OPENROUTER_GLM, "OpenRouter GLM", "openrouter", OPENROUTER_GLM),
    ROUTE_OPENROUTER_MINIMAX: ModelRoute(
        ROUTE_OPENROUTER_MINIMAX, "OpenRouter MiniMax", "openrouter", OPENROUTER_MINIMAX
    ),
    ROUTE_OPENROUTER_GPT_4O: ModelRoute(
        ROUTE_OPENROUTER_GPT_4O,
        "OpenRouter GPT-4o",
        "openrouter",
        OPENROUTER_GPT_4O,
        allow_foreign=True,
    ),
    ROUTE_OPENROUTER_GPT_4_1: ModelRoute(
        ROUTE_OPENROUTER_GPT_4_1,
        "OpenRouter GPT-4.1",
        "openrouter",
        OPENROUTER_GPT_4_1,
        allow_foreign=True,
    ),
    ROUTE_OPENROUTER_DEEPSEEK_V41: ModelRoute(
        ROUTE_OPENROUTER_DEEPSEEK_V41,
        "OpenRouter DeepSeek V4.1",
        "openrouter",
        OPENROUTER_DEEPSEEK_V41,
    ),
    ROUTE_OPENROUTER_CLAUDE_OPUS_55: ModelRoute(
        ROUTE_OPENROUTER_CLAUDE_OPUS_55,
        "OpenRouter Claude Opus 5.5",
        "openrouter",
        OPENROUTER_CLAUDE_OPUS_55,
        allow_foreign=True,
    ),
    ROUTE_OPENROUTER_GPT_6_LUNA: ModelRoute(
        ROUTE_OPENROUTER_GPT_6_LUNA,
        "OpenRouter GPT-6 Luna",
        "openrouter",
        OPENROUTER_GPT_6_LUNA,
        allow_foreign=True,
    ),
    ROUTE_DEEPSEEK_FLASH: ModelRoute(
        ROUTE_DEEPSEEK_FLASH, "DeepSeek 官方", "deepseek", DEEPSEEK_VISION_MODEL
    ),
}

ROUTE_ALIASES = {
    "openrouter-qwen-32b": ROUTE_OPENROUTER_QWEN_27B,
    "openrouter-qwen-8b": ROUTE_OPENROUTER_QWEN_FLASH,
    "openrouter-deepseek-flash": ROUTE_OPENROUTER_QWEN_PLUS,
    "deepseek/deepseek-v4.1-flash": ROUTE_OPENROUTER_QWEN_PLUS,
    "qwen/qwen3-vl-235b-a22b-thinking": ROUTE_OPENROUTER_QWEN_235B,
    "qwen/qwen3-vl-32b-instruct": ROUTE_OPENROUTER_QWEN_27B,
    "qwen/qwen3-vl-8b-instruct": ROUTE_OPENROUTER_QWEN_FLASH,
    ROUTE_DOUBAO_MINI: ROUTE_DOUBAO_MINI,
    ROUTE_DOUBAO_LITE: ROUTE_DOUBAO_LITE,
    ROUTE_DOUBAO_TURBO: ROUTE_DOUBAO_TURBO,
    ROUTE_DOUBAO_PRO: ROUTE_DOUBAO_PRO,
    "doubao-seed-vision": ROUTE_DOUBAO_TURBO,
    "doubao": ROUTE_DOUBAO_TURBO,
    "豆包": ROUTE_DOUBAO_TURBO,
    "doubao-seed-1-6-vision": ROUTE_DOUBAO_TURBO,
    "doubao-seed-1-6-vision-250815": ROUTE_DOUBAO_TURBO,
    "doubao-seed-2-0-mini-260428": ROUTE_DOUBAO_MINI,
    "doubao-seed-2-0-lite-260428": ROUTE_DOUBAO_LITE,
    "doubao-seed-2-1-turbo-260628": ROUTE_DOUBAO_TURBO,
    "doubao-seed-2-1-pro-260915": ROUTE_DOUBAO_PRO,
    DOUBAO_MINI_MODEL: ROUTE_DOUBAO_MINI,
    DOUBAO_LITE_MODEL: ROUTE_DOUBAO_LITE,
    DOUBAO_TURBO_MODEL: ROUTE_DOUBAO_TURBO,
    DOUBAO_PRO_MODEL: ROUTE_DOUBAO_PRO,
    TIER_GOOD: ROUTE_OPENROUTER_QWEN_235B,
    "high": ROUTE_OPENROUTER_QWEN_235B,
    "best": ROUTE_OPENROUTER_QWEN_235B,
    "好": ROUTE_OPENROUTER_QWEN_235B,
    ROUTE_OPENROUTER_QWEN_235B: ROUTE_OPENROUTER_QWEN_235B,
    TIER_MEDIUM: ROUTE_OPENROUTER_QWEN_27B,
    "mid": ROUTE_OPENROUTER_QWEN_27B,
    "中等": ROUTE_OPENROUTER_QWEN_27B,
    ROUTE_OPENROUTER_QWEN_27B: ROUTE_OPENROUTER_QWEN_27B,
    TIER_SIMPLE: ROUTE_DEEPSEEK_FLASH,
    "low": ROUTE_DEEPSEEK_FLASH,
    "easy": ROUTE_DEEPSEEK_FLASH,
    "简单": ROUTE_DEEPSEEK_FLASH,
    ROUTE_DEEPSEEK_FLASH: ROUTE_DEEPSEEK_FLASH,
    ROUTE_OPENROUTER_QWEN_FLASH: ROUTE_OPENROUTER_QWEN_FLASH,
    ROUTE_OPENROUTER_QWEN_PLUS: ROUTE_OPENROUTER_QWEN_PLUS,
    OPENROUTER_QWEN_PLUS: ROUTE_OPENROUTER_QWEN_PLUS,
    "openrouter-deepseek": ROUTE_OPENROUTER_QWEN_PLUS,
    "openrouter-gpt": ROUTE_OPENROUTER_GPT_4O,
    "gpt-4o": ROUTE_OPENROUTER_GPT_4O,
    "gpt4o": ROUTE_OPENROUTER_GPT_4O,
    OPENROUTER_GPT_4O: ROUTE_OPENROUTER_GPT_4O,
    "gpt-4.1": ROUTE_OPENROUTER_GPT_4_1,
    OPENROUTER_GPT_4_1: ROUTE_OPENROUTER_GPT_4_1,
    ROUTE_OPENROUTER_GPT_4O: ROUTE_OPENROUTER_GPT_4O,
    ROUTE_OPENROUTER_GPT_4_1: ROUTE_OPENROUTER_GPT_4_1,
    "deepseek/deepseek-v4.1-flash-1017": ROUTE_OPENROUTER_DEEPSEEK_V41,
    "deepseek-v4.1-flash-1017": ROUTE_OPENROUTER_DEEPSEEK_V41,
    OPENROUTER_DEEPSEEK_V41: ROUTE_OPENROUTER_DEEPSEEK_V41,
    ROUTE_OPENROUTER_DEEPSEEK_V41: ROUTE_OPENROUTER_DEEPSEEK_V41,
    "anthropic/claude-opus-5.5": ROUTE_OPENROUTER_CLAUDE_OPUS_55,
    "claude-opus-5.5": ROUTE_OPENROUTER_CLAUDE_OPUS_55,
    OPENROUTER_CLAUDE_OPUS_55: ROUTE_OPENROUTER_CLAUDE_OPUS_55,
    ROUTE_OPENROUTER_CLAUDE_OPUS_55: ROUTE_OPENROUTER_CLAUDE_OPUS_55,
    "openai/gpt-6-luna": ROUTE_OPENROUTER_GPT_6_LUNA,
    "gpt-6-luna": ROUTE_OPENROUTER_GPT_6_LUNA,
    OPENROUTER_GPT_6_LUNA: ROUTE_OPENROUTER_GPT_6_LUNA,
    ROUTE_OPENROUTER_GPT_6_LUNA: ROUTE_OPENROUTER_GPT_6_LUNA,
}

TIER_LABELS = {
    ROUTE_DOUBAO_MINI: "豆包 Mini",
    ROUTE_DOUBAO_LITE: "豆包 Lite",
    ROUTE_DOUBAO_TURBO: "豆包 Turbo",
    ROUTE_DOUBAO_PRO: "豆包 Pro",
    ROUTE_OPENROUTER_QWEN_235B: "OpenRouter",
    ROUTE_OPENROUTER_QWEN_27B: "OpenRouter",
    ROUTE_OPENROUTER_QWEN_FLASH: "OpenRouter",
    ROUTE_OPENROUTER_QWEN_PLUS: "OpenRouter Qwen Plus",
    ROUTE_OPENROUTER_GLM: "OpenRouter GLM",
    ROUTE_OPENROUTER_MINIMAX: "OpenRouter MiniMax",
    ROUTE_DEEPSEEK_FLASH: "DeepSeek 官方",
    TIER_GOOD: "OpenRouter",
    TIER_MEDIUM: "OpenRouter",
    TIER_SIMPLE: "DeepSeek",
}

CHINESE_MODEL_MARKERS = (
    "qwen/",
    "qwen3",
    "deepseek",
    "alibaba",
    "z-ai/",
    "zhipu",
    "glm-",
    "moonshot",
    "minimax",
    "stepfun",
    "step/",
    "baidu/",
    "ernie",
    "tencent/",
    "hunyuan",
    "bytedance",
    "doubao",
    "thudm",
    "internlm",
    "01-ai",
    "yi/",
)

FOREIGN_MODEL_MARKERS = (
    "openai/",
    "gpt-",
    "o1-",
    "anthropic/",
    "claude",
    "google/",
    "gemini",
    "meta-llama",
    "llama-",
    "mistral",
    "x-ai/",
    "grok",
    "cohere/",
    "amazon/",
    "perplexity/",
    "nvidia/",
    "microsoft/",
)


def normalize_model_tier(value: str | None) -> str:
    key = str(value or "").strip()
    if not key:
        return DEFAULT_MODEL_TIER
    if key in MODEL_ROUTES:
        return key
    if key in ROUTE_ALIASES:
        return ROUTE_ALIASES[key]
    lowered = key.lower()
    if lowered in MODEL_ROUTES:
        return lowered
    return ROUTE_ALIASES.get(lowered, DEFAULT_MODEL_TIER)


def is_chinese_model(model_id: str | None) -> bool:
    lowered = str(model_id or "").strip().lower()
    if not lowered:
        return False
    if any(marker in lowered for marker in FOREIGN_MODEL_MARKERS):
        return False
    return any(marker in lowered for marker in CHINESE_MODEL_MARKERS)


def format_route_label(route: ModelRoute) -> str:
    return f"{route.vendor} · {route.model}"


def route_options() -> list[tuple[str, str, str]]:
    return [(route.route_id, route.vendor, route.model) for route in MODEL_ROUTES.values()]


def tier_options() -> list[tuple[str, str, str]]:
    return route_options()


@dataclass(frozen=True)
class ModelChoice:
    tier: str
    label: str
    provider: str
    model: str
    deepseek_model: str
    openrouter_model: str
    display_name: str
    route: str = ""
    doubao_model: str = DOUBAO_VISION_MODEL

    def to_payload(self) -> dict[str, str]:
        return {
            "tier": self.tier,
            "route": self.route or self.tier,
            "label": self.label,
            "provider": self.provider,
            "model": self.model,
            "display_name": self.display_name,
        }


def resolve_model_choice(
    tier: str | None,
    *,
    has_deepseek: bool,
    has_openrouter: bool,
    has_doubao: bool = False,
) -> ModelChoice:
    route_id = normalize_model_tier(tier)
    route = MODEL_ROUTES[route_id]
    has_provider = {
        "doubao": has_doubao,
        "openrouter": has_openrouter,
        "deepseek": has_deepseek,
    }
    openrouter_model = OPENROUTER_QWEN_235B
    if has_provider.get(route.provider):
        provider = route.provider
        model = route.model
        if provider == "openrouter":
            openrouter_model = model
    elif route.provider == "deepseek" and has_openrouter:
        provider = "openrouter"
        model = OPENROUTER_QWEN_PLUS
        openrouter_model = OPENROUTER_QWEN_PLUS
    elif route.provider == "openrouter" and has_deepseek:
        provider = "deepseek"
        model = DEEPSEEK_VISION_MODEL
    else:
        provider = "none"
        model = ""
    if model and not route.allow_foreign and not is_chinese_model(model):
        provider = "none"
        model = ""
    label = format_route_label(route)
    if model:
        vendor = PROVIDER_LABELS.get(provider, provider)
        display_name = f"{vendor} / {model}"
    else:
        display_name = f"{route.vendor} / 未配置 Key"
    doubao_model = route.model if route.provider == "doubao" else DOUBAO_VISION_MODEL
    return ModelChoice(
        tier=route_id,
        label=label,
        provider=provider,
        model=model,
        deepseek_model=DEEPSEEK_VISION_MODEL,
        openrouter_model=openrouter_model,
        display_name=display_name,
        route=route_id,
        doubao_model=doubao_model,
    )
