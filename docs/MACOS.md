# macOS 版说明（对应 Windows v0.2.84）

Windows 版（`dist/QQMusic-CustomerC.exe`）和 macOS 版是同一套源码，功能差别只在系统接口。

## 一、能不能做、做到什么程度

| 能力 | macOS | 说明 |
|---|---|---|
| 截图搜题（框选 / 全屏 / 自动截屏） | ✅ | 需要「屏幕录制」权限 |
| 手机端扫码、流式答案、多设备 | ✅ | 同一 WiFi，8000 端口 |
| 桌面悬浮字幕 + 捕获排除 | ✅ | `NSWindow.sharingType = none`，共享/录屏看不到 |
| 字幕开关 `Alt+Z` | ✅ | 全局快捷键，需要「辅助功能」权限 |
| 中键长按 1 秒开关自动截屏 | ✅ | 同上 |
| 左键双击 / 三连击、`Alt+F` / `Alt+G`、解决黑屏、捕获排除自愈 | ❌ | 这些是 Windows 轮询/窗口接口实现，macOS 没有对应机制 |
| Google Gemini 直连、自定义模型 ID、答案格式 | ✅ | 与 Windows 同一套代码，填 Google Key 即可 |
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

产物命名带版本号：`QQMusic-macOS-arm64-v<版本>.zip`（例如 `v0.2.84`），App 的 Info.plist 也会写入同一个版本号。

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
| 产物 | `QQMusic-macOS-arm64-v<版本>.zip`、`SHA256SUMS-arm64.txt`；Intel 版为 `QQMusic-macOS-x86_64-v<版本>.zip`、`SHA256SUMS-x86_64.txt` |
| Intel 触发 | 打 `v*` 标签时自动同时构建；也可在 Actions 手动运行并勾选 intel |
| Intel 构建机 | 默认 `macos-15-intel`；若该镜像不可用，手动触发时把 `intel_runner` 改成 `macos-13` |
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
3. 系统设置 → 隐私与安全性 → **辅助功能**：勾选 QQMusic（否则鼠标手势、`Alt+Z`、中键长按都不生效）。
4. 授权后完全退出 App 再打开一次。

## 四、和 Windows 版的行为差异

- 单击 Ctrl 截全屏是 Windows 客户 C 版特性，macOS 用 **Control + 左键长按** 或右键 2 秒代替。
- 双击/三连击、`Alt+F`/`Alt+G`、解决黑屏、捕获排除自愈都依赖 Windows 接口，macOS 不提供；macOS 用「中键长按 1 秒」开关自动截屏。
- 字幕置顶用 `NSWindow` 的浮动层级 + 400ms 重新 orderFront，不做 Windows 那套 `WindowFromPoint` 遮挡检测。
- 「共享屏幕时隐藏控制台」在 macOS 用 `sharingType`，效果与 Windows 的 `WDA_EXCLUDEFROMCAPTURE` 相同。
- 字幕开关从 `Ctrl+Alt+O` 改成 `Alt+Z`（macOS 上 Option+Z 会输入 Ω，程序已兼容）。

## 五、已构建的 .app 怎么用（拿到别人打好的包）

> 当前仓库对应的最新版本是 **v0.2.84**；旧包（v0.2.64）没有 Gemini 直连、自定义模型、答案格式这些功能。

1. 确认 Mac 架构：包里的可执行文件是 arm64 时只能在 Apple Silicon（M 系列）上跑；Intel 机器要另打 x86_64 版。
2. 把 `QQMusic.app` 拖进「应用程序」，首次右键 → 打开（未签名，Gatekeeper 会拦）。
3. 若提示「已损坏」，终端执行 `xattr -dr com.apple.quarantine /Applications/QQMusic.app`。
4. 授权：系统设置 → 隐私与安全性 → 屏幕录制 / 辅助功能，勾选 QQMusic，然后完全退出重开。
5. 手机端与控制台同一 WiFi，浏览器打开控制台显示的地址即可。

## 六、常见问题

| 现象 | 处理 |
|---|---|
| 截图全黑 / 空白 | 没给「屏幕录制」权限；授权后重启 App |
| 鼠标手势没反应 | 没给「辅助功能」权限 |
| 字幕看不到 | 检查勾选「显示桌面流式悬浮答案」；按 `Alt+Z` 试一次（旧包用 `Ctrl+Alt+O`） |
| 手机连不上 | 同一 WiFi、关 VPN、防火墙放行 8000 |
| 启动报「已损坏」 | 终端执行 `xattr -dr com.apple.quarantine /Applications/QQMusic.app` |
