# v0.2.63 — macOS 适配

Windows 版保持原样；这一版把同一套源码往 macOS 上补齐，并把打包脚本补全。

## 能用的部分

- 截图搜题、自动截全屏、手机端扫码与流式答案、题库（含 OCR）、模型路线（含 GPT-4o / GPT-4.1）、悬浮字幕与捕获排除，全部沿用现有实现。
- 字幕新增 macOS 分支：每 400ms 通过 `NSWindow` 的 `orderWindow:above` 重新顶到浮动层级，并复用已有的位置兜底（分辨率/DPI 变化后拉回屏幕内）。
- macOS 快捷键用 pynput 全局监听实现：`Ctrl+Alt+O` 开关字幕、鼠标中键长按 1 秒开关自动截屏；需要「辅助功能」权限。
- 截图异常修复在 macOS 上自动关闭（配置读入时就强制 `enabled=False`），控制台开关置灰并给出说明，避免每张截图多拍两帧。

## 做不到的部分

截图异常修复依赖 Windows 的 `SetWindowDisplayAffinity` / DWM / DirectComposition；macOS 的 `NSWindow.sharingType = .none` 只能由窗口所属进程修改，也没有等价注入手段，ScreenCaptureKit 同样尊重该标记。因此 Mac 上这个开关不可用。

## 打包

- 新增 `packaging/macos/package.sh`：装依赖 → 跑 pytest → PyInstaller 打 `QQMusic.app`（`assets/app.icns`、bundle id `com.sayuriqvq.QQMusic`）→ 写入 `Info.plist` → ad-hoc 签名 → `ditto` 压缩。支持 `PACKAGE_USE_VENV` / `PACKAGE_INSTALL_DEPS` / `PACKAGE_RUN_TESTS` / `PACKAGE_ZIP_NAME` 环境变量，便于 CI 复用。
- 新增 `requirements-macos.txt`（`pyobjc-framework-Cocoa` / `Quartz`），Windows 不安装。
- `build_macos.sh` 改为调用上面的脚本，并同时安装两份依赖。
- 新增 `docs/MACOS.md`：功能对照表、权限设置、打包与常见问题。
- 新增 `.github/workflows/build-macos.yml`：打 `v*` 标签即在 `macos-14` 上跑测试 → 打 App → 上传 `QQMusic-macOS-arm64.zip` 与 SHA256 → 自动挂到同名 Release；手动触发可加 Intel 版。
- 新增 `.gitattributes`（shell 保持 LF、bat 保持 CRLF、二进制标记），`.gitignore` 增加 `.build-venv/`。

## 验证

- Python 回归 **339 项通过**，1 项非 Windows 占位测试跳过。
- 新增测试：macOS 下修复策略自动关闭、字幕 `_keep_front` 走 NSWindow 分支、mac 快捷键组合只触发一次、中键 1 秒触发/0.3 秒不触发。
- **限制**：本机构建环境是 Windows，无法交叉编译 `.app`，也没有在真机上跑过 macOS 包；`dist/QQMusic.app` 需要在一台 Mac 上执行 `./build_macos.sh` 生成并实机验收。
