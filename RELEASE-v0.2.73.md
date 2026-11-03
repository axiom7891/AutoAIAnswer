# v0.2.73

两条改动：接入三个新模型路线，悬浮字幕透明度放开到 0–100%。

## 新增模型路线

| 路线 ID | 模型 | 说明 |
|---|---|---|
| `openrouter-deepseek-v41` | `deepseek/deepseek-v4.1-flash-1017` | 走 OpenRouter，属国产模型白名单，无需额外开关 |
| `openrouter-claude-opus-55` | `anthropic/claude-opus-5.5` | 走 OpenRouter，标记为境外模型（需 OpenRouter Key） |
| `openrouter-gpt-6-luna` | `openai/gpt-6-luna` | 同上 |

三个路线同时出现在**电脑端下拉框**（由 `route_options()` 自动带出）和**手机端模型下拉**；别名、`resolve_model_choice`、`TIER_LABELS` 一并补齐。

### 不影响正常使用的保护

新模型 ID 是否在 OpenRouter 上线不由本地决定，所以加了一层兜底：

- `VisionClient._friendly_http_error` 把 OpenRouter 的 **400 / 404 / 422**（模型不存在、未开通、参数不被支持）转成 `ModelUnavailableError`；
- `FailoverVisionClient` 捕获它后，自动 `apply_model_tier(DEFAULT_MODEL_TIER)` 回退到默认路线并**重试一次**，截图流程不会因为选了一个不存在的模型直接报错；
- 回退只做一次（切换后 `_requested_tier` 已是默认路线，二次失败按原逻辑抛错），不会死循环；
- 豆包 404 的原有提示（模型未开通）保持不变；402 额度不足仍按原逻辑切换供应商。

## 悬浮字幕透明度

- 滑块范围由 **15–100** 改为 **0–100**，0% 即完全透明；
- 初始值读取与 `StreamingOverlay.set_opacity_percent` 的下限同步改为 0。

## 验证

- Python 回归 **387 项通过**，1 项跳过。
- 新增测试：三条路线的模型 ID 精确匹配、境外标记、`resolve_model_choice` 解析、`_switch_to_default_route` 只回退一次、OpenRouter 404 → `ModelUnavailableError`、手机端下拉包含三条新路线、透明度 0–100。
- 既有模型测试同步更新为 11 条 OpenRouter 路线与新的境外模型集合。
