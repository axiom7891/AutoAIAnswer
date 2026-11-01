from __future__ import annotations

from dataclasses import replace

from ai_screenshot_assistant.capture.roi import Roi
from ai_screenshot_assistant.config import settings
from ai_screenshot_assistant.core.workflow import AssistantWorkflow


class FakeCapture:
    def capture_png(self, roi, debug_path=None):
        return b"png"

    def capture_fullscreen_png(self, x=None, y=None, debug_path=None):
        return b"fullpng"


class FakeAI:
    def __init__(self) -> None:
        self.calls = 0

    def analyze_images_stream(self, png_images, user_text=None, conversation=None):
        self.calls += 1
        yield "答案：AI\n解析：模型回答"


class FakeBank:
    def __init__(self) -> None:
        self.total_count = 1
        self.calls = 0

    def find_answer(self, png_bytes):
        self.calls += 1
        return "答案：C\n解析：题库匹配"


class FakePublisher:
    def __init__(self) -> None:
        self.events = []

    def send_sync(self, event):
        self.events.append(event)


def _workflow(bank_enabled: bool = True):
    publisher = FakePublisher()
    ai = FakeAI()
    bank = FakeBank()
    workflow = AssistantWorkflow(
        session_id="s1",
        capture=FakeCapture(),
        ai_client=ai,
        publisher=publisher,
        app_settings=replace(settings, save_debug_image=False),
    )
    workflow.bank = bank
    workflow.bank_enabled = bank_enabled
    results = []
    workflow.on_result = results.append
    return workflow, publisher, ai, bank, results


def test_bank_hit_returns_answer_without_calling_ai() -> None:
    workflow, publisher, ai, bank, results = _workflow()

    workflow.process_roi(Roi(left=1, top=2, width=30, height=40))

    assert bank.calls == 1
    assert ai.calls == 0
    types = [event["type"] for event in publisher.events]
    assert "answer.started" in types
    assert "answer.completed" in types
    started = next(event for event in publisher.events if event["type"] == "answer.started")
    assert started["payload"]["source"] == "bank"
    completed = next(event for event in publisher.events if event["type"] == "answer.completed")
    assert completed["payload"]["result"]["source"] == "bank"
    assert "答案：C" in completed["payload"]["result"]["text"]
    assert results and results[0]["answer"] == "C"


def test_bank_is_skipped_when_question_text_is_present() -> None:
    workflow, publisher, ai, bank, _results = _workflow()

    workflow.process_fullscreen(user_text="解释一下这道题", is_chat=True, use_conversation=True)

    assert bank.calls == 0
    assert ai.calls == 1
    started = next(event for event in publisher.events if event["type"] == "answer.started")
    assert started["payload"]["source"] == "ai"


def test_bank_disabled_falls_back_to_ai() -> None:
    workflow, _publisher, ai, bank, _results = _workflow(bank_enabled=False)

    workflow.process_roi(Roi(left=1, top=2, width=30, height=40))

    assert bank.calls == 0
    assert ai.calls == 1


def test_workflow_reports_analysis_events_and_can_retry_last_png() -> None:
    workflow, publisher, ai, _bank, _results = _workflow(bank_enabled=False)
    started = []
    finished = []
    workflow.on_analysis_started = lambda: started.append(True)
    workflow.on_analysis_finished = lambda: finished.append(True)

    workflow.process_roi(Roi(left=1, top=2, width=30, height=40))
    assert ai.calls == 1
    assert started == [True]
    assert finished == [True]

    assert workflow.retry_last_analysis() is True
    assert ai.calls == 2
    assert started == [True, True]
    assert finished == [True, True]
    assert any(event["type"] == "answer.completed" for event in publisher.events)

