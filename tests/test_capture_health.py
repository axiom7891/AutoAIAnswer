from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from ai_screenshot_assistant.capture.health import (
    ANOMALY_FLICKER,
    FRAME_BLACK,
    FRAME_BLANK,
    FRAME_CONTENT_LOST,
    FRAME_OK,
    FRAME_PARTIAL_BLACK,
    FRAME_TRANSPARENT,
    HealthThresholds,
    analyze_frame,
    content_correlation,
    detect_content_gap,
    evaluate_frames,
    frame_delta_ratio,
)


def question_page(width: int = 800, height: int = 600) -> Image.Image:
    image = Image.new("RGB", (width, height), (250, 250, 248))
    draw = ImageDraw.Draw(image)
    for row in range(12):
        draw.text((40, 40 + row * 30), f"{row + 1}. Question with options A B C D", fill=(18, 18, 18))
    return image


def dark_theme_page(width: int = 800, height: int = 600) -> Image.Image:
    image = Image.new("RGB", (width, height), (8, 8, 10))
    draw = ImageDraw.Draw(image)
    for row in range(12):
        draw.text((40, 40 + row * 30), f"{row + 1}. Bright text on dark background", fill=(235, 235, 235))
    return image


def blacked_out_page() -> Image.Image:
    image = question_page()
    ImageDraw.Draw(image).rectangle([90, 90, 710, 510], fill=(0, 0, 0))
    return image


def test_normal_page_is_ok() -> None:
    report = analyze_frame(question_page())

    assert report.kind == FRAME_OK
    assert report.ok
    assert report.reason == ""
    assert report.detail > 5


def test_dark_theme_with_text_is_not_flagged_as_black() -> None:
    report = analyze_frame(dark_theme_page())

    assert report.kind == FRAME_OK


def test_pure_black_frame_is_detected() -> None:
    report = analyze_frame(Image.new("RGB", (640, 480), (0, 0, 0)))

    assert report.kind == FRAME_BLACK
    assert "全黑" in report.reason


def test_near_black_noise_frame_is_detected() -> None:
    image = Image.new("RGB", (320, 240), (2, 2, 3))
    ImageDraw.Draw(image).rectangle([0, 0, 8, 8], fill=(6, 6, 6))

    assert analyze_frame(image).kind == FRAME_BLACK


def test_uniform_white_frame_is_blank() -> None:
    report = analyze_frame(Image.new("RGB", (640, 480), (255, 255, 255)))

    assert report.kind == FRAME_BLANK
    assert "单一颜色" in report.reason


def test_fully_transparent_frame_is_detected() -> None:
    report = analyze_frame(Image.new("RGBA", (400, 300), (12, 12, 12, 0)))

    assert report.kind == FRAME_TRANSPARENT
    assert report.alpha_coverage == 0.0


def test_partially_transparent_frame_is_not_transparent() -> None:
    image = question_page(400, 300).convert("RGBA")
    ImageDraw.Draw(image).rectangle([0, 0, 199, 299], fill=(0, 0, 0, 0))

    assert analyze_frame(image).kind != FRAME_TRANSPARENT


def test_black_block_inside_content_is_partial_black() -> None:
    report = analyze_frame(blacked_out_page())

    assert report.kind == FRAME_PARTIAL_BLACK
    assert "暗块" in report.reason


def test_black_strip_on_edge_is_not_partial_black() -> None:
    image = question_page()
    ImageDraw.Draw(image).rectangle([0, 0, 799, 120], fill=(0, 0, 0))

    assert analyze_frame(image).kind != FRAME_PARTIAL_BLACK


def test_thresholds_can_be_relaxed_to_accept_black_frame() -> None:
    relaxed = HealthThresholds(
        dark_ratio=1.1,
        dark_mean_luma=-1.0,
        dark_bright_ratio=-1.0,
        blank_dominant_ratio=1.1,
    )

    assert analyze_frame(Image.new("RGB", (64, 64), (0, 0, 0)), relaxed).kind == FRAME_OK


def test_frame_delta_ratio_separates_content_and_black() -> None:
    assert frame_delta_ratio(question_page(), question_page()) < 0.01
    assert frame_delta_ratio(question_page(), Image.new("RGB", (800, 600), (0, 0, 0))) > 0.8


def test_evaluate_all_healthy_frames() -> None:
    diagnosis = evaluate_frames([question_page(), question_page()])

    assert diagnosis.ok
    assert diagnosis.kind == FRAME_OK
    assert diagnosis.best_index == 0
    assert diagnosis.describe()


def test_evaluate_mixed_frames_reports_flicker_and_keeps_healthy_frame() -> None:
    diagnosis = evaluate_frames([Image.new("RGB", (800, 600), (0, 0, 0)), question_page()])

    assert diagnosis.kind == ANOMALY_FLICKER
    assert diagnosis.mixed_kind == FRAME_BLACK
    assert diagnosis.repair_kind == FRAME_BLACK
    assert diagnosis.best_index == 1
    assert "闪屏" in diagnosis.reason
    assert diagnosis.describe()


def test_evaluate_all_broken_frames_reports_dominant_kind() -> None:
    diagnosis = evaluate_frames(
        [Image.new("RGB", (400, 300), (0, 0, 0)), Image.new("RGB", (400, 300), (255, 255, 255))]
    )

    assert diagnosis.kind in {FRAME_BLACK, FRAME_BLANK}
    assert not diagnosis.ok
    assert diagnosis.severity > 0


def test_evaluate_picks_richest_broken_frame_when_nothing_is_healthy() -> None:
    black = Image.new("RGB", (800, 600), (0, 0, 0))
    diagnosis = evaluate_frames([black, blacked_out_page()])

    assert diagnosis.best_index == 1


def test_evaluate_rejects_empty_sequence() -> None:
    with pytest.raises(ValueError):
        evaluate_frames([])


def plain_desktop(width: int = 800, height: int = 600) -> Image.Image:
    image = Image.new("RGB", (width, height), (58, 92, 140))
    ImageDraw.Draw(image).rectangle([0, height - 40, width, height], fill=(30, 30, 34))
    return image


def test_content_correlation_matches_identical_images() -> None:
    page = question_page()

    assert content_correlation(page, page) > 0.99


def test_content_correlation_is_low_for_unrelated_images() -> None:
    assert content_correlation(question_page(), plain_desktop()) < 0.5


def test_detect_content_gap_flags_hidden_window() -> None:
    gap = detect_content_gap(plain_desktop(), question_page())

    assert gap.lost is True
    assert "相关性" in gap.reason
    assert gap.window_detail > 4


def test_detect_content_gap_accepts_normal_capture() -> None:
    page = question_page()

    assert detect_content_gap(page, page).lost is False


def test_detect_content_gap_accepts_faint_blend() -> None:
    page = question_page()
    blended = Image.blend(page, Image.new("RGB", page.size, (255, 255, 255)), 0.7)

    assert detect_content_gap(blended, page).lost is False


def test_detect_content_gap_skips_empty_window() -> None:
    gap = detect_content_gap(question_page(400, 300), Image.new("RGB", (400, 300), (0, 0, 0)))

    assert gap.lost is False
    assert "没有可用内容" in gap.reason


def test_content_lost_kind_is_labelled() -> None:
    assert FRAME_CONTENT_LOST == "content_lost"


def test_diagnosis_with_source_marks_printwindow() -> None:
    diagnosis = evaluate_frames([question_page()]).with_source("printwindow")

    assert diagnosis.source == "printwindow"
    assert diagnosis.ok
