from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from ai_screenshot_assistant.capture import screenshot as screenshot_module
from ai_screenshot_assistant.capture.repair import RepairAction, RepairPolicy
from ai_screenshot_assistant.capture.roi import Roi
from ai_screenshot_assistant.capture.screenshot import ScreenCapture

REGION = {"left": 0, "top": 0, "width": 400, "height": 300}


def question_page(width: int = 400, height: int = 300) -> Image.Image:
    image = Image.new("RGB", (width, height), (250, 250, 248))
    draw = ImageDraw.Draw(image)
    for row in range(8):
        draw.text((20, 20 + row * 28), f"{row + 1}. question text", fill=(20, 20, 20))
    return image


def black_frame() -> Image.Image:
    return Image.new("RGB", (400, 300), (0, 0, 0))


class ScriptedGrabber:
    def __init__(self, batches: list[list[Image.Image]]) -> None:
        self.batches = [list(batch) for batch in batches]
        self.calls: list[tuple[dict, int, float]] = []

    def grab_many(self, region, count=1, interval_seconds=0.0):
        self.calls.append((dict(region), count, interval_seconds))
        if not self.batches:
            return []
        return list(self.batches.pop(0))


class RecordingSession:
    instances: list["RecordingSession"] = []
    window_image: Image.Image | None = None
    content_gap_kind: str | None = None
    hidden_window_kind: str | None = None
    report_path = None

    def __init__(self, policy) -> None:
        self.policy = policy
        self.supported = True
        self.targets = ["窗口A(0x1)"]
        self.repairs: list[str] = []
        self.closed = False
        RecordingSession.instances.append(self)

    def repair(self, diagnosis, region):
        self.repairs.append(diagnosis.repair_kind)
        return [RepairAction("窗口A(0x1)", "clear_affinity", True, "注入解除")]

    def content_gap(self, capture, region):
        kind = RecordingSession.content_gap_kind
        if not kind:
            return None
        from ai_screenshot_assistant.capture.health import CaptureDiagnosis, analyze_frame

        return CaptureDiagnosis(
            kind=kind,
            reports=(analyze_frame(capture),),
            deltas=(),
            best_index=0,
            reason="窗口内容与截图相关性 0.10",
            mixed_kind=kind,
        )

    def hidden_window(self, region):
        kind = RecordingSession.hidden_window_kind
        if not kind:
            return None
        from ai_screenshot_assistant.capture.health import CaptureDiagnosis

        return CaptureDiagnosis(
            kind=kind,
            reports=(),
            deltas=(),
            best_index=0,
            reason="窗口A(0x1) 带 捕获排除",
            mixed_kind=kind,
        )

    def printwindow(self, region):
        return RecordingSession.window_image

    def write_report(self, **kwargs):
        return RecordingSession.report_path

    def close(self):
        self.closed = True
        return []


@pytest.fixture()
def session_spy(monkeypatch):
    RecordingSession.instances = []
    RecordingSession.window_image = None
    RecordingSession.content_gap_kind = None
    RecordingSession.hidden_window_kind = None
    RecordingSession.report_path = None
    monkeypatch.setattr(screenshot_module, "RepairSession", RecordingSession)
    return RecordingSession


def test_healthy_capture_returns_first_frame_without_report(session_spy) -> None:
    grabber = ScriptedGrabber([[question_page()], [black_frame()]])
    capture = ScreenCapture(policy=RepairPolicy(sample_frames=1), grabber=grabber)

    image = capture.capture_image(REGION)

    assert image.getpixel((5, 5)) == (250, 250, 248)
    assert capture.take_report() == ""
    assert capture.last_outcome is not None
    assert capture.last_outcome.attempts == 1
    assert session_spy.instances[0].repairs == []
    assert session_spy.instances[0].closed is True
    assert len(grabber.calls) == 1
    assert grabber.calls[0][1] == 1


def test_black_first_frame_triggers_patch_and_retry(session_spy) -> None:
    grabber = ScriptedGrabber([[black_frame()], [question_page()]])
    capture = ScreenCapture(policy=RepairPolicy(max_attempts=3, sample_frames=1), grabber=grabber)

    image = capture.capture_image(REGION)

    assert image.getpixel((5, 5)) == (250, 250, 248)
    assert capture.last_outcome is not None
    assert capture.last_outcome.attempts == 2
    assert session_spy.instances[0].repairs == ["black"]
    assert session_spy.instances[0].closed is True
    report = capture.take_report()
    assert "截图异常" in report
    assert "解除捕获排除" in report
    assert "重拍 1 次" in report
    assert capture.take_report() == ""


def test_all_attempts_broken_return_best_frame(monkeypatch, session_spy) -> None:
    monkeypatch.setattr(screenshot_module.time, "sleep", lambda *_: None)
    grabber = ScriptedGrabber([[black_frame()], [black_frame()], [black_frame()]])
    capture = ScreenCapture(policy=RepairPolicy(max_attempts=3, sample_frames=1), grabber=grabber)

    image = capture.capture_image(REGION)

    assert image.getpixel((5, 5)) == (0, 0, 0)
    assert len(grabber.calls) == 3
    assert capture.last_outcome is not None
    assert capture.last_outcome.ok is False
    assert "仍未完全恢复" in capture.last_outcome.summary()


def test_disabled_policy_grabs_single_frame(monkeypatch) -> None:
    monkeypatch.setattr(screenshot_module, "RepairSession", pytest.fail)
    grabber = ScriptedGrabber([[black_frame()]])
    capture = ScreenCapture(policy=RepairPolicy(enabled=False, sample_frames=3), grabber=grabber)

    image = capture.capture_image(REGION)

    assert image.getpixel((5, 5)) == (0, 0, 0)
    assert len(grabber.calls) == 1
    assert grabber.calls[0][1] == 1
    assert capture.take_report() == ""


def test_printwindow_fallback_wins_when_healthier(session_spy) -> None:
    session_spy.window_image = question_page()
    grabber = ScriptedGrabber([[black_frame()], [black_frame()]])
    capture = ScreenCapture(policy=RepairPolicy(max_attempts=2, sample_frames=1), grabber=grabber)

    image = capture.capture_image(REGION)

    assert image.getpixel((5, 5)) == (250, 250, 248)
    assert capture.last_outcome is not None
    assert capture.last_outcome.source == "printwindow"
    assert capture.last_outcome.ok
    assert "PrintWindow" in capture.take_report()


def test_hidden_window_state_triggers_repair_without_pixel_evidence(session_spy) -> None:
    session_spy.hidden_window_kind = "content_lost"
    grabber = ScriptedGrabber([[question_page()], [question_page()]])
    capture = ScreenCapture(policy=RepairPolicy(max_attempts=2, sample_frames=1), grabber=grabber)

    capture.capture_image(REGION)

    assert len(grabber.calls) == 2
    assert session_spy.instances[0].repairs == ["content_lost"]
    assert "内容缺失" in capture.take_report()


def test_diagnostics_path_appended_to_report(session_spy, tmp_path) -> None:
    report = tmp_path / "capture-diagnose.txt"
    session_spy.hidden_window_kind = "content_lost"
    session_spy.report_path = report
    grabber = ScriptedGrabber([[question_page()], [question_page()]])
    capture = ScreenCapture(policy=RepairPolicy(max_attempts=2, sample_frames=1), grabber=grabber)

    capture.capture_image(REGION)

    assert capture.last_diagnostics_path == report
    assert str(report) in capture.take_report()


def test_diagnostics_not_written_when_capture_is_healthy(session_spy, tmp_path) -> None:
    session_spy.report_path = tmp_path / "capture-diagnose.txt"
    grabber = ScriptedGrabber([[question_page()]])
    capture = ScreenCapture(policy=RepairPolicy(sample_frames=1), grabber=grabber)

    capture.capture_image(REGION)

    assert capture.last_diagnostics_path is None
    assert capture.take_report() == ""


def test_dump_diagnostics_returns_report_path(session_spy, tmp_path) -> None:
    report = tmp_path / "manual-diagnose.txt"
    session_spy.report_path = report
    capture = ScreenCapture(policy=RepairPolicy(), grabber=ScriptedGrabber([[question_page()]]))

    path = capture.dump_diagnostics(REGION)

    assert path == report


def test_content_gap_triggers_repair_even_when_frame_looks_normal(session_spy) -> None:
    session_spy.content_gap_kind = "content_lost"
    grabber = ScriptedGrabber([[question_page()], [question_page()]])
    capture = ScreenCapture(policy=RepairPolicy(max_attempts=2, sample_frames=1), grabber=grabber)

    capture.capture_image(REGION)

    assert len(grabber.calls) == 2
    assert session_spy.instances[0].repairs == ["content_lost"]
    assert capture.last_outcome is not None
    assert capture.last_outcome.attempts == 2
    assert "内容缺失" in capture.take_report()


def test_content_gap_ignored_when_policy_disabled(session_spy) -> None:
    session_spy.content_gap_kind = "content_lost"
    grabber = ScriptedGrabber([[question_page()]])
    capture = ScreenCapture(policy=RepairPolicy(enabled=False), grabber=grabber)

    capture.capture_image(REGION)

    assert len(grabber.calls) == 1
    assert capture.take_report() == ""


def test_flicker_retry_samples_one_extra_frame(session_spy) -> None:
    grabber = ScriptedGrabber(
        [
            [black_frame(), question_page()],
            [question_page(), question_page(), question_page()],
        ]
    )
    capture = ScreenCapture(policy=RepairPolicy(max_attempts=2, sample_frames=2), grabber=grabber)

    capture.capture_image(REGION)

    assert grabber.calls[0][1] == 2
    assert grabber.calls[1][1] == 3


def test_sample_frames_and_interval_are_forwarded(session_spy) -> None:
    grabber = ScriptedGrabber([[question_page(), question_page()]])
    capture = ScreenCapture(
        policy=RepairPolicy(sample_frames=2, sample_interval_ms=30), grabber=grabber
    )

    capture.capture_image(REGION)

    assert grabber.calls[0][1] == 2
    assert grabber.calls[0][2] == pytest.approx(0.03)


def test_capture_png_encodes_and_writes_debug_image(tmp_path: Path, session_spy) -> None:
    grabber = ScriptedGrabber([[question_page()]])
    capture = ScreenCapture(policy=RepairPolicy(sample_frames=1), grabber=grabber)
    debug_path = tmp_path / "debug" / "image.png"

    png = capture.capture_png(Roi(left=0, top=0, width=40, height=30), debug_path=debug_path)

    assert png.startswith(b"\x89PNG")
    assert debug_path.exists()
    with Image.open(io.BytesIO(png)) as image:
        assert image.size == (400, 300)


def test_empty_grabber_result_raises(session_spy) -> None:
    capture = ScreenCapture(policy=RepairPolicy(sample_frames=1), grabber=ScriptedGrabber([[]]))

    with pytest.raises(RuntimeError):
        capture.capture_image(REGION)


def test_diagnostics_payload_describes_last_capture(session_spy) -> None:
    grabber = ScriptedGrabber(
        [[black_frame(), question_page()], [question_page(), question_page()]]
    )
    capture = ScreenCapture(policy=RepairPolicy(max_attempts=2, sample_frames=2), grabber=grabber)
    capture.capture_image(REGION)

    payload = capture.diagnostics()

    assert payload["kind"] == "flicker"
    assert payload["final_kind"] == "ok"
    assert payload["ok"] is True
    assert payload["attempts"] == 2
    assert payload["repairs"][0]["patch"] == "clear_affinity"


def test_set_repair_enabled_toggles_policy() -> None:
    capture = ScreenCapture(policy=RepairPolicy(enabled=True), grabber=ScriptedGrabber([]))

    assert capture.repair_enabled is True
    capture.set_repair_enabled(False)
    assert capture.repair_enabled is False
    capture.set_policy(RepairPolicy(enabled=True))
    assert capture.repair_enabled is True
