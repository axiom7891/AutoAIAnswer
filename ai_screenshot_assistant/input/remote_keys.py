"""电脑键盘遥控手机端答案框：Ctrl+Alt+方向键 滚动，Ctrl+Alt+P 开关自动巡览。

手机端页面不认识这些按键，桌面端把按键翻译成 ``answer.scroll`` / ``answer.autopan``
事件，经后端 WebSocket 广播给手机页面执行滚动。
"""

from __future__ import annotations

import sys
import threading
import time

_CTRL_NAMES = {"ctrl", "ctrl_l", "ctrl_r"}
_ALT_NAMES = {"alt", "alt_l", "alt_r", "alt_gr"}
_ACTION_KEYS = {
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "w": "up",
    "a": "left",
    "s": "down",
    "d": "right",
    "p": "toggle",
}
_VK_ACTIONS = {38: "up", 40: "down", 37: "left", 39: "right", 87: "up", 65: "left", 83: "down", 68: "right", 80: "toggle"}


class RemoteScrollState:
    """纯逻辑：把按键序列翻译成滚动动作，便于测试。"""

    def __init__(self, throttle_seconds: float = 0.12) -> None:
        self.throttle_seconds = throttle_seconds
        self.pressed: set[str] = set()
        self._last_fired: dict[str, float] = {}

    @staticmethod
    def key_name(key: object) -> str:
        name = getattr(key, "name", None)
        if name:
            return str(name).lower()
        char = getattr(key, "char", None)
        if isinstance(char, str) and char:
            return char.lower()
        vk = getattr(key, "vk", None)
        return f"vk{vk}" if vk is not None else ""

    def _ctrl_alt_down(self) -> bool:
        return bool(self.pressed & _CTRL_NAMES) and bool(self.pressed & _ALT_NAMES)

    def press(self, key: object, now: float | None = None) -> str:
        name = self.key_name(key)
        if not name:
            return ""
        self.pressed.add(name)
        if name in _CTRL_NAMES or name in _ALT_NAMES:
            return ""
        if not self._ctrl_alt_down():
            return ""
        action = _ACTION_KEYS.get(name)
        if action is None:
            vk = getattr(key, "vk", None)
            action = _VK_ACTIONS.get(vk) if isinstance(vk, int) else None
        if action is None:
            return ""
        now = time.monotonic() if now is None else now
        last = self._last_fired.get(action, 0.0)
        if now - last < self.throttle_seconds:
            return ""
        self._last_fired[action] = now
        return action

    def release(self, key: object) -> None:
        self.pressed.discard(self.key_name(key))


class RemoteAnswerKeyListener:
    def __init__(self, on_scroll, on_toggle_pan=None) -> None:
        self.on_scroll = on_scroll
        self.on_toggle_pan = on_toggle_pan
        self.state = RemoteScrollState()
        self._listener = None
        self._lock = threading.Lock()

    def _press(self, key: object) -> None:
        with self._lock:
            action = self.state.press(key)
        if action == "toggle":
            if self.on_toggle_pan is not None:
                self.on_toggle_pan()
        elif action:
            self.on_scroll(action)

    def _release(self, key: object) -> None:
        with self._lock:
            self.state.release(key)

    def start(self) -> None:
        if sys.platform not in {"win32", "darwin"}:
            return
        if self._listener is not None:
            return
        from pynput import keyboard

        try:
            self._listener = keyboard.Listener(
                on_press=self._press,
                on_release=self._release,
                suppress=False,
            )
            self._listener.start()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        with self._lock:
            self.state.pressed.clear()
