# v0.2.61

针对「换了电脑还是截不到透明窗口」再修一轮：把判定从「靠像素证据」改成「像素 + 窗口状态双通道」，并加了现场诊断文件。

## 为什么上一版还不行

带 `WDA_EXCLUDEFROMCAPTURE` / `WDA_MONITOR` 的窗口，`PrintWindow` 也返回全黑（实测 detail=0.0）。上一版靠「窗口自身渲染 vs 截图」的互相关找内容缺失，这类窗口恰好没有任何可比对的内容，所以判定为「窗口自身没有可用内容」，什么都不做——正好漏在最常见的防截图方式上。

## 改动

- 新增窗口状态兜底：取截取区域**最上层**（按 `EnumWindows` 的 z-order，不再是按覆盖面积）的窗口，若它带 `WDA_MONITOR` / 捕获排除 / `DWMWA_CLOAK` / 图层 alpha < 250 / `WS_EX_NOREDIRECTIONBITMAP`，直接判「内容缺失」并打补丁，不再依赖像素证据。
- 窗口探测改为按 z-order 排序，`content_image` / `first_hiding_window` / `PrintWindow` 回退都只认「区域最上层那个窗口」，避免拿背景窗口的渲染结果冒充截图（上一版会把别的窗口内容当结果返回）。
- 打补丁只动两类窗口：带藏画面标志的，和区域最上层那一个；其余窗口不再重绘。
- 新增「截图诊断」按钮：抓一帧 + 枚举覆盖窗口（hwnd/class/title/pid/位数/rect/exstyle/affinity/cloaked/layered/noredir）+ 逐个窗口 PrintWindow 探测，写成 `%LOCALAPPDATA%\QQMusic\Logs\capture-diagnose-<时间>.txt`，控制台回显路径；异常截图也会自动落一份。
- 新增环境变量 `CAPTURE_REPAIR_STATE`（状态兜底，默认开）、`CAPTURE_REPAIR_DIAGNOSTICS`（自动诊断报告，默认开）。

## 验证

- Python 回归 317 项通过，1 项非 Windows 占位测试跳过。
- 实机端到端（`WDA_EXCLUDEFROMCAPTURE` 的 720×460 答题窗口）：捕获排除 0x11，纯截图细节 20.5（只有背景）→ 状态兜底判「内容缺失」→ 注入解除捕获排除成功 → 重拍细节 53.5，尝试 2 次、来源为桌面抓取（不再借别的窗口）→ 结束后状态还原为 0x11。
- 诊断文件实测包含窗口表与 PrintWindow 探测：该窗口 `affinity=0x11`、`PrintWindow=成功 detail=0.0`，可直接看出「PrintWindow 拿不到内容，必须解除保护后重拍」。
