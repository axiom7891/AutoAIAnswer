from __future__ import annotations

from ai_screenshot_assistant.capture.blackout import BlackoutSession


class FakeNative:
    supported = True

    def __init__(self) -> None:
        self.applied: list[str] = []
        self.restored = 0

    def describe_windows(self, region, max_windows=8):
        return ["0x1234 exam.exe 全屏"]

    def apply(self, kind, region, max_windows=3):
        self.applied.append(kind)
        return [("0x1234 exam.exe", "clear_affinity", True, "已解除")], ""

    def restore(self):
        self.restored += 1
        return [("0x1234 exam.exe", "clear_affinity", True, "已还原")]


def session_with(native) -> BlackoutSession:
    session = BlackoutSession()
    session._native = native
    return session


def test_engage_and_release_roundtrip() -> None:
    native = FakeNative()
    session = session_with(native)
    region = {"left": 0, "top": 0, "width": 100, "height": 100}

    ok, lines = session.engage(region)

    assert ok is True
    assert session.active is True
    assert native.applied == ["content_lost"]
    assert any("clear_affinity" in line for line in lines)

    restored = session.release()

    assert session.active is False
    assert native.restored == 1
    assert restored


def test_unsupported_session_does_nothing() -> None:
    class Unsupported:
        supported = False

    session = session_with(Unsupported())
    region = {"left": 0, "top": 0, "width": 10, "height": 10}

    ok, lines = session.engage(region)
    assert ok is False
    assert session.release() == []


def test_no_changes_returns_false() -> None:
    class Noop:
        supported = True

        def describe_windows(self, region, max_windows=8):
            return []

        def apply(self, kind, region, max_windows=3):
            return [], "没有找到覆盖该区域的窗口"

        def restore(self):
            return []

    session = session_with(Noop())
    ok, lines = session.engage({"left": 0, "top": 0, "width": 10, "height": 10})

    assert ok is False
    assert lines

class _Record:
    def __init__(self, hidden: bool) -> None:
        self.hidden = hidden

    def hiding_flags(self):
        return ["affinity"] if self.hidden else []
