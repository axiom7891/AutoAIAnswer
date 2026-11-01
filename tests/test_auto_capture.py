import time

from ai_screenshot_assistant.ui.auto_capture import (
    DEFAULT_INTERVAL_SECONDS,
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    AutoCaptureScheduler,
    clamp_interval_seconds,
)


def test_interval_is_clamped_and_invalid_values_fall_back() -> None:
    assert clamp_interval_seconds(30) == 30
    assert clamp_interval_seconds("45") == 45
    assert clamp_interval_seconds(0) == MIN_INTERVAL_SECONDS
    assert clamp_interval_seconds(10**9) == MAX_INTERVAL_SECONDS
    assert clamp_interval_seconds("not-a-number") == DEFAULT_INTERVAL_SECONDS
    assert clamp_interval_seconds(None) == DEFAULT_INTERVAL_SECONDS


def test_scheduler_skips_ticks_while_busy(qapp) -> None:
    calls: list[str] = []
    busy = {"value": False}
    scheduler = AutoCaptureScheduler(
        lambda: calls.append("capture"),
        lambda: busy["value"],
    )

    scheduler._tick()
    assert calls == ["capture"]

    busy["value"] = True
    scheduler._tick()
    assert calls == ["capture"]

    busy["value"] = False
    scheduler._tick()
    assert calls == ["capture", "capture"]


def test_scheduler_start_stop_respects_minimum_interval(qapp) -> None:
    scheduler = AutoCaptureScheduler(lambda: None)

    scheduler.start(0)
    assert scheduler.running
    assert scheduler.interval_seconds == MIN_INTERVAL_SECONDS

    scheduler.stop()
    assert not scheduler.running


def test_scheduler_timer_fires_capture(qapp) -> None:
    calls: list[str] = []
    scheduler = AutoCaptureScheduler(lambda: calls.append("capture"))
    scheduler.start(1)
    try:
        deadline = time.monotonic() + 5
        while not calls and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
    finally:
        scheduler.stop()
    assert calls == ["capture"]
