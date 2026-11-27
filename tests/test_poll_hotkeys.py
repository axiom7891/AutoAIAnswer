from __future__ import annotations

from ai_screenshot_assistant.input.poll_hotkeys import (
    VK_CONTROL,
    VK_LBUTTON,
    VK_MBUTTON,
    VK_MENU,
    VK_RBUTTON,
    VK_SHIFT,
    VK_Z,
    PollingHotkeys,
)


class FakeKeys:
    def __init__(self) -> None:
        self.state: dict[int, bool] = {}

    def set(self, **kwargs: bool) -> None:
        mapping = {
            "left": VK_LBUTTON,
            "right": VK_RBUTTON,
            "middle": VK_MBUTTON,
            "ctrl": VK_CONTROL,
            "shift": VK_SHIFT,
            "alt": VK_MENU,
            "z": VK_Z,
        }
        for name, pressed in kwargs.items():
            self.state[mapping[name]] = pressed

    def __call__(self, vk: int) -> bool:
        return self.state.get(vk, False)


def make_listener(keys: FakeKeys):
    fired: list[str] = []
    listener = PollingHotkeys(
        on_double_click=lambda: fired.append("double"),
        on_triple_click=lambda: fired.append("triple"),
        on_middle_long=lambda: fired.append("middle"),
        on_alt_z=lambda: fired.append("alt_z"),
        on_ctrl_tap=lambda: fired.append("ctrl_tap"),
        on_ctrl_shift_left=lambda: fired.append("shift_left"),
        on_ctrl_shift_right=lambda: fired.append("shift_right"),
        on_fix_toggle=lambda: fired.append("fix_toggle"),
        on_fix_release=lambda: fired.append("fix_release"),
        key_state=keys,
    )
    return listener, fired


def click(listener: PollingHotkeys, keys: FakeKeys, start: float, held: float = 0.05) -> float:
    keys.set(left=True)
    listener.process_tick(start)
    keys.set(left=False)
    listener.process_tick(start + held)
    return start + held


def test_double_click_fires_once() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    end = click(listener, keys, 10.0)
    end = click(listener, keys, end + 0.1)
    listener.process_tick(end + 0.5)  # 越过双击延迟

    assert fired == ["double"]


def test_triple_click_fires_triple_and_resets() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    end = click(listener, keys, 20.0)
    end = click(listener, keys, end + 0.1)
    end = click(listener, keys, end + 0.1)
    listener.process_tick(end + 0.5)

    assert fired == ["triple"]


def test_long_press_does_not_count_as_clicks() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    keys.set(left=True)
    listener.process_tick(30.0)
    listener.process_tick(30.9)  # 超过 0.6s 长按
    keys.set(left=False)
    listener.process_tick(31.0)
    click(listener, keys, 31.2)
    listener.process_tick(32.0)

    assert fired == []


def test_middle_long_press_fires_while_held() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    keys.set(middle=True)
    listener.process_tick(40.0)
    listener.process_tick(40.5)
    assert fired == []
    listener.process_tick(41.05)
    listener.process_tick(41.5)

    assert fired == ["middle"]


def test_alt_z_fires_once_per_press() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    keys.set(alt=True)
    listener.process_tick(50.0)
    keys.set(z=True)
    listener.process_tick(50.1)
    listener.process_tick(50.2)
    keys.set(z=False)
    listener.process_tick(50.3)
    keys.set(z=True)
    listener.process_tick(50.4)

    assert fired == ["alt_z", "alt_z"]


def test_z_without_alt_does_nothing() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    keys.set(z=True)
    listener.process_tick(60.0)

    assert fired == []


def test_ctrl_tap_fires_once() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    keys.set(ctrl=True)
    listener.process_tick(70.0)
    keys.set(ctrl=False)
    listener.process_tick(70.1)

    assert fired == ["ctrl_tap"]


def test_ctrl_with_other_key_is_not_a_tap() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    keys.set(ctrl=True)
    listener.process_tick(80.0)
    keys.set(left=True)
    listener.process_tick(80.05)
    keys.set(left=False)
    listener.process_tick(80.1)
    keys.set(ctrl=False)
    listener.process_tick(80.2)

    assert "ctrl_tap" not in fired


def test_ctrl_shift_click_fires_multi_actions() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    keys.set(ctrl=True, shift=True)
    listener.process_tick(90.0)
    keys.set(left=True)
    listener.process_tick(90.05)
    keys.set(left=False)
    listener.process_tick(90.1)
    keys.set(right=True)
    listener.process_tick(90.2)
    keys.set(right=False)
    listener.process_tick(90.25)

    assert fired == ["shift_left", "shift_right"]


def test_disabled_listener_does_not_fire() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)
    listener.enabled = False

    keys.set(middle=True)
    listener.process_tick(100.0)
    listener.process_tick(101.2)

    assert fired == []


def test_alt_f_and_alt_g_fire() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    keys.set(alt=True)
    listener.process_tick(110.0)
    keys.set(z=False)
    listener.process_tick(110.05)
    keys.state[0x46] = True
    listener.process_tick(110.1)
    keys.state[0x46] = False
    listener.process_tick(110.2)
    keys.state[0x47] = True
    listener.process_tick(110.3)

    assert "fix_toggle" in fired
    assert "fix_release" in fired


def test_ctrl_alt_f_no_longer_fires() -> None:
    keys = FakeKeys()
    listener, fired = make_listener(keys)

    keys.set(ctrl=True, alt=True)
    listener.process_tick(120.0)
    keys.state[0x46] = True
    listener.process_tick(120.1)

    assert "fix_toggle" not in fired
