# v0.2.64 — macOS 首次成功出包

这一版没有改功能，只修了在 macOS CI 上暴露出来的两处问题，并让 GitHub Actions 真正产出 `.app`。

## 修复

- `mouse_listener._is_ctrl_shift_held()` 在 Windows 分支里写了函数内 `import ctypes`，导致 macOS 分支调用 `ctypes.util.find_library` 时抛 `UnboundLocalError`（等于 Mac 上一按左键就崩）。改为使用模块级 `ctypes`。
- `tests/test_overlay_keepalive.py` 的 timer 断言写死 150ms；macOS 上是 400ms（`MAC_FRONT_INTERVAL_MS`），改为按平台取期望值。
- 新增回归：非 Windows 平台下 `_is_ctrl_shift_held()` 必须安全返回 `False`。

## CI

- 工作流新增 `main` 分支触发（只跑测试与打包，不建 Release），tag 触发仍会发布。
- 测试步骤改为 `set -o pipefail | tee`，失败时把 pytest 尾部写进 job summary，并把 `FAILED ...` 行输出成注解，方便直接定位（这次就是靠它拿到两条失败原因的）。

## 验证

- 本地：340 项通过，1 项跳过。
- GitHub Actions（`macos-14`，run 41302465851）：`Run tests`、`Build QQMusic.app`、`Checksums`、`Upload artifacts` 全部 success，产出 `QQMusic-macOS-arm64.zip`。
- 发版（tag `v0.2.64`，run 41302735555）：构建与 `Attach to GitHub Release` 均 success。

## 产物

- Release：https://github.com/axiom7891/AutoAIAnswer/releases/tag/v0.2.64
- 资产：`QQMusic-macOS-arm64.zip`（152,386,190 字节，SHA256 `2552a519…02f2b5b9`）、`SHA256SUMS-arm64.txt`（内容与实际文件一致）
- macOS 真机首次运行仍需允许「屏幕录制」与「辅助功能」。
