#!/usr/bin/env bash
# 一键在 macOS 上构建：创建虚拟环境、安装依赖、跑测试、打包 App 与 zip。
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! "$PYTHON_BIN" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"; then
  echo "Need Python 3.11 or newer. Set PYTHON_BIN to a suitable interpreter." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt -r requirements-macos.txt

bash packaging/macos/package.sh
