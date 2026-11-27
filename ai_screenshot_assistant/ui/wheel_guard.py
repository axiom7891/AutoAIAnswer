"""鼠标滚轮：停在可选项上时只滚动页面，不改选项值。

做法只有一条：把这些控件的 ``wheelEvent`` 改成 ``ignore()``。Qt 收到未接受的
滚轮事件后会自动往父级传，外层 QScrollArea 照常滚动——不自己 sendEvent，
不会在弹层打开时重入，也就不会崩。

注意：这里**不做**应用级事件过滤，避免把本该滚动的滚轮事件吞掉。
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSlider, QSpinBox


class _WheelSafeMixin:
    """滚轮一律不处理，交给父级滚动区域。"""

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        event.ignore()


class WheelSafeComboBox(_WheelSafeMixin, QComboBox):
    pass


class WheelSafeSpinBox(_WheelSafeMixin, QSpinBox):
    pass


class WheelSafeDoubleSpinBox(_WheelSafeMixin, QDoubleSpinBox):
    pass


class WheelSafeSlider(_WheelSafeMixin, QSlider):
    pass
