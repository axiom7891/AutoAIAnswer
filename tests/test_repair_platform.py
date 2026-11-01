from __future__ import annotations

import sys

from ai_screenshot_assistant.capture import repair as repair_module
from ai_screenshot_assistant.capture.repair import RepairPolicy


def test_repair_disabled_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(repair_module.sys, "platform", "darwin")

    policy = RepairPolicy.from_settings()

    assert policy.enabled is False
    assert policy.max_attempts >= 1


def test_repair_enabled_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(repair_module.sys, "platform", "win32")

    policy = RepairPolicy.from_settings()

    assert policy.enabled is True


def test_policy_can_still_be_constructed_manually() -> None:
    policy = RepairPolicy(enabled=True, sample_frames=1)

    assert policy.enabled is True
    assert policy.with_enabled(False).enabled is False
    assert sys.platform in {"win32", "darwin", "linux"} or sys.platform
