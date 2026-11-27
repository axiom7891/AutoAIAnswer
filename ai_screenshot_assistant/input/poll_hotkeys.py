"""轮询式全局快捷键（Win32 GetAsyncKeyState），不装键盘/鼠标钩子。

用途：某些考试客户端会把前台窗口提到高完整性级别，低权限进程的
WH_KEYBOARD_LL / WH_MOUSE_LL 钩子收不到事件（UIPI 直接拦掉），表现为
"进考试后快捷键失效"。轮询只读按键状态，不注入、不挂钩子、不打开目标
进程，因此不受 UIPI 影响，也不会因为 SetWindowsHookEx 被安全软件盯上。

支持动作：
- 鼠标左键双击 → 截整屏；左键三连击 → 开关自动截全屏
- 鼠标中键按住 1 秒 → 开关自动截全屏
- Alt+Z → 显示/隐藏悬浮字幕
- Ctrl 单击（前后没有别的键）→ 截整屏（客户 C）
- Ctrl+Shift+左键 / 右键 → 连续截图 / 分析连续截图缓存
"""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_MBUTTON = 0x04
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_Z = 0x5A
VK_F = 0x46
VK_G = 0x47

_CLICK_WINDOW_SECONDS = 0.35   # 连击统计窗口
_CLICK_MAX_SECONDS = 0.6       # 单次按住超过这个时长算长按，不参与连击
_DOUBLE_CLICK_GUARD = 0.25     # 连击判定后短暂锁定，避免误判
_DOUBLE_CLICK_DELAY = 0.28     # 双击延迟派发，等第三击；三连击只发 triple
_MIDDLE_LONG_SECONDS = 1.0
_ACTION_GUARD_SECONDS = 0.12


class PollingHotkeys:
    """按固定间隔读取按键状态，把边沿翻译成动作回调。"""

    def __init__(
        self,
        *,
        on_double_click: Callable[[], None] | None = None,
        on_triple_click: Callable[[], None] | None = None,
        on_middle_long: Callable[[], None] | None = None,
        on_alt_z: Callable[[], None] | None = None,
        on_ctrl_tap: Callable[[], None] | None = None,
        on_ctrl_shift_left: Callable[[], None] | None = None,
        on_ctrl_shift_right: Callable[[], None] | None = None,
        on_fix_toggle: Callable[[], None] | None = None,
        on_fix_release: Callable[[], None] | None = None,
        key_state: Callable[[int], bool] | None = None,
        interval: float = 0.016,
    ) -> None:
        self.on_double_click = on_double_click
        self.on_triple_click = on_triple_click
        self.on_middle_long = on_middle_long
        self.on_alt_z = on_alt_z
        self.on_ctrl_tap = on_ctrl_tap
        self.on_ctrl_shift_left = on_ctrl_shift_left
        self.on_ctrl_shift_right = on_ctrl_shift_right
        self.on_fix_toggle = on_fix_toggle
        self.on_fix_release = on_fix_release
        self.interval = interval
        self.enabled = True
        self._key_state = key_state or self._default_key_state
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # 左键连击状态
        self._left_down_at: float | None = None
        self._left_clicks = 0
        self._last_click_at = 0.0
        self._pending_double_at: float | None = None
        self._suppress_clicks_until = 0.0
        # 中键
        self._middle_down_at: float | None = None
        self._middle_fired = False
        # Alt+Z
        self._z_down = False
        # Ctrl 单击
        self._ctrl_down_at: float | None = None
        self._ctrl_dirty = False
        # Ctrl+Shift+左右键
        self._shift_left_down = False
        self._shift_right_down = False
        # 去重
        self._last_action_at: dict[str, float] = {}
        # 上一帧状态
        self._prev: dict[int, bool] = {}

    # ---- 采集 ----

    @staticmethod
    def _default_key_state(vk: int) -> bool:
        if sys.platform != "win32":
            return False
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    def _down(self, vk: int) -> bool:
        try:
            return bool(self._key_state(vk))
        except Exception:
            return False

    def _dispatch(self, name: str, callback: Callable[[], None] | None, now: float) -> None:
        if callback is None or not self.enabled:
            return
        previous = self._last_action_at.get(name, 0.0)
        if now - previous < _ACTION_GUARD_SECONDS:
            return
        self._last_action_at[name] = now
        callback()

    # ---- 单帧逻辑（可单独测试）----

    def process_tick(self, now: float) -> None:
        # 到点还没等到第三击，才把双击派发出去
        if self._pending_double_at is not None and now >= self._pending_double_at:
            self._pending_double_at = None
            self._dispatch("double", self.on_double_click, now)

        left = self._down(VK_LBUTTON)
        right = self._down(VK_RBUTTON)
        middle = self._down(VK_MBUTTON)
        ctrl = self._down(VK_CONTROL)
        shift = self._down(VK_SHIFT)
        alt = self._down(VK_MENU)
        z = self._down(VK_Z)

        # 左键：连击统计（长按不计数）
        if left and not self._prev.get(VK_LBUTTON, False):
            self._left_down_at = now
        elif not left and self._prev.get(VK_LBUTTON, False) and self._left_down_at is not None:
            held = now - self._left_down_at
            self._left_down_at = None
            if held <= _CLICK_MAX_SECONDS and now >= self._suppress_clicks_until:
                if now - self._last_click_at > _CLICK_WINDOW_SECONDS:
                    self._left_clicks = 0
                self._left_clicks += 1
                self._last_click_at = now
                if self._left_clicks == 2:
                    self._pending_double_at = now + _DOUBLE_CLICK_DELAY
                elif self._left_clicks >= 3:
                    self._pending_double_at = None
                    self._dispatch("triple", self.on_triple_click, now)
                    self._left_clicks = 0
                    self._suppress_clicks_until = now + _DOUBLE_CLICK_GUARD
        elif left and self._left_down_at is not None and now - self._left_down_at > _CLICK_MAX_SECONDS:
            # 长按（框选/拖拽）不参与连击统计
            self._suppress_clicks_until = now + 0.2
            self._left_clicks = 0

        # 中键长按
        if middle and not self._prev.get(VK_MBUTTON, False):
            self._middle_down_at = now
            self._middle_fired = False
        if middle and self._middle_down_at is not None and not self._middle_fired:
            if now - self._middle_down_at >= _MIDDLE_LONG_SECONDS:
                self._middle_fired = True
                self._dispatch("middle", self.on_middle_long, now)
        if not middle:
            self._middle_down_at = None

        # Alt+Z（按下沿触发一次）
        if z and not self._prev.get(VK_Z, False) and alt:
            self._dispatch("alt_z", self.on_alt_z, now)

        # Ctrl 单击：按下时若已有其他键则作废
        if ctrl and not self._prev.get(VK_CONTROL, False):
            self._ctrl_down_at = now
            self._ctrl_dirty = bool(left or right or middle or shift or alt or z)
        if ctrl and self._ctrl_down_at is not None and not self._ctrl_dirty:
            if left or right or middle or shift or alt or z:
                self._ctrl_dirty = True
        if not ctrl and self._prev.get(VK_CONTROL, False) and self._ctrl_down_at is not None:
            held = now - self._ctrl_down_at
            if not self._ctrl_dirty and held <= _CLICK_MAX_SECONDS:
                self._dispatch("ctrl_tap", self.on_ctrl_tap, now)
            self._ctrl_down_at = None
            self._ctrl_dirty = False

        # Alt+F 切换解决黑屏 / Alt+G 还原（两键组合，考试全屏时也能用）
        fkey = self._down(VK_F)
        gkey = self._down(VK_G)
        if fkey and not self._prev.get(VK_F, False) and alt and not ctrl:
            self._dispatch("fix_toggle", self.on_fix_toggle, now)
        if gkey and not self._prev.get(VK_G, False) and alt and not ctrl:
            self._dispatch("fix_release", self.on_fix_release, now)

        # Ctrl+Shift+左/右键（每次按下触发一次）
        if left and not self._prev.get(VK_LBUTTON, False) and ctrl and shift:
            self._dispatch("shift_left", self.on_ctrl_shift_left, now)
        if right and not self._prev.get(VK_RBUTTON, False) and ctrl and shift:
            self._dispatch("shift_right", self.on_ctrl_shift_right, now)

        self._prev = {
            VK_LBUTTON: left,
            VK_RBUTTON: right,
            VK_MBUTTON: middle,
            VK_CONTROL: ctrl,
            VK_SHIFT: shift,
            VK_MENU: alt,
            VK_Z: z,
            VK_F: fkey,
            VK_G: gkey,
        }

    # ---- 生命周期 ----

    def start(self) -> None:
        if sys.platform != "win32":
            return
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="poll-hotkeys")
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval):
            if not self.enabled:
                continue
            try:
                self.process_tick(time.monotonic())
            except Exception:
                continue

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None
        with self._lock:
            self._prev = {}
