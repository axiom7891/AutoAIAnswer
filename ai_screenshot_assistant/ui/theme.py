"""控制台主题：现代深色 / 浅色两套 QSS。

只做视觉层，不改任何业务控件与信号；由 MainWindow 在启动与切换主题时调用。
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

FONT_STACK = '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif'

_DARK = {
    "bg": "#0e1116",
    "surface": "#161b23",
    "surface2": "#11161e",
    "border": "#232b36",
    "border_strong": "#2c3644",
    "text": "#e8eefb",
    "muted": "#8c99ac",
    "accent": "#35c08a",
    "accent_hover": "#43d29a",
    "accent_text": "#06130d",
}

_LIGHT = {
    "bg": "#f4f6fb",
    "surface": "#ffffff",
    "surface2": "#f8fafd",
    "border": "#e2e8f2",
    "border_strong": "#cfd8e6",
    "text": "#1b2430",
    "muted": "#6b7a90",
    "accent": "#18ad7c",
    "accent_hover": "#149a6d",
    "accent_text": "#ffffff",
}

_QSS_TEMPLATE = """
* {{
    font-family: {font};
}}
QMainWindow, QWidget#Root, QScrollArea {{
    background: {bg};
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QFrame#HeaderCard {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 16px;
}}
QFrame#Card {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 14px;
}}
QLabel {{
    color: {text};
    background: transparent;
}}
QLabel#AppTitle {{
    font-size: 21px;
    font-weight: 700;
    color: {text};
}}
QLabel#AppSubtitle {{
    font-size: 11px;
    color: {muted};
}}
QLabel#CardTitle {{
    font-size: 13px;
    font-weight: 700;
    color: {text};
}}
QLabel#CardHint {{
    font-size: 11px;
    color: {muted};
}}
QLabel#Chip {{
    background: {accent};
    color: {accent_text};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#ChipMuted {{
    background: {surface2};
    color: {muted};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
}}
QPushButton {{
    background: {surface2};
    border: 1px solid {border_strong};
    border-radius: 9px;
    padding: 7px 14px;
    color: {text};
    min-height: 18px;
}}
QPushButton:hover {{
    border-color: {accent};
    color: {text};
}}
QPushButton:pressed {{
    background: {border};
}}
QPushButton:disabled {{
    color: {muted};
    border-color: {border};
    background: transparent;
}}
QPushButton[class="primary"] {{
    background: {accent};
    border: 1px solid {accent};
    color: {accent_text};
    font-weight: 700;
    padding: 9px 18px;
}}
QPushButton[class="primary"]:hover {{
    background: {accent_hover};
    border-color: {accent_hover};
}}
QPushButton[class="ghost"] {{
    background: transparent;
}}
QPushButton[class="danger"] {{
    background: transparent;
    border: 1px solid {border_strong};
    color: {text};
}}
QLineEdit, QComboBox, QSpinBox {{
    background: {surface2};
    border: 1px solid {border_strong};
    border-radius: 8px;
    padding: 6px 10px;
    color: {text};
    min-height: 18px;
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {accent};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {surface};
    border: 1px solid {border_strong};
    border-radius: 8px;
    selection-background-color: {border};
    color: {text};
    outline: none;
}}
QTextEdit {{
    background: {surface2};
    border: 1px solid {border_strong};
    border-radius: 10px;
    padding: 8px;
    color: {text};
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
QCheckBox {{
    spacing: 8px;
    color: {text};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid {border_strong};
    background: {surface2};
}}
QCheckBox::indicator:hover {{
    border-color: {accent};
}}
QCheckBox::indicator:checked {{
    background: {accent};
    border-color: {accent};
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {border};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {accent};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: {accent};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {border_strong};
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {muted};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QToolTip {{
    background: {surface};
    color: {text};
    border: 1px solid {border_strong};
    padding: 6px 8px;
}}
QMenu {{
    background: {surface};
    border: 1px solid {border_strong};
    color: {text};
}}
QMenu::item:selected {{
    background: {border};
}}
"""

DARK_QSS = _QSS_TEMPLATE.format(font=FONT_STACK, **_DARK)
LIGHT_QSS = _QSS_TEMPLATE.format(font=FONT_STACK, **_LIGHT)


def _palette(colors: dict[str, str]) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["surface2"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["surface2"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["accent_text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    return palette


def apply_app_theme(app: QApplication | None, theme: str = "dark") -> str:
    """应用主题并返回实际使用的主题名（dark / light）。"""
    name = "light" if str(theme).lower() == "light" else "dark"
    if app is None:
        return name
    colors = _LIGHT if name == "light" else _DARK
    app.setStyle("Fusion")
    app.setPalette(_palette(colors))
    font = QFont("Microsoft YaHei UI", 10)
    if not font.exactMatch():
        font = QFont(app.font())
        font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(LIGHT_QSS if name == "light" else DARK_QSS)
    return name
