# v0.2.69

手机端代码答案字号可以更小，并新增「自适应」：长答案自动缩到能整段塞进答案框，且设置会一直记住。

## 新增 / 改动

- 代码字号选项：**自适应（默认）**、特小 6px、小 8px、较小 10px、中 13px、大 16px。
- **自适应算法**：渲染后从 13px 起逐级往下试，取「答案框不出现纵向滚动」的最大字号，下限 6px；换题、放大/还原、旋转屏幕、窗口尺寸变化都会重新计算。
- CSS 修正：`font` 简写换成 `font-family` + `font-size: var(--code-font-size)` + `line-height`，避免部分手机浏览器忽略 `var()` 导致字号不生效；答案区加 `text-size-adjust: 100%`，防止移动端自动放大字号。
- **设置持久化到两端**：
  - 手机端存 localStorage，换下一题仍然是这个字号；
  - 改动时发 `command.set_code_view` 给电脑端，电脑端存进 QSettings（`phone/code_font`、`phone/code_wrap`）；手机每次连接，电脑端主动推 `code.view`，清缓存或换手机也不会丢设置。
- 默认「代码自动换行」保持开启，配合自适应字号，长代码整段可见。

## 验证

- Python 回归 **367 项通过**，1 项跳过；`node --check app.js` 通过。
- 新增/更新测试：字号选项与 `value="auto"`、`fitCodeFont` 的上下限与循环条件、`command.set_code_view` 经手机 WS → 后端 → 桌面 WS 的转发、桌面端 `phone/code_font` / `phone/code_wrap` 持久化与 `code.view` 推送。
- 实机：启动 EXE 后从 `127.0.0.1:8000` 实拉 `app.js` 52,005 字节（含 `fitCodeFont`、`CODE_FIT_MIN = 6`、`applyCodeViewFromDesktop`）、首页 6,128 字节（含 `value="auto"` 与「自适应」）、`style.css` 11,876 字节（含 `font-size: var(--code-font-size)`、`text-size-adjust`）。
