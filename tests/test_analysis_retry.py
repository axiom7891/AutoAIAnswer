from __future__ import annotations

import threading
from types import SimpleNamespace

from ai_screenshot_assistant.ui.main_window import MainWindow


class FakeTimer:
    def __init__(self) -> None:
        self.milliseconds = 0
        self.active = False

    def start(self, milliseconds: int) -> None:
        self.milliseconds = milliseconds
        self.active = True

    def stop(self) -> None:
        self.active = False


def test_analysis_watchdog_starts_and_stops_with_activity() -> None:
    timer = FakeTimer()
    window = SimpleNamespace(
        retry_enabled=True,
        retry_timeout_seconds=45,
        retry_max_attempts=1,
        _analysis_in_flight=0,
        _analysis_retries_used=0,
        retry_timer=timer,
    )

    MainWindow._on_analysis_started(window)
    assert window._analysis_in_flight == 1
    assert timer.active is True
    assert timer.milliseconds == 45000

    MainWindow._on_analysis_finished(window)
    assert window._analysis_in_flight == 0
    assert timer.active is False


def test_analysis_watchdog_retries_then_stops_at_limit() -> None:
    timer = FakeTimer()
    retried = threading.Event()
    statuses: list[str] = []
    window = SimpleNamespace(
        retry_enabled=True,
        retry_timeout_seconds=30,
        retry_max_attempts=1,
        _analysis_in_flight=1,
        _analysis_retries_used=0,
        retry_timer=timer,
        set_status=lambda message: statuses.append(message),
        _log=lambda message: None,
        _run_retry_analysis=retried.set,
    )

    MainWindow._on_retry_timeout(window)
    assert retried.wait(1) is True
    assert window._analysis_retries_used == 1
    assert timer.active is True
    assert "自动重试" in statuses[0]

    MainWindow._on_retry_timeout(window)
    assert window._analysis_retries_used == 1
    assert timer.active is False
