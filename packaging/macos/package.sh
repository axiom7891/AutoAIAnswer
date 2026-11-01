#!/usr/bin/env bash
# 在 macOS 上把源码打成 QQMusic.app 并压缩成 zip。
# 用法（在项目根目录）：bash packaging/macos/package.sh
#
# 可用的环境变量（CI 用）：
#   PACKAGE_USE_VENV=0        不创建/不激活 .venv，直接用当前 python
#   PACKAGE_INSTALL_DEPS=0    跳过 pip 安装
#   PACKAGE_RUN_TESTS=0       跳过 pytest（CI 里单独跑）
#   PACKAGE_ZIP_NAME=...      输出 zip 名，默认 QQMusic-macOS.zip
#   PYTHON_BIN=...            指定解释器
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PY="${PYTHON_BIN:-python3}"
ZIP_NAME="${PACKAGE_ZIP_NAME:-QQMusic-macOS.zip}"
SELECTED_SIGN="${PACKAGE_CODESIGN_IDENTITY:-}"
if [[ -z "$SELECTED_SIGN" ]]; then
  SELECTED_SIGN="-"
fi
ARCH="$(uname -m)"

if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "需要 Python 3.11 或更高版本，可用 PYTHON_BIN 指定解释器" >&2
  exit 1
fi

if [[ "${PACKAGE_USE_VENV:-1}" == "1" && -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ ! -d .venv ]]; then
    "$PY" -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "== 平台：$(uname -s) $(uname -r) / ${ARCH} =="
echo "== Python：$(python -c 'import sys; print(sys.version.split()[0])') =="

if [[ "${PACKAGE_INSTALL_DEPS:-1}" == "1" ]]; then
  python -m pip install --upgrade pip >/dev/null
  python -m pip install -r requirements.txt -r requirements-macos.txt
fi

if [[ "${PACKAGE_RUN_TESTS:-1}" == "1" ]]; then
  echo "== 运行回归测试 =="
  python -m pytest tests -q -o faulthandler_timeout=120
fi

echo "== 清理旧产物 =="
rm -rf build "dist/QQMusic.app" "dist/${ZIP_NAME}"

echo "== PyInstaller 打包 =="
python -m PyInstaller \
  --noconfirm --clean --windowed \
  --name QQMusic \
  --icon assets/app.icns \
  --osx-bundle-identifier com.sayuriqvq.QQMusic \
  --add-data "ai_screenshot_assistant/web/static:ai_screenshot_assistant/web/static" \
  --add-data "assets:assets" \
  --hidden-import mouse \
  --hidden-import pynput.keyboard._darwin \
  --hidden-import pynput.mouse._darwin \
  --hidden-import AppKit \
  --hidden-import Quartz \
  --hidden-import ai_screenshot_assistant.ui.native_capture \
  --hidden-import ai_screenshot_assistant.ui.macos_capture \
  --hidden-import ai_screenshot_assistant.input.mac_hotkeys \
  --hidden-import ai_screenshot_assistant.capture.health \
  --hidden-import ai_screenshot_assistant.capture.repair \
  --hidden-import openpyxl \
  --hidden-import pypdf \
  --hidden-import docx \
  --collect-all rapidocr_onnxruntime \
  --collect-all onnxruntime \
  --collect-all pypdfium2 \
  --exclude-module pytest \
  main.py

APP="dist/QQMusic.app"
if [[ ! -d "$APP" ]]; then
  echo "打包失败：没有生成 $APP" >&2
  exit 1
fi

echo "== 写入 Info.plist 权限说明 =="
PLIST="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :NSHighResolutionCapable true" "$PLIST" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :NSHighResolutionCapable bool true" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :NSSupportsAutomaticGraphicsSwitching bool true" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :NSAppleEventsUsageDescription string '用于读取屏幕内容并显示答案'" "$PLIST" 2>/dev/null || true
# macOS 首次截图/全局监听会弹权限：屏幕录制 + 辅助功能。

echo "== 签名（${SELECTED_SIGN}）=="
codesign --force --deep --sign "$SELECTED_SIGN" "$APP"
if codesign --verify --deep --strict "$APP"; then
  echo "签名校验通过"
else
  echo "警告：签名校验未通过（ad-hoc 包通常仍可右键打开，继续打包）" >&2
fi

echo "== 压缩 =="
ditto -c -k --sequesterRsrc --keepParent "$APP" "dist/${ZIP_NAME}"

echo
echo "完成（${ARCH}）："
echo "  App: $ROOT/dist/QQMusic.app"
echo "  Zip: $ROOT/dist/${ZIP_NAME}"
echo "首次运行：右键 App → 打开；随后在「系统设置 → 隐私与安全性」里允许"
echo "  屏幕录制（截图）与 辅助功能（鼠标手势 / 全局快捷键）。"
