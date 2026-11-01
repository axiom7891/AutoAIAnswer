"""Windows 窗口级截图异常修复：窗口探测 + 跨进程注入补丁。

截图出现下面三类异常时，往往都是「目标窗口」自己把画面藏起来了：

* 黑屏 / 局部黑块：窗口调用了 ``SetWindowDisplayAffinity(WDA_MONITOR)``（防截屏的答题端、
  浏览器扩展常见做法）、被 DWM ``DWMWA_CLOAK`` 隐藏，或带了 ``WS_EX_NOREDIRECTIONBITMAP``
  走 DirectComposition 直出，GDI 抓出来只有黑。
* 透明屏：窗口是 ``WS_EX_LAYERED``，用 ``SetLayeredWindowAttributes`` 把 alpha 调低或设了
  色键，抓屏拿到的就是「看不见」的合成结果。
* 闪屏：上述补丁时有时无、或画面在两帧之间被清空重绘，抓到的帧一半正常一半全黑。

``SetWindowDisplayAffinity`` 只允许窗口所属进程调用，跨进程直调会返回
``ERROR_ACCESS_DENIED``。所以修复补丁分两档：

1. 直调：``SetWindowLongPtrW`` / ``SetLayeredWindowAttributes`` / ``DwmSetWindowAttribute``
   这类由窗口管理器代为执行的 API，先在本进程直接调用；
2. 注入：直调被拒时，用 ``VirtualAllocEx`` + ``WriteProcessMemory`` + ``CreateRemoteThread``
   把一段位置无关的 x64 stub 注入目标进程，在目标进程里解析
   ``GetModuleHandleA`` / ``GetProcAddress`` 后调用目标 API。stub 把返回值写回远程结果槽，
   再用 ``ReadProcessMemory`` 取回，避免 ``GetExitCodeThread`` 的 32 位截断。

所有补丁都带原始状态快照，``WindowRepair.restore()`` 逆序还原，只在截图窗口期生效。
"""

from __future__ import annotations

import ctypes
import io
import os
import struct
import sys
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Sequence

from ai_screenshot_assistant.capture.health import (
    FRAME_BLACK,
    FRAME_BLANK,
    FRAME_CONTENT_LOST,
    FRAME_PARTIAL_BLACK,
    FRAME_TRANSPARENT,
)

IS_WINDOWS = sys.platform == "win32"

WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_NOREDIRECTIONBITMAP = 0x00200000

DWMWA_CLOAK = 13
DWMWA_EXTENDED_FRAME_BOUNDS = 9

LWA_COLORKEY = 0x00000001
LWA_ALPHA = 0x00000002

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

RDW_INVALIDATE = 0x0001
RDW_ERASE = 0x0004
RDW_FRAME = 0x0400
RDW_ALLCHILDREN = 0x0080
RDW_UPDATENOW = 0x0100

PW_RENDERFULLCONTENT = 0x00000002

PROCESS_CREATE_THREAD = 0x0002
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

MEM_COMMIT = 0x0001000
MEM_RESERVE = 0x0002000
MEM_RELEASE = 0x0008000
PAGE_EXECUTE_READWRITE = 0x00000040
DIB_RGB_COLORS = 0

_SKIP_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "SysShadow",
    "ForegroundStaging",
    "TaskListThumbnailWnd",
    # 输入法/系统弹层：常驻置顶但不承载内容，注入它们只有噪音。
    "Windows.UI.Core.CoreWindow",
}

_REMOTE_BUFFER_SIZE = 0x1000
_REMOTE_RESULT_OFFSET = 0x080
_REMOTE_DATA_OFFSET = 0x100

PATCH_UNCLOAK = "uncloak"
PATCH_CLEAR_AFFINITY = "clear_affinity"
PATCH_LAYERED_BOOST = "layered_alpha"
PATCH_CLEAR_NOREDIRECTION = "clear_noredirection"
PATCH_REDRAW = "redraw"

PATCH_LABELS = {
    PATCH_UNCLOAK: "取消 DWM 隐藏",
    PATCH_CLEAR_AFFINITY: "解除捕获排除",
    PATCH_LAYERED_BOOST: "还原图层不透明度",
    PATCH_CLEAR_NOREDIRECTION: "移除 DirectComposition 直出",
    PATCH_REDRAW: "强制重绘",
}

# 每种异常要打的补丁，顺序即执行顺序。
_PATCH_PLAN = {
    FRAME_BLACK: (
        PATCH_CLEAR_AFFINITY,
        PATCH_UNCLOAK,
        PATCH_LAYERED_BOOST,
        PATCH_CLEAR_NOREDIRECTION,
        PATCH_REDRAW,
    ),
    FRAME_PARTIAL_BLACK: (
        PATCH_CLEAR_AFFINITY,
        PATCH_UNCLOAK,
        PATCH_CLEAR_NOREDIRECTION,
        PATCH_REDRAW,
    ),
    FRAME_TRANSPARENT: (
        PATCH_LAYERED_BOOST,
        PATCH_CLEAR_NOREDIRECTION,
        PATCH_CLEAR_AFFINITY,
        PATCH_REDRAW,
    ),
    FRAME_BLANK: (
        PATCH_CLEAR_NOREDIRECTION,
        PATCH_UNCLOAK,
        PATCH_REDRAW,
    ),
    # 截图里看不到窗口内容（透明窗口/被隐藏/DComp 直出）：逐项解除后再重绘。
    FRAME_CONTENT_LOST: (
        PATCH_LAYERED_BOOST,
        PATCH_UNCLOAK,
        PATCH_CLEAR_AFFINITY,
        PATCH_CLEAR_NOREDIRECTION,
        PATCH_REDRAW,
    ),
}

Action = tuple[str, str, bool, str]


@dataclass(frozen=True)
class WindowRecord:
    hwnd: int
    title: str
    class_name: str
    process_id: int
    rect: tuple[int, int, int, int]
    overlap: int
    ex_style: int
    display_affinity: int
    cloaked: bool
    layered: bool
    layered_flags: int
    layered_alpha: int
    layered_colorkey: int
    bits: str
    layered_known: bool = True
    z_order: int = 0

    @property
    def label(self) -> str:
        name = self.title.strip() or self.class_name or "窗口"
        if len(name) > 24:
            name = name[:24] + "…"
        return f"{name}(0x{self.hwnd:X})"

    @property
    def noredirection(self) -> bool:
        return bool(self.ex_style & WS_EX_NOREDIRECTIONBITMAP)

    def flags(self) -> list[str]:
        flags: list[str] = []
        if self.display_affinity == WDA_MONITOR:
            flags.append("WDA_MONITOR 黑块")
        elif self.display_affinity == WDA_EXCLUDEFROMCAPTURE:
            flags.append("已捕获排除")
        if self.cloaked:
            flags.append("DWM 隐藏")
        if self.layered:
            flags.append(f"图层 alpha={self.layered_alpha}")
        if self.noredirection:
            flags.append("DComp 直出")
        return flags

    def hiding_flags(self) -> list[str]:
        """只列「会让内容从截图里消失」的状态，供无像素证据时兜底判定。"""

        flags: list[str] = []
        if self.display_affinity != WDA_NONE:
            flags.append("捕获排除")
        if self.cloaked:
            flags.append("DWM 隐藏")
        if self.layered and self.layered_alpha < 250:
            flags.append(f"图层 alpha={self.layered_alpha}")
        if self.noredirection:
            flags.append("DComp 直出")
        return flags


@dataclass
class _WindowState:
    """修补前的原始状态，用于还原。"""

    hwnd: int
    ex_style: int
    display_affinity: int
    cloaked: bool
    layered: bool
    layered_flags: int
    layered_alpha: int
    layered_colorkey: int
    layered_known: bool = True
    process_id: int = 0
    bits: str = "?"
    patched: list[str] = field(default_factory=list)


def _unavailable_reason() -> str:
    return "仅 Windows 支持窗口注入修复"


if not IS_WINDOWS:

    def enable_debug_privilege() -> bool:
        return False

    def is_composition_enabled() -> bool:
        return False

    def dwm_flush() -> None:
        return

    def probe_windows(region: dict[str, int], max_windows: int = 3) -> list[WindowRecord]:
        return []

    class WindowRepair:
        supported = False

        def __init__(self, inject_remote: bool = True) -> None:
            self.inject_remote = inject_remote

        def apply(self, kind: str, region: dict[str, int], max_windows: int = 3) -> tuple[list[Action], str]:
            return [], _unavailable_reason()

        def restore(self) -> list[Action]:
            return []

        def printwindow_png(self, region: dict[str, int]) -> bytes | None:
            return None

        def content_image(self, region: dict[str, int], min_overlap_ratio: float = 0.6):
            return None

        def first_hiding_window(
            self,
            region: dict[str, int],
            min_overlap_ratio: float = 0.6,
        ) -> WindowRecord | None:
            return None

        def describe_windows(self, region: dict[str, int], max_windows: int = 8) -> list[str]:
            return []

        def printwindow_probe(self, region: dict[str, int], max_windows: int = 5) -> list[str]:
            return []

        def describe_targets(self) -> list[str]:
            return []

else:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
    except OSError:  # pragma: no cover - 正常系统一定存在
        dwmapi = None

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32
    _OUR_BITS = "x64" if ctypes.sizeof(ctypes.c_void_p) == 8 else "x86"

    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = _ULONG_PTR
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, _ULONG_PTR]
    user32.SetWindowLongPtrW.restype = _ULONG_PTR
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.GetLayeredWindowAttributes.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.COLORREF),
        ctypes.POINTER(wintypes.BYTE),
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetLayeredWindowAttributes.restype = wintypes.BOOL
    user32.SetLayeredWindowAttributes.argtypes = [
        wintypes.HWND,
        wintypes.COLORREF,
        wintypes.BYTE,
        wintypes.DWORD,
    ]
    user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
    user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.HANDLE, wintypes.UINT]
    user32.RedrawWindow.restype = wintypes.BOOL
    user32.GetWindowDC.argtypes = [wintypes.HWND]
    user32.GetWindowDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL

    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.VirtualAllocEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_size_t,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.VirtualAllocEx.restype = ctypes.c_void_p
    kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    kernel32.VirtualFreeEx.restype = wintypes.BOOL
    kernel32.WriteProcessMemory.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.WriteProcessMemory.restype = wintypes.BOOL
    kernel32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL
    kernel32.CreateRemoteThread.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.CreateRemoteThread.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetModuleHandleA.argtypes = [wintypes.LPCSTR]
    kernel32.GetModuleHandleA.restype = ctypes.c_void_p
    kernel32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
    kernel32.GetProcAddress.restype = ctypes.c_void_p
    kernel32.IsWow64Process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel32.IsWow64Process.restype = wintypes.BOOL

    if dwmapi is not None:
        dwmapi.DwmGetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
        dwmapi.DwmSetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
        dwmapi.DwmFlush.argtypes = []
        dwmapi.DwmFlush.restype = ctypes.c_long
        dwmapi.DwmIsCompositionEnabled.argtypes = [ctypes.POINTER(wintypes.BOOL)]
        dwmapi.DwmIsCompositionEnabled.restype = ctypes.c_long

    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class _BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    _TOKEN_ADJUST_PRIVILEGES = 0x0020
    _TOKEN_QUERY = 0x0008
    _SE_PRIVILEGE_ENABLED = 0x00000002

    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.LookupPrivilegeValueW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
    ]
    advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
    advapi32.AdjustTokenPrivileges.argtypes = [
        wintypes.HANDLE,
        wintypes.BOOL,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL

    class _LUID(ctypes.Structure):
        _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

    class _LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", _LUID), ("Attributes", wintypes.DWORD)]

    class _TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", _LUID_AND_ATTRIBUTES * 1)]

    _debug_privilege_state: bool | None = None

    def enable_debug_privilege() -> bool:
        """启用 SeDebugPrivilege：读高权限目标进程内存时要用。"""

        global _debug_privilege_state
        if _debug_privilege_state is not None:
            return _debug_privilege_state
        _debug_privilege_state = False
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(),
            _TOKEN_ADJUST_PRIVILEGES | _TOKEN_QUERY,
            ctypes.byref(token),
        ):
            return False
        try:
            luid = _LUID()
            if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
                return False
            privileges = _TOKEN_PRIVILEGES(
                PrivilegeCount=1,
                Privileges=(_LUID_AND_ATTRIBUTES * 1)(
                    _LUID_AND_ATTRIBUTES(Luid=luid, Attributes=_SE_PRIVILEGE_ENABLED)
                ),
            )
            ctypes.set_last_error(0)
            advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(privileges), 0, None, None)
            _debug_privilege_state = ctypes.get_last_error() == 0
        except Exception:
            _debug_privilege_state = False
        finally:
            kernel32.CloseHandle(token)
        return _debug_privilege_state

    def is_composition_enabled() -> bool:
        if dwmapi is None:
            return False
        enabled = wintypes.BOOL()
        return dwmapi.DwmIsCompositionEnabled(ctypes.byref(enabled)) == 0 and bool(enabled.value)

    def dwm_flush() -> None:
        if dwmapi is not None:
            try:
                dwmapi.DwmFlush()
            except Exception:
                pass

    def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
        if dwmapi is not None:
            value = wintypes.RECT()
            if (
                dwmapi.DwmGetWindowAttribute(
                    wintypes.HWND(hwnd),
                    DWMWA_EXTENDED_FRAME_BOUNDS,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
                == 0
                and value.right > value.left
                and value.bottom > value.top
            ):
                return value.left, value.top, value.right, value.bottom
        rect = wintypes.RECT()
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return 0, 0, 0, 0
        return rect.left, rect.top, rect.right, rect.bottom

    def _overlap(rect: tuple[int, int, int, int], region: dict[str, int]) -> int:
        left = max(rect[0], region["left"])
        top = max(rect[1], region["top"])
        right = min(rect[2], region["left"] + region["width"])
        bottom = min(rect[3], region["top"] + region["height"])
        if right <= left or bottom <= top:
            return 0
        return (right - left) * (bottom - top)

    def _process_bits(handle: int) -> str:
        wow64 = wintypes.BOOL()
        try:
            if kernel32.IsWow64Process(wintypes.HANDLE(handle), ctypes.byref(wow64)):
                return "x86" if wow64.value else "x64"
        except Exception:
            pass
        return "?"

    def _window_text(hwnd: int) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, 256)
        return buffer.value

    def _class_name(hwnd: int) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(wintypes.HWND(hwnd), buffer, 256)
        return buffer.value

    def _window_pid(hwnd: int) -> int:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
        return int(pid.value)

    def _display_affinity(hwnd: int) -> int:
        value = wintypes.DWORD()
        if not user32.GetWindowDisplayAffinity(wintypes.HWND(hwnd), ctypes.byref(value)):
            return WDA_NONE
        return int(value.value)

    def _is_cloaked(hwnd: int) -> bool:
        if dwmapi is None:
            return False
        value = wintypes.DWORD()
        result = dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_CLOAK, ctypes.byref(value), ctypes.sizeof(value)
        )
        return result == 0 and bool(value.value)

    def _current_ex_style(hwnd: int) -> int:
        return int(user32.GetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE)) & 0xFFFFFFFF

    def _noredirection_active(hwnd: int) -> bool:
        return bool(_current_ex_style(hwnd) & WS_EX_NOREDIRECTIONBITMAP)

    def _layered_attrs(hwnd: int) -> tuple[int, int, int, bool]:
        """(标志, alpha, 色键, 是否可读)。读不到说明窗口在用 UpdateLayeredWindow。"""

        colorkey = wintypes.COLORREF()
        alpha = wintypes.BYTE()
        flags = wintypes.DWORD()
        ok = user32.GetLayeredWindowAttributes(
            wintypes.HWND(hwnd), ctypes.byref(colorkey), ctypes.byref(alpha), ctypes.byref(flags)
        )
        if not ok:
            return 0, 0, 0, False
        return int(flags.value), int(alpha.value), int(colorkey.value), True

    def _layered_state(hwnd: int, ex_style: int) -> tuple[bool, int, int, int, bool]:
        """返回 (是否分层, 标志, alpha, 色键, 属性是否可读)。"""

        if not ex_style & WS_EX_LAYERED:
            return False, 0, 255, 0, True
        flags, alpha, colorkey, known = _layered_attrs(hwnd)
        if not known:
            return True, 0, 255, 0, False
        return True, flags, alpha, colorkey, True

    def probe_windows(region: dict[str, int], max_windows: int = 3) -> list[WindowRecord]:
        """找覆盖该区域的顶层窗口，按 z-order（最上层在前）返回。"""

        own_pid = os.getpid()
        region_area = max(1, region["width"] * region["height"])
        found: list[WindowRecord] = []
        order = 0

        def _callback(hwnd: int, _lparam: int) -> bool:
            nonlocal order
            if not user32.IsWindowVisible(wintypes.HWND(hwnd)):
                return True
            rect = _window_rect(hwnd)
            if rect[2] - rect[0] < 8 or rect[3] - rect[1] < 8:
                return True
            area = _overlap(rect, region)
            if area < region_area * 0.15:
                return True
            class_name = _class_name(hwnd)
            if class_name in _SKIP_CLASSES:
                return True
            pid = _window_pid(hwnd)
            if pid == own_pid:
                return True
            order += 1
            ex_style = int(user32.GetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE)) & 0xFFFFFFFF
            (
                layered,
                layered_flags,
                layered_alpha,
                layered_colorkey,
                layered_known,
            ) = _layered_state(hwnd, ex_style)
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            bits = "?"
            if handle:
                try:
                    bits = _process_bits(handle)
                finally:
                    kernel32.CloseHandle(handle)
            found.append(
                WindowRecord(
                    hwnd=hwnd,
                    title=_window_text(hwnd),
                    class_name=class_name,
                    process_id=pid,
                    rect=rect,
                    overlap=area,
                    ex_style=ex_style,
                    display_affinity=_display_affinity(hwnd),
                    cloaked=_is_cloaked(hwnd),
                    layered=layered,
                    layered_flags=layered_flags,
                    layered_alpha=layered_alpha,
                    layered_colorkey=layered_colorkey,
                    bits=bits,
                    layered_known=layered_known,
                    z_order=order,
                )
            )
            return True

        user32.EnumWindows(WNDENUMPROC(_callback), 0)
        # EnumWindows 本身就是从最上层往下枚举：先按 z 排，同样 z 再按覆盖面积。
        found.sort(key=lambda record: (record.z_order, -record.overlap))
        return found[:max_windows]

    class RemoteInvoker:
        """往目标进程注入一次函数调用，取回 64 位返回值。"""

        def __init__(self, process_id: int) -> None:
            self.process_id = process_id
            self.error = ""
            self.handle = kernel32.OpenProcess(
                PROCESS_CREATE_THREAD
                | PROCESS_VM_OPERATION
                | PROCESS_VM_WRITE
                | PROCESS_VM_READ
                | PROCESS_QUERY_INFORMATION,
                False,
                process_id,
            )
            if not self.handle:
                self.handle = kernel32.OpenProcess(
                    PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ,
                    False,
                    process_id,
                )
            self.base = 0
            self._offset = _REMOTE_DATA_OFFSET
            self._cache: dict[tuple[str, str], int] = {}
            if not self.handle:
                error = ctypes.get_last_error()
                if error == 5:
                    self.error = "OpenProcess 拒绝访问（目标可能以管理员运行，请用管理员身份启动本程序）"
                else:
                    self.error = f"OpenProcess 失败 ({error})"
                return
            self.base = int(
                kernel32.VirtualAllocEx(
                    self.handle,
                    None,
                    _REMOTE_BUFFER_SIZE,
                    MEM_COMMIT | MEM_RESERVE,
                    PAGE_EXECUTE_READWRITE,
                )
                or 0
            )
            if not self.base:
                self.error = f"VirtualAllocEx 失败 ({ctypes.get_last_error()})"

        def __bool__(self) -> bool:
            return bool(self.handle) and bool(self.base) and not self.error

        def __enter__(self) -> "RemoteInvoker":
            return self

        def __exit__(self, *_exc) -> None:
            self.close()

        def close(self) -> None:
            if self.base and self.handle:
                kernel32.VirtualFreeEx(self.handle, ctypes.c_void_p(self.base), 0, MEM_RELEASE)
                self.base = 0
            if self.handle:
                kernel32.CloseHandle(self.handle)
                self.handle = None

        # ---- 远程内存 ----

        def _write(self, address: int, data: bytes) -> bool:
            buffer = ctypes.create_string_buffer(data, len(data))
            written = ctypes.c_size_t()
            ok = kernel32.WriteProcessMemory(
                self.handle,
                ctypes.c_void_p(address),
                buffer,
                len(data),
                ctypes.byref(written),
            )
            return bool(ok) and written.value == len(data)

        def _read_u64(self, address: int) -> int:
            buffer = (ctypes.c_char * 8)()
            read = ctypes.c_size_t()
            if not kernel32.ReadProcessMemory(
                self.handle, ctypes.c_void_p(address), buffer, 8, ctypes.byref(read)
            ):
                return 0
            return struct.unpack("<Q", bytes(buffer))[0]

        def alloc_bytes(self, data: bytes) -> int:
            size = len(data) + 1
            if self._offset + size > _REMOTE_BUFFER_SIZE:
                raise MemoryError("注入缓冲区不足")
            address = self.base + self._offset
            if not self._write(address, data + b"\x00"):
                raise OSError(f"WriteProcessMemory 失败 ({ctypes.get_last_error()})")
            self._offset += (size + 15) & ~15
            return address

        def _stub(self, fn_address: int, args: Sequence[int]) -> bytes:
            """位置无关 stub：前 4 个参数进寄存器，第 5–8 个走栈参数，返回值写入结果槽。"""

            values = [int(value) & 0xFFFFFFFFFFFFFFFF for value in list(args)[:8]]
            code = bytearray()
            movs = (b"\x48\xB9", b"\x48\xBA", b"\x49\xB8", b"\x49\xB9")
            for index, value in enumerate(values[:4]):
                code += movs[index] + struct.pack("<Q", value)
            code += b"\x48\x83\xEC\x68"  # sub rsp, 0x68：影子空间 + 4 个栈参数 + 对齐
            for index, value in enumerate(values[4:]):
                # mov dword [rsp+0x20+8*i], imm32
                code += b"\xC7\x44\x24" + bytes([0x20 + 8 * index]) + struct.pack("<I", value & 0xFFFFFFFF)
            code += b"\x48\xB8" + struct.pack("<Q", fn_address & 0xFFFFFFFFFFFFFFFF)
            code += b"\xFF\xD0"  # call rax
            code += b"\x48\x83\xC4\x68"  # add rsp, 0x68
            code += b"\x49\xBB" + struct.pack("<Q", self.base + _REMOTE_RESULT_OFFSET)
            code += b"\x49\x89\x03"  # mov [r11], rax
            code += b"\xC3"
            return bytes(code)

        def call(self, fn_address: int, args: Sequence[int], timeout_ms: int = 4000) -> int:
            if not self:
                return 0
            stub = self._stub(fn_address, args)
            if not self._write(self.base, stub):
                return 0
            thread_id = wintypes.DWORD()
            thread = kernel32.CreateRemoteThread(
                self.handle, None, 0, ctypes.c_void_p(self.base), None, 0, ctypes.byref(thread_id)
            )
            if not thread:
                self.error = f"CreateRemoteThread 失败 ({ctypes.get_last_error()})"
                return 0
            try:
                kernel32.WaitForSingleObject(thread, timeout_ms)
            finally:
                kernel32.CloseHandle(thread)
            return self._read_u64(self.base + _REMOTE_RESULT_OFFSET)

        def _shared_kernel32(self) -> bool:
            """校验目标进程的 kernel32 基址与本进程一致（系统 DLL 同址映射）。"""

            local = int(kernel32.GetModuleHandleA(b"kernel32.dll") or 0)
            if not local:
                return False
            buffer = (ctypes.c_char * 2)()
            read = ctypes.c_size_t()
            if not kernel32.ReadProcessMemory(
                self.handle, ctypes.c_void_p(local), buffer, 2, ctypes.byref(read)
            ):
                return False
            return bytes(buffer) == b"MZ"

        def resolve(self, dll: str, function: str) -> int:
            key = (dll.lower(), function)
            if key in self._cache:
                return self._cache[key]
            if not self._shared_kernel32():
                self.error = "目标进程 kernel32 基址不可读，跳过注入"
                return 0
            local_kernel32 = int(kernel32.GetModuleHandleA(b"kernel32.dll") or 0)
            get_module = int(
                kernel32.GetProcAddress(ctypes.c_void_p(local_kernel32), b"GetModuleHandleA") or 0
            )
            load_library = int(
                kernel32.GetProcAddress(ctypes.c_void_p(local_kernel32), b"LoadLibraryA") or 0
            )
            get_proc = int(
                kernel32.GetProcAddress(ctypes.c_void_p(local_kernel32), b"GetProcAddress") or 0
            )
            if not get_module or not get_proc:
                self.error = "本地 GetModuleHandleA/GetProcAddress 解析失败"
                return 0
            module_name = self.alloc_bytes(dll.encode("ascii"))
            module = self.call(get_module, [module_name])
            if not module and load_library and not self.error:
                module = self.call(load_library, [module_name])
            if not module:
                if not self.error:
                    self.error = f"目标进程加载 {dll} 失败"
                return 0
            function_name = self.alloc_bytes(function.encode("ascii"))
            address = self.call(get_proc, [module, function_name])
            if address:
                self._cache[key] = address
            return address

    def _remote_call(
        pid: int,
        dll: str,
        function: str,
        args: Sequence[int | bytes],
        timeout_ms: int = 4000,
    ) -> tuple[int, str]:
        with RemoteInvoker(pid) as invoker:
            if not invoker:
                return 0, invoker.error or "注入器初始化失败"
            address = invoker.resolve(dll, function)
            if not address:
                return 0, invoker.error or f"{dll}!{function} 解析失败"
            remote_args: list[int] = []
            for value in args:
                if isinstance(value, (bytes, bytearray)):
                    remote_args.append(invoker.alloc_bytes(bytes(value)))
                else:
                    remote_args.append(int(value))
            result = invoker.call(address, remote_args, timeout_ms)
            return result, invoker.error

    class WindowRepair:
        """给可疑窗口打临时补丁，并保证还原。"""

        supported = True

        def __init__(self, inject_remote: bool = True) -> None:
            self.inject_remote = inject_remote
            self._states: dict[int, _WindowState] = {}
            self._targets: list[WindowRecord] = []
            if inject_remote:
                enable_debug_privilege()

        # ---- 补丁实现：(是否成功, 说明, 是否真的改了东西) ----

        def _state_of(self, record: WindowRecord) -> _WindowState:
            state = self._states.get(record.hwnd)
            if state is None:
                state = _WindowState(
                    hwnd=record.hwnd,
                    ex_style=record.ex_style,
                    display_affinity=record.display_affinity,
                    cloaked=record.cloaked,
                    layered=record.layered,
                    layered_flags=record.layered_flags,
                    layered_alpha=record.layered_alpha,
                    layered_colorkey=record.layered_colorkey,
                    layered_known=record.layered_known,
                    process_id=record.process_id,
                    bits=record.bits,
                )
                self._states[record.hwnd] = state
            return state

        def _can_inject_values(self, process_id: int, bits: str) -> tuple[bool, str]:
            if not self.inject_remote:
                return False, "注入已关闭"
            if bits == "?":
                return False, "目标进程位数未知，跳过注入"
            if bits != _OUR_BITS:
                return False, f"目标是 {bits} 进程，注入会破坏目标，已跳过"
            if not process_id:
                return False, "目标进程未知"
            return True, ""

        def _set_display_affinity(
            self,
            hwnd: int,
            process_id: int,
            bits: str,
            affinity: int,
        ) -> tuple[bool, str]:
            """设置捕获排除：直调优先，被拒时注入目标进程调用。"""

            ctypes.set_last_error(0)
            if user32.SetWindowDisplayAffinity(wintypes.HWND(hwnd), affinity):
                return True, "直调"
            local_error = ctypes.get_last_error()
            allowed, reason = self._can_inject_values(process_id, bits)
            if not allowed:
                return False, f"直调被拒 (Win32 {local_error})，{reason}"
            value, error = _remote_call(
                process_id, "user32.dll", "SetWindowDisplayAffinity", [hwnd, affinity]
            )
            if value:
                return True, "注入"
            return False, f"直调 Win32 {local_error}；注入失败：{error or '返回 0'}"

        def _set_cloak(
            self,
            hwnd: int,
            process_id: int,
            bits: str,
            cloaked: bool,
        ) -> tuple[bool, str]:
            value = 1 if cloaked else 0
            if dwmapi is not None:
                flag = wintypes.DWORD(value)
                if (
                    dwmapi.DwmSetWindowAttribute(
                        wintypes.HWND(hwnd), DWMWA_CLOAK, ctypes.byref(flag), ctypes.sizeof(flag)
                    )
                    == 0
                ):
                    return True, "直调"
            allowed, reason = self._can_inject_values(process_id, bits)
            if not allowed:
                return False, f"DwmSetWindowAttribute 失败，{reason}"
            result, error = _remote_call(
                process_id,
                "dwmapi.dll",
                "DwmSetWindowAttribute",
                [hwnd, DWMWA_CLOAK, struct.pack("<I", value), 4],
            )
            if result == 0:
                return True, "注入"
            return False, f"注入失败：{error or '返回非 0'}"

        def _set_layered(
            self,
            hwnd: int,
            process_id: int,
            bits: str,
            colorkey: int,
            alpha: int,
            flags: int,
        ) -> tuple[bool, str]:
            ctypes.set_last_error(0)
            if user32.SetLayeredWindowAttributes(wintypes.HWND(hwnd), colorkey, alpha, flags):
                return True, "直调"
            local_error = ctypes.get_last_error()
            allowed, reason = self._can_inject_values(process_id, bits)
            if not allowed:
                return False, f"直调被拒 (Win32 {local_error})，{reason}"
            value, error = _remote_call(
                process_id,
                "user32.dll",
                "SetLayeredWindowAttributes",
                [hwnd, colorkey, alpha, flags],
            )
            if value:
                return True, "注入"
            return False, f"直调 Win32 {local_error}；注入失败：{error or '返回 0'}"

        def _write_ex_style(
            self,
            hwnd: int,
            process_id: int,
            bits: str,
            style: int,
        ) -> tuple[bool, str]:
            frame_flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
            ctypes.set_last_error(0)
            previous = int(user32.SetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE, style))
            if not (previous == 0 and ctypes.get_last_error() != 0):
                user32.SetWindowPos(wintypes.HWND(hwnd), None, 0, 0, 0, 0, frame_flags)
                return True, "直调"
            local_error = ctypes.get_last_error()
            allowed, reason = self._can_inject_values(process_id, bits)
            if not allowed:
                return False, f"SetWindowLongPtrW 被拒 (Win32 {local_error})，{reason}"
            value, error = _remote_call(
                process_id, "user32.dll", "SetWindowLongPtrW", [hwnd, GWL_EXSTYLE, style]
            )
            _remote_call(
                process_id, "user32.dll", "SetWindowPos", [hwnd, 0, 0, 0, 0, 0, frame_flags]
            )
            if value:
                return True, "注入"
            return False, f"直调 Win32 {local_error}；注入失败：{error or '返回 0'}"

        # ---- 补丁：读取回状态为准，写入返回值只用来解释过程 ----

        def _patch_affinity(self, record: WindowRecord) -> tuple[bool, str, bool]:
            if record.display_affinity == WDA_NONE:
                return True, "未开启捕获排除", False
            ok, mode = self._set_display_affinity(record.hwnd, record.process_id, record.bits, WDA_NONE)
            if _display_affinity(record.hwnd) == WDA_NONE:
                return True, (f"{mode}解除" if ok else "已解除（写入返回失败但状态已变化）"), True
            return False, (mode if not ok else f"{mode}调用成功但读回仍带捕获排除"), False

        def _patch_uncloak(self, record: WindowRecord) -> tuple[bool, str, bool]:
            if not record.cloaked:
                return True, "未被 DWM 隐藏", False
            ok, mode = self._set_cloak(record.hwnd, record.process_id, record.bits, False)
            if not _is_cloaked(record.hwnd):
                return True, (f"{mode}取消隐藏" if ok else "已取消隐藏（写入返回失败但状态已变化）"), True
            return False, (mode if not ok else f"{mode}调用成功但窗口仍处于隐藏"), False

        def _patch_layered(self, record: WindowRecord) -> tuple[bool, str, bool]:
            if not record.layered:
                return True, "不是分层窗口", False
            if not record.layered_known:
                return False, "窗口用 UpdateLayeredWindow 自绘，图层属性不可直调，改走 PrintWindow", False
            if record.layered_alpha >= 255 and not record.layered_flags & LWA_COLORKEY:
                return True, "图层已不透明", False
            ok, mode = self._set_layered(record.hwnd, record.process_id, record.bits, 0, 255, LWA_ALPHA)
            _flags, alpha, _key, known = _layered_attrs(record.hwnd)
            if known and alpha >= 250:
                return True, f"{mode} alpha {record.layered_alpha}→{alpha}", True
            if not known:
                return ok, (f"{mode}已写入" if ok else mode), ok
            return False, (mode if not ok else f"{mode}调用成功但读回 alpha 未提升"), False

        def _patch_noredirection(self, record: WindowRecord) -> tuple[bool, str, bool]:
            if not record.noredirection:
                return True, "没有 DComp 直出标志", False
            ok, mode = self._write_ex_style(
                record.hwnd, record.process_id, record.bits, record.ex_style & ~WS_EX_NOREDIRECTIONBITMAP
            )
            if not _noredirection_active(record.hwnd):
                return True, (f"{mode}切回 GDI 重定向位图" if ok else "已切回 GDI 重定向位图"), True
            if not ok:
                return False, mode, False
            return False, f"{mode}后直出标志仍在（AppContainer/UIPI 拒绝改写）", False

        def _patch_redraw(self, record: WindowRecord) -> tuple[bool, str, bool]:
            user32.RedrawWindow(
                wintypes.HWND(record.hwnd),
                None,
                None,
                RDW_INVALIDATE | RDW_ERASE | RDW_FRAME | RDW_ALLCHILDREN | RDW_UPDATENOW,
            )
            dwm_flush()
            return True, "已请求重绘并刷新 DWM", True

        def _dispatch(self, patch: str, record: WindowRecord) -> tuple[bool, str, bool]:
            handler = {
                PATCH_CLEAR_AFFINITY: self._patch_affinity,
                PATCH_UNCLOAK: self._patch_uncloak,
                PATCH_LAYERED_BOOST: self._patch_layered,
                PATCH_CLEAR_NOREDIRECTION: self._patch_noredirection,
                PATCH_REDRAW: self._patch_redraw,
            }[patch]
            try:
                return handler(record)
            except Exception as exc:  # pragma: no cover - 真实注入失败才会到
                return False, f"{type(exc).__name__}: {exc}", False

        def apply(
            self,
            kind: str,
            region: dict[str, int],
            max_windows: int = 3,
        ) -> tuple[list[Action], str]:
            """给覆盖该区域的窗口打补丁，返回 [(目标, 补丁, 是否成功, 细节)]。"""

            plan = _PATCH_PLAN.get(kind)
            if not plan:
                return [], f"无需窗口补丁（{kind}）"
            targets = probe_windows(region, max_windows=max_windows)
            self._targets = targets or self._targets
            if not targets:
                return [], "没有找到覆盖该区域的窗口"
            actions: list[Action] = []
            region_area = max(1, region["width"] * region["height"])
            topmost = targets[0]
            for record in targets:
                # 只动「带藏画面标志」的窗口和区域最上层那一个，别去碰无关窗口。
                if not record.hiding_flags() and record.hwnd != topmost.hwnd:
                    continue
                state = self._state_of(record)
                for patch in plan:
                    if patch in state.patched:
                        continue
                    if patch == PATCH_CLEAR_NOREDIRECTION and record.overlap < region_area * 0.6:
                        # 只盖住一角的窗口不会让整幅截图发黑，不动它的合成方式。
                        continue
                    ok, detail, changed = self._dispatch(patch, record)
                    if ok and changed:
                        state.patched.append(patch)
                    if ok and not changed:
                        # 该窗口本来就没有这一项保护，不写进日志免得刷屏。
                        continue
                    actions.append((record.label, patch, ok, detail))
            dwm_flush()
            return actions, ""

        # ---- 还原 ----

        def _restore_window(self, state: _WindowState) -> list[Action]:
            actions: list[Action] = []
            hwnd = state.hwnd
            label = f"0x{hwnd:X}"
            for patch in reversed(state.patched):
                if patch == PATCH_CLEAR_NOREDIRECTION:
                    want_active = bool(state.ex_style & WS_EX_NOREDIRECTIONBITMAP)
                    if _noredirection_active(hwnd) == want_active:
                        actions.append((label, patch, True, "直出标志已是原状"))
                        continue
                    ok, mode = self._write_ex_style(hwnd, state.process_id, state.bits, state.ex_style)
                    restored = _noredirection_active(hwnd) == want_active
                    actions.append(
                        (
                            label,
                            patch,
                            ok and restored,
                            "已恢复直出标志" if restored else f"恢复直出标志失败：{mode}",
                        )
                    )
                elif patch == PATCH_LAYERED_BOOST:
                    ok, detail = True, "图层无需恢复"
                    if state.layered and state.layered_known:
                        flags = state.layered_flags or LWA_ALPHA
                        applied, mode = self._set_layered(
                            hwnd,
                            state.process_id,
                            state.bits,
                            state.layered_colorkey,
                            state.layered_alpha,
                            flags,
                        )
                        now_flags, now_alpha, now_key, known = _layered_attrs(hwnd)
                        restored = applied and (
                            not known
                            or (now_alpha == state.layered_alpha and now_key == state.layered_colorkey)
                        )
                        ok = restored
                        detail = "已恢复图层属性" if restored else f"恢复图层属性失败：{mode}"
                    actions.append((label, patch, ok, detail))
                elif patch == PATCH_UNCLOAK:
                    ok, detail = True, "DWM 隐藏状态无需恢复"
                    if state.cloaked:
                        applied, mode = self._set_cloak(hwnd, state.process_id, state.bits, True)
                        restored = applied and _is_cloaked(hwnd)
                        ok = restored
                        detail = "已恢复 DWM 隐藏状态" if restored else f"恢复 DWM 隐藏失败：{mode}"
                    actions.append((label, patch, ok, detail))
                elif patch == PATCH_CLEAR_AFFINITY:
                    if state.display_affinity == WDA_NONE:
                        actions.append((label, patch, True, "捕获排除无需恢复"))
                        continue
                    if _display_affinity(hwnd) == state.display_affinity:
                        actions.append((label, patch, True, "捕获排除已是原状"))
                        continue
                    applied, mode = self._set_display_affinity(
                        hwnd, state.process_id, state.bits, state.display_affinity
                    )
                    restored = _display_affinity(hwnd) == state.display_affinity
                    actions.append(
                        (
                            label,
                            patch,
                            applied and restored,
                            "已恢复捕获排除" if restored else f"恢复捕获排除失败：{mode}",
                        )
                    )
            state.patched.clear()
            return actions

        def restore(self) -> list[Action]:
            actions: list[Action] = []
            for state in list(self._states.values()):
                try:
                    actions.extend(self._restore_window(state))
                except Exception:
                    continue
            self._states.clear()
            dwm_flush()
            return actions

        def describe_targets(self) -> list[str]:
            lines = []
            for record in self._targets:
                flags = "、".join(record.flags()) or "无异常标志"
                lines.append(f"{record.label} {record.class_name} pid={record.process_id} {flags}")
            return lines

        # ---- PrintWindow 回退 ----

        def _print_window(self, hwnd: int):
            from PIL import Image

            left, top, right, bottom = _window_rect(hwnd)
            width, height = right - left, bottom - top
            if width <= 0 or height <= 0:
                return None
            screen_dc = user32.GetWindowDC(wintypes.HWND(hwnd))
            if not screen_dc:
                return None
            memory_dc = gdi32.CreateCompatibleDC(screen_dc)
            buffer: bytes | None = None
            try:
                info = _BITMAPINFO()
                info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
                info.bmiHeader.biWidth = width
                info.bmiHeader.biHeight = -height  # 负高度 = top-down
                info.bmiHeader.biPlanes = 1
                info.bmiHeader.biBitCount = 32
                info.bmiHeader.biCompression = 0
                bits = ctypes.c_void_p()
                bitmap = gdi32.CreateDIBSection(
                    memory_dc, ctypes.byref(info), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
                )
                if not bitmap or not bits:
                    return None
                previous = gdi32.SelectObject(memory_dc, bitmap)
                try:
                    if not user32.PrintWindow(wintypes.HWND(hwnd), memory_dc, PW_RENDERFULLCONTENT):
                        return None
                    buffer = ctypes.string_at(bits, width * height * 4)
                finally:
                    gdi32.SelectObject(memory_dc, previous)
                    gdi32.DeleteObject(bitmap)
            finally:
                gdi32.DeleteDC(memory_dc)
                user32.ReleaseDC(wintypes.HWND(hwnd), screen_dc)
            if not buffer:
                return None
            image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
            return image.convert("RGB")

        def _crop_to_region(self, image, hwnd: int, region: dict[str, int]):
            left, top, right, bottom = _window_rect(hwnd)
            box = (
                max(0, region["left"] - left),
                max(0, region["top"] - top),
                min(right - left, region["left"] + region["width"] - left),
                min(bottom - top, region["top"] + region["height"] - top),
            )
            if box[2] <= box[0] or box[3] <= box[1]:
                return None
            return image.crop(box)

        def _topmost_covering(
            self,
            region: dict[str, int],
            min_overlap_ratio: float = 0.6,
            max_windows: int = 5,
        ) -> WindowRecord | None:
            """区域最上层的那个窗口：屏幕上是它决定了这块区域长什么样。"""

            region_area = max(1, region["width"] * region["height"])
            for record in probe_windows(region, max_windows=max_windows):
                if record.overlap >= region_area * min_overlap_ratio:
                    return record
            return None

        def content_image(
            self,
            region: dict[str, int],
            min_overlap_ratio: float = 0.6,
        ):
            """截取区域最上层窗口的「自身渲染」画面，用于判断内容是否被藏掉。"""

            record = self._topmost_covering(region, min_overlap_ratio)
            if record is None:
                return None
            image = self._print_window(record.hwnd)
            if image is None:
                return None
            return self._crop_to_region(image, record.hwnd, region)

        def first_hiding_window(
            self,
            region: dict[str, int],
            min_overlap_ratio: float = 0.6,
        ) -> WindowRecord | None:
            """只看区域最上层窗口的状态：捕获排除/隐藏/低 alpha/直出。"""

            record = self._topmost_covering(region, min_overlap_ratio)
            if record is None:
                return None
            return record if record.hiding_flags() else None

        def describe_windows(self, region: dict[str, int], max_windows: int = 8) -> list[str]:
            lines: list[str] = []
            for record in probe_windows(region, max_windows=max_windows):
                flags = "、".join(record.flags()) or "无"
                lines.append(
                    f"hwnd=0x{record.hwnd:X} class={record.class_name} "
                    f"title={record.title!r} pid={record.process_id} bits={record.bits} "
                    f"rect={record.rect} overlap={record.overlap} "
                    f"exstyle=0x{record.ex_style:X} affinity=0x{record.display_affinity:X} "
                    f"cloaked={record.cloaked} layered={record.layered}"
                    f"(flags={record.layered_flags},alpha={record.layered_alpha},known={record.layered_known}) "
                    f"noredir={record.noredirection} 状态={flags}"
                )
            return lines

        def printwindow_probe(self, region: dict[str, int], max_windows: int = 5) -> list[str]:
            """逐个窗口试 PrintWindow，报告能否取到内容，供诊断文件使用。"""

            from PIL import ImageStat

            region_area = max(1, region["width"] * region["height"])
            lines: list[str] = []
            for record in probe_windows(region, max_windows=max_windows):
                if record.overlap < region_area * 0.3:
                    continue
                image = self._print_window(record.hwnd)
                if image is None:
                    lines.append(f"hwnd=0x{record.hwnd:X} PrintWindow=失败")
                    continue
                detail = ImageStat.Stat(image.convert("L")).stddev[0]
                lines.append(f"hwnd=0x{record.hwnd:X} PrintWindow=成功 detail={detail:.1f}")
            return lines

        def printwindow_png(self, region: dict[str, int]) -> bytes | None:
            candidates = [record.hwnd for record in self._targets]
            if not candidates:
                candidates = [record.hwnd for record in probe_windows(region, max_windows=3)]
            for hwnd in candidates:
                image = self._print_window(hwnd)
                if image is None:
                    continue
                cropped = self._crop_to_region(image, hwnd, region)
                if cropped is None:
                    continue
                buffer = io.BytesIO()
                cropped.save(buffer, format="PNG")
                return buffer.getvalue()
            return None
