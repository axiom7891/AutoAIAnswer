from __future__ import annotations

from ai_screenshot_assistant.input.remote_keys import RemoteAnswerKeyListener, RemoteScrollState


class FakeKey:
    def __init__(self, name: str | None = None, char: str | None = None, vk: int | None = None) -> None:
        if name is not None:
            self.name = name
        if char is not None:
            self.char = char
        if vk is not None:
            self.vk = vk


def chord(state: RemoteScrollState, key: FakeKey, now: float) -> str:
    state.press(FakeKey(name="ctrl_l"))
    state.press(FakeKey(name="alt_l"))
    return state.press(key, now=now)


def test_arrow_keys_scroll_all_four_directions() -> None:
    state = RemoteScrollState()

    assert chord(state, FakeKey(name="up"), 10.0) == "up"
    assert chord(state, FakeKey(name="down"), 11.0) == "down"
    assert chord(state, FakeKey(name="left"), 12.0) == "left"
    assert chord(state, FakeKey(name="right"), 13.0) == "right"


def test_wasd_aliases_work() -> None:
    state = RemoteScrollState()

    assert chord(state, FakeKey(char="w"), 10.0) == "up"
    assert chord(state, FakeKey(char="a"), 11.0) == "left"
    assert chord(state, FakeKey(char="s"), 12.0) == "down"
    assert chord(state, FakeKey(char="d"), 13.0) == "right"
    assert chord(state, FakeKey(char="p"), 14.0) == "toggle"


def test_requires_ctrl_and_alt() -> None:
    state = RemoteScrollState()

    assert state.press(FakeKey(name="up"), now=10.0) == ""
    state.press(FakeKey(name="ctrl_l"))
    assert state.press(FakeKey(name="up"), now=11.0) == ""
    state.press(FakeKey(name="alt_l"))
    assert state.press(FakeKey(name="up"), now=12.0) == "up"


def test_throttle_limits_repeat_rate() -> None:
    state = RemoteScrollState(throttle_seconds=0.12)

    assert chord(state, FakeKey(name="down"), 10.0) == "down"
    assert chord(state, FakeKey(name="down"), 10.05) == ""
    assert chord(state, FakeKey(name="down"), 10.20) == "down"


def test_release_clears_modifiers() -> None:
    state = RemoteScrollState()
    state.press(FakeKey(name="ctrl_l"))
    state.press(FakeKey(name="alt_l"))
    state.release(FakeKey(name="ctrl_l"))

    assert state.pressed == {"alt_l"}
    assert state.press(FakeKey(name="up"), now=10.0) == ""


def test_listener_dispatches_actions() -> None:
    scrolls: list[str] = []
    toggles: list[bool] = []
    listener = RemoteAnswerKeyListener(
        on_scroll=lambda direction: scrolls.append(direction),
        on_toggle_pan=lambda: toggles.append(True),
    )

    listener._press(FakeKey(name="ctrl_l"))
    listener._press(FakeKey(name="alt_l"))
    listener._press(FakeKey(name="down"))
    listener._press(FakeKey(char="p"))
    listener._release(FakeKey(name="down"))

    assert scrolls == ["down"]
    assert toggles == [True]
    assert "down" not in listener.state.pressed
