"""Platform capture-exclusion helpers for the desktop overlay."""

from __future__ import annotations

import sys

if sys.platform == "win32":
    from ai_screenshot_assistant.ui.win32_capture import (
        CHROMA_KEY_RGB,
        apply_capture_exclusion,
        hwnd_from_widget,
        is_excluded_from_capture,
        keep_overlay_fronted,
        overlay_is_topmost,
        root_window_at,
        set_color_key_opacity,
        set_no_activate,
        window_center,
    )

    def apply_window_capture_exclusion(target: object, enabled: bool = True) -> tuple[bool, str]:
        hwnd = target if isinstance(target, int) else hwnd_from_widget(target)
        return apply_capture_exclusion(hwnd, enabled)
elif sys.platform == "darwin":
    from ai_screenshot_assistant.ui.macos_capture import (
        CHROMA_KEY_RGB,
        apply_capture_exclusion,
        apply_window_capture_exclusion,
        hwnd_from_widget,
        is_excluded_from_capture,
        keep_overlay_fronted,
        set_color_key_opacity,
        set_no_activate,
    )

    def overlay_is_topmost(hwnd: int) -> bool:
        return True

    def window_center(hwnd: int) -> tuple[int, int] | None:
        return None

    def root_window_at(x: int, y: int) -> int:
        return 0
else:
    CHROMA_KEY_RGB = (1, 2, 3)

    def hwnd_from_widget(widget: object) -> int:
        return 0

    def apply_capture_exclusion(hwnd: int, enabled: bool = True) -> tuple[bool, str]:
        if not hwnd:
            return False, "窗口句柄尚未创建"
        return False, "当前平台不支持捕获排除"

    def apply_window_capture_exclusion(target: object, enabled: bool = True) -> tuple[bool, str]:
        return False, "当前平台不支持控制台捕获排除"

    def is_excluded_from_capture(hwnd: int) -> bool:
        return False

    def keep_overlay_fronted(target: object) -> bool:
        return False

    def overlay_is_topmost(hwnd: int) -> bool:
        return False

    def window_center(hwnd: int) -> tuple[int, int] | None:
        return None

    def root_window_at(x: int, y: int) -> int:
        return 0

    def set_no_activate(hwnd: int, enabled: bool = True) -> None:
        return

    def set_color_key_opacity(
        hwnd: int,
        alpha: int,
        rgb: tuple[int, int, int] = CHROMA_KEY_RGB,
    ) -> None:
        return
