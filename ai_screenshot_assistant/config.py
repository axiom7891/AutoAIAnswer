from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            candidates.append(Path(bundle_dir) / ".env")
    candidates.append(Path.cwd() / ".env")
    candidates.append(Path(__file__).resolve().parents[1] / ".env")
    for path in candidates:
        if path.exists():
            load_dotenv(path)
            return
    load_dotenv()


_load_env()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-vl-235b-a22b-instruct")
    doubao_api_key: str = os.getenv("ARK_API_KEY", "")
    doubao_base_url: str = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    doubao_model: str = os.getenv("ARK_MODEL", "doubao-seed-1-6-vision-250815")
    model_tier: str = os.getenv("MODEL_TIER", "openrouter-qwen-235b")
    backend_url: str = os.getenv("BACKEND_URL", "auto")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))
    embedded_backend: bool = _bool_env("EMBEDDED_BACKEND", True)
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "90"))
    save_debug_image: bool = _bool_env("SAVE_DEBUG_IMAGE", False)
    # 截图异常修复：黑屏 / 闪屏 / 透明屏时给目标窗口注入临时补丁再重拍
    capture_repair_enabled: bool = _bool_env("CAPTURE_REPAIR", True)
    capture_repair_attempts: int = max(1, min(5, int(os.getenv("CAPTURE_REPAIR_ATTEMPTS", "3"))))
    capture_repair_samples: int = max(1, min(4, int(os.getenv("CAPTURE_REPAIR_SAMPLES", "2"))))
    capture_repair_inject: bool = _bool_env("CAPTURE_REPAIR_INJECT", True)
    capture_repair_content: bool = _bool_env("CAPTURE_REPAIR_CONTENT", True)
    capture_repair_state: bool = _bool_env("CAPTURE_REPAIR_STATE", True)
    capture_repair_diagnostics: bool = _bool_env("CAPTURE_REPAIR_DIAGNOSTICS", True)


settings = Settings()
