from __future__ import annotations

from ai_screenshot_assistant.ui.capture_guard import CaptureExclusionGuard


class FakeWin:
    def __init__(self) -> None:
        self.excluded = {"console": True, "overlay": True}
        self.apply_calls: list[str] = []
        self.apply_ok = True

    def targets(self):
        return [("控制台", 1), ("悬浮字幕", 2)]

    def read(self, hwnd: int) -> bool:
        return self.excluded["console" if hwnd == 1 else "overlay"]

    def apply(self, hwnd: int) -> tuple[bool, str]:
        name = "console" if hwnd == 1 else "overlay"
        self.apply_calls.append(name)
        if self.apply_ok:
            self.excluded[name] = True
        return self.apply_ok, "ok" if self.apply_ok else "被接管"


def make_guard(fake: FakeWin):
    statuses: list[str] = []
    hijacks: list[str] = []
    guard = CaptureExclusionGuard(
        fake.targets, apply=fake.apply, read=fake.read, interval_ms=10_000
    )
    guard.status.connect(statuses.append)
    guard.hijacked.connect(hijacks.append)
    return guard, statuses, hijacks


def test_all_excluded_does_nothing() -> None:
    fake = FakeWin()
    guard, statuses, _ = make_guard(fake)

    assert guard.check_once() is True
    assert fake.apply_calls == []
    assert statuses == []


def test_external_clear_is_repaired_and_reported() -> None:
    fake = FakeWin()
    guard, statuses, _ = make_guard(fake)
    fake.excluded["overlay"] = False

    assert guard.check_once() is True
    assert fake.apply_calls == ["overlay"]
    assert guard.reassert_count == 1
    assert statuses and "悬浮字幕" in statuses[0]


def test_persistent_failure_reports_hijack_once() -> None:
    fake = FakeWin()
    fake.apply_ok = False
    guard, _, hijacks = make_guard(fake)
    fake.excluded["console"] = False

    guard.check_once()
    assert hijacks == []
    guard.check_once()
    guard.check_once()

    assert len(hijacks) == 1
    assert "接管" in hijacks[0]


def test_reassert_now_fixes_cleared_window() -> None:
    fake = FakeWin()
    guard, statuses, _ = make_guard(fake)
    fake.excluded["console"] = False

    guard.reassert_now()

    assert fake.excluded["console"] is True
    assert guard.reassert_count == 1


def test_empty_targets_is_safe() -> None:
    guard = CaptureExclusionGuard(lambda: [], apply=lambda hwnd: (True, ""), read=lambda hwnd: True)

    assert guard.check_once() is True
