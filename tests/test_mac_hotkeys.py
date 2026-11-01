from __future__ import annotations

import sys

import pytest

from ai_screenshot_assistant.input.mac_hotkeys import MacHotkeyListener


class FakeKey:
    def __init__(self, name: str | None = None, char: str | None = None) -> None:
        if name is not None:
            self.name = name
        if char is not None:
            self.char = char


class FakeButton:
    def __init__(self, name: str) -> None:
        self.name = name


def test_ctrl_alt_o_toggles_once() -> None:
    toggles: list[bool] = []
    listener = MacHotkeyListener(on_overlay_toggle=lambda: toggles.append(True))

    listener.handle_press(FakeKey(name="ctrl"))
    listener.handle_press(FakeKey(name="alt"))
    listener.handle_press(FakeKey(char="o"))
    listener.handle_press(FakeKey(char="o"))  # 自动重复不重复触发
    assert toggles == [True]

    listener.handle_release(FakeKey(char="o"))
    listener.handle_release(FakeKey(name="alt"))
    listener.handle_release(FakeKey(name="ctrl"))
    listener.handle_press(FakeKey(name="ctrl"))
    listener.handle_press(FakeKey(name="alt"))
    listener.handle_press(FakeKey(char="o"))
    assert toggles == [True, True]


def test_ctrl_o_without_alt_does_nothing() -> None:
    toggles: list[bool] = []
    listener = MacHotkeyListener(on_overlay_toggle=lambda: toggles.append(True))

    listener.handle_press(FakeKey(name="ctrl"))
    listener.handle_press(FakeKey(char="o"))

    assert toggles == []


def test_middle_long_press_triggers(monkeypatch) -> None:
    toggles: list[bool] = []
    listener = MacHotkeyListener(on_middle_long=lambda: toggles.append(True))
    times = iter((10.0, 11.2))
    monkeypatch.setattr(
        "ai_screenshot_assistant.input.mac_hotkeys.time.monotonic", lambda: next(times)
    )

    listener.handle_click(FakeButton("middle"), True)
    listener.handle_click(FakeButton("middle"), False)

    assert listener.middle_long_press_seconds == 1.0
    assert toggles == [True]


def test_middle_short_click_ignored(monkeypatch) -> None:
    toggles: list[bool] = []
    listener = MacHotkeyListener(on_middle_long=lambda: toggles.append(True))
    times = iter((10.0, 10.3))
    monkeypatch.setattr(
        "ai_screenshot_assistant.input.mac_hotkeys.time.monotonic", lambda: next(times)
    )

    listener.handle_click(FakeButton("middle"), True)
    listener.handle_click(FakeButton("middle"), False)

    assert toggles == []


def test_left_click_is_ignored() -> None:
    toggles: list[bool] = []
    listener = MacHotkeyListener(on_middle_long=lambda: toggles.append(True))

    listener.handle_click(FakeButton("left"), True)
    listener.handle_click(FakeButton("left"), False)

    assert toggles == []


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS 会真的启动 pynput 全局监听")
def test_start_is_noop_off_macos() -> None:
    listener = MacHotkeyListener()
    listener.start()
    listener.stop()
    assert listener._keyboard is None
    assert listener._mouse is None
