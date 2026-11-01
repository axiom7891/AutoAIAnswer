from __future__ import annotations

from ai_screenshot_assistant.input.remote_keys import RemoteAnswerKeyListener, RemoteScrollState


class FakeKey:
    def __init__(self, name: str | None = None, vk: int | None = None) -> None:
        if name is not None:
            self.name = name
        if vk is not None:
            self.vk = vk


def test_plain_arrows_scroll_without_modifiers() -> None:
    state = RemoteScrollState()

    assert state.press(FakeKey(name="up"), now=10.0) == "up"
    assert state.press(FakeKey(name="down"), now=11.0) == "down"
    assert state.press(FakeKey(name="left"), now=12.0) == "left"
    assert state.press(FakeKey(name="right"), now=13.0) == "right"


def test_vk_codes_are_supported() -> None:
    state = RemoteScrollState()

    assert state.press(FakeKey(vk=38), now=10.0) == "up"
    assert state.press(FakeKey(vk=40), now=11.0) == "down"
    assert state.press(FakeKey(vk=37), now=12.0) == "left"
    assert state.press(FakeKey(vk=39), now=13.0) == "right"


def test_wasd_and_other_keys_are_ignored() -> None:
    state = RemoteScrollState()

    assert state.press(FakeKey(name="w"), now=10.0) == ""
    assert state.press(FakeKey(name="p"), now=11.0) == ""
    assert state.press(FakeKey(name="space"), now=12.0) == ""


def test_throttle_limits_repeat_rate() -> None:
    state = RemoteScrollState(throttle_seconds=0.08)

    assert state.press(FakeKey(name="down"), now=10.0) == "down"
    assert state.press(FakeKey(name="down"), now=10.03) == ""
    assert state.press(FakeKey(name="down"), now=10.20) == "down"


def test_release_clears_state() -> None:
    state = RemoteScrollState()
    state.press(FakeKey(name="up"), now=10.0)

    state.release(FakeKey(name="up"))

    assert state.pressed == set()


def test_listener_dispatches_and_can_be_disabled() -> None:
    scrolls: list[str] = []
    listener = RemoteAnswerKeyListener(on_scroll=scrolls.append)

    listener._press(FakeKey(name="down"))
    listener.set_enabled(False)
    listener._press(FakeKey(name="up"))
    listener.set_enabled(True)
    listener._press(FakeKey(name="right"))

    assert scrolls == ["down", "right"]


def test_hook_and_poll_do_not_double_fire() -> None:
    scrolls: list[str] = []
    listener = RemoteAnswerKeyListener(on_scroll=scrolls.append)

    listener._press(FakeKey(name="down"))
    listener._dispatch("down")

    assert scrolls == ["down"]


def test_poll_fallback_detects_rising_edges() -> None:
    keys = {38: False, 40: False, 37: False, 39: False}
    scrolls: list[str] = []
    listener = RemoteAnswerKeyListener(
        on_scroll=scrolls.append,
        key_state=lambda vk: keys.get(vk, False),
    )
    previous: dict[int, bool] = {}

    keys[40] = True
    listener.poll_step(previous)
    listener.poll_step(previous)
    keys[40] = False
    listener.poll_step(previous)
    keys[37] = True
    listener.poll_step(previous)

    assert scrolls == ["down", "left"]


def test_poll_ignores_keys_while_disabled() -> None:
    keys = {38: False, 40: True, 37: False, 39: False}
    scrolls: list[str] = []
    listener = RemoteAnswerKeyListener(on_scroll=scrolls.append, key_state=lambda vk: keys.get(vk, False))
    listener.set_enabled(False)

    listener.poll_step({})

    assert scrolls == []

