"""电脑键盘方向键遥控手机端答案框（↑ ↓ ← →，无组合键）。

手机页面不认识电脑按键，桌面端把按键翻译成滚动指令，走两条路：
1. WebSocket 广播（快）；
2. POST 后端 ``/scroll/{session_id}``，手机页面每 700ms 轮询兜底。

按键采集也有两条路，保证「一定能用」：
- pynput 全局键盘钩子（正常情况）；
- Win32 ``GetAsyncKeyState`` 轮询（钩子被安全软件/管理员权限挡掉时仍然有效）。
两条路都触发时按 60ms 去重。
"""

from __future__ import annotations

import sys
import threading
import time

_ACTION_KEYS = {
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
}
_VK_ACTIONS = {38: "up", 40: "down", 37: "left", 39: "right"}
_DEDUPE_SECONDS = 0.06


class RemoteScrollState:
    """纯逻辑：把方向键翻译成滚动动作，便于测试。"""

    def __init__(self, throttle_seconds: float = 0.08) -> None:
        self.throttle_seconds = throttle_seconds
        self.pressed: set[str] = set()
        self._last_fired: dict[str, float] = {}

    @staticmethod
    def key_name(key: object) -> str:
        name = getattr(key, "name", None)
        if name:
            return str(name).lower()
        vk = getattr(key, "vk", None)
        return f"vk{vk}" if vk is not None else ""

    def press(self, key: object, now: float | None = None) -> str:
        name = self.key_name(key)
        if not name:
            return ""
        self.pressed.add(name)
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
    def __init__(self, on_scroll, on_toggle_pan=None, key_state=None) -> None:
        self.on_scroll = on_scroll
        self.on_toggle_pan = on_toggle_pan
        self.state = RemoteScrollState()
        self.enabled = True
        self.error = ""
        self._key_state = key_state or self._default_key_state
        self._listener = None
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_dispatch: dict[str, float] = {}

    # ---- 采集：钩子 + 轮询 ----

    @staticmethod
    def _default_key_state(vk: int) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import ctypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
            user32.GetAsyncKeyState.restype = ctypes.c_short
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)
        except Exception:
            return False

    def _dispatch(self, action: str) -> None:
        if not action or not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            if now - self._last_dispatch.get(action, 0.0) < _DEDUPE_SECONDS:
                return
            self._last_dispatch[action] = now
        self.on_scroll(action)

    def _press(self, key: object) -> None:
        if not self.enabled:
            return
        with self._lock:
            action = self.state.press(key)
        if action:
            self._dispatch(action)

    def _release(self, key: object) -> None:
        with self._lock:
            self.state.release(key)

    def poll_step(self, previous: dict[int, bool]) -> None:
        """轮询一轮按键状态；返回是否新按下。"""
        for vk, action in _VK_ACTIONS.items():
            try:
                down = bool(self._key_state(vk))
            except Exception:
                down = False
            if down and not previous.get(vk, False):
                self._dispatch(action)
            previous[vk] = down

    def _poll_loop(self) -> None:
        previous = {vk: False for vk in _VK_ACTIONS}
        while not self._stop_event.wait(0.04):
            if not self.enabled:
                previous = {vk: False for vk in _VK_ACTIONS}
                continue
            self.poll_step(previous)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def start(self) -> None:
        if sys.platform not in {"win32", "darwin"}:
            return
        if sys.platform == "win32" and self._poll_thread is None:
            self._stop_event.clear()
            self._poll_thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="remote-arrow-poll"
            )
            self._poll_thread.start()
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
            self.error = ""
        except Exception as exc:
            # 钩子装不上不影响轮询兜底
            self.error = str(exc)
            self._listener = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=1)
            self._poll_thread = None
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        with self._lock:
            self.state.pressed.clear()
