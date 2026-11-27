from __future__ import annotations

import threading
from types import SimpleNamespace

from ai_screenshot_assistant.ui.main_window import MainWindow


class Button:
    def __init__(self) -> None:
        self.text = ""
        self.enabled = True

    def setText(self, text: str) -> None:  # noqa: N802
        self.text = text

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self.enabled = enabled


def make_stub(**overrides):
    logs: list[str] = []
    errors: list[str] = []
    restores: list[object] = []
    stub = SimpleNamespace(
        multi_hotkeys_enabled=True,
        _last_multi_capture_at=0.0,
        _last_analyze_cache_at=0.0,
        _multi_capture_busy=False,
        _pending_lock=threading.Lock(),
        pending_screenshots=[],
        pending_screenshot_labels=[],
        analyze_pending_button=Button(),
        clear_pending_button=Button(),
        _update_pending_buttons=lambda: None,
        _log=lambda message: logs.append(message),
        signals=SimpleNamespace(
            error=SimpleNamespace(emit=lambda message: errors.append(message)),
            pending_restore=SimpleNamespace(emit=lambda payload: restores.append(payload)),
        ),
        workflow=None,
        mouse_listener=None,
        _reset_analysis_retry=lambda: None,
    )
    for key, value in overrides.items():
        setattr(stub, key, value)
    return stub, logs, errors, restores


def test_duplicate_shortcut_is_ignored() -> None:
    calls: list[int] = []
    stub, _, _, _ = make_stub(_capture_multi_screenshot=lambda: calls.append(1))

    MainWindow._on_multi_capture_shortcut(stub)
    MainWindow._on_multi_capture_shortcut(stub)

    assert len(calls) == 1


def test_shortcut_does_nothing_when_disabled() -> None:
    calls: list[int] = []
    stub, _, _, _ = make_stub(
        multi_hotkeys_enabled=False,
        _capture_multi_screenshot=lambda: calls.append(1),
    )

    MainWindow._on_multi_capture_shortcut(stub)

    assert calls == []


def test_busy_capture_does_not_spawn_thread() -> None:
    spawned: list[object] = []
    stub, _, _, _ = make_stub(
        workflow=SimpleNamespace(),
        _multi_capture_busy=True,
        _multi_capture_point=lambda: (10, 10),
    )
    original = threading.Thread

    class FakeThread:
        def __init__(self, *args, **kwargs):
            spawned.append(args)

        def start(self):
            spawned.append("started")

    threading.Thread = FakeThread  # type: ignore[misc]
    try:
        MainWindow._capture_multi_screenshot(stub)
    finally:
        threading.Thread = original  # type: ignore[misc]

    assert spawned == []
    assert stub._multi_capture_busy is True


def test_cache_keeps_five_and_logs_replacement() -> None:
    stub, logs, _, _ = make_stub()

    for index in range(6):
        MainWindow._on_pending_capture_ready(stub, f"png-{index}".encode(), f"t{index}")

    assert len(stub.pending_screenshots) == 5
    assert stub.pending_screenshots[0] == b"png-1"
    assert any("替换" in message for message in logs)


def test_analysis_failure_requests_restore() -> None:
    class FailingWorkflow:
        def process_mobile_images(self, *args, **kwargs):
            raise RuntimeError("model down")

    stub, _, errors, restores = make_stub(workflow=FailingWorkflow())

    MainWindow._run_pending_analysis(stub, [b"a", b"b"], ["t1", "t2"], None)

    assert errors and "model down" in errors[0]
    assert restores and restores[0][0] == [b"a", b"b"]


def test_restore_puts_images_back() -> None:
    stub, logs, _, _ = make_stub()

    MainWindow._on_pending_restore(stub, ([b"a", b"b"], ["t1", "t2"]))

    assert stub.pending_screenshots == [b"a", b"b"]
    assert any("放回缓存" in message for message in logs)


def test_empty_cache_logs_hint() -> None:
    stub, logs, _, _ = make_stub(workflow=SimpleNamespace())

    MainWindow._analyze_pending_screenshots(stub)

    assert any("空的" in message for message in logs)
