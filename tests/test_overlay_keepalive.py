from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings

from ai_screenshot_assistant.ui.streaming_overlay import (
    FRONT_INTERVAL_MS,
    MAC_FRONT_INTERVAL_MS,
    StreamingOverlay,
)


def expected_interval() -> int:
    return MAC_FRONT_INTERVAL_MS if sys.platform == "darwin" else FRONT_INTERVAL_MS


def make_overlay(tmp_path: Path) -> StreamingOverlay:
    settings = QSettings(str(tmp_path / "overlay.ini"), QSettings.Format.IniFormat)
    return StreamingOverlay(settings)


def test_front_timer_setup(tmp_path: Path, qapp) -> None:
    overlay = make_overlay(tmp_path)
    try:
        assert overlay._front_timer.interval() == expected_interval()
        overlay.show()
        qapp.processEvents()
        assert overlay._front_timer.isActive()
        overlay.hide()
        qapp.processEvents()
        assert not overlay._front_timer.isActive()
    finally:
        overlay.close()


def test_clamp_pulls_overlay_back_on_screen(tmp_path: Path, qapp) -> None:
    overlay = make_overlay(tmp_path)
    try:
        overlay.move(-8000, -8000)
        overlay._clamp_to_screen()
        qapp.processEvents()
        screen = qapp.primaryScreen().availableGeometry()
        assert screen.intersects(overlay.frameGeometry())
    finally:
        overlay.close()


def test_clamp_keeps_visible_overlay_in_place(tmp_path: Path, qapp) -> None:
    overlay = make_overlay(tmp_path)
    try:
        overlay.move(40, 40)
        before = overlay.pos()
        overlay._clamp_to_screen()
        assert overlay.pos() == before
    finally:
        overlay.close()


def test_keep_front_is_safe_when_hidden(tmp_path: Path, qapp) -> None:
    overlay = make_overlay(tmp_path)
    try:
        overlay._keep_front()  # 未显示时不应抛异常
        assert overlay._front_misses == 0
    finally:
        overlay.close()


def test_overlay_exposes_status_signal(tmp_path: Path, qapp) -> None:
    overlay = make_overlay(tmp_path)
    try:
        received: list[str] = []
        overlay.status.connect(received.append)
        overlay.status.emit("测试")
        assert received == ["测试"]
    finally:
        overlay.close()


def test_macos_keep_front_uses_nswindow_order(tmp_path: Path, qapp, monkeypatch) -> None:
    from ai_screenshot_assistant.ui import streaming_overlay as module

    calls: list[object] = []
    monkeypatch.setattr(module, "_IS_MAC", True)
    monkeypatch.setattr(module, "keep_overlay_fronted", lambda target: calls.append(target))
    overlay = make_overlay(tmp_path)
    try:
        monkeypatch.setattr(overlay, "isVisible", lambda: True)
        overlay._keep_alive = True
        overlay._front_misses = 0
        overlay._keep_front()
        assert calls and calls[-1] is overlay
        assert overlay._front_misses == 0
    finally:
        overlay.close()
