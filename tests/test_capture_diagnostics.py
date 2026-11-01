from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from ai_screenshot_assistant.capture import diagnostics as diagnostics_module
from ai_screenshot_assistant.capture.diagnostics import write_capture_report
from ai_screenshot_assistant.capture.health import evaluate_frames
from ai_screenshot_assistant.capture.repair import RepairAction, RepairPolicy


def question_page(width: int = 400, height: int = 300) -> Image.Image:
    image = Image.new("RGB", (width, height), (250, 250, 248))
    draw = ImageDraw.Draw(image)
    for row in range(6):
        draw.text((20, 20 + row * 30), f"{row + 1}. question text", fill=(20, 20, 20))
    return image


class FakeNative:
    def describe_windows(self, region, max_windows=8):
        return [
            "hwnd=0x1234 class=Chrome_WidgetWin_1 title='答题' pid=999 bits=x64 "
            "exstyle=0x80000 affinity=0x11 cloaked=False layered=True(flags=2,alpha=89,known=True) "
            "noredir=False 状态=已捕获排除、图层 alpha=89"
        ]

    def printwindow_probe(self, region, max_windows=5):
        return ["hwnd=0x1234 PrintWindow=成功 detail=28.4"]


class FakeSession:
    supported = True
    reason = ""
    targets = ["窗口A(0x1)"]
    actions = [RepairAction("窗口A(0x1)", "clear_affinity", True, "注入解除")]

    def __init__(self) -> None:
        self._native = FakeNative()


def test_report_records_region_and_diagnosis(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(diagnostics_module, "diagnostics_dir", lambda: tmp_path)
    diagnosis = evaluate_frames([Image.new("RGB", (400, 300), (0, 0, 0))])

    path = write_capture_report(
        region={"left": 10, "top": 20, "width": 400, "height": 300},
        diagnosis=diagnosis,
        policy=RepairPolicy(),
        session=None,
        image=Image.new("RGB", (400, 300), (0, 0, 0)),
    )

    text = path.read_text(encoding="utf-8")
    assert path.parent == tmp_path
    assert path.name.startswith("capture-diagnose-")
    assert "截取区域" in text
    assert "black" in text
    assert "修复策略" in text
    assert "怎么读这份报告" in text


def test_report_lists_windows_and_printwindow_probe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(diagnostics_module, "diagnostics_dir", lambda: tmp_path)

    path = write_capture_report(
        region={"left": 0, "top": 0, "width": 400, "height": 300},
        diagnosis=None,
        policy=RepairPolicy(),
        session=FakeSession(),
        image=None,
        extra=["手动诊断"],
    )

    text = path.read_text(encoding="utf-8")
    assert "hwnd=0x1234" in text
    assert "affinity=0x11" in text
    assert "PrintWindow=成功 detail=28.4" in text
    assert "补丁动作" in text
    assert "手动诊断" in text


def test_report_handles_missing_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(diagnostics_module, "diagnostics_dir", lambda: tmp_path)

    path = write_capture_report(region={"left": 0, "top": 0, "width": 10, "height": 10})

    text = path.read_text(encoding="utf-8")
    assert "窗口修复后端: 未启用" in text
    assert "诊断结论: 未体检" in text
