"""截图异常修复策略与会话：把体检结果落到「给窗口打补丁 + 重拍」。

``ScreenCapture`` 只负责取帧，本模块负责：

1. 记录本次截图要用多少帧、重拍几次、要不要注入；
2. 按诊断结果调度窗口补丁（Windows 走 ``win32_window_repair``，其他平台直接跳过）；
3. 兜底还原：补丁带看门狗定时器，截图线程万一卡死也会在几十秒内自动还原；
4. 把结果整理成一句中文日志，方便控制台回显。
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field, replace

from PIL import Image

from ai_screenshot_assistant.capture.health import (
    ANOMALY_FLICKER,
    FRAME_CONTENT_LOST,
    FRAME_OK,
    KIND_LABELS,
    CaptureDiagnosis,
    analyze_frame,
    detect_content_gap,
)

try:  # 非 Windows 平台也要能导入
    from ai_screenshot_assistant.capture.win32_window_repair import PATCH_LABELS
except Exception:  # pragma: no cover - 只有模块损坏才会发生
    PATCH_LABELS = {}


@dataclass(frozen=True)
class RepairPolicy:
    """一次截图修复的预算与开关。"""

    enabled: bool = True
    max_attempts: int = 3
    sample_frames: int = 2
    sample_interval_ms: int = 45
    retry_delay_ms: int = 150
    printwindow_fallback: bool = True
    inject_remote: bool = True
    max_windows: int = 3
    restore_after_seconds: float = 25.0
    content_check: bool = True
    state_probe: bool = True
    diagnostics: bool = True

    @classmethod
    def from_settings(cls, app_settings=None) -> "RepairPolicy":
        if app_settings is None:
            from ai_screenshot_assistant.config import settings as app_settings  # 延迟导入避免环
        # 窗口注入补丁只有 Windows 有对应 API；macOS 上直接关掉，避免截一张图多拍两帧。
        platform_supported = sys.platform == "win32"
        return cls(
            enabled=bool(getattr(app_settings, "capture_repair_enabled", True)) and platform_supported,
            max_attempts=max(1, min(5, int(getattr(app_settings, "capture_repair_attempts", 3)))),
            sample_frames=max(1, min(4, int(getattr(app_settings, "capture_repair_samples", 2)))),
            inject_remote=bool(getattr(app_settings, "capture_repair_inject", True)),
            content_check=bool(getattr(app_settings, "capture_repair_content", True)),
            state_probe=bool(getattr(app_settings, "capture_repair_state", True)),
            diagnostics=bool(getattr(app_settings, "capture_repair_diagnostics", True)),
        )

    def with_enabled(self, enabled: bool) -> "RepairPolicy":
        return replace(self, enabled=bool(enabled))


@dataclass(frozen=True)
class RepairAction:
    target: str
    patch: str
    ok: bool
    detail: str
    phase: str = "apply"

    @property
    def label(self) -> str:
        return PATCH_LABELS.get(self.patch, self.patch)

    def describe(self) -> str:
        mark = "✓" if self.ok else "✗"
        return f"{mark} {self.label} {self.target}：{self.detail}"


class RepairSession:
    """一次截图窗口期内的补丁会话，退出时必须还原。"""

    def __init__(self, policy: RepairPolicy) -> None:
        self.policy = policy
        self.actions: list[RepairAction] = []
        self.targets: list[str] = []
        self.reason = ""
        self._native = None
        self._timer: threading.Timer | None = None
        self.supported = False
        if not policy.enabled:
            self.reason = "截图异常修复已关闭"
            return
        if sys.platform != "win32":
            self.reason = "仅 Windows 支持窗口注入修复"
            return
        try:
            from ai_screenshot_assistant.capture.win32_window_repair import WindowRepair
        except Exception as exc:  # pragma: no cover - 真实环境不会失败
            self.reason = f"窗口修复模块不可用：{exc}"
            return
        try:
            self._native = WindowRepair(inject_remote=policy.inject_remote)
        except Exception as exc:  # pragma: no cover
            self.reason = f"窗口修复初始化失败：{exc}"
            return
        self.supported = bool(getattr(self._native, "supported", False))
        if not self.supported:
            self.reason = "当前系统不支持窗口补丁"

    # ---- 生命周期 ----

    def __enter__(self) -> "RepairSession":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def repair(self, diagnosis: CaptureDiagnosis, region: dict[str, int]) -> list[RepairAction]:
        if not self.supported or self._native is None:
            return []
        if diagnosis.kind == FRAME_OK:
            return []
        raw, reason = self._native.apply(
            diagnosis.repair_kind, region, max_windows=self.policy.max_windows
        )
        if reason:
            self.reason = reason
        actions = [RepairAction(*item) for item in raw]
        self.actions.extend(actions)
        self.targets = list(self._native.describe_targets())
        if any(action.ok and action.phase == "apply" for action in actions):
            self._start_watchdog()
        return actions

    def content_gap(self, capture: Image.Image, region: dict[str, int]) -> CaptureDiagnosis | None:
        """对比窗口自身渲染与桌面截取结果：内容被藏掉时给出「内容缺失」诊断。"""

        if not self.supported or self._native is None or not self.policy.content_check:
            return None
        getter = getattr(self._native, "content_image", None)
        if not callable(getter):
            return None
        try:
            window_image = getter(region)
        except Exception:
            return None
        if window_image is None:
            return None
        try:
            gap = detect_content_gap(capture, window_image)
        except Exception:
            return None
        if not gap.lost:
            return None
        return CaptureDiagnosis(
            kind=FRAME_CONTENT_LOST,
            reports=(analyze_frame(capture),),
            deltas=(),
            best_index=0,
            reason=gap.reason,
            mixed_kind=FRAME_CONTENT_LOST,
        )

    def hidden_window(self, region: dict[str, int]) -> CaptureDiagnosis | None:
        """没有像素证据时按窗口状态兜底：谁带着捕获排除/隐藏/低 alpha/直出标志。"""

        if not self.supported or self._native is None or not self.policy.state_probe:
            return None
        probe = getattr(self._native, "first_hiding_window", None)
        if not callable(probe):
            return None
        try:
            record = probe(region)
        except Exception:
            return None
        if record is None:
            return None
        flags = "、".join(record.hiding_flags())
        return CaptureDiagnosis(
            kind=FRAME_CONTENT_LOST,
            reports=(),
            deltas=(),
            best_index=0,
            reason=f"{record.label} {record.class_name} pid={record.process_id} 带 {flags}",
            mixed_kind=FRAME_CONTENT_LOST,
        )

    def printwindow(self, region: dict[str, int]) -> Image.Image | None:
        if not self.supported or self._native is None:
            return None
        try:
            data = self._native.printwindow_png(region)
        except Exception:
            return None
        if not data:
            return None
        try:
            import io

            with Image.open(io.BytesIO(data)) as image:
                return image.convert("RGB").copy()
        except Exception:
            return None

    def close(self) -> list[RepairAction]:
        self._cancel_watchdog()
        if not self.supported or self._native is None:
            return []
        try:
            raw = self._native.restore()
        except Exception:
            raw = []
        actions = [RepairAction(*item, phase="restore") for item in raw]
        self.actions.extend(actions)
        return actions

    # ---- 看门狗 ----

    def _start_watchdog(self) -> None:
        if self._timer is not None:
            return
        timeout = max(5.0, float(self.policy.restore_after_seconds))
        self._timer = threading.Timer(timeout, self._watchdog_restore)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_watchdog(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _watchdog_restore(self) -> None:  # pragma: no cover - 只在截图卡死时触发
        self._timer = None
        try:
            if self._native is not None:
                self._native.restore()
        except Exception:
            pass

    # ---- 汇总 ----

    def write_report(
        self,
        *,
        region: dict[str, int],
        diagnosis: CaptureDiagnosis | None = None,
        image: Image.Image | None = None,
        extra: list[str] | None = None,
    ):
        """落一份现场诊断 txt，返回路径；用于「点一下就能发过来」的排障。"""

        try:
            from ai_screenshot_assistant.capture.diagnostics import write_capture_report
        except Exception:
            return None
        try:
            return write_capture_report(
                region=region,
                diagnosis=diagnosis,
                policy=self.policy,
                session=self,
                image=image,
                extra=extra,
            )
        except Exception:
            return None

    def applied_labels(self) -> list[str]:
        labels: list[str] = []
        for action in self.actions:
            if action.phase != "apply" or not action.ok:
                continue
            if action.label not in labels:
                labels.append(action.label)
        return labels


@dataclass
class CaptureOutcome:
    """一次截图的最终产物与修复记录。"""

    image: Image.Image
    diagnosis: CaptureDiagnosis
    attempts: int = 1
    repairs: list[RepairAction] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    source: str = "grabber"
    initial: CaptureDiagnosis | None = None

    @property
    def ok(self) -> bool:
        return self.diagnosis.ok

    @property
    def repaired(self) -> bool:
        return bool(self.repairs) or self.source == "printwindow"

    @property
    def original(self) -> CaptureDiagnosis:
        return self.initial or self.diagnosis

    def summary(self) -> str:
        if self.ok and not self.repaired:
            return ""
        first = self.original
        head = f"截图异常：{first.label}"
        if first.kind == ANOMALY_FLICKER:
            head += f"（底层 {KIND_LABELS.get(first.repair_kind, first.repair_kind)}）"
        parts = [head]
        labels: list[str] = []
        for action in self.repairs:
            if action.phase == "apply" and action.ok and action.label not in labels:
                labels.append(action.label)
        if labels:
            parts.append("已注入补丁：" + "、".join(labels))
        elif self.targets:
            parts.append("目标窗口：" + self.targets[0])
        if self.source == "printwindow":
            parts.append("改用窗口 PrintWindow 抓取")
        parts.append(f"重拍 {max(0, self.attempts - 1)} 次")
        failed_restore = [
            action for action in self.repairs if action.phase == "restore" and not action.ok
        ]
        if failed_restore:
            parts.append("还原失败：" + failed_restore[0].label)
        parts.append("已恢复可用画面" if self.ok else "仍未完全恢复")
        return "；".join(parts)

    def to_payload(self) -> dict:
        first = self.original
        return {
            "kind": first.kind,
            "label": first.label,
            "final_kind": self.diagnosis.kind,
            "ok": self.ok,
            "attempts": self.attempts,
            "source": self.source,
            "targets": self.targets,
            "repairs": [
                {"target": action.target, "patch": action.patch, "ok": action.ok, "detail": action.detail}
                for action in self.repairs
                if action.phase == "apply"
            ],
        }
