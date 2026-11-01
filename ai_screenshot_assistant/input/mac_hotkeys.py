"""macOS 辅助快捷键：Ctrl+Alt+O 开关字幕、鼠标中键长按 1 秒 开关自动截屏。

Windows 走 ``CtrlScreenshotListener``（pynput 键盘监听）和 ``MouseRoiListener`` 的
中键钩子；macOS 没有 Windows 那套全局钩子，这里统一用 pynput 的全局监听实现同样的
两个动作。首次使用需要在「系统设置 → 隐私与安全性 → 辅助功能」里允许本程序。
"""

from __future__ import annotations

import sys
import threading
import time

_CTRL_NAMES = {"ctrl", "ctrl_l", "ctrl_r"}
_ALT_NAMES = {"alt", "alt_l", "alt_r", "alt_gr"}


class MacHotkeyListener:
    def __init__(
        self,
        on_overlay_toggle=None,
        on_middle_long=None,
        middle_long_seconds: float = 1.0,
    ) -> None:
        self.on_overlay_toggle = on_overlay_toggle
        self.on_middle_long = on_middle_long
        self.middle_long_press_seconds = middle_long_seconds
        self._pressed: set[str] = set()
        self._overlay_fired = False
        self._middle_down_at: float | None = None
        self._keyboard = None
        self._mouse = None
        self._lock = threading.Lock()

    # ---- 纯逻辑（便于测试，不依赖 pynput） ----

    @staticmethod
    def _key_name(key: object) -> str:
        name = getattr(key, "name", None)
        if name:
            return str(name)
        char = getattr(key, "char", None)
        return str(char).lower() if char else ""

    def handle_press(self, key: object) -> None:
        name = self._key_name(key)
        with self._lock:
            self._pressed.add(name)
            combo = name == "o" and bool(self._pressed & _CTRL_NAMES) and bool(self._pressed & _ALT_NAMES)
            if not combo or self._overlay_fired:
                return
            self._overlay_fired = True
        if self.on_overlay_toggle is not None:
            self.on_overlay_toggle()

    def handle_release(self, key: object) -> None:
        name = self._key_name(key)
        with self._lock:
            self._pressed.discard(name)
            if name == "o" or name in _CTRL_NAMES or name in _ALT_NAMES:
                self._overlay_fired = False

    def handle_click(self, button: object, pressed: bool) -> None:
        name = str(getattr(button, "name", button) or "")
        if name != "middle":
            return
        if pressed:
            self._middle_down_at = time.monotonic()
            return
        started = self._middle_down_at
        self._middle_down_at = None
        if started is not None and time.monotonic() - started >= self.middle_long_press_seconds:
            if self.on_middle_long is not None:
                self.on_middle_long()

    # ---- 全局监听 ----

    def start(self) -> None:
        if sys.platform != "darwin":
            return
        if self._keyboard is not None or self._mouse is not None:
            return
        from pynput import keyboard, mouse

        try:
            self._keyboard = keyboard.Listener(
                on_press=lambda key: self.handle_press(key),
                on_release=lambda key: self.handle_release(key),
                suppress=False,
            )
            self._mouse = mouse.Listener(
                on_click=lambda x, y, button, pressed: self.handle_click(button, pressed),
                suppress=False,
            )
            self._keyboard.start()
            self._mouse.start()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        for listener in (self._keyboard, self._mouse):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
        self._keyboard = None
        self._mouse = None
        with self._lock:
            self._pressed.clear()
            self._overlay_fired = False
            self._middle_down_at = None
