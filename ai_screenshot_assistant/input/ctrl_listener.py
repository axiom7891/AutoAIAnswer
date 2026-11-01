from __future__ import annotations

from collections.abc import Callable
import sys
import threading


class CtrlTapState:
    def __init__(self) -> None:
        self.enabled = True
        self.pressed: set[str] = set()
        self.candidate: str | None = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.candidate = None

    def press(self, key: str, other_keys_down: bool = False) -> None:
        if key in self.pressed:
            return
        self.candidate = (
            key if self.enabled and key in {"ctrl_l", "ctrl_r"}
            and not self.pressed and not other_keys_down else None
        )
        self.pressed.add(key)

    def release(self, key: str) -> bool:
        trigger = self.enabled and self.candidate == key and self.pressed == {key}
        self.pressed.discard(key)
        self.candidate = None
        return trigger


class CtrlScreenshotListener:
    _VK_O = 0x4F
    _VK_CONTROL = 0x11
    _VK_MENU = 0x12

    def __init__(self, on_tap: Callable[[], None], on_overlay_toggle: Callable[[], None] | None = None) -> None:
        self.on_tap = on_tap
        self.on_overlay_toggle = on_overlay_toggle
        self.state = CtrlTapState()
        self._lock = threading.Lock()
        self._keyboard = None
        self._mouse = None
        self._overlay_combo_down = False

    @staticmethod
    def _key_id(key: object) -> str:
        name = getattr(key, "name", None)
        if name in {"ctrl", "ctrl_l"}:
            return "ctrl_l"
        if name == "ctrl_r":
            return "ctrl_r"
        vk = getattr(key, "vk", None)
        if vk is None:
            vk = getattr(getattr(key, "value", None), "vk", None)
        return f"vk:{vk}" if vk is not None else str(key)

    @staticmethod
    def _other_keys_down(ctrl: str) -> bool:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        ignored = {0x11, 0xA2 if ctrl == "ctrl_l" else 0xA3}
        return any(user32.GetAsyncKeyState(vk) & 0x8000
                   for vk in range(1, 255) if vk not in ignored)

    @staticmethod
    def _key_vk(key: object) -> int | None:
        vk = getattr(key, "vk", None)
        if vk is None:
            vk = getattr(getattr(key, "value", None), "vk", None)
        try:
            return int(vk) if vk is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _ctrl_alt_down(cls) -> bool:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        return bool(user32.GetAsyncKeyState(cls._VK_CONTROL) & 0x8000) and bool(
            user32.GetAsyncKeyState(cls._VK_MENU) & 0x8000
        )

    @classmethod
    def _is_overlay_combo(cls, key: object) -> bool:
        """Ctrl+Alt+O：显示/隐藏桌面悬浮字幕。"""

        return cls._key_vk(key) == cls._VK_O and cls._ctrl_alt_down()

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.state.set_enabled(enabled)
            self._overlay_combo_down = False

    def _on_press(self, key: object) -> None:
        key_id = self._key_id(key)
        if self._is_overlay_combo(key):
            if not self._overlay_combo_down:
                self._overlay_combo_down = True
                if self.on_overlay_toggle is not None:
                    self.on_overlay_toggle()
        other = key_id in {"ctrl_l", "ctrl_r"} and self._other_keys_down(key_id)
        with self._lock:
            self.state.press(key_id, other_keys_down=other)

    def _on_release(self, key: object) -> None:
        if self._key_vk(key) == self._VK_O:
            self._overlay_combo_down = False
        with self._lock:
            trigger = self.state.release(self._key_id(key))
        if trigger:
            self.on_tap()

    def _on_click(self, _x: int, _y: int, button: object, pressed: bool) -> None:
        key = f"mouse:{button}"
        with self._lock:
            if pressed:
                self.state.press(key)
            else:
                self.state.release(key)

    def start(self) -> None:
        if sys.platform != "win32":
            return
        if self._keyboard is not None:
            return
        from pynput import keyboard, mouse

        try:
            self._mouse = mouse.Listener(on_click=self._on_click, suppress=False)
            self._keyboard = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release, suppress=False,
            )
            self._mouse.start()
            self._mouse.wait()
            self._keyboard.start()
            self._keyboard.wait()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        self.set_enabled(False)
        for listener in (self._keyboard, self._mouse):
            if listener is not None:
                listener.stop()
        self._keyboard = None
        self._mouse = None
