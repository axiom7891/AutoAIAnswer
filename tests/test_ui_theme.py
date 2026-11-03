from __future__ import annotations

from pathlib import Path

from ai_screenshot_assistant.ui.theme import DARK_QSS, LIGHT_QSS, apply_app_theme

ROOT = Path(__file__).resolve().parents[1]


def test_dark_theme_defines_core_widgets() -> None:
    for selector in (
        "QFrame#Card",
        "QFrame#HeaderCard",
        "QPushButton[class=\"primary\"]",
        "QLabel#AppTitle",
        "QLabel#Chip",
        "QCheckBox::indicator:checked",
        "QSlider::handle:horizontal",
        "QScrollBar::handle:vertical",
    ):
        assert selector in DARK_QSS


def test_light_theme_is_a_separate_stylesheet() -> None:
    assert LIGHT_QSS != DARK_QSS
    assert "#ffffff" in LIGHT_QSS


def test_apply_theme_returns_normalized_name() -> None:
    assert apply_app_theme(None, "dark") == "dark"
    assert apply_app_theme(None, "light") == "light"
    assert apply_app_theme(None, "unknown") == "dark"


def test_main_window_uses_cards_and_theme_module() -> None:
    source = (ROOT / "ai_screenshot_assistant" / "ui" / "main_window.py").read_text(encoding="utf-8")

    assert "apply_app_theme" in source
    assert "def _make_card" in source
    assert 'setObjectName("Card")' in source
    assert 'setObjectName("HeaderCard")' in source
    assert "setProperty(\"class\", \"primary\")" in source
    assert 'self.status_label.setObjectName("Chip")' in source
    assert 'self.provider_label.setObjectName("ChipMuted")' in source


def test_main_applies_theme_before_window() -> None:
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "apply_app_theme(app" in main_source
    assert "appearance/theme" in main_source


def test_status_chip_truncates_long_messages() -> None:
    source = (ROOT / "ai_screenshot_assistant" / "ui" / "main_window.py").read_text(encoding="utf-8")

    assert "len(text) <= 18" in source
    assert 'self.status_label.setToolTip(text)' in source
