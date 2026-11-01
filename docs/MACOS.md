# macOS 版说明

Windows 版（`dist/QQMusic-CustomerC.exe`）和 macOS 版是同一套源码，功能差别只在系统接口。

## 一、能不能做、做到什么程度

| 能力 | macOS | 说明 |
|---|---|---|
| 截图搜题（框选 / 全屏 / 自动截屏） | ✅ | 需要「屏幕录制」权限 |
| 手机端扫码、流式答案、多设备 | ✅ | 同一 WiFi，8000 端口 |
| 桌面悬浮字幕 + 捕获排除 | ✅ | `NSWindow.sharingType = none`，共享/录屏看不到 |
| 字幕开关 `Ctrl+Alt+O` | ✅ | 全局快捷键，需要「辅助功能」权限 |
| 中键长按 1 秒开关自动截屏 | ✅ | 同上 |
| 本地题库（CSV/Excel/PDF/Word/截图 OCR） | ✅ | 首次加载 OCR 稍慢 |
| 模型路线（含 GPT-4o / GPT-4.1） | ✅ | 与 Windows 完全一致 |
| 截图异常自动修复（黑屏 / 透明窗口） | ❌ | macOS 没有对应接口，开关在 Mac 上置灰 |
| 截图诊断报告 | ⚠️ | 能生成报告，但没有 Windows 那套窗口状态表 |

**为什么修复功能在 Mac 上做不到**：Windows 的防截屏是 `SetWindowDisplayAffinity` / DWM 隐藏 / DirectComposition 直出，别的进程可以通过注入解除；macOS 的防截屏是窗口自己把 `sharingType` 设成 `none`，系统不允许其他进程修改，ScreenCaptureKit 也会尊重这个标记。用户态没有等价手段，所以直接关掉，避免截一张图多拍两帧。

## 二、在 Mac 上怎么打包

需要 macOS + Python 3.11/3.12（Apple Silicon 与 Intel 都可以，产物对应本机架构）。

```bash
cd AutoAIAnswer-CustomerC
chmod +x build_macos.sh
./build_macos.sh
```

脚本会：建 `.venv` → 装 `requirements.txt` + `requirements-macos.txt` → 跑 `pytest` → PyInstaller 打 `QQMusic.app` → ad-hoc 签名 → 压缩。

产物：

- `dist/QQMusic.app`
- `dist/QQMusic-macOS.zip`

> PyInstaller 不能交叉编译：Windows 上打不出 `.app`，必须在 Mac 上执行上面两条命令。

## 2.1 用 GitHub Actions 自动打包（打 tag 就出 zip）

仓库里已经带好 `.github/workflows/build-macos.yml`：推到 GitHub 后，打 `v*` 标签就会在 macOS 跑测试、打 App、签名、上传 zip 并挂到 Release。已实测可用：v0.2.64 的产物见 https://github.com/axiom7891/AutoAIAnswer/releases/tag/v0.2.64 。

触发方式：

- 打 tag：`git tag v0.2.64 && git push origin v0.2.64`
- 推到 `main`：只跑测试与打包，用于提前发现 macOS 专属问题（不建 Release）
- 或在 Actions 页面点 **Run workflow**（只留 artifacts；可勾选同时构建 Intel 版）

流程与产物：

| 项目 | 说明 |
|---|---|
| Runner | `macos-14`（Apple Silicon）；手动触发可加 `macos-13`（Intel，标记为可选） |
| Python | 3.12（`actions/setup-python`，带 pip 缓存） |
| 步骤 | 装依赖 → `pytest` → `packaging/macos/package.sh`（跳过重复装依赖与测试）→ 校验和 → 上传 |
| 产物 | `QQMusic-macOS-arm64.zip`、`SHA256SUMS-arm64.txt`；Intel 版为 `x86_64` |
| Release | 仅 tag 触发；资产 `*.zip` + `SHA256SUMS-*.txt`，自动生成 release notes |

需要的仓库设置：

1. 代码在 GitHub 上（私有仓库也可以）。
2. 仓库 **Settings → Actions → General → Workflow permissions** 选 “Read and write permissions”，release 才能挂资产（工作流里已声明 `permissions: contents: write`）。
3. 首次把项目推上去：

```bash
git init
git add .
git commit -m "init: AutoAIAnswer v0.2.63"
git branch -M main
git remote add origin https://github.com/<你的账号>/AutoAIAnswer-CustomerC.git
git push -u origin main
git tag v0.2.63
git push origin v0.2.63
```

> `.gitignore` 已排除 `.venv/`、`.build-venv/`、`dist/`、`build/`、`.env`，不会把 1GB 的构建环境推上去。
> 私有仓库的 macOS 分钟数按 10 倍计费；公开仓库免费。

## 三、首次运行

1. 双击 `QQMusic.app`；若提示「无法打开，因为来自身份不明的开发者」，右键 → 打开。
2. 系统设置 → 隐私与安全性 → **屏幕录制**：勾选 QQMusic（否则截图是黑的/空白的）。
3. 系统设置 → 隐私与安全性 → **辅助功能**：勾选 QQMusic（否则鼠标手势、`Ctrl+Alt+O`、中键长按都不生效）。
4. 授权后完全退出 App 再打开一次。

## 四、和 Windows 版的行为差异

- 单击 Ctrl 截全屏是 Windows 客户 C 版特性，macOS 用 **Control + 左键长按** 或右键 2 秒代替。
- 字幕置顶用 `NSWindow` 的浮动层级 + 400ms 重新 orderFront，不做 Windows 那套 `WindowFromPoint` 遮挡检测。
- 「共享屏幕时隐藏控制台」在 macOS 用 `sharingType`，效果与 Windows 的 `WDA_EXCLUDEFROMCAPTURE` 相同。

## 五、常见问题

| 现象 | 处理 |
|---|---|
| 截图全黑 / 空白 | 没给「屏幕录制」权限；授权后重启 App |
| 鼠标手势没反应 | 没给「辅助功能」权限 |
| 字幕看不到 | 检查勾选「显示桌面流式悬浮答案」；按 `Ctrl+Alt+O` 试一次 |
| 手机连不上 | 同一 WiFi、关 VPN、防火墙放行 8000 |
| 启动报「已损坏」 | 终端执行 `xattr -dr com.apple.quarantine /Applications/QQMusic.app` |
