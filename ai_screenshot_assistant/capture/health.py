"""截图帧体检：黑屏、局部黑块、纯色空白、透明屏、闪屏。

只做纯 PIL 计算，不碰 Windows API，所以 macOS 与 CI 都能跑这套判定。
截图修复流程用它决定「这张图是不是废图」「该给哪个窗口打补丁」「多帧里取哪一帧」。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from PIL import Image, ImageChops, ImageStat

FRAME_OK = "ok"
FRAME_BLACK = "black"
FRAME_PARTIAL_BLACK = "partial_black"
FRAME_BLANK = "blank"
FRAME_TRANSPARENT = "transparent"
FRAME_CONTENT_LOST = "content_lost"

ANOMALY_OK = FRAME_OK
ANOMALY_FLICKER = "flicker"

# 数值越大越糟糕，用于在多种异常里挑主因、以及比较修复前后哪张更健康。
SEVERITY = {
    FRAME_OK: 0,
    FRAME_BLANK: 1,
    FRAME_CONTENT_LOST: 2,
    FRAME_PARTIAL_BLACK: 2,
    FRAME_BLACK: 3,
    FRAME_TRANSPARENT: 4,
    ANOMALY_FLICKER: 3,
}

KIND_LABELS = {
    FRAME_OK: "正常",
    FRAME_BLACK: "黑屏",
    FRAME_PARTIAL_BLACK: "局部黑块",
    FRAME_BLANK: "纯色空白",
    FRAME_TRANSPARENT: "透明屏",
    FRAME_CONTENT_LOST: "内容缺失",
    ANOMALY_FLICKER: "闪屏",
}

DARK_CUTOFF = 16
BRIGHT_CUTOFF = 200

_MAX_ANALYSIS_SIDE = 640
_GRID_SIDE = 32
_DELTA_SIDE = 128
_CONTENT_SAMPLE_SIZE = (160, 120)
_DELTA_PIXEL_THRESHOLD = 24
_SURROUND_BRIGHT_LUMA = 110.0


@dataclass(frozen=True)
class HealthThresholds:
    """判定阈值；放宽可减少误报，收紧则更敏感。"""

    dark_ratio: float = 0.995
    dark_mean_luma: float = 2.5
    dark_bright_ratio: float = 0.002
    black_detail: float = 2.0
    blank_dominant_ratio: float = 0.997
    blank_detail: float = 1.2
    alpha_coverage_min: float = 0.01
    partial_black_min_share: float = 0.12
    partial_black_max_share: float = 0.97
    flicker_delta_ratio: float = 0.25
    content_correlation_min: float = 0.35
    content_window_detail_min: float = 4.0


DEFAULT_THRESHOLDS = HealthThresholds()


@dataclass(frozen=True)
class FrameReport:
    kind: str
    width: int
    height: int
    mean_luma: float
    dark_ratio: float
    bright_ratio: float
    dominant_ratio: float
    detail: float
    color_count: int
    alpha_coverage: float
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.kind == FRAME_OK

    @property
    def severity(self) -> int:
        return SEVERITY.get(self.kind, 0)

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)

    def describe(self) -> str:
        return (
            f"{self.label} {self.width}x{self.height} "
            f"luma={self.mean_luma:.1f} dark={self.dark_ratio:.3f} "
            f"detail={self.detail:.1f}"
        )


def _downscale(image: Image.Image, max_side: int) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image
    scale = max_side / float(longest)
    size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(size, Image.Resampling.BILINEAR)


def _dominant_ratio(image: Image.Image) -> tuple[float, int]:
    """把画面压到 32x32 再做 8 级色量化，返回最常见颜色占比与颜色数。"""

    small = _downscale(image.convert("RGB"), _GRID_SIDE).resize(
        (_GRID_SIDE, _GRID_SIDE), Image.Resampling.BILINEAR
    )
    counts: dict[int, int] = {}
    data = small.tobytes()
    for index in range(0, len(data), 3):
        key = ((data[index] >> 5) << 6) | ((data[index + 1] >> 5) << 3) | (data[index + 2] >> 5)
        counts[key] = counts.get(key, 0) + 1
    total = max(1, len(data) // 3)
    dominant = max(counts.values()) if counts else total
    return dominant / total, len(counts)


def _alpha_coverage(image: Image.Image) -> float:
    if "A" not in image.getbands():
        return 1.0
    histogram = image.getchannel("A").histogram()
    total = max(1, sum(histogram))
    return sum(histogram[9:]) / total


def _luma_grid(sample: Image.Image) -> list[int]:
    """32x32 亮度网格，一行像素值就是 32 字节，取起来最省事。"""

    grid = _downscale(sample.convert("L"), _GRID_SIDE).resize(
        (_GRID_SIDE, _GRID_SIDE), Image.Resampling.BILINEAR
    )
    return list(grid.tobytes())


def _largest_dark_block(values: Sequence[int], dark_cutoff: int = DARK_CUTOFF) -> tuple[int, int, int, int, int]:
    """四邻域连通块，返回 (像素数, 左, 上, 右, 下)，右/下为开区间。"""

    cells = len(values)
    seen = bytearray(cells)
    best: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0)
    for start in range(cells):
        if seen[start] or values[start] > dark_cutoff:
            continue
        seen[start] = 1
        stack = [start]
        size = 0
        left = right = start % _GRID_SIDE
        top = bottom = start // _GRID_SIDE
        while stack:
            current = stack.pop()
            size += 1
            row, col = divmod(current, _GRID_SIDE)
            left = min(left, col)
            right = max(right, col)
            top = min(top, row)
            bottom = max(bottom, row)
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = row + dr, col + dc
                if 0 <= nr < _GRID_SIDE and 0 <= nc < _GRID_SIDE:
                    nxt = nr * _GRID_SIDE + nc
                    if not seen[nxt] and values[nxt] <= dark_cutoff:
                        seen[nxt] = 1
                        stack.append(nxt)
        if size > best[0]:
            best = (size, left, top, right + 1, bottom + 1)
    return best


def _strip_luma(values: Sequence[int], rect: tuple[int, int, int, int], side: str) -> float:
    """暗块外侧一圈的平均亮度；越界或没有余量时返回 -1。"""

    _, left, top, right, bottom = rect
    rows = range(_GRID_SIDE)
    columns = range(_GRID_SIDE)
    if side == "top":
        if top <= 0:
            return -1.0
        rows = range(0, top)
    elif side == "bottom":
        if bottom >= _GRID_SIDE:
            return -1.0
        rows = range(bottom, _GRID_SIDE)
    elif side == "left":
        if left <= 0:
            return -1.0
        columns = range(0, left)
    else:
        if right >= _GRID_SIDE:
            return -1.0
        columns = range(right, _GRID_SIDE)
    total = 0
    count = 0
    for row in rows:
        base = row * _GRID_SIDE
        for col in columns:
            total += values[base + col]
            count += 1
    return total / count if count else -1.0


def _partial_black_share(values: Sequence[int]) -> tuple[float, float]:
    """返回 (暗像素占比, 最大暗块占比)，只用于日志与判定。"""

    cells = len(values)
    dark_total = sum(1 for value in values if value <= DARK_CUTOFF)
    block = _largest_dark_block(values)
    if not block[0]:
        return dark_total / cells, 0.0
    # 黑块必须被亮内容包住，才说明它挡住了本该有画面的窗口区域。
    outside = [
        _strip_luma(values, block, "top"),
        _strip_luma(values, block, "bottom"),
    ]
    wrapped_vertical = all(value >= _SURROUND_BRIGHT_LUMA for value in outside if value >= 0) and sum(
        1 for value in outside if value >= _SURROUND_BRIGHT_LUMA
    ) == 2
    if not wrapped_vertical:
        sides = [
            _strip_luma(values, block, "left"),
            _strip_luma(values, block, "right"),
        ]
        wrapped_horizontal = all(value >= _SURROUND_BRIGHT_LUMA for value in sides if value >= 0) and sum(
            1 for value in sides if value >= _SURROUND_BRIGHT_LUMA
        ) == 2
        if not wrapped_horizontal:
            return dark_total / cells, 0.0
    return dark_total / cells, block[0] / cells


def analyze_frame(
    image: Image.Image,
    thresholds: HealthThresholds = DEFAULT_THRESHOLDS,
) -> FrameReport:
    """判定单帧截图属于正常、黑屏、局部黑块、纯色空白还是透明屏。"""

    width, height = image.size
    sample = _downscale(image.convert("RGB"), _MAX_ANALYSIS_SIDE)
    gray = sample.convert("L")
    histogram = gray.histogram()
    total = max(1, sum(histogram))
    dark_ratio = sum(histogram[: DARK_CUTOFF + 1]) / total
    bright_ratio = sum(histogram[BRIGHT_CUTOFF:]) / total
    mean_luma = sum(index * count for index, count in enumerate(histogram)) / total
    detail = float(ImageStat.Stat(gray).stddev[0])
    alpha_coverage = _alpha_coverage(image)

    dominant_ratio = 0.0
    color_count = 0
    if detail <= thresholds.blank_detail + 6:
        dominant_ratio, color_count = _dominant_ratio(sample)

    kind = FRAME_OK
    reason = ""

    if alpha_coverage < thresholds.alpha_coverage_min:
        kind = FRAME_TRANSPARENT
        reason = f"整帧 alpha 覆盖率 {alpha_coverage:.2%}，画面被图层透明化"
    elif (
        dark_ratio >= thresholds.dark_ratio
        and mean_luma <= thresholds.dark_mean_luma + 12
        and detail <= thresholds.black_detail
    ) or (mean_luma <= thresholds.dark_mean_luma and bright_ratio <= thresholds.dark_bright_ratio):
        kind = FRAME_BLACK
        reason = f"平均亮度 {mean_luma:.1f}，暗像素 {dark_ratio:.2%}，画面全黑"
    elif dominant_ratio >= thresholds.blank_dominant_ratio and detail <= thresholds.blank_detail:
        kind = FRAME_BLANK
        reason = f"单一颜色占比 {dominant_ratio:.2%}，内容没有渲染出来"
    else:
        dark_share, block_share = _partial_black_share(_luma_grid(sample))
        if (
            thresholds.partial_black_min_share <= block_share <= thresholds.partial_black_max_share
            and dark_share >= block_share
        ):
            kind = FRAME_PARTIAL_BLACK
            reason = f"暗块占画面 {block_share:.0%}，疑似有窗口被黑块遮挡"

    return FrameReport(
        kind=kind,
        width=width,
        height=height,
        mean_luma=mean_luma,
        dark_ratio=dark_ratio,
        bright_ratio=bright_ratio,
        dominant_ratio=dominant_ratio,
        detail=detail,
        color_count=color_count,
        alpha_coverage=alpha_coverage,
        reason=reason,
    )


def frame_delta_ratio(first: Image.Image, second: Image.Image) -> float:
    """两帧灰度差异占比（0–1），用于描述闪屏程度。"""

    if first.size != second.size:
        second = second.resize(first.size, Image.Resampling.BILINEAR)
    left = _downscale(first.convert("L"), _DELTA_SIDE)
    right = _downscale(second.convert("L"), _DELTA_SIDE)
    histogram = ImageChops.difference(left, right).histogram()
    total = max(1, sum(histogram))
    return sum(histogram[_DELTA_PIXEL_THRESHOLD:]) / total


def _content_sample(image: Image.Image) -> bytes:
    return image.convert("L").resize(_CONTENT_SAMPLE_SIZE, Image.Resampling.BILINEAR).tobytes()


def content_correlation(first: Image.Image, second: Image.Image) -> float:
    """两图灰度归一化互相关（-1–1）：1 表示结构一致。

    用来判断「窗口自己渲染的内容」有没有真的出现在截到的画面里：
    半透明混合后结构仍在 → 相关性高；窗口被隐藏/整块透明 → 只剩背景 → 相关性低。
    """

    left = _content_sample(first)
    right = _content_sample(second)
    count = min(len(left), len(right))
    if count == 0:
        return 0.0
    left_total = sum(left[:count])
    right_total = sum(right[:count])
    left_mean = left_total / count
    right_mean = right_total / count
    numerator = 0.0
    left_square = 0.0
    right_square = 0.0
    for index in range(count):
        left_value = left[index] - left_mean
        right_value = right[index] - right_mean
        numerator += left_value * right_value
        left_square += left_value * left_value
        right_square += right_value * right_value
    denominator = (left_square * right_square) ** 0.5
    if denominator <= 1e-6:
        return 0.0
    return numerator / denominator


@dataclass(frozen=True)
class ContentGap:
    lost: bool
    correlation: float
    window_detail: float
    capture_detail: float
    reason: str


def detect_content_gap(
    capture: Image.Image,
    window: Image.Image,
    thresholds: HealthThresholds = DEFAULT_THRESHOLDS,
) -> ContentGap:
    """对比「桌面截到的区域」与「窗口自身渲染」，判断内容是否被藏掉了。"""

    sample = _CONTENT_SAMPLE_SIZE
    window_gray = window.convert("L").resize(sample, Image.Resampling.BILINEAR)
    capture_gray = capture.convert("L").resize(sample, Image.Resampling.BILINEAR)
    window_detail = float(ImageStat.Stat(window_gray).stddev[0])
    capture_detail = float(ImageStat.Stat(capture_gray).stddev[0])
    correlation = content_correlation(capture, window)
    if window_detail < thresholds.content_window_detail_min:
        return ContentGap(
            lost=False,
            correlation=correlation,
            window_detail=window_detail,
            capture_detail=capture_detail,
            reason=f"窗口自身没有可用内容（细节 {window_detail:.1f}）",
        )
    lost = correlation < thresholds.content_correlation_min
    reason = (
        f"窗口内容与截图相关性 {correlation:.2f}"
        f"（窗口细节 {window_detail:.0f} / 截图细节 {capture_detail:.0f}）"
    )
    return ContentGap(
        lost=lost,
        correlation=correlation,
        window_detail=window_detail,
        capture_detail=capture_detail,
        reason=reason,
    )


@dataclass(frozen=True)
class CaptureDiagnosis:
    """一次截图（可能含多帧）的总体诊断。"""

    kind: str
    reports: tuple[FrameReport, ...]
    deltas: tuple[float, ...]
    best_index: int
    reason: str = ""
    mixed_kind: str = FRAME_OK
    source: str = "capture"

    @property
    def ok(self) -> bool:
        return self.kind == FRAME_OK

    @property
    def severity(self) -> int:
        return SEVERITY.get(self.kind, 0)

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)

    @property
    def repair_kind(self) -> str:
        """真正要修的是哪一种缺陷：闪屏时看底层异常。"""

        return self.mixed_kind if self.kind == ANOMALY_FLICKER else self.kind

    def with_source(self, source: str) -> "CaptureDiagnosis":
        return replace(self, source=source)

    def describe(self) -> str:
        frames = ", ".join(report.label for report in self.reports)
        parts = [f"{self.label}（{frames}）"]
        if self.reason:
            parts.append(self.reason)
        if self.deltas:
            parts.append(f"帧差 {max(self.deltas):.0%}")
        return "；".join(parts)


def _best_index(reports: Sequence[FrameReport]) -> int:
    """正常帧里取细节最丰富的一帧；全都异常时取细节最多的一帧，尽量不丢内容。"""

    best = 0
    best_key = (-1, -1.0)
    for index, report in enumerate(reports):
        key = (1 if report.ok else 0, report.detail)
        if key > best_key:
            best_key = key
            best = index
    return best


def evaluate_frames(
    images: Sequence[Image.Image],
    thresholds: HealthThresholds = DEFAULT_THRESHOLDS,
) -> CaptureDiagnosis:
    """多帧体检：全正常→ok；正常帧与异常帧交替→判定闪屏。"""

    if not images:
        raise ValueError("没有可用于体检的截图帧")

    reports = tuple(analyze_frame(image, thresholds) for image in images)
    deltas = tuple(
        frame_delta_ratio(images[index - 1], images[index]) for index in range(1, len(images))
    )
    best_index = _best_index(reports)
    broken = [report for report in reports if not report.ok]

    if not broken:
        return CaptureDiagnosis(
            kind=FRAME_OK,
            reports=reports,
            deltas=deltas,
            best_index=best_index,
            reason="",
        )

    if len(broken) < len(reports):
        dominant = max(broken, key=lambda report: report.severity)
        reason = f"{len(broken)}/{len(reports)} 帧异常（{dominant.label}），判定闪屏"
        return CaptureDiagnosis(
            kind=ANOMALY_FLICKER,
            mixed_kind=dominant.kind,
            reports=reports,
            deltas=deltas,
            best_index=best_index,
            reason=reason,
        )

    dominant = max(reports, key=lambda report: (report.severity, report.detail))
    return CaptureDiagnosis(
        kind=dominant.kind,
        mixed_kind=dominant.kind,
        reports=reports,
        deltas=deltas,
        best_index=best_index,
        reason=dominant.reason,
    )
