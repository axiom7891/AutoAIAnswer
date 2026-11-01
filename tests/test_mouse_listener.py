from ai_screenshot_assistant.input.mouse_listener import MouseRoiListener


def test_ctrl_shift_probe_is_safe_off_windows(monkeypatch) -> None:
    """macOS 分支不能因为函数内的 import ctypes 而抛 UnboundLocalError。"""

    listener = MouseRoiListener(lambda x, y: None, lambda x, y: None)
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.sys.platform", "darwin")
    monkeypatch.setattr(
        "ai_screenshot_assistant.input.mouse_listener.ctypes.util.find_library",
        lambda name: None,
    )

    assert listener._is_ctrl_shift_held() is False

    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.sys.platform", "linux")
    assert listener._is_ctrl_shift_held() is False


def test_long_press_threshold_is_two_seconds(monkeypatch) -> None:
    long_clicks = []
    short_clicks = []
    listener = MouseRoiListener(lambda x, y: long_clicks.append((x, y)), lambda x, y: short_clicks.append((x, y)))
    listener._left_down_at = 10.0
    listener._left_down_position = (3, 4)
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.time.monotonic", lambda: 12.0)

    listener._handle_left_up()

    assert listener.long_press_seconds == 2.0
    assert long_clicks == [(3, 4)]
    assert short_clicks == []


def test_disabled_listener_ignores_and_clears_pending_click() -> None:
    clicks = []
    listener = MouseRoiListener(lambda x, y: clicks.append((x, y)), lambda x, y: clicks.append((x, y)))
    listener._left_down_at = 10.0
    listener._left_down_position = (3, 4)

    listener.set_enabled(False)
    listener._handle_left_up()

    assert listener.enabled is False
    assert listener._left_down_at is None
    assert listener._left_down_position is None
    assert clicks == []


def test_explicit_position_supports_macos_callback(monkeypatch) -> None:
    clicks = []
    listener = MouseRoiListener(lambda x, y: clicks.append((x, y)), lambda x, y: clicks.append((x, y)))
    times = iter((10.0, 12.1))
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.time.monotonic", lambda: next(times))

    listener._handle_left_down((120, 240))
    listener._handle_left_up()

    assert clicks == [(120, 240)]


def test_long_left_then_short_left_emits_two_points(monkeypatch) -> None:
    long_left = []
    short_left = []
    listener = MouseRoiListener(
        lambda x, y: long_left.append((x, y)),
        lambda x, y: short_left.append((x, y)),
    )
    times = iter((10.0, 12.1, 13.0, 13.2))
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.time.monotonic", lambda: next(times))

    listener._handle_left_down((100, 200))
    listener._handle_left_up()
    listener._handle_left_down((300, 500))
    listener._handle_left_up()

    assert long_left == [(100, 200)]
    assert short_left == [(300, 500)]


def test_right_long_press_fires_fullscreen_callback(monkeypatch) -> None:
    long_right = []
    listener = MouseRoiListener(
        lambda x, y: None,
        lambda x, y: None,
        lambda x, y: long_right.append((x, y)),
    )
    times = iter((10.0, 12.1))
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.time.monotonic", lambda: next(times))

    listener._handle_right_down((8, 9))
    listener._handle_right_up()

    assert long_right == [(8, 9)]


def test_short_right_click_is_ignored(monkeypatch) -> None:
    long_right = []
    short_left = []
    listener = MouseRoiListener(
        lambda x, y: None,
        lambda x, y: short_left.append((x, y)),
        lambda x, y: long_right.append((x, y)),
    )
    times = iter((10.0, 10.4))
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.time.monotonic", lambda: next(times))

    listener._handle_right_down((8, 9))
    listener._handle_right_up()

    assert long_right == []
    assert short_left == []


def test_disabled_listener_clears_pending_right_click() -> None:
    clicks = []
    listener = MouseRoiListener(lambda x, y: None, lambda x, y: None, lambda x, y: clicks.append((x, y)))
    listener._right_down_at = 10.0
    listener._right_down_position = (8, 9)

    listener.set_enabled(False)
    listener._handle_right_up()

    assert listener._right_down_at is None
    assert listener._right_down_position is None
    assert clicks == []


def test_stop_without_start_is_safe_on_macos(monkeypatch) -> None:
    listener = MouseRoiListener(lambda x, y: None, lambda x, y: None)
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.sys.platform", "darwin")
    listener.stop()


def test_ctrl_shift_left_click_uses_multi_capture_shortcut(monkeypatch) -> None:
    long_clicks = []
    short_clicks = []
    shortcuts = []
    listener = MouseRoiListener(
        lambda x, y: long_clicks.append((x, y)),
        lambda x, y: short_clicks.append((x, y)),
        on_ctrl_shift_left=lambda: shortcuts.append("capture"),
    )
    monkeypatch.setattr(listener, "_is_ctrl_shift_held", lambda: True)

    listener._handle_left_down((10, 20))
    listener._handle_left_up()

    assert shortcuts == ["capture"]
    assert long_clicks == []
    assert short_clicks == []


def test_ctrl_shift_right_click_uses_analyze_shortcut(monkeypatch) -> None:
    long_right = []
    shortcuts = []
    listener = MouseRoiListener(
        lambda x, y: None,
        lambda x, y: None,
        lambda x, y: long_right.append((x, y)),
        on_ctrl_shift_right=lambda: shortcuts.append("analyze"),
    )
    monkeypatch.setattr(listener, "_is_ctrl_shift_held", lambda: True)

    listener._handle_right_down((10, 20))
    listener._handle_right_up()

    assert shortcuts == ["analyze"]
    assert long_right == []


def test_disabled_shortcuts_do_not_intercept_normal_clicks(monkeypatch) -> None:
    short_clicks = []
    shortcuts = []
    listener = MouseRoiListener(
        lambda x, y: None,
        lambda x, y: short_clicks.append((x, y)),
        on_ctrl_shift_left=lambda: shortcuts.append("capture"),
    )
    monkeypatch.setattr(listener, "_is_ctrl_shift_held", lambda: True)
    listener.set_shortcuts_enabled(False)

    listener._handle_left_down((10, 20))
    listener._handle_left_up()

    assert shortcuts == []
    assert short_clicks == [(10, 20)]


def test_control_left_long_press_triggers_fullscreen(monkeypatch) -> None:
    long_left = []
    long_right = []
    listener = MouseRoiListener(
        lambda x, y: long_left.append((x, y)),
        lambda x, y: None,
        lambda x, y: long_right.append((x, y)),
    )
    monkeypatch.setattr(listener, "_is_control_held", lambda: True)
    times = iter((10.0, 12.1))
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.time.monotonic", lambda: next(times))

    listener._handle_left_down((1, 2))
    listener._handle_left_up()

    assert long_right == [(1, 2)]
    assert long_left == []


def test_middle_long_press_toggles_auto_capture(monkeypatch) -> None:
    toggles = []
    listener = MouseRoiListener(
        lambda x, y: None,
        lambda x, y: None,
        on_middle_long=lambda: toggles.append(True),
    )
    times = iter((10.0, 11.2))
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.time.monotonic", lambda: next(times))

    listener._handle_middle_down()
    listener._handle_middle_up()

    assert listener.middle_long_press_seconds == 1.0
    assert toggles == [True]


def test_short_middle_click_is_ignored(monkeypatch) -> None:
    toggles = []
    listener = MouseRoiListener(
        lambda x, y: None,
        lambda x, y: None,
        on_middle_long=lambda: toggles.append(True),
    )
    times = iter((10.0, 10.4))
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.time.monotonic", lambda: next(times))

    listener._handle_middle_down()
    listener._handle_middle_up()

    assert toggles == []


def test_disabled_listener_clears_pending_middle_press(monkeypatch) -> None:
    toggles = []
    listener = MouseRoiListener(
        lambda x, y: None,
        lambda x, y: None,
        on_middle_long=lambda: toggles.append(True),
    )
    listener._middle_down_at = 10.0
    monkeypatch.setattr("ai_screenshot_assistant.input.mouse_listener.time.monotonic", lambda: 12.0)

    listener.set_enabled(False)
    listener._handle_middle_up()

    assert listener._middle_down_at is None
    assert toggles == []

