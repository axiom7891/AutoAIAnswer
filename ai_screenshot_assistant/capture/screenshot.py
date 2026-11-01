from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Protocol

from PIL import Image

from ai_screenshot_assistant.capture.health import (
    ANOMALY_FLICKER,
    CaptureDiagnosis,
    evaluate_frames,
)
from ai_screenshot_assistant.capture.repair import (
    CaptureOutcome,
    RepairAction,
    RepairPolicy,
    RepairSession,
)
from ai_screenshot_assistant.capture.roi import Roi
from ai_screenshot_assistant.utils.display import scale_roi, screen_scale_at

FULLSCREEN_MAX_SIDE = 2880


def point_in_monitor(monitor: dict[str, int], x: int, y: int) -> bool:
    left = monitor["left"]
    top = monitor["top"]
    return left <= x < left + monitor["width"] and top <= y < top + monitor["height"]


def monitor_containing_point(
    monitors: list[dict[str, int]],
    x: int | None = None,
    y: int | None = None,
    scale: float = 1.0,
) -> dict[str, int]:
    physical = monitors[1:] if len(monitors) > 1 else monitors
    if not physical:
        raise RuntimeError("No display is available for fullscreen capture")
    if x is None or y is None:
        return physical[0]
    candidates = [(int(x), int(y))]
    if scale > 1.0001:
        candidates.append((int(round(x * scale)), int(round(y * scale))))
    for cx, cy in candidates:
        for monitor in physical:
            if point_in_monitor(monitor, cx, cy):
                return monitor
    return physical[0]


def fit_image(image: Image.Image, max_side: int = FULLSCREEN_MAX_SIDE) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image
    scale = max_side / longest
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


class FrameGrabber(Protocol):
    """取帧端口：真实实现是 mss，测试可以换成假实现。"""

    def grab_many(
        self,
        region: dict[str, int],
        count: int = 1,
        interval_seconds: float = 0.0,
    ) -> list[Image.Image]: ...


class MssGrabber:
    def grab_many(
        self,
        region: dict[str, int],
        count: int = 1,
        interval_seconds: float = 0.0,
    ) -> list[Image.Image]:
        import mss

        frames: list[Image.Image] = []
        with mss.mss() as sct:
            for index in range(max(1, count)):
                if index and interval_seconds > 0:
                    time.sleep(interval_seconds)
                shot = sct.grab(region)
                frames.append(Image.frombytes("RGB", shot.size, shot.rgb))
        return frames


class ScreenCapture:
    """截图入口：取帧 → 体检 → 给异常窗口注入修复补丁 → 重拍 → 取最稳帧。"""

    def __init__(
        self,
        policy: RepairPolicy | None = None,
        grabber: FrameGrabber | None = None,
    ) -> None:
        self.policy = policy or RepairPolicy.from_settings()
        self.grabber: FrameGrabber = grabber or MssGrabber()
        self.last_outcome: CaptureOutcome | None = None
        self.last_diagnostics_path: Path | None = None
        self._last_report = ""

    # ---- 策略 ----

    def set_policy(self, policy: RepairPolicy) -> None:
        self.policy = policy

    def set_repair_enabled(self, enabled: bool) -> None:
        self.policy = self.policy.with_enabled(enabled)

    @property
    def repair_enabled(self) -> bool:
        return bool(self.policy.enabled)

    # ---- 对外接口 ----

    def capture_png(self, roi: Roi, debug_path: Path | None = None) -> bytes:
        scale = self._coordinate_scale(roi.left, roi.top)
        region = scale_roi(roi, scale).to_mss_monitor()
        image = self.capture_image(region)
        return self._encode(image, debug_path)

    def capture_fullscreen_png(
        self,
        x: int | None = None,
        y: int | None = None,
        debug_path: Path | None = None,
    ) -> bytes:
        import mss

        scale = self._coordinate_scale(x, y)
        with mss.mss() as sct:
            monitor = monitor_containing_point(sct.monitors, x, y, scale=scale)
        image = self.capture_image(monitor)
        return self._encode(fit_image(image), debug_path)

    def capture_image(self, region: dict[str, int]) -> Image.Image:
        """按策略取帧；发现黑屏/闪屏/透明屏时先修窗口再重拍。"""

        policy = self.policy
        if not policy.enabled:
            frames = self.grabber.grab_many(region, 1)
            if not frames:
                raise RuntimeError("截图返回空帧")
            diagnosis = evaluate_frames(frames)
            self.last_outcome = CaptureOutcome(
                image=frames[0], diagnosis=diagnosis, attempts=1, source="grabber"
            )
            self._last_report = ""
            return self.last_outcome.image

        diagnosis: CaptureDiagnosis | None = None
        initial: CaptureDiagnosis | None = None
        frames: list[Image.Image] = []
        repairs: list[RepairAction] = []
        attempts = 0
        source = "grabber"
        session = RepairSession(policy)
        try:
            while True:
                attempts += 1
                # 闪屏时多取一帧，命中干净画面的概率更高。
                extra = 1 if diagnosis is not None and diagnosis.kind == ANOMALY_FLICKER else 0
                count = max(1, min(4, policy.sample_frames + extra))
                frames = self.grabber.grab_many(
                    region,
                    count,
                    policy.sample_interval_ms / 1000.0,
                )
                if not frames:
                    raise RuntimeError("截图返回空帧")
                diagnosis = evaluate_frames(frames)
                image = frames[diagnosis.best_index]
                if diagnosis.ok:
                    # 画面看着“正常”也可能只是背景：先拿窗口自身渲染对一下，
                    # 再退一步按窗口状态兜底（捕获排除/隐藏/低 alpha/直出）。
                    gap = session.content_gap(image, region)
                    if gap is None:
                        gap = session.hidden_window(region)
                    if gap is not None:
                        diagnosis = gap
                if initial is None or (initial.ok and not diagnosis.ok):
                    initial = diagnosis
                if diagnosis.ok or attempts >= policy.max_attempts:
                    break
                repairs.extend(session.repair(diagnosis, region))
                if policy.retry_delay_ms > 0:
                    time.sleep(policy.retry_delay_ms / 1000.0)

            image = frames[diagnosis.best_index]
            if policy.printwindow_fallback and not diagnosis.ok and session.supported:
                fallback = session.printwindow(region)
                if fallback is not None:
                    fallback_diagnosis = evaluate_frames([fallback])
                    if fallback_diagnosis.severity < diagnosis.severity:
                        image = fallback
                        diagnosis = fallback_diagnosis
                        source = "printwindow"
        finally:
            repairs.extend(session.close())

        outcome = CaptureOutcome(
            image=image,
            diagnosis=diagnosis.with_source(source),
            attempts=attempts,
            repairs=repairs,
            targets=session.targets,
            source=source,
            initial=initial,
        )
        self.last_outcome = outcome
        self._last_report = outcome.summary()
        if policy.diagnostics and (not outcome.ok or outcome.repaired):
            path = session.write_report(region=region, diagnosis=outcome.diagnosis, image=image)
            if path is not None:
                self.last_diagnostics_path = path
                self._last_report = f"{self._last_report}；诊断报告：{path}"
        return outcome.image

    # ---- 诊断回显 ----

    def dump_diagnostics(self, region: dict[str, int]) -> Path | None:
        """现场诊断：抓一帧 + 枚举窗口 + PrintWindow 探测，写一份 txt 报告。"""

        session = RepairSession(self.policy)
        image: Image.Image | None = None
        diagnosis: CaptureDiagnosis | None = None
        try:
            frames = self.grabber.grab_many(region, 1)
            if frames:
                image = frames[0]
                diagnosis = evaluate_frames(frames)
            return session.write_report(
                region=region,
                diagnosis=diagnosis,
                image=image,
                extra=["手动诊断：只采集现场信息，未发送给 AI"],
            )
        except Exception:
            return None
        finally:
            session.close()

    def take_report(self) -> str:
        """取走本次修复日志（只回显一次）。"""

        report, self._last_report = self._last_report, ""
        return report

    def diagnostics(self) -> dict:
        if self.last_outcome is None:
            return {}
        return self.last_outcome.to_payload()

    # ---- 内部 ----

    @staticmethod
    def _coordinate_scale(x: int | None = None, y: int | None = None) -> float:
        # mouse.get_position() and mss use the same physical desktop coordinates
        # on Windows. Applying Qt's logical-to-physical ratio again shifts ROI.
        if sys.platform == "win32":
            return 1.0
        return screen_scale_at(x, y)

    def _encode(self, image: Image.Image, debug_path: Path | None = None) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        png = buffer.getvalue()
        if debug_path is not None:
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(debug_path)
        return png
