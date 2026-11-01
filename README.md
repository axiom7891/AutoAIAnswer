# AutoAIAnswer

Windows / macOS 截图搜题助手。通过全局鼠标手势框选屏幕题目，调用视觉模型分析，并把答案实时流式发送到同一局域网内的手机浏览器；也可选择在桌面显示轻量透明悬浮答案。

## 平台支持

同一套源码，两个平台各自打包：

| 平台 | 打包入口 | 产物 | 捕获排除方式 |
|---|---|---|---|
| Windows | `BUILD_CUSTOMER_C.bat` | `dist/QQMusic-CustomerC.exe`（单文件） | `WDA_EXCLUDEFROMCAPTURE` |
| macOS | `./build_macos.sh` | `dist/QQMusic.app` / `dist/QQMusic-macOS.zip` | `NSWindow.sharingType = .none` |

macOS 版功能差异、权限设置与打包细节见 [docs/MACOS.md](docs/MACOS.md)；Windows 版验收清单见 [CUSTOMER-C.md](CUSTOMER-C.md)。

**macOS 上做不到的一项**：截图异常修复（解除别的程序的防截屏）。macOS 的 `sharingType` 只能由窗口自己改，系统不允许其他进程修改，因此该开关在 Mac 上置灰；其余功能（截图、字幕、题库、手机端、模型、快捷键）保持一致。

## 直接下载

[下载 Windows 版 AutoAIAnswer-Windows.zip](https://github.com/SAYURIqvq/AutoAIAnswer/releases/latest/download/AutoAIAnswer-Windows.zip)

[下载 macOS 版 AutoAIAnswer-macOS.dmg](https://github.com/SAYURIqvq/AutoAIAnswer/releases/latest/download/AutoAIAnswer-macOS.dmg)

无需安装 Python，下载对应系统版本后直接运行，并在软件界面中填写自己的 DeepSeek/OpenRouter API Key。公开发行版不包含作者的 API Key。

### 在 GitHub 页面中找到下载文件

1. 在仓库首页右侧找到 **Releases**。
2. 点击最新版本 **AutoAIAnswer v0.2.5**。
3. 进入发布页面后展开 **Assets**。
4. Windows 点击 **AutoAIAnswer-Windows.zip**；macOS 点击 **AutoAIAnswer-macOS.dmg**。

如果没有看到右侧栏，也可以直接点击上方的“下载 Windows 单文件版”链接，或打开 [Releases 页面](https://github.com/SAYURIqvq/AutoAIAnswer/releases/latest)。

## 核心体验

### 手机端实时查看

电脑完成框选后，模型返回的内容会立即逐段推送到手机浏览器，无需等待完整答案生成。手机端只保留一个清晰的输出区域，答案和解析连续显示，适合把电脑屏幕留给当前工作。

<table>
  <tr>
    <td width="50%"><img src="docs/images/mobile-live-answer.jpg" alt="手机端实时接收搜题答案" /></td>
    <td width="50%"><img src="docs/images/mobile-answer-demo.jpg" alt="手机端答案与解析显示效果" /></td>
  </tr>
  <tr>
    <td align="center">手机与电脑配合，实时查看模型答案</td>
    <td align="center">电脑透明水印可以拖动调整透明度和大小</td>
  </tr>
</table>

### 轻量透明悬浮答案（水印效果）

桌面端可开启类似歌词或水印的答案悬浮层：文字小巧、低透明、始终置顶，并可拖动到任意位置。模型生成时内容会同步流式追加，不需要切换窗口。悬浮层默认关闭，可随时在主窗口中开启或隐藏，并自动记住上次位置。

> 悬浮答案是普通系统置顶窗口，可能出现在屏幕共享或录制画面中；本项目不提供规避录屏、共享屏幕或监控检测的功能。

## 功能

- 支持选择题、判断题、填空题、计算题和简答题；一图多题会按题号对应作答
- DeepSeek、OpenRouter 与豆包均可选，只需配置其中一把 Key 即可使用
- 手机和桌面选择「路线 + 模型」：豆包 `doubao-seed-2-0/2-1` 系列、OpenRouter 通义千问 VL / GLM / MiniMax / GPT-4o / GPT-4.1、DeepSeek Flash；下拉框只显示「厂商 · 模型 ID」，不带速度/准确度备注
- 默认只走国产模型；显式选择 `OpenRouter GPT-4o / GPT-4.1` 时才调用 OpenAI 模型（复用 OpenRouter Key，不需要额外 Key）
- 先走当前选中路线；该路线返回 HTTP 402 时再按 OpenRouter → DeepSeek → 豆包切换一次
- DeepSeek Key、OpenRouter Key、豆包 Key 和模型路线可在桌面界面保存
- 手机对话支持清空聊天并释放电脑端会话内存
- 左键长按 2 秒框选题目；右键长按 2 秒截取当前屏幕全屏（macOS 也可用 Control+左键，或窗口内「截取当前屏幕」）
- 控制台可开启「自动截全屏」，按 1–3600 秒间隔自动截图搜题；上一次截图或分析未完成时跳过本次
- 快捷键：`Ctrl+Alt+O` 显示/隐藏悬浮字幕；鼠标中键长按 1 秒 开关自动截屏；`Ctrl` 单键截全屏（客户 C）
- 截图异常自动修复：出现黑屏、局部黑块、整屏透明或两帧闪烁时，自动定位覆盖截取区域的窗口并注入临时修复补丁（解除捕获排除、取消 DWM 隐藏、还原图层不透明度、移除 DirectComposition 直出、强制重绘），重拍后挑最稳的一帧；补丁在本次截图结束后按原状态还原
- 支持上传本地题库（Excel/CSV/JSON/PDF/Word/题目截图），题库命中时优先返回题库答案；文本题库使用本地 OCR 匹配
- 同一二维码支持多台手机同时连接，共享截图、流式答案、截图对话、清空操作与模型选择
- 分析超时自动重试、手机答案分页/按秒自动翻页、连续截图多图分析，适合长答案和多屏资料题
- 多图快捷键：`Ctrl+Shift+鼠标左键` 连续截图，`Ctrl+Shift+鼠标右键` 发送分析，控制台在托盘时也可用
- 手机二维码配对，答案与解析在单一输出框中实时流式显示
- 手机端可一键让电脑截全屏，也可输入追问后截全屏并发送给 AI，支持围绕同一截图任务连续追问
- 手机端答案框支持外接键盘：`Shift+W/S` 上下翻页、`Shift+A/D` 左右滚动代码块，长代码不再看不全
- 每个代码块有独立「复制代码」按钮；答案区支持「每 N 字符分段复制」（20–2000），适合有字数上限的作答框
- 11px、约 18% 不透明度的水印式桌面悬浮答案，可拖动、置顶并记忆位置
- 模型生成期间暂停鼠标手势，避免误触

## 截图异常修复（黑屏 / 闪屏 / 透明屏）

框选或全屏截图拿到废图时，默认会自动诊断并修复，不需要重新点一遍：

| 异常 | 判定依据 | 修复补丁 |
|---|---|---|
| 黑屏 | 整帧平均亮度极低、暗像素 ≥99.5%、几乎没有内容 | 解除 `WDA_MONITOR` 捕获排除、取消 DWM `DWMWA_CLOAK`、移除 `WS_EX_NOREDIRECTIONBITMAP`、强制重绘 |
| 局部黑块 | 暗区连成一块且被亮内容包住 | 同上，按 z-order 依次处理覆盖截取区域的窗口 |
| 透明屏 | 整帧 alpha 覆盖率为 0 | 把分层窗口 alpha 还原到 255、清掉色键，再重绘 |
| 纯色空白 | 单一颜色占比 ≥99.7% 且细节接近 0 | 移除 DirectComposition 直出、取消隐藏、重绘 |
| 闪屏 | 同一批多帧里正常帧与异常帧交替 | 按底层缺陷打补丁，重拍时多取一帧，取细节最丰富的正常帧 |
| 内容缺失 | 桌面截到的区域与窗口自身渲染（PrintWindow）灰度互相关 < 0.35，或区域最上层窗口带捕获排除 / DWM 隐藏 / 低 alpha / DComp 直出 | 依次还原图层 alpha、取消 DWM 隐藏、解除捕获排除、移除 DComp 直出、重绘 |

「内容缺失」专治「截图看着正常、但透明窗口的题目没进来」：桌面 `BitBlt` 截到的其实是窗口背后的背景，光看亮度和颜色判不出来。两条通道一起判——能拿到窗口自身渲染就做互相关对比；拿不到（`WDA_*` 窗口的 `PrintWindow` 返回全黑）就按区域最上层窗口的状态兜底。补丁之后仍拿不到内容时，直接把窗口自身渲染结果当截图返回。

截不到时点控制台「截图诊断」：会把覆盖当前屏幕的窗口（hwnd / class / pid / 位数 / `affinity` / `cloaked` / `layered` / `noredir`）和逐个窗口的 `PrintWindow` 探测写成 `%LOCALAPPDATA%\QQMusic\Logs\capture-diagnose-<时间>.txt`，异常截图也会自动落一份。

补丁分两档执行：先在本进程直调窗口 API；`SetWindowDisplayAffinity` 这类只允许窗口所属进程调用的 API 被拒时，用 `VirtualAllocEx` + `WriteProcessMemory` + `CreateRemoteThread` 把位置无关 stub 注入目标进程，在目标进程内解析 `GetModuleHandleA` / `GetProcAddress` 后调用，返回值经远程结果槽读回。每个补丁写入后都会读回窗口真实状态校验，读回没变化就按失败记日志，不会出现「报成功但其实没生效」。补丁全部带原始状态快照，截图结束后逆序还原（还原同样读回校验）；另有 25 秒看门狗，截图线程卡死也会自动还原。修复后仍有异常时，改用该窗口的 `PrintWindow(PW_RENDERFULLCONTENT)` 取图，并只在体检结果更好时采用。

限制：目标进程必须与本程序位数一致（32 位目标不会被注入，只做重拍与 PrintWindow）；AppContainer/UWP、受保护进程或反注入驱动拦截时会跳过注入并在日志说明原因。控制台「截图异常自动修复（黑屏 / 闪屏 / 透明屏）」可随时关闭。

## 本地题库

控制台「上传题库」支持：

- Excel / CSV / TSV / TXT：第一列题目、第二列答案；可带「题目 / 答案」表头。
- PDF / Word（.docx）：自动提取「题目：/答案：」或「1. 题目 + 答案：」格式；扫描版 PDF 会自动 OCR 前 30 页。
- JSON：`[["题目", "答案"]]`、`{"题目": "答案"}` 或 `{"questions": [{"question": "...", "answer": "..."}]}`。
- 题目截图：选择 PNG/JPG/WebP/BMP 后逐张填写答案，按图片指纹匹配。

文本题库使用本地 RapidOCR 识别截图，命中后直接返回题库答案，未命中才调用模型；题库优先开关可随时关闭。题库保存在 `%APPDATA%\AI Screenshot Assistant\question_bank.json`。

## 使用方式

1. 启动程序，至少填写一把 DeepSeek、OpenRouter 或豆包 Key 并保存，再选择要走的路线和模型。
2. 确保手机与电脑连接同一局域网。
3. 用手机扫描桌面窗口中的二维码并保持页面打开。
4. 框选题目：在起点按住左键至少 2 秒，松开后移动到终点，再普通单击一次左键。
5. 全屏截题：在题目所在屏幕按住右键 2 秒后松开；macOS 也可用 Control+左键长按，或点击窗口里的「截取当前屏幕」。
6. 手机端也可以点击「截全屏」让电脑立即截取当前屏幕；需要补充条件或追问时，在输入框写问题后点击「截全屏并提问」。
7. 程序截图并分析，多题会按题号对应输出；答案会实时显示在手机端，若开启悬浮答案也会同步显示在桌面。
8. 资料分析等多屏题目：滚动页面后点「连续截图」或按 `Ctrl+Shift+左键` 缓存最多 5 张，再点「分析缓存」或按 `Ctrl+Shift+右键` 一起发送。
9. 手机长答案可用「上一页 / 下一页」阅读，也可勾选「自动翻页」并设置间隔秒数。

Windows 首次运行可能询问防火墙权限，请允许程序访问“专用网络”，否则手机可能无法连接电脑的 8000 端口。

### macOS 首次运行

1. 打开 DMG，将 `AutoAIAnswer.app` 拖入“应用程序”。
2. 由于当前版本未使用 Apple Developer ID 签名，首次打开请在 Finder 中右键应用并选择“打开”。
3. 根据系统提示，在“系统设置 → 隐私与安全性”中允许 **辅助功能**（监听框选手势）和 **屏幕录制**（截取题目区域）。
4. 授权后若手势或截图仍不可用，请完全退出应用后重新打开。

## 模型切换规则

- 手机和桌面都可以选择具体路线和模型：豆包 `doubao-seed-1-6-vision-250815`、OpenRouter `qwen/qwen3-vl-235b-a22b-thinking` / `qwen/qwen3-vl-32b-instruct`、DeepSeek `deepseek-flash`。
- 没填对应 Key 的路线会显示「未配置 Key」，不会发请求。旧的「简单」档在没有 DeepSeek Key 时仍可回落到 `qwen/qwen3-vl-8b-instruct`。
- 先走当前选中路线；该路线返回 HTTP 402 且还有其他 Key 时，按 OpenRouter → DeepSeek → 豆包再试一次。
- 认证失败、限流、超时、网络错误和服务端错误不会自动切换，以免重复消耗额度。

## 从源码运行

需要 Windows 或 macOS，以及 Python 3.11 或更高版本。

Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

macOS:

```bash
chmod +x run_desktop.sh
./run_desktop.sh
```

也可以直接编辑界面中的 Key 并保存。`.env` 仅用于首次提供默认值，已被 Git 忽略。

## 配置

复制 `.env.example` 为 `.env`，按需设置：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com

OPENROUTER_API_KEY=
OPENROUTER_MODEL=qwen/qwen3-vl-235b-a22b-thinking
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MODEL_TIER=good

# 截图异常修复（黑屏 / 闪屏 / 透明屏）
CAPTURE_REPAIR=1
CAPTURE_REPAIR_ATTEMPTS=3
CAPTURE_REPAIR_SAMPLES=2
CAPTURE_REPAIR_INJECT=1
CAPTURE_REPAIR_CONTENT=1
CAPTURE_REPAIR_STATE=1
CAPTURE_REPAIR_DIAGNOSTICS=1
```

`CAPTURE_REPAIR_ATTEMPTS` 是含首拍在内的取帧轮数（1–5），`CAPTURE_REPAIR_SAMPLES` 是每轮取几帧（1–4）；`CAPTURE_REPAIR_INJECT=0` 只做窗口 API 直调与重拍，不向目标进程注入；`CAPTURE_REPAIR_CONTENT=0` 关闭「窗口自身渲染比对」；`CAPTURE_REPAIR_STATE=0` 关闭「窗口状态兜底」；`CAPTURE_REPAIR_DIAGNOSTICS=0` 关闭异常截图自动写诊断文件。

不要提交真实 API Key。桌面界面保存的设置由 Qt `QSettings` 存储在当前系统用户配置中。

## 测试

```powershell
python -m pytest tests -q
```

## 构建单文件 EXE / macOS 应用

Windows（本仓库当前交付形态，产物名 `QQMusic-CustomerC.exe`）：

```bat
BUILD_CUSTOMER_C.bat
```

macOS（必须在 Mac 上执行，PyInstaller 不能交叉编译）：

```bash
chmod +x build_macos.sh
./build_macos.sh
```

生成 `dist/QQMusic.app` 与 `dist/QQMusic-macOS.zip`，并对 App 做 ad-hoc 签名。首次运行前请在「系统设置 → 隐私与安全性」中允许 **屏幕录制** 与 **辅助功能**，详见 [docs/MACOS.md](docs/MACOS.md)。公开构建不会嵌入本地 `.env` 或任何 API Key；仓库已忽略 `dist/`、`build/`、`.env` 和 `*.spec`。

### GitHub Actions 自动出包

推到 GitHub 后，打 `v*` 标签即触发 [`.github/workflows/build-macos.yml`](.github/workflows/build-macos.yml)：在 `macos-14` 上跑回归 → `packaging/macos/package.sh` 打 App → 上传 `QQMusic-macOS-arm64.zip` 与校验和 → 自动创建/更新同名 Release。也可以在 Actions 页面手动触发（只留 artifacts，可勾选同时构建 Intel 版）。

```bash
git tag v0.2.63
git push origin v0.2.63
```

注意：仓库 **Settings → Actions → General → Workflow permissions** 需要选 “Read and write permissions”，否则 Release 挂不上资产；`.gitattributes` 已统一换行，避免 Windows 提交的 CRLF 破坏 macOS 上的 bash 脚本。

## 安全说明

- API Key 在用户要求下以明文形式显示和保存，请只在可信电脑上使用。
- 桌面悬浮窗是普通置顶窗口，可能出现在屏幕共享或录制内容中。
- 本项目不提供规避录屏、共享屏幕或监控检测的功能。

## License

当前仓库未附带开源许可证。未经作者明确授权，不代表允许复制、修改或再分发。
