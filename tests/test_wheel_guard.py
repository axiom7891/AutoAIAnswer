from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ai_screenshot_assistant.ui.wheel_guard import (
    WheelSafeComboBox,
    WheelSafeSlider,
    WheelSafeSpinBox,
)


def wheel_event(delta: int = -120) -> QWheelEvent:
    return QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def build_scroll_area(widget: QWidget) -> QScrollArea:
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.addWidget(widget)
    filler = QWidget()
    filler.setMinimumHeight(2000)
    layout.addWidget(filler)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(content)
    area.resize(320, 200)
    area.show()
    return area


def test_combo_wheel_is_ignored_so_parent_can_scroll(qapp) -> None:
    combo = WheelSafeComboBox()
    combo.addItems(["a", "b", "c"])
    combo.setCurrentIndex(0)
    area = build_scroll_area(combo)
    qapp.processEvents()

    event = wheel_event(-120)
    combo.wheelEvent(event)

    # 未接受 → Qt 会把它冒泡给外层 QScrollArea，页面照常滚动
    assert event.isAccepted() is False
    assert combo.currentIndex() == 0
    area.close()


def test_combo_with_focus_still_does_not_change_value(qapp) -> None:
    combo = WheelSafeComboBox()
    combo.addItems(["a", "b", "c"])
    combo.setCurrentIndex(0)
    area = build_scroll_area(combo)
    combo.setFocus()
    qapp.processEvents()

    event = wheel_event(-120)
    combo.wheelEvent(event)

    assert event.isAccepted() is False
    assert combo.currentIndex() == 0
    area.close()


def test_spin_wheel_is_ignored(qapp) -> None:
    spin = WheelSafeSpinBox()
    spin.setRange(1, 100)
    spin.setValue(50)
    area = build_scroll_area(spin)
    qapp.processEvents()

    event = wheel_event(-120)
    spin.wheelEvent(event)

    assert event.isAccepted() is False
    assert spin.value() == 50
    area.close()


def test_slider_wheel_is_ignored(qapp) -> None:
    slider = WheelSafeSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(50)
    area = build_scroll_area(slider)
    qapp.processEvents()

    event = wheel_event(-120)
    slider.wheelEvent(event)

    assert event.isAccepted() is False
    assert slider.value() == 50
    area.close()


def test_no_global_event_filter_is_installed() -> None:
    import ai_screenshot_assistant.ui.wheel_guard as module

    assert not hasattr(module, "WheelGuard")
    assert not hasattr(module, "install_wheel_guard")
