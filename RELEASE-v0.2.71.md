# v0.2.71

电脑键盘改回**纯方向键**遥控手机答案框，并加了三重保底，解决「有人电脑上按了没反应」。

## 改动

- 遥控按键改为 **↑ / ↓ / ← / →**，不再需要 Ctrl 或 Alt；只保留这四个键（WASD、Ctrl+Alt+P 全部移除）。
- 控制台新增开关「方向键 ↑ ↓ ← → 直接遥控手机答案框（不用组合键）」，默认勾选，状态写入 QSettings（`phone/arrow_remote`）。
- 方向键在别的软件里照常可用（不拦截、不吞键），只是同时把滚动指令发给手机。

## 为什么之前可能不生效（三重保底）

1. **按键采集双通道**：pynput 全局钩子之外，新增 Win32 `GetAsyncKeyState` 每 40ms 轮询，钩子被安全软件或管理员权限挡掉时轮询仍然有效；两条通道都触发时按 60ms 去重，不会重复滚动（实测 5 次按键 = 5 条指令）。
2. **传输双通道**：WebSocket 事件之外，新增 HTTP `POST /scroll/{session_id}` 队列，手机页面每 700ms 轮询 `GET /scroll/{session_id}?after=N`。只要手机能打开页面，HTTP 这条路必定可用，不再依赖 WS 状态。
3. **进程唯一性**：排查时发现本机有一个旧的 `QQMusic-CustomerC-v0.2.69.exe` 仍在占用 8000 端口，导致手机连的是旧版本、看起来「新功能没生效」。升级时请先在任务管理器结束所有 `QQMusic-CustomerC*.exe`，再启动新版本。

## 验证

- Python 回归 **374 项通过**，1 项跳过；`node --check app.js` 通过。
- 新增测试：纯方向键映射、VK 码、WASD/其他键忽略、60ms 去重、轮询上升沿、禁用时轮询不发、`/scroll` 队列往返与非法方向 400。
- 实机（Windows）：EXE 启动后 `POST /sessions` 建会话，用 pynput 合成 ↓↓→↑← 五次按键，回调与 HTTP 队列都恰好 5 条且顺序一致；`app.js` 52,968 字节含 `pollScrollCommands`，`/scroll/` 两个端点已注册。
