"""防止别的"解决黑屏"工具把本软件的捕获排除清掉。

背景：一些考试端配套工具会遍历窗口、把 ``SetWindowDisplayAffinity`` 清成
``WDA_NONE``（这样截图才能拍到考试窗口），但它会连控制台和悬浮字幕一起清掉，
导致共享屏幕/录屏里能看到我们的窗口。

这里每 300ms 巡检一次自己的窗口：
- 发现 affinity 不是 ``WDA_EXCLUDEFROMCAPTURE`` 就立刻补回来；
- 补完立刻读回校验，连续失败说明被别的程序接管（hook 了 API），只提示一次，
  不反复对抗。

只读/写自己进程拥有的窗口，不碰别的进程。
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal

IntervalMs = 300


class CaptureExclusionGuard(QObject):
    status = Signal(str)
    hijacked = Signal(str)

    def __init__(
        self,
        targets_provider: Callable[[], list[tuple[str, int]]],
        *,
        apply: Callable[[int], tuple[bool, str]] | None = None,
        read: Callable[[int], bool] | None = None,
        interval_ms: int = IntervalMs,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._targets_provider = targets_provider
        self._apply = apply or _default_apply
        self._read = read or _default_read
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.check_once)
        self._failures: dict[str, int] = {}
        self._hijack_reported = False
        self.reassert_count = 0

    # ---- 逻辑（可单独测试）----

    def check_once(self) -> bool:
        if sys.platform != "win32" and self._apply is _default_apply:
            return True
        all_ok = True
        for name, hwnd in self._list_targets():
            if not hwnd:
                continue
            try:
                ok = bool(self._read(hwnd))
            except Exception:
                ok = False
            if ok:
                self._failures[name] = 0
                continue
            applied, detail = self._apply(hwnd)
            still_ok = bool(self._read(hwnd)) if applied else False
            if still_ok:
                self.reassert_count += 1
                self._failures[name] = 0
                self.status.emit(f"{name} 的捕获排除被外部清掉，已重新补上（第 {self.reassert_count} 次）")
                continue
            all_ok = False
            self._failures[name] = self._failures.get(name, 0) + 1
            if self._failures[name] >= 2 and not self._hijack_reported:
                self._hijack_reported = True
                self.hijacked.emit(
                    f"{name} 的捕获排除无法恢复（{detail}）：可能有别的程序接管了这个接口，"
                    "共享屏幕时请手动隐藏字幕或关闭控制台"
                )
        return all_ok

    def _list_targets(self) -> list[tuple[str, int]]:
        try:
            return list(self._targets_provider())
        except Exception:
            return []

    # ---- 生命周期 ----

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def reassert_now(self) -> None:
        """窗口显示/隐藏、分辨率变化后立刻补一次。"""
        for name, hwnd in self._list_targets():
            if not hwnd:
                continue
            try:
                if self._read(hwnd):
                    continue
                applied, _ = self._apply(hwnd)
                if applied and self._read(hwnd):
                    self.reassert_count += 1
            except Exception:
                continue


def _default_apply(hwnd: int) -> tuple[bool, str]:
    from ai_screenshot_assistant.ui.native_capture import apply_capture_exclusion

    return apply_capture_exclusion(hwnd, True)


def _default_read(hwnd: int) -> bool:
    from ai_screenshot_assistant.ui.native_capture import is_excluded_from_capture

    return bool(is_excluded_from_capture(hwnd))
