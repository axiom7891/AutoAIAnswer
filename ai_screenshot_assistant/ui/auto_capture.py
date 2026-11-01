from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer

DEFAULT_INTERVAL_SECONDS = 30
MIN_INTERVAL_SECONDS = 1
MAX_INTERVAL_SECONDS = 3600


def clamp_interval_seconds(value: object) -> int:
    try:
        seconds = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SECONDS
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, seconds))


class AutoCaptureScheduler(QObject):
    """Fires a fullscreen capture on a fixed interval, skipping while one runs."""

    def __init__(
        self,
        on_capture: Callable[[], None],
        is_busy: Callable[[], bool] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_capture = on_capture
        self._is_busy = is_busy or (lambda: False)
        self._interval_seconds = DEFAULT_INTERVAL_SECONDS
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._tick)

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    @property
    def interval_seconds(self) -> int:
        return self._interval_seconds

    def start(self, interval_seconds: int) -> None:
        self._interval_seconds = clamp_interval_seconds(interval_seconds)
        self._timer.start(self._interval_seconds * 1000)

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        if self._is_busy():
            return
        self._on_capture()
