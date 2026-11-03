from __future__ import annotations

import base64
import gc
from pathlib import Path
import secrets
import sys
import threading
import time
from typing import Any

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QPixmap, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai_screenshot_assistant.ai.client import FailoverVisionClient, ProviderConfig
from ai_screenshot_assistant.ai.prompt import VISION_PROMPT
from ai_screenshot_assistant.ai.models import DEFAULT_MODEL_TIER, MODEL_ROUTES, normalize_model_tier, route_options
from ai_screenshot_assistant.backend_api import BackendApi, BackendSession
from ai_screenshot_assistant.bank.question_bank import (
    IMAGE_SUFFIXES,
    QuestionBank,
    default_bank_path,
    import_bank_file,
)
from ai_screenshot_assistant.capture.repair import RepairPolicy
from ai_screenshot_assistant.capture.screenshot import ScreenCapture
from ai_screenshot_assistant.config import settings
from ai_screenshot_assistant.core.messages import Event
from ai_screenshot_assistant.core.workflow import AssistantWorkflow
from ai_screenshot_assistant.desktop_command_client import DesktopCommandClient
from ai_screenshot_assistant.input.mouse_listener import MouseRoiListener
from ai_screenshot_assistant.input.ctrl_listener import CtrlScreenshotListener
from ai_screenshot_assistant.input.remote_keys import RemoteAnswerKeyListener
from ai_screenshot_assistant.input.mac_hotkeys import MacHotkeyListener
from ai_screenshot_assistant.resources import app_icon_path
from ai_screenshot_assistant.ui.auto_capture import (
    DEFAULT_INTERVAL_SECONDS,
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    AutoCaptureScheduler,
    clamp_interval_seconds,
)
from ai_screenshot_assistant.ui.streaming_overlay import StreamingOverlay
from ai_screenshot_assistant.ui.native_capture import apply_window_capture_exclusion
from ai_screenshot_assistant.ui.theme import apply_app_theme
from ai_screenshot_assistant.utils.qrcode_image import QR_DISPLAY_PX, pair_qr_png_bytes
from ai_screenshot_assistant.websocket_client import DesktopWebSocketPublisher

gAppName = str("QQMusic")

class UiSignals(QObject):
    local_update = Signal(object)
    status = Signal(str)
    result = Signal(dict)
    error = Signal(str)
    provider_changed = Signal(str)
    stream_started = Signal()
    stream_delta = Signal(str)
    stream_completed = Signal(str)
    stream_error = Signal(str)
    mobile_fullscreen_requested = Signal(dict)
    ctrl_fullscreen_requested = Signal()
    clear_conversation_requested = Signal()
    model_tier_requested = Signal(str)
    desktop_command_received = Signal(dict)
    mouse_long_left = Signal(int, int)
    mouse_short_left = Signal(int, int)
    mouse_long_right = Signal(int, int)
    analysis_started = Signal()
    analysis_finished = Signal()
    pending_capture_ready = Signal(object, str)
    multi_capture_requested = Signal()
    analyze_cache_requested = Signal()
    repair_report = Signal(str)
    diagnostics_ready = Signal(str)
    auto_capture_toggle_requested = Signal()
    overlay_toggle_requested = Signal()


class MainWindow(QMainWindow):
    def __init__(self, backend_url: str | None = None) -> None:
        super().__init__()
        self.backend_url = backend_url or settings.backend_url
        self.setWindowTitle(gAppName)
        icon = self._app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.setMinimumSize(560, 640)
        self.app_settings = QSettings("AI Screenshot Assistant", "Desktop")

        legacy_key = str(self.app_settings.value("api/key", "") or "")
        self.deepseek_key = str(
            self.app_settings.value("providers/deepseek_key", legacy_key or settings.deepseek_api_key) or ""
        )
        self.openrouter_key = str(
            self.app_settings.value("providers/openrouter_key", settings.openrouter_api_key) or ""
        )
        self.doubao_key = str(
            self.app_settings.value("providers/doubao_key", settings.doubao_api_key) or ""
        )
        self.model_tier = normalize_model_tier(
            str(self.app_settings.value("providers/model_tier", settings.model_tier) or DEFAULT_MODEL_TIER)
        )
        self.system_prompt = str(self.app_settings.value("prompt/system", VISION_PROMPT) or VISION_PROMPT)
        self.ui_font_family = str(self.app_settings.value("appearance/font_family", "系统默认") or "系统默认")
        self.ui_theme = str(self.app_settings.value("appearance/theme", "dark") or "dark")

        self.signals = UiSignals()
        self.signals.local_update.connect(lambda callback: callback())
        self.signals.status.connect(self.set_status)
        self.signals.result.connect(self.show_result)
        self.signals.error.connect(self.show_error)
        self.signals.provider_changed.connect(self._on_provider_failover)
        self.signals.clear_conversation_requested.connect(self._clear_conversation)
        self.signals.model_tier_requested.connect(self._on_model_tier_requested)
        self.signals.desktop_command_received.connect(self._handle_desktop_command)
        self.signals.mouse_long_left.connect(self._left_up)
        self.signals.mouse_short_left.connect(self._second_left_up)
        self.signals.mouse_long_right.connect(self._right_long)
        self.signals.analysis_started.connect(self._on_analysis_started)
        self.signals.analysis_finished.connect(self._on_analysis_finished)
        self.signals.pending_capture_ready.connect(self._on_pending_capture_ready)
        self.signals.multi_capture_requested.connect(self._on_multi_capture_shortcut)
        self.signals.analyze_cache_requested.connect(self._on_analyze_cache_shortcut)
        self.signals.repair_report.connect(self._log)
        self.signals.diagnostics_ready.connect(self._on_diagnostics_ready)
        self.signals.auto_capture_toggle_requested.connect(self._toggle_auto_capture)
        self.signals.overlay_toggle_requested.connect(self._toggle_overlay_shortcut)

        self.overlay = StreamingOverlay(self.app_settings)
        self.overlay.status.connect(self.signals.repair_report.emit)
        self.signals.stream_started.connect(self._on_stream_started)
        self.signals.stream_delta.connect(self.overlay.append_delta)
        self.signals.stream_completed.connect(self.overlay.complete_stream)
        self.signals.stream_error.connect(self.overlay.show_error)

        self.session: BackendSession | None = None
        self.publisher: DesktopWebSocketPublisher | None = None
        self.command_client: DesktopCommandClient | None = None
        self.workflow: AssistantWorkflow | None = None
        self.mouse_listener: MouseRoiListener | None = None
        self.ctrl_listener: CtrlScreenshotListener | None = None
        self.mac_hotkeys: MacHotkeyListener | None = None
        self.remote_keys: RemoteAnswerKeyListener | None = None
        self.remote_pan_enabled = False
        self.ctrl_capture_enabled = self._settings_bool("customer_c/ctrl_capture", True)
        self._force_quit = False
        self.tray_icon: QSystemTrayIcon | None = None
        self.region_gesture_enabled = self._settings_bool("gestures/region_enabled", True)
        self.fullscreen_gesture_enabled = self._settings_bool("gestures/fullscreen_enabled", True)
        self.auto_capture_enabled = self._settings_bool("auto_capture/enabled", False)
        self.auto_capture_seconds = clamp_interval_seconds(
            self.app_settings.value("auto_capture/interval_seconds", DEFAULT_INTERVAL_SECONDS)
        )
        self._capture_lock = threading.Lock()
        self._capture_in_flight = 0
        self.bank_path = default_bank_path()
        self.question_bank = QuestionBank.load(self.bank_path)
        self.bank_enabled = self._settings_bool("bank/enabled", True)
        self.multi_hotkeys_enabled = self._settings_bool("multi_capture/hotkeys_enabled", True)
        self.repair_enabled = self._settings_bool("capture/repair_enabled", settings.capture_repair_enabled)
        self.retry_enabled = self._settings_bool("retry/enabled", True)
        try:
            retry_timeout = int(self.app_settings.value("retry/timeout_seconds", 60) or 60)
        except (TypeError, ValueError):
            retry_timeout = 60
        self.retry_timeout_seconds = max(15, min(300, retry_timeout))
        try:
            retry_max = int(self.app_settings.value("retry/max_attempts", 1) or 1)
        except (TypeError, ValueError):
            retry_max = 1
        self.retry_max_attempts = max(1, min(3, retry_max))
        self._analysis_in_flight = 0
        self._analysis_retries_used = 0
        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self._on_retry_timeout)
        self._pending_lock = threading.Lock()
        self.pending_screenshots: list[bytes] = []
        self.pending_screenshot_labels: list[str] = []
        self.auto_capture_scheduler = AutoCaptureScheduler(
            self._capture_current_screen_from_auto,
            self._capture_busy,
            self,
        )

        self.status_label = QLabel("状态：准备中")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.provider_label = QLabel("当前模型：未配置")
        self.provider_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.deepseek_key_input = QLineEdit(self.deepseek_key)
        self.deepseek_key_input.setEchoMode(QLineEdit.Normal)
        self.deepseek_key_input.setPlaceholderText("可选，DeepSeek Flash 看图")
        self.openrouter_key_input = QLineEdit(self.openrouter_key)
        self.openrouter_key_input.setEchoMode(QLineEdit.Normal)
        self.openrouter_key_input.setPlaceholderText("可选，通义千问 VL")
        self.doubao_key_input = QLineEdit(self.doubao_key)
        self.doubao_key_input.setEchoMode(QLineEdit.Normal)
        self.doubao_key_input.setPlaceholderText("可选，火山方舟 ARK_API_KEY")
        self.model_tier_combo = QComboBox()
        for route_id, vendor, model in route_options():
            self.model_tier_combo.addItem(f"{vendor} · {model}", route_id)
        index = self.model_tier_combo.findData(self.model_tier)
        self.model_tier_combo.setCurrentIndex(index if index >= 0 else 0)
        self._refresh_model_route_availability()
        self.model_tier_combo.currentIndexChanged.connect(self._on_desktop_model_tier)
        self.save_providers_button = QPushButton("保存模型配置")
        self.save_providers_button.clicked.connect(self.save_provider_settings)
        self.save_status = QLabel("")
        self.prompt_input = QTextEdit()
        self.prompt_input.setAcceptRichText(False)
        self.prompt_input.setPlainText(self.system_prompt)
        self.prompt_input.setMinimumHeight(180)
        self.prompt_input.setPlaceholderText("输入系统 Prompt，不限制字数")
        self.save_prompt_button = QPushButton("保存系统 Prompt")
        self.save_prompt_button.clicked.connect(self.save_prompt_settings)
        self.font_combo = QComboBox()
        for family in ("Times New Roman", "系统默认", "Arial", "Microsoft YaHei"):
            self.font_combo.addItem(family, family)
        self.font_combo.setCurrentIndex(max(0, self.font_combo.findData(self.ui_font_family)))
        self.font_combo.currentIndexChanged.connect(self._apply_appearance_settings)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("黑色", "dark")
        self.theme_combo.addItem("白色", "light")
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self.ui_theme)))
        self.theme_combo.currentIndexChanged.connect(self._apply_appearance_settings)
        self.text_color_combo = QComboBox()
        self.text_color_combo.addItem("白色", "white")
        self.text_color_combo.addItem("黑色", "black")
        self.text_color_combo.addItem("蓝色", "blue")
        self.text_color_combo.addItem("红色", "red")
        self.text_color_combo.setCurrentIndex(max(0, self.text_color_combo.findData(self.app_settings.value("overlay/text_color", "white"))))
        self.text_color_combo.currentIndexChanged.connect(self._apply_appearance_settings)
        self.overlay_toggle = QCheckBox("显示桌面流式悬浮答案")
        self.overlay_toggle.toggled.connect(self.set_overlay_visible)
        overlay_visible = self._settings_bool("overlay/visible", True)
        self.console_capture_toggle = QCheckBox("共享屏幕时隐藏控制台")
        self.console_capture_toggle.setChecked(
            self._settings_bool("capture/hide_console", sys.platform in {"darwin", "win32"})
        )
        self.console_capture_toggle.toggled.connect(self.set_console_capture_excluded)
        self.repair_toggle = QCheckBox("截图异常自动修复（黑屏 / 闪屏 / 透明屏）")
        self.repair_toggle.setChecked(self.repair_enabled)
        self.repair_toggle.setToolTip(
            "截图出现全黑、黑块、整屏透明、两帧闪烁，或「看着正常但窗口内容没截进来」（透明/被隐藏窗口）时，"
            "自动给覆盖该区域的窗口注入临时修复补丁"
            "（解除捕获排除、取消 DWM 隐藏、还原图层不透明度、移除 DirectComposition 直出、强制重绘），"
            "然后重新取帧并挑最稳的一帧；补丁在本次截图结束后自动还原。"
        )
        self.repair_toggle.toggled.connect(self.set_capture_repair_enabled)
        if sys.platform != "win32":
            # 窗口注入补丁依赖 Windows 的捕获排除 / DWM / DirectComposition，macOS 没有对应接口。
            self.repair_enabled = False
            self.repair_toggle.setChecked(False)
            self.repair_toggle.setEnabled(False)
            self.repair_toggle.setToolTip(
                "仅 Windows 支持截图异常修复（需要解除其他程序的窗口保护）。"
                "macOS 上截图、字幕、题库、模型等功能正常。"
            )
        self.capture_diagnostics_button = QPushButton("截图诊断")
        self.capture_diagnostics_button.setToolTip(
            "抓取控制台所在屏幕，把覆盖它的窗口、捕获保护状态和 PrintWindow 结果写成一份诊断文件，"
            "用于排查「某个窗口截不到」。报告保存在系统日志目录的 QQMusic\\Logs。"
        )
        self.capture_diagnostics_button.clicked.connect(self._run_capture_diagnostics)
        opacity_percent = int(self.app_settings.value("overlay/opacity_percent", 50) or 50)
        opacity_percent = max(15, min(100, opacity_percent))
        self.opacity_label = QLabel(f"字幕透明度：{opacity_percent}%")
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(15, 100)
        self.opacity_slider.setValue(opacity_percent)
        self.opacity_slider.valueChanged.connect(self._on_overlay_opacity)
        self.overlay.set_opacity_percent(opacity_percent)
        font_px = int(self.app_settings.value("overlay/font_px", 18) or 18)
        font_px = max(8, min(22, font_px))
        self.font_label = QLabel(f"字幕字号：{font_px}px")
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(8, 22)
        self.font_slider.setValue(font_px)
        self.font_slider.valueChanged.connect(self._on_overlay_font)
        self.overlay.set_font_px(font_px)
        self.region_gesture_toggle = QCheckBox("开启左键长按 2 秒框选手势")
        self.region_gesture_toggle.setChecked(self.region_gesture_enabled)
        self.region_gesture_toggle.toggled.connect(self.set_region_gesture_enabled)
        self.fullscreen_gesture_toggle = QCheckBox("开启右键长按 2 秒全屏截图手势")
        self.fullscreen_gesture_toggle.setChecked(self.fullscreen_gesture_enabled)
        self.fullscreen_gesture_toggle.toggled.connect(self.set_fullscreen_gesture_enabled)
        self.fullscreen_button = QPushButton("截取当前屏幕")
        self.fullscreen_button.clicked.connect(self._capture_current_screen)
        self.multi_capture_button = QPushButton("连续截图")
        self.multi_capture_button.setToolTip("截取当前屏幕并加入多图缓存；滚动页面后再次点击，最多 5 张。")
        self.multi_capture_button.clicked.connect(self._capture_multi_screenshot)
        self.analyze_pending_button = QPushButton("分析缓存（0）")
        self.analyze_pending_button.setEnabled(False)
        self.analyze_pending_button.clicked.connect(self._analyze_pending_screenshots)
        self.clear_pending_button = QPushButton("清空缓存")
        self.clear_pending_button.setEnabled(False)
        self.clear_pending_button.clicked.connect(self._clear_pending_screenshots)
        self.multi_hotkeys_toggle = QCheckBox("启用多图快捷键")
        self.multi_hotkeys_toggle.setChecked(self.multi_hotkeys_enabled)
        self.multi_hotkeys_toggle.setToolTip(
            "Ctrl+Shift+鼠标左键：连续截图；Ctrl+Shift+鼠标右键：分析缓存。快捷键在控制台最小化到托盘时仍生效。"
        )
        self.multi_hotkeys_toggle.toggled.connect(self._set_multi_hotkeys_enabled)
        self.remote_arrows_toggle = QCheckBox("方向键 ↑ ↓ ← → 直接遥控手机答案框（不用组合键）")
        self.remote_arrows_toggle.setChecked(self._settings_bool("phone/arrow_remote", True))
        self.remote_arrows_toggle.setToolTip(
            "勾选后，电脑上按方向键即可滚动手机端答案框：↑/↓ 翻页，←/→ 代码左右滚。"
            "不需要按住 Ctrl 或 Alt；其他软件里的方向键仍照常使用。"
        )
        self.remote_arrows_toggle.toggled.connect(self.set_remote_arrows_enabled)
        self.retry_toggle = QCheckBox("分析超时自动重试")
        self.retry_toggle.setChecked(self.retry_enabled)
        self.retry_toggle.setToolTip("截图后超过设定秒数仍未返回答案时，自动用同一张截图重新分析。")
        self.retry_timeout_spin = QSpinBox()
        self.retry_timeout_spin.setRange(15, 300)
        self.retry_timeout_spin.setSuffix(" 秒")
        self.retry_timeout_spin.setValue(self.retry_timeout_seconds)
        self.retry_attempts_spin = QSpinBox()
        self.retry_attempts_spin.setRange(1, 3)
        self.retry_attempts_spin.setSuffix(" 次")
        self.retry_attempts_spin.setValue(self.retry_max_attempts)
        self.retry_toggle.toggled.connect(self._set_retry_enabled)
        self.retry_timeout_spin.valueChanged.connect(self._set_retry_timeout)
        self.retry_attempts_spin.valueChanged.connect(self._set_retry_attempts)
        self.auto_capture_toggle = QCheckBox("自动截全屏")
        self.auto_capture_toggle.setChecked(self.auto_capture_enabled)
        self.auto_capture_toggle.setToolTip(
            "开启后按设定间隔自动截取控制台所在屏幕并发送给 AI；上一次截图或分析尚未完成时会跳过本次。"
        )
        self.auto_capture_interval_spin = QSpinBox()
        self.auto_capture_interval_spin.setRange(MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS)
        self.auto_capture_interval_spin.setSuffix(" 秒")
        self.auto_capture_interval_spin.setValue(self.auto_capture_seconds)
        self.auto_capture_interval_spin.setToolTip("自动截全屏的间隔（1–3600 秒）；间隔过短会快速消耗模型额度。")
        self.auto_capture_toggle.toggled.connect(self._set_auto_capture_enabled)
        self.auto_capture_interval_spin.valueChanged.connect(self._set_auto_capture_interval)
        self.bank_toggle = QCheckBox("题库优先")
        self.bank_toggle.setChecked(self.bank_enabled)
        self.bank_toggle.setToolTip("开启后先匹配本地题库，命中则直接返回题库答案，不再调用模型。")
        self.bank_toggle.toggled.connect(self._set_bank_enabled)
        self.bank_status_label = QLabel()
        self.bank_status_label.setWordWrap(True)
        self.upload_bank_button = QPushButton("上传题库")
        self.upload_bank_button.setToolTip(
            "支持 CSV/TSV/TXT/JSON/Excel/PDF/Word（题目、答案两列），也支持选择题目截图后逐张填写答案。"
        )
        self.upload_bank_button.clicked.connect(self._upload_question_bank)
        self.clear_bank_button = QPushButton("清空题库")
        self.clear_bank_button.clicked.connect(self._clear_question_bank)
        self.mobile_label = QLabel("手机端：正在创建配对链接")
        self.mobile_label.setWordWrap(True)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setScaledContents(False)
        self.qr_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.qr_label.setContentsMargins(12, 12, 12, 12)
        self.qr_label.setFixedSize(QR_DISPLAY_PX + 24, QR_DISPLAY_PX + 24)
        self.qr_label.setStyleSheet("QLabel { background: #ffffff; border-radius: 12px; }")
        self.qr_label.setVisible(False)
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMinimumHeight(72)
        self.logs.setMaximumHeight(140)
        self.logs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.logs.document().setMaximumBlockCount(80)
        self.clear_chat_button = QPushButton("清空对话记录")
        self.clear_chat_button.clicked.connect(self._clear_conversation)

        provider_form = QFormLayout()
        provider_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        provider_form.setHorizontalSpacing(14)
        provider_form.setVerticalSpacing(8)
        provider_form.addRow("DeepSeek Key（可选）", self.deepseek_key_input)
        provider_form.addRow("OpenRouter Key（可选）", self.openrouter_key_input)
        provider_form.addRow("豆包 Key（可选）", self.doubao_key_input)
        provider_form.addRow("模型", self.model_tier_combo)

        save_row = QHBoxLayout()
        save_row.setSpacing(10)
        save_row.addWidget(self.save_providers_button)
        save_row.addWidget(self.save_status, 1)

        appearance_row = QHBoxLayout()
        appearance_row.setSpacing(8)
        appearance_row.addWidget(QLabel("字体"))
        appearance_row.addWidget(self.font_combo)
        appearance_row.addWidget(QLabel("控制台主题"))
        appearance_row.addWidget(self.theme_combo)
        appearance_row.addWidget(QLabel("字幕文字"))
        appearance_row.addWidget(self.text_color_combo)
        appearance_row.addStretch(1)

        repair_row = QHBoxLayout()
        repair_row.setSpacing(10)
        repair_row.addWidget(self.repair_toggle)
        repair_row.addWidget(self.capture_diagnostics_button)
        repair_row.addStretch(1)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.opacity_label)
        opacity_row.addWidget(self.opacity_slider, 1)

        font_row = QHBoxLayout()
        font_row.addWidget(self.font_label)
        font_row.addWidget(self.font_slider, 1)

        multi_row = QHBoxLayout()
        multi_row.setSpacing(10)
        multi_row.addWidget(self.multi_capture_button)
        multi_row.addWidget(self.analyze_pending_button)
        multi_row.addWidget(self.clear_pending_button)
        multi_row.addStretch(1)

        multi_hint = QLabel("资料分析：滚动页面后连续截图（最多 5 张），再点「分析缓存」一起发送。")
        multi_hint.setObjectName("CardHint")
        multi_hint.setWordWrap(True)

        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(10)
        hotkey_row.addWidget(self.multi_hotkeys_toggle)
        hotkey_row.addStretch(1)

        hotkey_hint = QLabel(
            "Ctrl+Shift+左键 连续截图 · Ctrl+Shift+右键 分析缓存 · "
            "Ctrl+Alt+O 显示/隐藏字幕 · 鼠标中键长按 1 秒 开关自动截屏 · "
            "方向键 ↑↓←→ 滚动手机答案框"
        )
        hotkey_hint.setObjectName("CardHint")
        hotkey_hint.setWordWrap(True)

        auto_capture_row = QHBoxLayout()
        auto_capture_row.setSpacing(8)
        auto_capture_row.addWidget(self.auto_capture_toggle)
        auto_capture_row.addWidget(QLabel("每"))
        auto_capture_row.addWidget(self.auto_capture_interval_spin)
        auto_capture_row.addStretch(1)

        retry_row = QHBoxLayout()
        retry_row.setSpacing(8)
        retry_row.addWidget(self.retry_toggle)
        retry_row.addWidget(QLabel("超过"))
        retry_row.addWidget(self.retry_timeout_spin)
        retry_row.addWidget(QLabel("仍未出答案时自动重试"))
        retry_row.addWidget(self.retry_attempts_spin)
        retry_row.addStretch(1)

        bank_row = QHBoxLayout()
        bank_row.setSpacing(10)
        bank_row.addWidget(self.bank_toggle)
        bank_row.addWidget(self.bank_status_label, 1)
        bank_buttons = QHBoxLayout()
        bank_buttons.setSpacing(10)
        bank_buttons.addWidget(self.upload_bank_button)
        bank_buttons.addWidget(self.clear_bank_button)
        bank_buttons.addStretch(1)

        mobile_row = QHBoxLayout()
        mobile_row.setSpacing(10)
        mobile_row.addWidget(self.mobile_label, 1)
        self.copy_mobile_button = QPushButton("复制网址")
        self.copy_mobile_button.setProperty("class", "ghost")
        self.copy_mobile_button.setEnabled(False)
        self.copy_mobile_button.clicked.connect(self._copy_mobile_url)
        mobile_row.addWidget(self.copy_mobile_button)

        qr_wrap = QWidget()
        qr_wrap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        qr_layout = QVBoxLayout(qr_wrap)
        qr_layout.setContentsMargins(0, 6, 0, 6)
        qr_layout.addWidget(self.qr_label, 0, Qt.AlignmentFlag.AlignHCenter)

        gesture_hint = QLabel(self._gesture_hint_text())
        gesture_hint.setObjectName("CardHint")
        gesture_hint.setWordWrap(True)

        if sys.platform == "win32":
            self.ctrl_capture_toggle = QCheckBox("Ctrl 单键松开截全屏搜题（客户 C）")
            self.ctrl_capture_toggle.setChecked(self.ctrl_capture_enabled)
            self.ctrl_capture_toggle.toggled.connect(self._set_ctrl_capture_enabled)

        self.fullscreen_button.setProperty("class", "primary")
        self.fullscreen_button.setMinimumHeight(40)
        self.multi_capture_button.setProperty("class", "ghost")
        self.analyze_pending_button.setProperty("class", "ghost")
        self.clear_pending_button.setProperty("class", "ghost")
        self.save_providers_button.setProperty("class", "primary")
        self.save_prompt_button.setProperty("class", "primary")
        self.upload_bank_button.setProperty("class", "ghost")
        self.clear_bank_button.setProperty("class", "ghost")
        self.clear_chat_button.setProperty("class", "ghost")
        for checkbox in (
            self.overlay_toggle,
            self.console_capture_toggle,
            self.repair_toggle,
            self.remote_arrows_toggle,
            self.region_gesture_toggle,
            self.fullscreen_gesture_toggle,
            self.multi_hotkeys_toggle,
            self.retry_toggle,
            self.auto_capture_toggle,
            self.bank_toggle,
        ):
            checkbox.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout()
        root.setContentsMargins(22, 20, 22, 22)
        root.setSpacing(14)

        header = QFrame()
        header.setObjectName("HeaderCard")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(20, 18, 20, 18)
        header_row.setSpacing(12)
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        app_title = QLabel(gAppName)
        app_title.setObjectName("AppTitle")
        app_subtitle = QLabel("截图即答 · 手机同步 · 悬浮字幕")
        app_subtitle.setObjectName("AppSubtitle")
        title_box.addWidget(app_title)
        title_box.addWidget(app_subtitle)
        header_row.addLayout(title_box, 1)
        chip_box = QVBoxLayout()
        chip_box.setSpacing(6)
        self.status_label.setObjectName("Chip")
        self.provider_label.setObjectName("ChipMuted")
        chip_box.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignRight)
        chip_box.addWidget(self.provider_label, 0, Qt.AlignmentFlag.AlignRight)
        header_row.addLayout(chip_box)
        root.addWidget(header)

        actions_card, actions_body = self._make_card(
            "快捷操作", "点一下就能截屏分析；手势、托盘菜单与手机端同样可用。"
        )
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self.fullscreen_button, 2)
        action_row.addWidget(self.multi_capture_button, 1)
        actions_body.addLayout(action_row)
        actions_body.addLayout(multi_row)
        actions_body.addWidget(multi_hint)
        root.addWidget(actions_card)

        phone_card, phone_body = self._make_card(
            "手机端", "手机与电脑连同一个 WiFi，扫码后答案实时同步；方向键可直接遥控手机答案框。"
        )
        phone_body.addLayout(mobile_row)
        phone_body.addWidget(qr_wrap, 0, Qt.AlignmentFlag.AlignHCenter)
        phone_body.addWidget(self.remote_arrows_toggle)
        root.addWidget(phone_card)

        model_card, model_body = self._make_card("模型与密钥", "Key 只保存在本机，填任意一个即可开始。")
        model_body.addLayout(provider_form)
        model_body.addLayout(save_row)
        root.addWidget(model_card)

        capture_card, capture_body = self._make_card("截图与手势")
        capture_body.addWidget(self.region_gesture_toggle)
        capture_body.addWidget(self.fullscreen_gesture_toggle)
        if sys.platform == "win32":
            capture_body.addWidget(self.ctrl_capture_toggle)
        capture_body.addLayout(auto_capture_row)
        capture_body.addLayout(repair_row)
        capture_body.addLayout(retry_row)
        root.addWidget(capture_card)

        overlay_card, overlay_body = self._make_card("悬浮字幕", "共享屏幕时字幕不会被录制进去。")
        overlay_body.addWidget(self.overlay_toggle)
        overlay_body.addWidget(self.console_capture_toggle)
        overlay_body.addLayout(opacity_row)
        overlay_body.addLayout(font_row)
        root.addWidget(overlay_card)

        appearance_card, appearance_body = self._make_card("外观")
        appearance_body.addLayout(appearance_row)
        root.addWidget(appearance_card)

        bank_card, bank_body = self._make_card("题库", "命中题库时直接返回答案，不再调用模型。")
        bank_body.addLayout(bank_row)
        bank_body.addLayout(bank_buttons)
        root.addWidget(bank_card)

        hotkey_card, hotkey_body = self._make_card("快捷键")
        hotkey_body.addLayout(hotkey_row)
        hotkey_body.addWidget(hotkey_hint)
        hotkey_body.addWidget(gesture_hint)
        root.addWidget(hotkey_card)

        prompt_card, prompt_body = self._make_card("系统 Prompt", "可编辑，不限字数；保存后对后续分析生效。")
        prompt_body.addWidget(self.prompt_input)
        prompt_body.addWidget(self.save_prompt_button)
        root.addWidget(prompt_card)

        log_card, log_body = self._make_card("运行日志")
        log_body.addWidget(self.logs)
        log_body.addWidget(self.clear_chat_button)
        root.addWidget(log_card)

        root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

        content = QWidget()
        content.setObjectName("Root")
        content.setLayout(root)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        self.setCentralWidget(scroll)
        self.signals.mobile_fullscreen_requested.connect(self._capture_current_screen_from_mobile)
        self.signals.ctrl_fullscreen_requested.connect(
            self._capture_from_ctrl, Qt.ConnectionType.QueuedConnection,
        )
        self._setup_tray_icon()
        self._setup_workflow()
        self._setup_platform_hotkeys()
        self._apply_auto_capture_setting()
        self._refresh_bank_status()
        self._update_pending_buttons()
        self._apply_appearance_settings()
        self.overlay_toggle.setChecked(overlay_visible)
        QTimer.singleShot(250, self._apply_console_capture_setting)
        QTimer.singleShot(600, self._maybe_prompt_macos_permissions)

    def _make_card(self, title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
        """视觉分组卡片：圆角容器 + 标题 + 副标题 + 内容区。"""
        card = QFrame()
        card.setObjectName("Card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(9)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")
            outer.addWidget(title_label)
        if subtitle:
            hint = QLabel(subtitle)
            hint.setObjectName("CardHint")
            hint.setWordWrap(True)
            outer.addWidget(hint)
        body = QVBoxLayout()
        body.setSpacing(8)
        outer.addLayout(body)
        return card, body

    def _setup_tray_icon(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._log("System tray unavailable; close will exit directly")
            return
        icon = self._app_icon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(icon)
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.show_main_window)
        capture_action = QAction("截取当前屏幕", self)
        capture_action.triggered.connect(self._capture_current_screen)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_from_tray)
        menu = QMenu(self)
        menu.addAction(show_action)
        menu.addAction(capture_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip(gAppName)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.show_main_window()

    def show_main_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(100, self._apply_console_capture_setting)

    def quit_from_tray(self) -> None:
        self._force_quit = True
        self.close()
        QApplication.quit()

    def _app_icon(self) -> QIcon:
        icon_path = app_icon_path()
        if icon_path is not None:
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon
        icon = QApplication.windowIcon()
        if not icon.isNull():
            return icon
        return QIcon()

    def _settings_bool(self, key: str, default: bool) -> bool:
        value = self.app_settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _build_ai_client(self) -> FailoverVisionClient:
        deepseek = ProviderConfig(
            name="DeepSeek",
            api_key=self.deepseek_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            timeout_seconds=settings.request_timeout_seconds,
            system_prompt=self.system_prompt,
        )
        openrouter = ProviderConfig(
            name="OpenRouter",
            api_key=self.openrouter_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_model,
            timeout_seconds=settings.request_timeout_seconds,
            system_prompt=self.system_prompt,
        )
        doubao = ProviderConfig(
            name="Doubao",
            api_key=self.doubao_key,
            base_url=settings.doubao_base_url,
            model=settings.doubao_model,
            timeout_seconds=settings.request_timeout_seconds,
            system_prompt=self.system_prompt,
        )
        return FailoverVisionClient(
            deepseek,
            openrouter,
            on_provider_changed=lambda name: self.signals.provider_changed.emit(name),
            model_tier=self.model_tier,
            doubao=doubao,
        )

    def save_prompt_settings(self) -> None:
        self.system_prompt = self.prompt_input.toPlainText() or VISION_PROMPT
        self.prompt_input.setPlainText(self.system_prompt)
        self.app_settings.setValue("prompt/system", self.system_prompt)
        self.app_settings.sync()
        if self.workflow is not None:
            self.workflow.ai_client = self._build_ai_client()
        self.save_status.setText("系统 Prompt 已保存")
        self.save_status.setStyleSheet("color: #198754;")

    def _copy_mobile_url(self) -> None:
        if self.session is not None:
            QApplication.clipboard().setText(self.session.pair_url)
            self.copy_mobile_button.setText("已复制")
            QTimer.singleShot(1500, lambda: self.copy_mobile_button.setText("复制网址"))

    def _apply_appearance_settings(self) -> None:
        self.ui_font_family = str(self.font_combo.currentData() or "系统默认")
        self.ui_theme = str(self.theme_combo.currentData() or "dark")
        self.app_settings.setValue("appearance/font_family", self.ui_font_family)
        self.app_settings.setValue("appearance/theme", self.ui_theme)
        self.app_settings.sync()
        self.setFont(QFont(self.ui_font_family, 12) if self.ui_font_family != "系统默认" else QApplication.font())
        text_color = str(self.text_color_combo.currentData())
        self.app_settings.setValue("overlay/text_color", text_color)
        self.app_settings.sync()
        self.overlay.set_text_appearance(self.ui_font_family, text_color)
        apply_app_theme(QApplication.instance(), self.ui_theme)
        if self.ui_font_family != "系统默认":
            self.setFont(QFont(self.ui_font_family, 12))
    def save_provider_settings(self) -> None:
        deepseek_key = self.deepseek_key_input.text().strip()
        openrouter_key = self.openrouter_key_input.text().strip()
        doubao_key = self.doubao_key_input.text().strip()
        if not deepseek_key and not openrouter_key and not doubao_key:
            self.save_status.setText("请至少填写 DeepSeek、OpenRouter 或豆包其中一把 Key")
            self.save_status.setStyleSheet("color: #d33;")
            return
        self.deepseek_key = deepseek_key
        self.openrouter_key = openrouter_key
        self.doubao_key = doubao_key
        self._refresh_model_route_availability()
        self.model_tier = normalize_model_tier(self.model_tier_combo.currentData())
        self.app_settings.setValue("providers/deepseek_key", deepseek_key)
        self.app_settings.setValue("providers/openrouter_key", openrouter_key)
        self.app_settings.setValue("providers/doubao_key", doubao_key)
        self.app_settings.setValue("providers/model_tier", self.model_tier)
        self.app_settings.sync()
        client = self._build_ai_client()
        if self.workflow is not None:
            self.workflow.ai_client = client
        self._refresh_provider_label()
        self._publish_model_changed()
        choice = getattr(client, "model_choice", None)
        display = getattr(choice, "display_name", "") if choice is not None else ""
        self.save_status.setText(f"已保存；{display}" if display else "已保存")
        self.save_status.setStyleSheet("color: #198754;")
        self._log("Provider settings updated")

    def set_provider(self, provider: str) -> None:
        self._refresh_provider_label(provider)

    def _refresh_model_route_availability(self) -> None:
        has_provider = {
            "doubao": bool(self.doubao_key.strip()),
            "openrouter": bool(self.openrouter_key.strip()),
            "deepseek": bool(self.deepseek_key.strip()),
        }
        for index, (route_id, vendor, model_name) in enumerate(route_options()):
            available = has_provider.get(MODEL_ROUTES[route_id].provider, False)
            suffix = "" if available else "（你还没有连接模型喔）"
            self.model_tier_combo.setItemText(index, f"{vendor} · {model_name}{suffix}")
            item = self.model_tier_combo.model().item(index)
            if item is not None:
                item.setEnabled(available)
        current_item = self.model_tier_combo.model().item(self.model_tier_combo.currentIndex())
        if current_item is not None and not current_item.isEnabled():
            for index in range(self.model_tier_combo.count()):
                item = self.model_tier_combo.model().item(index)
                if item is not None and item.isEnabled():
                    self.model_tier_combo.setCurrentIndex(index)
                    self.model_tier = normalize_model_tier(self.model_tier_combo.currentData())
                    break

    def _refresh_provider_label(self, provider: str | None = None) -> None:
        client = self.workflow.ai_client if self.workflow is not None else None
        choice = getattr(client, "model_choice", None)
        current = provider or getattr(client, "current_provider", "none")
        if choice is not None and getattr(choice, "display_name", ""):
            if current not in {None, "", choice.provider} and current != "none":
                model = client.current_model_id() if client is not None and hasattr(client, "current_model_id") else choice.model
                vendor = {"openrouter": "OpenRouter", "deepseek": "DeepSeek", "doubao": "豆包"}.get(current, current)
                self.provider_label.setText(f"当前模型：{vendor} / {model}" if model else f"当前模型：{vendor}")
                return
            self.provider_label.setText(f"当前模型：{choice.display_name}")
            return
        model = ""
        if client is not None and hasattr(client, "current_model_id"):
            model = client.current_model_id()
        vendor = {"openrouter": "OpenRouter", "deepseek": "DeepSeek", "doubao": "豆包"}.get(current)
        if vendor and model:
            self.provider_label.setText(f"当前模型：{vendor} / {model}")
        elif vendor:
            self.provider_label.setText(f"当前模型：{vendor}")
        else:
            self.provider_label.setText("当前模型：未配置 Key")

    def _on_provider_failover(self, provider: str) -> None:
        self.set_provider(provider)
        vendor = {"openrouter": "OpenRouter", "deepseek": "DeepSeek", "doubao": "豆包"}.get(provider, provider)
        self._log(f"额度不足，已切换到 {vendor}")

    def set_overlay_visible(self, visible: bool) -> None:
        self.app_settings.setValue("overlay/visible", visible)
        if visible:
            self.overlay.show()
        else:
            self.overlay.hide()

    def set_console_capture_excluded(self, enabled: bool) -> None:
        self.app_settings.setValue("capture/hide_console", enabled)
        self.app_settings.sync()
        QTimer.singleShot(0, self._apply_console_capture_setting)

    def _apply_console_capture_setting(self) -> None:
        enabled = self.console_capture_toggle.isChecked()
        ok, status = apply_window_capture_exclusion(self, enabled)
        if sys.platform in {"darwin", "win32"} and not ok:
            self._log(f"控制台捕获设置失败：{status}")

    def set_capture_repair_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled) and sys.platform == "win32"
        self.repair_enabled = enabled
        self.app_settings.setValue("capture/repair_enabled", self.repair_enabled)
        self.app_settings.sync()
        capture = getattr(self.workflow, "capture", None) if self.workflow is not None else None
        if capture is not None and hasattr(capture, "set_repair_enabled"):
            capture.set_repair_enabled(self.repair_enabled)
        self._log(f"截图异常自动修复：{'开启' if self.repair_enabled else '关闭'}")

    def _run_capture_diagnostics(self) -> None:
        if self.workflow is None:
            return
        center = self.frameGeometry().center()
        self._log("截图诊断：正在采集现场信息…")

        def worker() -> None:
            try:
                import mss

                from ai_screenshot_assistant.capture.screenshot import monitor_containing_point

                with mss.mss() as sct:
                    monitor = monitor_containing_point(sct.monitors, center.x(), center.y())
                path = self.workflow.capture.dump_diagnostics(monitor)
            except Exception as exc:
                self.signals.repair_report.emit(f"截图诊断失败：{exc}")
                return
            if path is None:
                self.signals.repair_report.emit("截图诊断失败：无法写出报告")
                return
            self.signals.diagnostics_ready.emit(str(path))

        threading.Thread(target=worker, daemon=True).start()

    def _on_diagnostics_ready(self, path: str) -> None:
        self._log(f"截图诊断报告：{path}")
        if self.isVisible():
            QMessageBox.information(self, "截图诊断", f"报告已保存：\n{path}")

    def _toggle_auto_capture(self) -> None:
        """鼠标中键长按 1 秒：开关「自动截全屏」。"""

        self.auto_capture_toggle.setChecked(not self.auto_capture_toggle.isChecked())

    def _toggle_overlay_shortcut(self) -> None:
        """Ctrl+Alt+O：显示/隐藏桌面悬浮字幕（与勾选框保持一致）。"""

        self.overlay_toggle.setChecked(not self.overlay_toggle.isChecked())
        self._log(f"悬浮字幕：{'显示' if self.overlay_toggle.isChecked() else '隐藏'}（快捷键）")

    def _on_overlay_opacity(self, percent: int) -> None:
        self.opacity_label.setText(f"字幕透明度：{percent}%")
        self.app_settings.setValue("overlay/opacity_percent", percent)
        self.overlay.set_opacity_percent(percent)

    def _on_overlay_font(self, size: int) -> None:
        self.font_label.setText(f"字幕字号：{size}px")
        self.app_settings.setValue("overlay/font_px", max(8, min(22, size)))
        self.overlay.set_font_px(size)

    def _on_capture_finished(self) -> None:
        if self.mouse_listener is not None:
            self.mouse_listener.set_enabled(True)
        capture = getattr(self.workflow, "capture", None) if self.workflow is not None else None
        take_report = getattr(capture, "take_report", None)
        if callable(take_report):
            report = take_report()
            if report:
                # 截图线程里回调，交给主线程写日志控件。
                self.signals.repair_report.emit(report)

    def _on_stream_started(self) -> None:
        # Overlay visibility is owned only by 「显示桌面流式悬浮答案」.
        # Streaming must not show/raise it, or the main console comes forward too.
        self.overlay.start_stream()

    def set_region_gesture_enabled(self, enabled: bool) -> None:
        self.region_gesture_enabled = enabled
        self.app_settings.setValue("gestures/region_enabled", enabled)
        self.app_settings.sync()

    def set_fullscreen_gesture_enabled(self, enabled: bool) -> None:
        self.fullscreen_gesture_enabled = enabled
        self.app_settings.setValue("gestures/fullscreen_enabled", enabled)
        self.app_settings.sync()
        self._log(f"右键全屏手势：{'开启' if enabled else '关闭'}")

    def _set_auto_capture_enabled(self, enabled: bool) -> None:
        self.auto_capture_enabled = enabled
        self.app_settings.setValue("auto_capture/enabled", enabled)
        self.app_settings.sync()
        self._apply_auto_capture_setting()
        if enabled:
            self._log(f"自动截全屏：开启，每 {self.auto_capture_seconds} 秒")
        else:
            self._log("自动截全屏：关闭")

    def _set_auto_capture_interval(self, seconds: int) -> None:
        self.auto_capture_seconds = clamp_interval_seconds(seconds)
        self.app_settings.setValue("auto_capture/interval_seconds", self.auto_capture_seconds)
        self.app_settings.sync()
        if self.auto_capture_enabled:
            self._apply_auto_capture_setting()
            self._log(f"自动截全屏：间隔已改为 {self.auto_capture_seconds} 秒")

    def _apply_auto_capture_setting(self) -> None:
        if self.auto_capture_enabled:
            self.auto_capture_scheduler.start(self.auto_capture_seconds)
        else:
            self.auto_capture_scheduler.stop()

    def _capture_current_screen_from_auto(self) -> None:
        self._log("自动截全屏：已触发")
        self._capture_current_screen()

    def _mark_capture_started(self) -> None:
        with self._capture_lock:
            self._capture_in_flight += 1

    def _mark_capture_finished(self) -> None:
        with self._capture_lock:
            self._capture_in_flight = max(0, self._capture_in_flight - 1)

    def _capture_busy(self) -> bool:
        with self._capture_lock:
            return self._capture_in_flight > 0

    def _set_retry_enabled(self, enabled: bool) -> None:
        self.retry_enabled = enabled
        self.app_settings.setValue("retry/enabled", enabled)
        self.app_settings.sync()
        if not enabled:
            self.retry_timer.stop()
        elif self._analysis_in_flight > 0:
            self.retry_timer.start(self.retry_timeout_seconds * 1000)
        self._log(f"分析超时自动重试：{'开启' if enabled else '关闭'}")

    def _set_retry_timeout(self, seconds: int) -> None:
        self.retry_timeout_seconds = max(15, min(300, int(seconds)))
        self.app_settings.setValue("retry/timeout_seconds", self.retry_timeout_seconds)
        self.app_settings.sync()
        if self.retry_enabled and self._analysis_in_flight > 0:
            self.retry_timer.start(self.retry_timeout_seconds * 1000)

    def _set_retry_attempts(self, attempts: int) -> None:
        self.retry_max_attempts = max(1, min(3, int(attempts)))
        self.app_settings.setValue("retry/max_attempts", self.retry_max_attempts)
        self.app_settings.sync()

    def _reset_analysis_retry(self) -> None:
        self._analysis_retries_used = 0

    def _on_analysis_started(self) -> None:
        self._analysis_in_flight += 1
        if self._analysis_in_flight == 1 and self.retry_enabled:
            self.retry_timer.start(self.retry_timeout_seconds * 1000)

    def _on_analysis_finished(self) -> None:
        self._analysis_in_flight = max(0, self._analysis_in_flight - 1)
        if self._analysis_in_flight == 0:
            self.retry_timer.stop()

    def _on_retry_timeout(self) -> None:
        if not self.retry_enabled or self._analysis_in_flight <= 0:
            self.retry_timer.stop()
            return
        if self._analysis_retries_used >= self.retry_max_attempts:
            self.set_status("分析超时：已达到最大重试次数，请重新截图")
            self.retry_timer.stop()
            return
        self._analysis_retries_used += 1
        self.set_status(
            f"分析超时，正在自动重试（{self._analysis_retries_used}/{self.retry_max_attempts}）"
        )
        threading.Thread(target=self._run_retry_analysis, daemon=True).start()
        self.retry_timer.start(self.retry_timeout_seconds * 1000)

    def _run_retry_analysis(self) -> None:
        if self.workflow is None:
            return
        try:
            started = self.workflow.retry_last_analysis()
        except Exception as exc:
            self.signals.error.emit(f"自动重试失败：{exc}")
            return
        if not started:
            self.signals.status.emit("自动重试失败：没有可重试的截图")

    def _set_multi_hotkeys_enabled(self, enabled: bool) -> None:
        self.multi_hotkeys_enabled = enabled
        self.app_settings.setValue("multi_capture/hotkeys_enabled", enabled)
        self.app_settings.sync()
        if self.mouse_listener is not None:
            self.mouse_listener.set_shortcuts_enabled(enabled)
        self._log(f"多图快捷键：{'开启' if enabled else '关闭'}")

    def _on_multi_capture_shortcut(self) -> None:
        if self.multi_hotkeys_enabled:
            self._capture_multi_screenshot()

    def _on_analyze_cache_shortcut(self) -> None:
        if self.multi_hotkeys_enabled:
            self._analyze_pending_screenshots()

    def _capture_multi_screenshot(self) -> None:
        if self.workflow is None or self.mouse_listener is None:
            return
        center = self.frameGeometry().center()
        self.mouse_listener.set_enabled(False)
        threading.Thread(
            target=self._run_pending_capture,
            args=(center.x(), center.y()),
            daemon=True,
        ).start()

    def _run_pending_capture(self, x: int, y: int) -> None:
        try:
            if self.workflow is not None:
                png = self.workflow.capture.capture_fullscreen_png(
                    x,
                    y,
                    debug_path=self.workflow._debug_path(),
                )
                self.signals.pending_capture_ready.emit(png, time.strftime("%H:%M:%S"))
        except Exception as exc:
            self.signals.error.emit(f"连续截图失败：{exc}")
        finally:
            if self.mouse_listener is not None:
                self.mouse_listener.set_enabled(True)

    def _on_pending_capture_ready(self, png: bytes, label: str) -> None:
        with self._pending_lock:
            self.pending_screenshots.append(png)
            self.pending_screenshot_labels.append(label)
            while len(self.pending_screenshots) > 5:
                self.pending_screenshots.pop(0)
                self.pending_screenshot_labels.pop(0)
            count = len(self.pending_screenshots)
        self._update_pending_buttons()
        self._log(f"连续截图：已缓存 {count} 张，继续滚动后截图，或点“分析缓存”")

    def _update_pending_buttons(self) -> None:
        with self._pending_lock:
            count = len(self.pending_screenshots)
        self.analyze_pending_button.setText(f"分析缓存（{count}）")
        self.analyze_pending_button.setEnabled(count > 0)
        self.clear_pending_button.setEnabled(count > 0)

    def _analyze_pending_screenshots(self) -> None:
        with self._pending_lock:
            pngs = list(self.pending_screenshots)
            self.pending_screenshots.clear()
            self.pending_screenshot_labels.clear()
        self._update_pending_buttons()
        if not pngs or self.workflow is None or self.mouse_listener is None:
            return
        self._reset_analysis_retry()
        self.mouse_listener.set_enabled(False)
        analysis = self.workflow._begin_analysis("direct")
        threading.Thread(
            target=self._run_pending_analysis,
            args=(pngs, analysis),
            daemon=True,
        ).start()

    def _run_pending_analysis(self, pngs: list[bytes], analysis) -> None:
        try:
            if self.workflow is not None:
                self.workflow.process_mobile_images(
                    pngs,
                    is_chat=False,
                    use_conversation=False,
                    analysis=analysis,
                )
        finally:
            if self.mouse_listener is not None:
                self.mouse_listener.set_enabled(True)

    def _clear_pending_screenshots(self) -> None:
        with self._pending_lock:
            self.pending_screenshots.clear()
            self.pending_screenshot_labels.clear()
        self._update_pending_buttons()
        self._log("连续截图缓存已清空")

    def _set_bank_enabled(self, enabled: bool) -> None:
        self.bank_enabled = enabled
        self.app_settings.setValue("bank/enabled", enabled)
        self.app_settings.sync()
        if self.workflow is not None:
            self.workflow.bank_enabled = enabled
        self._log(f"题库优先：{'开启' if enabled else '关闭'}")

    def _refresh_bank_status(self) -> None:
        self.bank_status_label.setText(self.question_bank.summary())
        self.bank_status_label.setToolTip(str(self.bank_path))
        self.bank_toggle.setEnabled(self.question_bank.total_count > 0)
        self.clear_bank_button.setEnabled(self.question_bank.total_count > 0)

    def _upload_question_bank(self) -> None:
        files, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "上传题库",
            str(Path.home()),
            "题库文件 (*.csv *.tsv *.txt *.json *.xlsx *.pdf *.docx *.doc);;"
            "题目截图 (*.png *.jpg *.jpeg *.webp *.bmp);;所有文件 (*)",
        )
        if not files:
            return
        added = 0
        for raw_path in files:
            path = Path(raw_path)
            if path.suffix.lower() in IMAGE_SUFFIXES:
                answer, accepted = QInputDialog.getMultiLineText(
                    self,
                    "添加截图题目",
                    f"{path.name}\n请输入这张截图的答案：",
                )
                if not accepted or not answer.strip():
                    continue
                try:
                    if self.question_bank.add_image(path.read_bytes(), answer, path.stem):
                        added += 1
                except Exception as exc:
                    self._log(f"截图题库导入失败：{path.name}：{exc}")
                continue
            try:
                added += import_bank_file(self.question_bank, path)
            except Exception as exc:
                QMessageBox.warning(self, "题库导入失败", f"{path.name}\n{exc}")
        if added:
            self.question_bank.save()
            self._refresh_bank_status()
            if self.workflow is not None:
                self.workflow.bank = self.question_bank
                self.workflow.bank_enabled = self.bank_enabled
            self._log(f"题库导入完成：新增或更新 {added} 题")
        else:
            self._log("题库导入：没有新增题目（格式为空或已存在）")

    def _clear_question_bank(self) -> None:
        if self.question_bank.total_count == 0:
            return
        reply = QMessageBox.question(
            self,
            "清空题库",
            "确定清空本地题库吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.question_bank.clear()
        self._refresh_bank_status()
        self._log("本地题库已清空")

    def _setup_workflow(self) -> None:
        try:
            pair_token = str(self.app_settings.value("mobile/pair_token", "") or "")
            if len(pair_token) < 24:
                pair_token = secrets.token_urlsafe(32)
                self.app_settings.setValue("mobile/pair_token", pair_token)
                self.app_settings.sync()
            self.session = BackendApi(self.backend_url).create_session(pair_token=pair_token)
            self.publisher = DesktopWebSocketPublisher(self.backend_url, self.session.session_id)
            self.command_client = DesktopCommandClient(
                self.backend_url,
                self.session.session_id,
                self.signals.desktop_command_received.emit,
            )
            self.mobile_label.setText(f"手机端：{self.session.pair_url}")
            self.copy_mobile_button.setEnabled(True)
            self._set_qr(self.session.pair_url)
            self._log(f"Mobile URL: {self.session.pair_url}")
        except Exception as exc:
            self.session = None
            self.publisher = None
            self._log(f"Backend unavailable; mobile streaming disabled: {exc}")

        session_id = self.session.session_id if self.session else "local"
        ai_client = self._build_ai_client()
        self.workflow = AssistantWorkflow(
            session_id=session_id,
            capture=ScreenCapture(
                policy=RepairPolicy(
                    enabled=self.repair_enabled and sys.platform == "win32",
                    max_attempts=settings.capture_repair_attempts,
                    sample_frames=settings.capture_repair_samples,
                    inject_remote=settings.capture_repair_inject,
                )
            ),
            ai_client=ai_client,
            publisher=self.publisher,
        )
        self.workflow.on_status = self.signals.status.emit
        self.workflow.on_result = self.show_result
        self.workflow.on_error = self.signals.error.emit
        self.workflow.on_stream_started = self._on_stream_started
        self.workflow.dispatch_local = self.signals.local_update.emit
        self.workflow.on_stream_delta = self.overlay.append_delta
        self.workflow.on_stream_completed = self.overlay.complete_stream
        self.workflow.on_stream_error = self.signals.stream_error.emit
        self.workflow.on_capture_finished = self._on_capture_finished
        self.workflow.on_analysis_started = self.signals.analysis_started.emit
        self.workflow.on_analysis_finished = self.signals.analysis_finished.emit
        self.workflow.bank = self.question_bank
        self.workflow.bank_enabled = self.bank_enabled
        self._refresh_provider_label(ai_client.current_provider)
        self._publish_model_changed()
        if ai_client.current_provider == "none":
            self.save_status.setText("请至少填写一把 API Key 后保存")
            self.save_status.setStyleSheet("color: #d33;")
        self.mouse_listener = MouseRoiListener(
            self.signals.mouse_long_left.emit,
            self.signals.mouse_short_left.emit,
            self.signals.mouse_long_right.emit,
            self.signals.multi_capture_requested.emit,
            self.signals.analyze_cache_requested.emit,
            on_middle_long=self.signals.auto_capture_toggle_requested.emit,
        )
        self.mouse_listener.set_shortcuts_enabled(self.multi_hotkeys_enabled)
        try:
            self.mouse_listener.start()
            self.workflow.start_capture()
        except Exception as exc:
            self._log(f"Input listener not active: {exc}")

    def _setup_platform_hotkeys(self) -> None:
        if sys.platform == "darwin":
            self._setup_mac_hotkeys()
        else:
            self._setup_ctrl_listener()
        self._setup_remote_answer_keys()

    def _setup_remote_answer_keys(self) -> None:
        self.remote_keys = RemoteAnswerKeyListener(
            on_scroll=self._remote_scroll_answer,
            on_toggle_pan=self._toggle_remote_autopan,
        )
        enabled = self._settings_bool("phone/arrow_remote", True)
        self.remote_keys.set_enabled(enabled)
        try:
            self.remote_keys.start()
            self._log(
                f"手机答案遥控：方向键 ↑↓←→（{'已启用' if enabled else '已关闭'}），无需组合键"
            )
        except Exception as exc:
            self._log(f"方向键遥控启动失败（其他软件可能占用了键盘钩子）：{exc}")

    def set_remote_arrows_enabled(self, enabled: bool) -> None:
        self.app_settings.setValue("phone/arrow_remote", bool(enabled))
        self.app_settings.sync()
        if self.remote_keys is not None:
            self.remote_keys.set_enabled(bool(enabled))
        self._log(f"方向键遥控手机答案框：{'开启' if enabled else '关闭'}")

    def _send_mobile_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.workflow is None or self.publisher is None:
            self._log("手机未连接，遥控指令未发送")
            return
        event = Event(type=event_type, session_id=self.workflow.session_id, payload=payload)
        try:
            self.publisher.send_sync(event.to_dict())
        except Exception as exc:
            self._log(f"遥控指令发送失败：{exc}")

    def _remote_scroll_answer(self, direction: str) -> None:
        self._send_mobile_event("answer.scroll", {"direction": direction, "steps": 1})
        threading.Thread(
            target=self._post_scroll_command, args=(direction,), daemon=True,
            name="remote-scroll-http",
        ).start()

    def _post_scroll_command(self, direction: str) -> None:
        """HTTP 兜底：手机端每 700ms 轮询这个队列，WS 异常也能滚。"""
        session = self.workflow.session_id if self.workflow is not None else ""
        if not session:
            return
        url = f"{self.backend_url.rstrip('/')}/scroll/{session}"
        try:
            import requests

            requests.post(url, json={"direction": direction, "steps": 1}, timeout=2)
        except Exception as exc:
            self._log(f"方向键指令发送失败：{exc}")

    def _toggle_remote_autopan(self) -> None:
        self.remote_pan_enabled = not self.remote_pan_enabled
        self._send_mobile_event("answer.autopan", {"enabled": self.remote_pan_enabled})
        self._log(f"手机代码自动巡览：{'开启' if self.remote_pan_enabled else '关闭'}")

    def _setup_mac_hotkeys(self) -> None:
        self.mac_hotkeys = MacHotkeyListener(
            on_overlay_toggle=self.signals.overlay_toggle_requested.emit,
            on_middle_long=self.signals.auto_capture_toggle_requested.emit,
        )
        try:
            self.mac_hotkeys.start()
            self._log("macOS 快捷键已启用：Ctrl+Alt+O 字幕开关，鼠标中键长按 1 秒 自动截屏")
        except Exception as exc:
            self._log(f"macOS 快捷键监听启动失败（需在辅助功能里允许本程序）：{exc}")

    def _setup_ctrl_listener(self) -> None:
        if sys.platform != "win32":
            return
        self.ctrl_listener = CtrlScreenshotListener(
            self.signals.ctrl_fullscreen_requested.emit,
            on_overlay_toggle=self.signals.overlay_toggle_requested.emit,
        )
        try:
            self.ctrl_listener.set_enabled(self.ctrl_capture_enabled)
            self.ctrl_listener.start()
        except Exception as exc:
            self._log(f"Ctrl 截图监听启动失败：{exc}")

    def _set_ctrl_capture_enabled(self, enabled: bool) -> None:
        self.ctrl_capture_enabled = enabled
        self.app_settings.setValue("customer_c/ctrl_capture", enabled)
        self.app_settings.sync()
        if self.ctrl_listener is not None:
            self.ctrl_listener.set_enabled(enabled)

    def _capture_from_ctrl(self) -> None:
        if self.ctrl_capture_enabled and self.workflow is not None:
            self._capture_current_screen()

    def _left_up(self, x: int, y: int) -> None:
        if not self.region_gesture_enabled:
            return
        if self.workflow is not None:
            self.workflow.left_up(x, y)

    def _second_left_up(self, x: int, y: int) -> None:
        if not self.region_gesture_enabled:
            return
        if self.workflow is None or self.mouse_listener is None:
            return
        self._reset_analysis_retry()
        self.mouse_listener.set_enabled(False)
        self._mark_capture_started()
        try:
            threading.Thread(target=self._run_selection, args=(x, y), daemon=True).start()
        except Exception as exc:
            self._mark_capture_finished()
            self.mouse_listener.set_enabled(True)
            self._log(f"框选截图线程启动失败：{exc}")

    def _run_selection(self, x: int, y: int) -> None:
        try:
            if self.workflow is not None:
                self.workflow.second_left_up(x, y)
        finally:
            self._mark_capture_finished()
            if self.mouse_listener is not None:
                self.mouse_listener.set_enabled(True)

    def _right_long(self, x: int, y: int) -> None:
        if not self.fullscreen_gesture_enabled:
            self._log("右键全屏手势已关闭")
            return
        self._capture_fullscreen_at(x, y)

    def _capture_fullscreen_at(
        self,
        x: int,
        y: int,
        user_text: str | None = None,
        use_conversation: bool = False,
        is_chat: bool = False,
        request_id: str | None = None,
    ) -> None:
        if self.workflow is None or self.mouse_listener is None:
            return
        self._reset_analysis_retry()
        self.mouse_listener.set_enabled(False)
        self._mark_capture_started()
        try:
            threading.Thread(
                target=self._run_fullscreen,
                args=(x, y, user_text, use_conversation, is_chat, request_id, self.workflow._begin_analysis("chat" if is_chat or use_conversation else "direct")),
                daemon=True,
            ).start()
        except Exception as exc:
            self._mark_capture_finished()
            self.mouse_listener.set_enabled(True)
            self._log(f"全屏截图线程启动失败：{exc}")
            return
        if not (is_chat or use_conversation):
            self.overlay.start_stream()

    def _capture_current_screen(self) -> None:
        center = self.frameGeometry().center()
        self._capture_fullscreen_at(center.x(), center.y())

    def _capture_current_screen_from_mobile(self, payload: dict[str, Any]) -> None:
        user_text = str(payload.get("text") or "").strip()
        use_conversation = bool(payload.get("conversation"))
        is_chat = bool(payload.get("chat"))
        request_id = str(payload.get("client_request_id") or "").strip() or None
        if user_text:
            self._log("手机端请求截取当前屏幕并追问")
        else:
            self._log("手机端请求截取当前屏幕")
        center = self.frameGeometry().center()
        self._capture_fullscreen_at(
            center.x(),
            center.y(),
            user_text=user_text or None,
            use_conversation=use_conversation,
            is_chat=is_chat,
            request_id=request_id,
        )

    def _capture_current_screen_preview_for_mobile(self) -> None:
        if self.workflow is None or self.mouse_listener is None:
            return
        center = self.frameGeometry().center()
        self.mouse_listener.set_enabled(False)
        self._mark_capture_started()
        try:
            threading.Thread(
                target=self._run_fullscreen_preview,
                args=(center.x(), center.y()),
                daemon=True,
            ).start()
        except Exception as exc:
            self._mark_capture_finished()
            self.mouse_listener.set_enabled(True)
            self._log(f"手机端截图线程启动失败：{exc}")

    def _submit_mobile_screenshots(self, payload: dict[str, Any]) -> None:
        if self.workflow is None or self.mouse_listener is None:
            return
        raw_images = payload.get("images")
        if not isinstance(raw_images, list):
            raw_images = []
        png_images: list[bytes] = []
        for raw_image in raw_images[:5]:
            if not isinstance(raw_image, str):
                continue
            image_data = raw_image.split(",", 1)[1] if "," in raw_image else raw_image
            try:
                png_images.append(base64.b64decode(image_data, validate=True))
            except Exception:
                self._log("手机端提交的截图解码失败，已跳过")
        user_text = str(payload.get("text") or "").strip()
        use_conversation = bool(payload.get("conversation"))
        is_chat = bool(payload.get("chat"))
        request_id = str(payload.get("client_request_id") or "").strip() or None
        raw_ids = payload.get("screenshot_ids")
        screenshot_ids = [str(item) for item in raw_ids[:5] if isinstance(item, str)] if isinstance(raw_ids, list) else []
        if len(screenshot_ids) != len(png_images):
            screenshot_ids = []
        self._log(f"手机端提交 {len(png_images)} 张截图" + ("并追问" if user_text else ""))
        self._reset_analysis_retry()
        self.mouse_listener.set_enabled(False)
        threading.Thread(
            target=self._run_mobile_screenshots,
            args=(png_images, user_text or None, use_conversation, is_chat, request_id, self.workflow._begin_analysis("chat" if is_chat or use_conversation else "direct"), screenshot_ids),
            daemon=True,
        ).start()

    def _handle_desktop_command(self, command: dict[str, Any]) -> None:
        if command.get("type") in {"command.get_prompt", "command.save_prompt"}:
            saving = command["type"] == "command.save_prompt"
            payload = command.get("payload") or {}
            if saving:
                if not isinstance(payload.get("text"), str):
                    return
                self.prompt_input.setPlainText(payload["text"])
                self.save_prompt_settings()
            if self.workflow is not None:
                self.workflow._publish("prompt.saved" if saving else "prompt.current", "prompt", {"text": self.system_prompt})
            return
        if command.get("type") == "command.get_model":
            self._publish_model_changed()
            self._publish_code_view()
            return
        if command.get("type") == "command.set_code_view":
            payload = command.get("payload")
            data = payload if isinstance(payload, dict) else {}
            font = str(data.get("font") or "auto")
            if font not in {"auto", "6", "8", "10", "13", "16"}:
                font = "auto"
            wrap = bool(data.get("wrap", True))
            self.app_settings.setValue("phone/code_font", font)
            self.app_settings.setValue("phone/code_wrap", wrap)
            self.app_settings.sync()
            self._log(f"手机代码显示：字号 {font}，自动换行 {'开' if wrap else '关'}")
            return
        if command.get("type") == "command.fullscreen":
            payload = command.get("payload")
            self.signals.mobile_fullscreen_requested.emit(payload if isinstance(payload, dict) else {})
        elif command.get("type") == "command.capture_fullscreen":
            self._capture_current_screen_preview_for_mobile()
        elif command.get("type") == "command.submit_screenshots":
            payload = command.get("payload")
            self._submit_mobile_screenshots(payload if isinstance(payload, dict) else {})
        elif command.get("type") == "command.clear_conversation":
            self.signals.clear_conversation_requested.emit()
        elif command.get("type") == "command.clear_direct":
            if self.workflow is not None:
                self.workflow.clear_direct()
            self.overlay.clear()
        elif command.get("type") == "command.set_model_tier":
            payload = command.get("payload")
            tier = ""
            if isinstance(payload, dict):
                tier = str(payload.get("route") or payload.get("tier") or "")
            self.signals.model_tier_requested.emit(tier)

    def _gesture_hint_text(self) -> str:
        if sys.platform == "darwin":
            return (
                "手势：左键长按 2 秒框选起点，再左键单击终点；"
                "右键或 Control+左键长按 2 秒截取当前屏幕。也可用「截取当前屏幕」按钮。"
                "一图多题会按题号对应作答；截图完成后可立即再按，新一次会覆盖上一题"
            )
        return (
            "手势：左键长按 2 秒框选起点，再左键单击终点；"
            "右键长按 2 秒截取当前屏幕全屏。一图多题会按题号对应作答；截图完成后可立即再按，新一次会覆盖上一题"
        )

    def _maybe_prompt_macos_permissions(self) -> None:
        from ai_screenshot_assistant.utils.macos_permissions import (
            accessibility_trusted,
            is_macos,
            open_privacy_pane,
            request_screen_recording,
            screen_recording_allowed,
        )

        if not is_macos():
            return
        request_screen_recording()
        missing: list[str] = []
        if not accessibility_trusted():
            missing.append("辅助功能（监听框选和右键手势）")
        if not screen_recording_allowed():
            missing.append("屏幕录制（截取题目）")
        if not missing:
            return
        self._log("macOS 需要授权：" + "、".join(missing))
        QMessageBox.information(
            self,
            "需要 macOS 权限",
            "请在「系统设置 → 隐私与安全性」中允许本应用：\n\n- "
            + "\n- ".join(missing)
            + "\n\n授权后请完全退出应用再重新打开。",
        )
        if not accessibility_trusted():
            open_privacy_pane("Privacy_Accessibility")
        elif not screen_recording_allowed():
            open_privacy_pane("Privacy_ScreenCapture")

    def _run_fullscreen(
        self,
        x: int,
        y: int,
        user_text: str | None = None,
        use_conversation: bool = False,
        is_chat: bool = False,
        request_id: str | None = None,
        analysis=None,
    ) -> None:
        try:
            if self.workflow is not None:
                self.workflow.process_fullscreen(
                    x,
                    y,
                    user_text=user_text,
                    use_conversation=use_conversation,
                    is_chat=is_chat,
                    request_id=request_id,
                    analysis=analysis,
                )
        finally:
            self._mark_capture_finished()
            if self.mouse_listener is not None:
                self.mouse_listener.set_enabled(True)

    def _run_fullscreen_preview(self, x: int, y: int) -> None:
        try:
            if self.workflow is not None:
                self.workflow.capture_fullscreen_for_mobile(x, y)
        finally:
            self._mark_capture_finished()
            if self.mouse_listener is not None:
                self.mouse_listener.set_enabled(True)

    def _run_mobile_screenshots(
        self,
        png_images: list[bytes],
        user_text: str | None = None,
        use_conversation: bool = False,
        is_chat: bool = False,
        request_id: str | None = None,
        analysis=None,
        screenshot_ids: list[str] | None = None,
    ) -> None:
        try:
            if self.workflow is not None:
                self.workflow.process_mobile_images(
                    png_images,
                    user_text=user_text,
                    use_conversation=use_conversation,
                    is_chat=is_chat,
                    request_id=request_id,
                    analysis=analysis,
                    screenshot_ids=screenshot_ids,
                )
        finally:
            if self.mouse_listener is not None:
                self.mouse_listener.set_enabled(True)

    def set_status(self, message: str) -> None:
        text = str(message).strip()
        short = text if len(text) <= 18 else text[:17] + "…"
        self.status_label.setText(f"状态：{short}")
        self.status_label.setToolTip(text)
        self._log(message)

    def show_result(self, result: dict[str, Any]) -> None:
        self._log("AI result completed")

    def show_error(self, message: str) -> None:
        self._log(f"Error: {message}")
        self.status_label.setText("状态：错误")

    def _log(self, message: str) -> None:
        self.logs.append(message)

    def _set_qr(self, url: str) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(pair_qr_png_bytes(url), "PNG")
        scaled = pixmap.scaled(
            QR_DISPLAY_PX,
            QR_DISPLAY_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.qr_label.setPixmap(scaled)
        self.qr_label.setFixedSize(scaled.width() + 24, scaled.height() + 24)
        self.qr_label.setVisible(True)

    def _on_desktop_model_tier(self, _index: int) -> None:
        self._apply_model_tier(str(self.model_tier_combo.currentData() or DEFAULT_MODEL_TIER))

    def _on_model_tier_requested(self, tier: str) -> None:
        self._apply_model_tier(tier, sync_combo=True)

    def _apply_model_tier(self, tier: str, *, sync_combo: bool = False) -> None:
        if self.workflow is None:
            self.model_tier = normalize_model_tier(tier)
            return
        payload = self.workflow.set_model_tier(tier)
        self.model_tier = normalize_model_tier(str(payload.get("tier") or tier))
        self.app_settings.setValue("providers/model_tier", self.model_tier)
        self.app_settings.sync()
        if sync_combo:
            self.model_tier_combo.blockSignals(True)
            index = self.model_tier_combo.findData(self.model_tier)
            if index >= 0:
                self.model_tier_combo.setCurrentIndex(index)
            self.model_tier_combo.blockSignals(False)
        self._refresh_provider_label()

    def _publish_code_view(self) -> None:
        font = str(self.app_settings.value("phone/code_font", "auto") or "auto")
        wrap_value = self.app_settings.value("phone/code_wrap", True)
        wrap = wrap_value if isinstance(wrap_value, bool) else str(wrap_value).lower() != "false"
        self._send_mobile_event("code.view", {"font": font, "wrap": wrap})

    def _publish_model_changed(self) -> None:
        if self.workflow is None:
            return
        client = self.workflow.ai_client
        apply_tier = getattr(client, "apply_model_tier", None)
        if callable(apply_tier):
            payload = apply_tier(self.model_tier, notify=False).to_payload()
            available_routes = getattr(client, "available_routes", None)
            if callable(available_routes):
                payload["available_routes"] = available_routes()
        else:
            payload = {"tier": self.model_tier}
        if self.publisher is not None:
            event = Event(
                type="model.changed",
                session_id=self.workflow.session_id,
                payload=payload,
            )
            try:
                self.publisher.send_sync(event.to_dict())
            except Exception as exc:
                self._log(f"Mobile update failed: {exc}")
        self._refresh_provider_label()

    def _clear_conversation(self) -> None:
        if self.workflow is not None:
            self.workflow.clear_conversation()
        gc.collect()
        self._log("已清空对话记录并释放内存")

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._force_quit and self.tray_icon is not None and self.tray_icon.isVisible():
            message = QMessageBox(self)
            message.setWindowTitle("关闭 AI 截图搜题助手")
            message.setText("要最小化到右下角托盘继续运行，还是直接退出？")
            to_tray = message.addButton("最小化到托盘", QMessageBox.ButtonRole.AcceptRole)
            exit_app = message.addButton("直接退出", QMessageBox.ButtonRole.DestructiveRole)
            cancel = message.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            message.setDefaultButton(to_tray)
            message.exec()
            clicked = message.clickedButton()
            if clicked is cancel:
                event.ignore()
                return
            if clicked is to_tray:
                event.ignore()
                self.hide()
                self.tray_icon.showMessage(
                    "AI 截图搜题助手仍在运行",
                    "可从右下角托盘图标恢复窗口或退出。",
                    QSystemTrayIcon.MessageIcon.Information,
                    2500,
                )
                return
            if clicked is exit_app:
                self._force_quit = True
                event.accept()
        self.auto_capture_scheduler.stop()
        self.retry_timer.stop()
        self._clear_pending_screenshots()
        self.overlay.close()
        if self.workflow is not None:
            self.workflow.cancel_active_analysis()
        if self.mouse_listener is not None:
            self.mouse_listener.stop()
        if self.ctrl_listener is not None:
            self.ctrl_listener.stop()
        if self.mac_hotkeys is not None:
            self.mac_hotkeys.stop()
        if self.remote_keys is not None:
            self.remote_keys.stop()
        if self.publisher is not None:
            self.publisher.close()
        if self.command_client is not None:
            self.command_client.close()
        if self.tray_icon is not None:
            self.tray_icon.hide()
        super().closeEvent(event)
        if self._force_quit:
            QApplication.quit()
