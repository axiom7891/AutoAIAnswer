from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from ai_screenshot_assistant.capture import repair as repair_module
from ai_screenshot_assistant.capture.health import ANOMALY_FLICKER, evaluate_frames
from ai_screenshot_assistant.capture.repair import (
    CaptureOutcome,
    RepairAction,
    RepairPolicy,
    RepairSession,
)


def question_page(width: int = 400, height: int = 300) -> Image.Image:
    image = Image.new("RGB", (width, height), (250, 250, 248))
    draw = ImageDraw.Draw(image)
    for row in range(8):
        draw.text((20, 20 + row * 28), f"{row + 1}. question text", fill=(20, 20, 20))
    return image


class FakeNative:
    window_content: Image.Image | None = None
    hiding_record = None

    def __init__(self, inject_remote: bool = True) -> None:
        self.inject_remote = inject_remote
        self.supported = True
        self.applied: list[tuple[str, str, bool, str]] = []
        self.restored = False

    def apply(self, kind, region, max_windows=3):
        self.applied.append((kind, region.get("left", 0), True, "fake"))
        return [("窗口A(0x1)", "clear_affinity", True, "注入解除")], ""

    def restore(self):
        self.restored = True
        return [("0x1", "clear_affinity", True, "已恢复捕获排除")]

    def describe_targets(self):
        return ["窗口A(0x1) Chrome_WidgetWin_1 pid=100 捕获排除"]

    def printwindow_png(self, region):
        import io

        buffer = io.BytesIO()
        question_page().save(buffer, format="PNG")
        return buffer.getvalue()

    def content_image(self, region, min_overlap_ratio=0.6):
        return FakeNative.window_content

    def first_hiding_window(self, region, min_overlap_ratio=0.6):
        return FakeNative.hiding_record


@pytest.fixture()
def fake_session(monkeypatch):
    monkeypatch.setattr(repair_module.sys, "platform", "win32")
    monkeypatch.setattr(
        "ai_screenshot_assistant.capture.win32_window_repair.WindowRepair", FakeNative
    )
    return RepairSession(RepairPolicy(enabled=True, sample_frames=1))


def test_policy_defaults_are_bounded() -> None:
    policy = RepairPolicy.from_settings()

    assert 1 <= policy.max_attempts <= 5
    assert 1 <= policy.sample_frames <= 4
    assert policy.max_windows >= 1
    assert policy.restore_after_seconds > 0


def test_policy_with_enabled_keeps_other_fields() -> None:
    policy = RepairPolicy(enabled=True, max_attempts=4, sample_frames=3)
    disabled = policy.with_enabled(False)

    assert disabled.enabled is False
    assert disabled.max_attempts == 4
    assert disabled.sample_frames == 3


def test_session_is_unsupported_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(repair_module.sys, "platform", "darwin")
    session = RepairSession(RepairPolicy(enabled=True))

    diagnosis = evaluate_frames([Image.new("RGB", (10, 10), (0, 0, 0))])

    assert session.supported is False
    assert session.repair(diagnosis, {"left": 0, "top": 0, "width": 10, "height": 10}) == []
    assert session.printwindow({"left": 0, "top": 0, "width": 10, "height": 10}) is None
    assert session.close() == []
    assert "Windows" in session.reason


def test_session_disabled_does_nothing() -> None:
    session = RepairSession(RepairPolicy(enabled=False))

    assert session.supported is False
    assert "关闭" in session.reason


def test_healthy_diagnosis_skips_window_patching(fake_session) -> None:
    diagnosis = evaluate_frames([question_page()])

    assert fake_session.supported is True
    assert fake_session.repair(diagnosis, {"left": 0, "top": 0, "width": 400, "height": 300}) == []


def test_black_diagnosis_applies_patch_and_reports(fake_session) -> None:
    diagnosis = evaluate_frames([Image.new("RGB", (400, 300), (0, 0, 0))])

    actions = fake_session.repair(diagnosis, {"left": 0, "top": 0, "width": 400, "height": 300})

    assert len(actions) == 1
    assert actions[0].ok
    assert "解除捕获排除" in fake_session.applied_labels()
    assert fake_session.targets
    assert fake_session._timer is not None


def test_session_close_restores_and_cancels_watchdog(fake_session) -> None:
    diagnosis = evaluate_frames([Image.new("RGB", (400, 300), (0, 0, 0))])
    fake_session.repair(diagnosis, {"left": 0, "top": 0, "width": 400, "height": 300})

    restored = fake_session.close()

    assert restored
    assert restored[0].phase == "restore"
    assert fake_session._timer is None


def test_printwindow_fallback_returns_image(fake_session) -> None:
    image = fake_session.printwindow({"left": 0, "top": 0, "width": 400, "height": 300})

    assert image is not None
    assert image.size == (400, 300)


def test_content_gap_detects_hidden_window(monkeypatch, fake_session) -> None:
    monkeypatch.setattr(FakeNative, "window_content", question_page(400, 300))
    capture = Image.new("RGB", (400, 300), (58, 92, 140))

    diagnosis = fake_session.content_gap(capture, {"left": 0, "top": 0, "width": 400, "height": 300})

    assert diagnosis is not None
    assert diagnosis.kind == "content_lost"
    assert diagnosis.repair_kind == "content_lost"
    assert "相关性" in diagnosis.reason


def test_content_gap_quiet_when_capture_matches(monkeypatch, fake_session) -> None:
    page = question_page(400, 300)
    monkeypatch.setattr(FakeNative, "window_content", page)

    assert fake_session.content_gap(page, {"left": 0, "top": 0, "width": 400, "height": 300}) is None


def test_content_gap_disabled_by_policy(monkeypatch) -> None:
    monkeypatch.setattr(repair_module.sys, "platform", "win32")
    monkeypatch.setattr(
        "ai_screenshot_assistant.capture.win32_window_repair.WindowRepair", FakeNative
    )
    monkeypatch.setattr(FakeNative, "window_content", question_page(400, 300))
    session = RepairSession(RepairPolicy(enabled=True, content_check=False))

    assert session.content_gap(Image.new("RGB", (400, 300), (0, 0, 0)), {"left": 0, "top": 0, "width": 400, "height": 300}) is None


def test_content_gap_unsupported_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(repair_module.sys, "platform", "darwin")
    session = RepairSession(RepairPolicy(enabled=True))

    assert session.content_gap(Image.new("RGB", (10, 10), (0, 0, 0)), {"left": 0, "top": 0, "width": 10, "height": 10}) is None


class FakeRecord:
    label = "答题客户端(0x1234)"
    class_name = "Chrome_WidgetWin_1"
    process_id = 999

    def hiding_flags(self):
        return ["捕获排除"]


def test_hidden_window_detects_by_state(monkeypatch, fake_session) -> None:
    monkeypatch.setattr(FakeNative, "hiding_record", FakeRecord())
    region = {"left": 0, "top": 0, "width": 400, "height": 300}

    diagnosis = fake_session.hidden_window(region)

    assert diagnosis is not None
    assert diagnosis.kind == "content_lost"
    assert "捕获排除" in diagnosis.reason


def test_hidden_window_quiet_without_flags(monkeypatch, fake_session) -> None:
    monkeypatch.setattr(FakeNative, "hiding_record", None)
    region = {"left": 0, "top": 0, "width": 400, "height": 300}

    assert fake_session.hidden_window(region) is None


def test_hidden_window_respects_policy(monkeypatch) -> None:
    monkeypatch.setattr(repair_module.sys, "platform", "win32")
    monkeypatch.setattr(
        "ai_screenshot_assistant.capture.win32_window_repair.WindowRepair", FakeNative
    )
    monkeypatch.setattr(FakeNative, "hiding_record", FakeRecord())
    session = RepairSession(RepairPolicy(enabled=True, state_probe=False))

    assert session.hidden_window({"left": 0, "top": 0, "width": 400, "height": 300}) is None


def test_repair_action_label_and_describe() -> None:
    action = RepairAction("窗口A(0x1)", "clear_affinity", True, "注入解除")

    assert action.describe().startswith("✓")
    assert "窗口A" in action.describe()


def test_outcome_summary_mentions_patches_and_retries() -> None:
    diagnosis = evaluate_frames(
        [Image.new("RGB", (400, 300), (0, 0, 0)), question_page()]
    )
    assert diagnosis.kind == ANOMALY_FLICKER
    outcome = CaptureOutcome(
        image=question_page(),
        diagnosis=diagnosis,
        attempts=2,
        repairs=[RepairAction("窗口A(0x1)", "clear_affinity", True, "注入解除")],
        targets=["窗口A(0x1)"],
    )

    summary = outcome.summary()

    assert "截图异常" in summary
    assert "闪屏" in summary
    assert "解除捕获排除" in summary
    assert "重拍 1 次" in summary
    assert outcome.repaired
    assert outcome.to_payload()["attempts"] == 2


def test_outcome_summary_silent_when_healthy() -> None:
    diagnosis = evaluate_frames([question_page()])
    outcome = CaptureOutcome(image=question_page(), diagnosis=diagnosis)

    assert outcome.summary() == ""
    assert outcome.repaired is False


def test_outcome_marks_printwindow_source() -> None:
    diagnosis = evaluate_frames([question_page()]).with_source("printwindow")
    outcome = CaptureOutcome(image=question_page(), diagnosis=diagnosis, source="printwindow")

    assert outcome.repaired
    assert "PrintWindow" in outcome.summary()
