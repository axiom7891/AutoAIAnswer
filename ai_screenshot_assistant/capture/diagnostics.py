"""把一次截图的可疑窗口、PrintWindow 结果与修复结论写成文本报告。

现场排查用：对方电脑上截不到某种窗口时，点一下「截图诊断」就会在
`%LOCALAPPDATA%\\QQMusic\\Logs` 下留一份 txt，里面能看出到底是
「没找到窗口」「窗口被捕获排除但注入失败」「PrintWindow 也拿不到内容」中的哪一种。
"""

from __future__ import annotations

import ctypes
import datetime as dt
import os
import platform
import sys
from pathlib import Path

from PIL import Image, ImageStat

from ai_screenshot_assistant.capture.health import CaptureDiagnosis


def diagnostics_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base / "QQMusic" / "Logs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "QQMusic"
    return Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "QQMusic" / "Logs"


def _image_stats(image: Image.Image | None) -> str:
    if image is None:
        return "无"
    gray = image.convert("L")
    stat = ImageStat.Stat(gray)
    return f"{image.size[0]}x{image.size[1]} mean={stat.mean[0]:.1f} stddev={stat.stddev[0]:.1f}"


def write_capture_report(
    *,
    region: dict[str, int],
    diagnosis: CaptureDiagnosis | None = None,
    policy=None,
    session=None,
    image: Image.Image | None = None,
    extra: list[str] | None = None,
) -> Path:
    target_dir = diagnostics_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target_dir / f"capture-diagnose-{stamp}.txt"

    lines: list[str] = []
    lines.append(f"截图诊断报告 {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"平台: {platform.platform()}")
    lines.append(
        f"Python: {sys.version.split()[0]} bits={ctypes.sizeof(ctypes.c_void_p) * 8} "
        f"frozen={bool(getattr(sys, 'frozen', False))}"
    )
    lines.append(f"截取区域: {region}")
    lines.append("")

    if policy is not None:
        lines.append(
            "修复策略: "
            f"enabled={policy.enabled} attempts={policy.max_attempts} samples={policy.sample_frames} "
            f"inject={policy.inject_remote} content_check={policy.content_check} "
            f"state_probe={getattr(policy, 'state_probe', None)}"
        )
    if diagnosis is not None:
        lines.append(f"诊断结论: {diagnosis.kind}（{diagnosis.label}）ok={diagnosis.ok}")
        lines.append(f"说明: {diagnosis.reason or '-'}")
        for index, report in enumerate(diagnosis.reports):
            lines.append(
                f"  帧{index}: kind={report.kind} luma={report.mean_luma:.1f} "
                f"dark={report.dark_ratio:.3f} detail={report.detail:.1f} "
                f"alpha={report.alpha_coverage:.3f} {report.reason}"
            )
    else:
        lines.append("诊断结论: 未体检")
    lines.append(f"截图统计: {_image_stats(image)}")
    lines.append("")

    if session is not None:
        lines.append(f"窗口修复后端: supported={getattr(session, 'supported', False)} "
                     f"reason={getattr(session, 'reason', '') or '-'}")
        targets = getattr(session, "targets", None)
        if targets:
            lines.append("修复目标:")
            lines.extend(f"  {line}" for line in targets)
        actions = getattr(session, "actions", None)
        if actions:
            lines.append("补丁动作:")
            lines.extend(f"  {action.describe()}" for action in actions)
        native = getattr(session, "_native", None)
        if native is not None:
            try:
                windows = native.describe_windows(region, max_windows=8)
            except Exception as exc:  # pragma: no cover - 只有真实 API 失败才会到
                windows = [f"枚举失败: {exc}"]
            lines.append("覆盖该区域的顶层窗口:")
            lines.extend(f"  {line}" for line in windows or ["（无）"])
            try:
                probes = native.printwindow_probe(region, max_windows=5)
            except Exception as exc:  # pragma: no cover
                probes = [f"探测失败: {exc}"]
            lines.append("PrintWindow 探测:")
            lines.extend(f"  {line}" for line in probes or ["（无）"])
    else:
        lines.append("窗口修复后端: 未启用")
    lines.append("")

    if extra:
        lines.append("附加信息:")
        lines.extend(f"  {line}" for line in extra)

    lines.append("")
    lines.append("怎么读这份报告:")
    lines.append("- 没有列出任何窗口 → 截取区域没有可识别的顶层窗口，检查是否截到了桌面/空白处。")
    lines.append("- 有窗口但「状态=无」且 PrintWindow 成功 → 画面确实正常，问题不在截图。")
    lines.append("- 状态含「捕获排除 / DWM 隐藏 / 图层 alpha」但补丁动作为空或失败 → 注入被拒（32 位或管理员权限）。")
    lines.append("- PrintWindow=失败 → 该窗口无法离屏取内容，只能靠解除保护后重拍。")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
