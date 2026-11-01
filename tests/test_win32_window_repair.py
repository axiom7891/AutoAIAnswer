from __future__ import annotations

import os
import sys

import pytest

from ai_screenshot_assistant.capture import win32_window_repair as wx
from ai_screenshot_assistant.capture.health import (
    FRAME_BLACK,
    FRAME_BLANK,
    FRAME_CONTENT_LOST,
    FRAME_PARTIAL_BLACK,
    FRAME_TRANSPARENT,
)

FAR_REGION = {"left": 200000, "top": 200000, "width": 200, "height": 150}


def record(**overrides) -> wx.WindowRecord:
    base = dict(
        hwnd=0x1234,
        title="答题客户端",
        class_name="Chrome_WidgetWin_1",
        process_id=4321,
        rect=(0, 0, 800, 600),
        overlap=480000,
        ex_style=0,
        display_affinity=wx.WDA_NONE,
        cloaked=False,
        layered=False,
        layered_flags=0,
        layered_alpha=255,
        layered_colorkey=0,
        bits="x64",
    )
    base.update(overrides)
    return wx.WindowRecord(**base)


def test_patch_plan_covers_every_supported_anomaly() -> None:
    assert set(wx._PATCH_PLAN) == {
        FRAME_BLACK,
        FRAME_PARTIAL_BLACK,
        FRAME_TRANSPARENT,
        FRAME_BLANK,
        FRAME_CONTENT_LOST,
    }
    for plan in wx._PATCH_PLAN.values():
        assert plan
        assert set(plan) <= set(wx.PATCH_LABELS)
    assert wx.PATCH_CLEAR_AFFINITY in wx._PATCH_PLAN[FRAME_BLACK]
    assert wx.PATCH_LAYERED_BOOST == wx._PATCH_PLAN[FRAME_TRANSPARENT][0]


def test_patch_labels_are_chinese() -> None:
    for patch, label in wx.PATCH_LABELS.items():
        assert patch
        assert label and not label.isascii()


def test_window_record_flags_surface_hiding_tricks() -> None:
    hidden = record(
        display_affinity=wx.WDA_MONITOR,
        cloaked=True,
        layered=True,
        layered_alpha=40,
        ex_style=wx.WS_EX_LAYERED | wx.WS_EX_NOREDIRECTIONBITMAP,
    )

    flags = hidden.flags()

    assert "WDA_MONITOR 黑块" in flags
    assert "DWM 隐藏" in flags
    assert "图层 alpha=40" in flags
    assert "DComp 直出" in flags
    assert hidden.noredirection is True


def test_window_record_excluded_affinity_label() -> None:
    flags = record(display_affinity=wx.WDA_EXCLUDEFROMCAPTURE).flags()

    assert "已捕获排除" in flags


def test_window_record_label_is_shortened() -> None:
    long_title = record(title="非常长的题库客户端窗口标题" * 3)

    assert long_title.label.endswith("…(0x1234)")
    assert len(long_title.label) < 40


def test_constant_values_match_win32_headers() -> None:
    assert wx.WDA_EXCLUDEFROMCAPTURE == 0x11
    assert wx.WS_EX_NOREDIRECTIONBITMAP == 0x00200000
    assert wx.DWMWA_CLOAK == 13
    assert wx.PW_RENDERFULLCONTENT == 0x2


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_probe_windows_skips_region_without_windows() -> None:
    assert wx.probe_windows(FAR_REGION, max_windows=3) == []


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_apply_without_targets_reports_reason() -> None:
    repair = wx.WindowRepair(inject_remote=False)

    actions, reason = repair.apply(FRAME_BLACK, FAR_REGION)

    assert actions == []
    assert "没有找到" in reason
    assert repair.restore() == []
    assert repair.printwindow_png(FAR_REGION) is None


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_noredirection_patch_reports_failure_when_style_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(wx, "_noredirection_active", lambda hwnd: True)
    repair = wx.WindowRepair(inject_remote=False)
    monkeypatch.setattr(repair, "_write_ex_style", lambda *args: (True, "注入"))

    ok, detail, changed = repair._patch_noredirection(record(ex_style=wx.WS_EX_NOREDIRECTIONBITMAP))

    assert ok is False
    assert changed is False
    assert "标志仍在" in detail


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_noredirection_patch_reports_success_after_readback(monkeypatch) -> None:
    monkeypatch.setattr(wx, "_noredirection_active", lambda hwnd: False)
    repair = wx.WindowRepair(inject_remote=False)
    monkeypatch.setattr(repair, "_write_ex_style", lambda *args: (True, "注入"))

    ok, detail, changed = repair._patch_noredirection(record(ex_style=wx.WS_EX_NOREDIRECTIONBITMAP))

    assert ok is True
    assert changed is True
    assert "GDI 重定向" in detail


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_noredirection_patch_trusts_readback_over_return_code(monkeypatch) -> None:
    monkeypatch.setattr(wx, "_noredirection_active", lambda hwnd: False)
    repair = wx.WindowRepair(inject_remote=False)
    monkeypatch.setattr(repair, "_write_ex_style", lambda *args: (False, "注入返回 0"))

    ok, detail, changed = repair._patch_noredirection(record(ex_style=wx.WS_EX_NOREDIRECTIONBITMAP))

    assert ok is True
    assert changed is True
    assert "GDI 重定向" in detail


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_affinity_patch_verifies_readback(monkeypatch) -> None:
    repair = wx.WindowRepair(inject_remote=False)
    monkeypatch.setattr(repair, "_set_display_affinity", lambda *args: (True, "注入"))
    monkeypatch.setattr(wx, "_display_affinity", lambda hwnd: wx.WDA_MONITOR)

    ok, detail, changed = repair._patch_affinity(record(display_affinity=wx.WDA_MONITOR))

    assert ok is False
    assert changed is False
    assert "读回" in detail


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_layered_patch_verifies_readback(monkeypatch) -> None:
    repair = wx.WindowRepair(inject_remote=False)
    monkeypatch.setattr(repair, "_set_layered", lambda *args: (True, "注入"))
    monkeypatch.setattr(wx, "_layered_attrs", lambda hwnd: (wx.LWA_ALPHA, 40, 0, True))

    ok, detail, changed = repair._patch_layered(
        record(layered=True, layered_alpha=40, ex_style=wx.WS_EX_LAYERED)
    )

    assert ok is False
    assert changed is False
    assert "alpha" in detail


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_layered_patch_success_after_readback(monkeypatch) -> None:
    repair = wx.WindowRepair(inject_remote=False)
    monkeypatch.setattr(repair, "_set_layered", lambda *args: (True, "直调"))
    monkeypatch.setattr(wx, "_layered_attrs", lambda hwnd: (wx.LWA_ALPHA, 255, 0, True))

    ok, detail, changed = repair._patch_layered(
        record(layered=True, layered_alpha=40, ex_style=wx.WS_EX_LAYERED)
    )

    assert ok is True
    assert changed is True
    assert "255" in detail


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_uncloak_patch_skips_when_not_cloaked() -> None:
    repair = wx.WindowRepair(inject_remote=False)

    ok, detail, changed = repair._patch_uncloak(record(cloaked=False))

    assert ok is True
    assert changed is False


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_layered_patch_skips_update_layered_window() -> None:
    repair = wx.WindowRepair(inject_remote=False)

    ok, detail, changed = repair._patch_layered(
        record(layered=True, layered_alpha=40, layered_known=False, ex_style=wx.WS_EX_LAYERED)
    )

    assert ok is False
    assert "UpdateLayeredWindow" in detail
    assert changed is False


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_restore_without_state_is_noop() -> None:
    assert wx.WindowRepair().restore() == []


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_debug_privilege_probe_returns_bool() -> None:
    assert isinstance(wx.enable_debug_privilege(), bool)


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_remote_invoker_allocates_and_frees_remote_buffer() -> None:
    invoker = wx.RemoteInvoker(os.getpid())
    try:
        assert invoker, invoker.error
        address = invoker.alloc_bytes(b"kernel32.dll")
        assert address > invoker.base
        assert invoker._read_u64(invoker.base + wx._REMOTE_RESULT_OFFSET) == 0
    finally:
        invoker.close()


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_remote_invoker_calls_kernel32_in_own_process() -> None:
    import ctypes

    invoker = wx.RemoteInvoker(os.getpid())
    try:
        assert invoker, invoker.error
        module_base = int(wx.kernel32.GetModuleHandleA(b"kernel32.dll") or 0)
        get_module_handle = int(
            wx.kernel32.GetProcAddress(ctypes.c_void_p(module_base), b"GetModuleHandleA") or 0
        )
        assert get_module_handle

        resolved = invoker.resolve("kernel32.dll", "GetModuleHandleA")
        assert resolved == get_module_handle

        module = invoker.call(get_module_handle, [invoker.alloc_bytes(b"kernel32.dll")])
        assert module == module_base

        missing = invoker.call(get_module_handle, [invoker.alloc_bytes(b"no_such_dll_xyz.dll")])
        assert missing == 0
    finally:
        invoker.close()


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_remote_stub_sets_argument_registers_and_stores_result() -> None:
    invoker = wx.RemoteInvoker(os.getpid())
    try:
        assert invoker, invoker.error
        stub = invoker._stub(0x1122334455667788, [0xAA, 0xBB, 0xCC, 0xDD])
    finally:
        invoker.close()

    assert stub.startswith(b"\x48\xB9")  # mov rcx, imm64
    assert b"\x48\xBA" in stub  # mov rdx
    assert b"\x49\xB8" in stub  # mov r8
    assert b"\x49\xB9" in stub  # mov r9
    assert b"\x48\x83\xEC\x68" in stub  # sub rsp, 0x68
    assert b"\xC7\x44\x24" not in stub  # 4 个参数不需要栈传参
    assert stub.endswith(b"\x49\x89\x03\xC3")  # mov [r11], rax; ret


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_remote_stub_places_extra_args_on_stack() -> None:
    invoker = wx.RemoteInvoker(os.getpid())
    try:
        assert invoker, invoker.error
        stub = invoker._stub(0x1122334455667788, [1, 2, 3, 4, 5, 6, 7])
    finally:
        invoker.close()

    assert b"\xC7\x44\x24\x20" in stub
    assert b"\xC7\x44\x24\x28" in stub
    assert b"\xC7\x44\x24\x30" in stub
    assert b"\xC7\x44\x24\x38" not in stub


@pytest.mark.skipif(not wx.IS_WINDOWS, reason="仅 Windows 有窗口 API")
def test_remote_stub_passes_stack_arguments_to_set_rect() -> None:
    import ctypes
    import struct

    invoker = wx.RemoteInvoker(os.getpid())
    try:
        assert invoker, invoker.error
        rect = invoker.alloc_bytes(b"\x00" * 16)
        set_rect = invoker.resolve("user32.dll", "SetRect")
        assert set_rect, invoker.error

        invoker.call(set_rect, [rect, 10, 20, 30, 40])

        buffer = (ctypes.c_char * 16)()
        read = ctypes.c_size_t()
        assert wx.kernel32.ReadProcessMemory(
            invoker.handle, ctypes.c_void_p(rect), buffer, 16, ctypes.byref(read)
        )
        assert struct.unpack("<4i", bytes(buffer)) == (10, 20, 30, 40)
    finally:
        invoker.close()


@pytest.mark.skipif(wx.IS_WINDOWS, reason="非 Windows 才走占位实现")
def test_stub_backend_is_inert_off_windows() -> None:
    assert wx.IS_WINDOWS is False
    assert wx.probe_windows(FAR_REGION) == []
    assert wx.enable_debug_privilege() is False
    repair = wx.WindowRepair()
    assert repair.supported is False
    actions, reason = repair.apply(FRAME_BLACK, FAR_REGION)
    assert actions == []
    assert "Windows" in reason
    assert repair.printwindow_png(FAR_REGION) is None
    assert repair.restore() == []


def test_module_exports_are_importable_on_every_platform() -> None:
    assert callable(wx.probe_windows)
    assert isinstance(wx.PATCH_LABELS, dict)
    assert sys.platform == ("win32" if wx.IS_WINDOWS else sys.platform)
