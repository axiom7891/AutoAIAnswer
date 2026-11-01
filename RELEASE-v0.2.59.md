# v0.2.59

- 新增「截图异常自动修复（黑屏 / 闪屏 / 透明屏）」，默认开启，可在控制台关闭。
- 每轮取 1–4 帧做体检，识别全黑、局部黑块、纯色空白、整屏透明，以及正常帧与异常帧交替的闪屏；正常帧里取细节最丰富的一帧，异常帧也保留最健康的一张，避免丢内容。
- 判定异常后按 z-order 定位覆盖截取区域的窗口，按缺陷类型打临时补丁：解除 `WDA_MONITOR` 捕获排除、取消 DWM `DWMWA_CLOAK`、把分层窗口 alpha 还原为 255 并清色键、移除 `WS_EX_NOREDIRECTIONBITMAP` 直出、强制重绘并刷新 DWM。
- 补丁先在本进程直调窗口 API；`SetWindowDisplayAffinity` 这类仅限窗口所属进程的调用被拒时，改为向目标进程注入位置无关 stub（`VirtualAllocEx` + `WriteProcessMemory` + `CreateRemoteThread`），在目标进程内解析 `GetModuleHandleA` / `GetProcAddress` 后调用，返回值经远程结果槽读回；32 位与 64 位不一致的目标不会注入，只做重拍与 PrintWindow。
- 补丁带原始状态快照，截图结束后逆序还原；每个补丁写入后都读回窗口真实状态校验，还原也读回校验，不会把「调用返回成功但系统拒绝」当成已修复。另有 25 秒看门狗兜底。重拍仍异常时改用该窗口的 `PrintWindow(PW_RENDERFULLCONTENT)`，只在体检结果更健康时采用。
- 修复摘要回显到控制台日志，手机端同步提示「截图黑屏已自动修复，正在分析」。
- 新增环境变量：`CAPTURE_REPAIR`、`CAPTURE_REPAIR_ATTEMPTS`、`CAPTURE_REPAIR_SAMPLES`、`CAPTURE_REPAIR_INJECT`。

## 验证范围

- Python 回归 294 项通过，1 项非 Windows 占位测试跳过。
- 合成图覆盖黑屏、噪声黑屏、纯色空白、整屏透明、局部黑块、边缘黑条、暗色主题正常页、闪屏混合帧与最稳帧选择。
- 注入引擎在自身进程内实机验证：单参数与 7 参数 stub 均正确执行，栈参数经远程 `SetRect` 回读校验。
- 带 `WDA_MONITOR` 的真实窗口端到端实测：截图平均亮度 0.0 → 249.2，目标捕获排除 1 → 0（注入解除）→ 还原回 1。
- 透明屏补丁跨进程实测：分层窗口 alpha 89 → 255，还原回 89。
- 真实屏幕取帧 1280×800 用时 0.32 秒，判定正常、无误报；PrintWindow 回退对真实窗口返回 PNG。
- UWP/AppContainer 窗口的扩展样式改写被系统拒绝，按设计报告失败并降级为重拍与 PrintWindow；真实答题端的修复效果仍需目标设备验收。
