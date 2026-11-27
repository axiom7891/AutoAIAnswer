"""手动「解决黑屏」：让考试端窗口对截图可见，并一直保持。

- 自动（截图流程内）：``capture.repair`` 每次截图前临时解除、截完还原；
- 持续（这里）：点开后对覆盖截图区域的窗口一直保持解除状态，直到用户
  关闭开关、按 ``Alt+G`` 或退出程序才还原。

不做定时复查：复查会反复 restore/apply，窗口会闪。需要重新解除时按一次
``Alt+F`` 关掉再开即可。

只处理覆盖截图区域、且带隐藏标志的窗口；本软件自己的窗口不碰。
"""

from __future__ import annotations

import sys
from typing import Any

from ai_screenshot_assistant.capture.health import FRAME_CONTENT_LOST


class BlackoutSession:
    def __init__(self, inject_remote: bool = True) -> None:
        self._native: Any = None
        self._active = False
        self._region: dict[str, int] | None = None
        self._targets: list[str] = []
        if sys.platform != "win32":
            return
        try:
            from ai_screenshot_assistant.capture.win32_window_repair import WindowRepair

            self._native = WindowRepair(inject_remote=inject_remote)
        except Exception:
            self._native = None

    @property
    def supported(self) -> bool:
        return bool(getattr(self._native, "supported", False))

    @property
    def active(self) -> bool:
        return self._active

    @property
    def targets(self) -> list[str]:
        return list(self._targets)

    def describe(self, region: dict[str, int], max_windows: int = 8) -> list[str]:
        if not self.supported:
            return ["当前系统不支持窗口修复"]
        try:
            return list(self._native.describe_windows(region, max_windows=max_windows))
        except Exception as exc:
            return [f"检测失败：{exc}"]

    def engage(self, region: dict[str, int], max_windows: int = 4) -> tuple[bool, list[str]]:
        if not self.supported:
            return False, ["当前系统不支持窗口修复"]
        try:
            actions, reason = self._native.apply(FRAME_CONTENT_LOST, region, max_windows=max_windows)
        except Exception as exc:
            return False, [f"修复失败：{exc}"]
        lines = [
            f"{label} · {patch} · {'成功' if ok else '失败'} · {detail}"
            for label, patch, ok, detail in actions
        ]
        changed = [line for line, action in zip(lines, actions) if action[2]]
        if not changed:
            return False, lines or [reason or "没有找到需要解除保护的窗口"]
        self._active = True
        self._region = dict(region)
        self._targets = sorted({action[0] for action in actions if action[2]})
        return True, lines

    def release(self) -> list[str]:
        self._active = False
        self._region = None
        self._targets = []
        if not self.supported:
            return []
        try:
            actions = self._native.restore()
        except Exception as exc:
            return [f"还原失败：{exc}"]
        return [f"{label} · {patch} · {'已还原' if ok else '还原失败'} · {detail}"
                for label, patch, ok, detail in actions]
