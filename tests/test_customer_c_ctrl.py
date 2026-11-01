from types import SimpleNamespace

import pytest

from ai_screenshot_assistant.input.ctrl_listener import CtrlTapState, CtrlScreenshotListener
from ai_screenshot_assistant.ui.main_window import MainWindow, UiSignals


@pytest.mark.parametrize("ctrl", ["ctrl_l", "ctrl_r"])
def test_single_ctrl_release_fires_once(ctrl):
    state = CtrlTapState()
    state.press(ctrl)
    for _ in range(30):
        state.press(ctrl)
    assert state.release(ctrl)
    assert not state.release(ctrl)


@pytest.mark.parametrize("other", ["c", "v", "a", "s", "shift", "alt", "cmd", "mouse:left", "ctrl_r"])
@pytest.mark.parametrize("release_ctrl_first", [True, False])
def test_chord_never_triggers(other, release_ctrl_first):
    state = CtrlTapState()
    state.press("ctrl_l")
    state.press(other)
    releases = ["ctrl_l", other] if release_ctrl_first else [other, "ctrl_l"]
    assert not any(state.release(key) for key in releases)
    state.press("ctrl_l")
    assert state.release("ctrl_l")


def test_other_key_held_before_ctrl_and_listener_start():
    state = CtrlTapState()
    state.press("ctrl_l", other_keys_down=True)
    assert not state.release("ctrl_l")
    state.press("shift")
    state.press("ctrl_l")
    assert not state.release("shift")
    assert not state.release("ctrl_l")


def test_toggle_during_hold_does_not_trigger_on_release():
    state = CtrlTapState()
    state.press("ctrl_l")
    state.set_enabled(False)
    state.set_enabled(True)
    assert not state.release("ctrl_l")
    state.press("ctrl_l")
    assert state.release("ctrl_l")
    state.set_enabled(False)
    state.press("ctrl_l")
    assert not state.release("ctrl_l")


def test_fast_repeated_taps_are_not_debounced():
    state = CtrlTapState()
    for _ in range(10):
        state.press("ctrl_r")
        assert state.release("ctrl_r")


def test_release_without_press_does_not_capture():
    assert not CtrlTapState().release("ctrl_l")


def test_listener_adapter_dispatches_only_single_ctrl(monkeypatch):
    taps = []
    listener = CtrlScreenshotListener(lambda: taps.append(True))
    monkeypatch.setattr(listener, "_other_keys_down", lambda _: False)
    ctrl = SimpleNamespace(name="ctrl_l")
    listener._on_press(ctrl)
    listener._on_release(ctrl)
    assert taps == [True]
    listener._on_press(ctrl)
    listener._on_click(0, 0, "left", True)
    listener._on_click(0, 0, "left", False)
    listener._on_release(ctrl)
    assert taps == [True]
    listener.stop()
    listener._on_press(ctrl)
    listener._on_release(ctrl)
    assert taps == [True]


def test_key_identity_does_not_depend_on_character_case():
    assert CtrlScreenshotListener._key_id(SimpleNamespace(vk=67, char="c")) == \
        CtrlScreenshotListener._key_id(SimpleNamespace(vk=67, char="C"))


def test_listener_start_stop_and_failure_cleanup(monkeypatch):
    import sys

    created = []

    class FakeListener:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.stopped = False
            created.append(self)

        def start(self):
            pass

        def wait(self):
            pass

        def stop(self):
            self.stopped = True

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "pynput", SimpleNamespace(
        keyboard=SimpleNamespace(Listener=FakeListener), mouse=SimpleNamespace(Listener=FakeListener)))
    listener = CtrlScreenshotListener(lambda: None)
    listener.start()
    listener.start()
    assert len(created) == 2
    assert all(item.kwargs["suppress"] is False for item in created)
    listener.stop()
    assert all(item.stopped for item in created)
    assert listener._keyboard is None and listener._mouse is None

    def fail_start(self):
        raise RuntimeError("hook failed")

    monkeypatch.setattr(FakeListener, "start", fail_start)
    with pytest.raises(RuntimeError, match="hook failed"):
        listener.start()
    assert all(item.stopped for item in created)


def test_listener_ignores_other_held_keys_before_start(monkeypatch):
    taps = []
    listener = CtrlScreenshotListener(lambda: taps.append(True))
    monkeypatch.setattr(listener, "_other_keys_down", lambda _: True)
    ctrl = SimpleNamespace(name="ctrl_r")
    listener._on_press(ctrl)
    listener._on_release(ctrl)
    assert taps == []


def test_ctrl_alt_o_toggles_overlay_once(monkeypatch):
    toggles = []
    listener = CtrlScreenshotListener(lambda: None, on_overlay_toggle=lambda: toggles.append(True))
    monkeypatch.setattr(CtrlScreenshotListener, "_ctrl_alt_down", classmethod(lambda cls: True))
    key_o = SimpleNamespace(vk=0x4F, char="o")

    listener._on_press(key_o)
    listener._on_press(key_o)  # 按住不放的自动重复不应重复触发
    listener._on_release(key_o)
    listener._on_press(key_o)

    assert toggles == [True, True]


def test_ctrl_alt_o_does_not_trigger_fullscreen_tap(monkeypatch):
    taps = []
    listener = CtrlScreenshotListener(lambda: taps.append(True))
    monkeypatch.setattr(CtrlScreenshotListener, "_ctrl_alt_down", classmethod(lambda cls: True))
    monkeypatch.setattr(listener, "_other_keys_down", lambda _: False)

    ctrl = SimpleNamespace(name="ctrl_l")
    alt = SimpleNamespace(vk=0x12, char=None)
    key_o = SimpleNamespace(vk=0x4F, char="o")
    for key in (ctrl, alt, key_o):
        listener._on_press(key)
    for key in (key_o, alt, ctrl):
        listener._on_release(key)

    assert taps == []


def test_plain_ctrl_tap_still_works_after_overlay_hotkey(monkeypatch):
    taps = []
    toggles = []
    listener = CtrlScreenshotListener(lambda: taps.append(True), on_overlay_toggle=lambda: toggles.append(True))
    monkeypatch.setattr(CtrlScreenshotListener, "_ctrl_alt_down", classmethod(lambda cls: True))
    monkeypatch.setattr(listener, "_other_keys_down", lambda _: False)
    key_o = SimpleNamespace(vk=0x4F, char="o")
    listener._on_press(key_o)
    listener._on_release(key_o)
    listener.set_enabled(True)

    ctrl = SimpleNamespace(name="ctrl_l")
    listener._on_press(ctrl)
    listener._on_release(ctrl)

    assert toggles == [True]
    assert taps == [True]


def test_ctrl_slot_reuses_existing_direct_capture(qapp):
    captures = []
    window = SimpleNamespace(ctrl_capture_enabled=True, workflow=object(),
                             _capture_current_screen=lambda: captures.append("direct"))
    signals = UiSignals()
    signals.ctrl_fullscreen_requested.connect(lambda: MainWindow._capture_from_ctrl(window))
    signals.ctrl_fullscreen_requested.emit()
    signals.ctrl_fullscreen_requested.emit()
    assert captures == ["direct", "direct"]
    window.ctrl_capture_enabled = False
    signals.ctrl_fullscreen_requested.emit()
    assert len(captures) == 2
    window.ctrl_capture_enabled = True
    window.workflow = None
    signals.ctrl_fullscreen_requested.emit()
    assert len(captures) == 2
