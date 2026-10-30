# P0 社会反馈闭环

本轮引擎版本为 `social-feedback-v1`，新建评测配置默认协议为 `agora-feedback-dev-2`。
已有 Artifact 可以作为起点，但新旧引擎的结果不能混合聚合，旧 episode 不能直接续跑。

## 运行链路

1. 从 Artifact 克隆独立世界，应用 episode seed；
2. 按模拟 tick 注入已冻结的公开反馈事件；
3. Candidate 接收任务、文化背景、当前 Feed、此前行动与工具结果、剩余预算；
4. 校验并执行 Candidate 动作；
5. NPC 根据实际曝光、内容、Persona、文化规范和关系历史生成反应；
6. 保存受众自己的关系状态，影响后续点赞、收藏、评论、关注和取消关注；
7. 独立 Observer 仅评估本轮实际曝光的受众，读取原帖、历史、受众背景和实际公开反应；
8. 保存轨迹、检查点和独立的行为/关系/反馈窗口指标。

环境受众与 Observer 分离。Observer 的评估分数不会直接操纵 NPC；NPC 使用自己的关系记忆。
关系记忆按“受众用户—内容作者”保存，每对关系保留最近 20 次互动。Candidate 无法看到这些
隐藏状态或未来反馈安排。

默认 `ScriptedDevelopmentAudience` 是明确标注的词汇规则基线，会区分敌意、修正和普通表达，
根据自定义文化规范中的 `avoid_phrases`/`prefer_phrases` 调整反应。它用于确定性开发回归，
不代表人类反应已被准确模拟。模型受众通过独立的 `audience` provider 接入。

## 立即运行本地示例

在仓库根目录执行，输出目录必须是新的：

```bash
PYTHONPATH=. .venv/bin/python examples/agora_oasis/feedback_demo.py \
  --output /tmp/agora-feedback-demo
```

该示例从相同 Artifact、seed 和动作预算出发，分别运行 `visible` 和 `hidden` 反馈条件。
第 1 tick 的用户评论指出预算与身体限制；规则 Candidate 在看见该反馈时回应并修正。
输出包括两个 episode 的 `trajectory.jsonl`、`metrics.json`、`attribution.json` 和世界副本。
这验证反馈闭环和消融接口，不是模型能力或真人一致性的实验结论。

## 配置

在 `agora-benchmark episode-init` 生成的配置中，设置 `episode.metadata`：

```json
{
  "task": {
    "objective": "发布旅行图文，理解用户异议并调整建议",
    "persona_constraints": {"role": "旅行博主"}
  },
  "culture": {"community": "evidence-first", "domain": "travel"},
  "budget": {"max_actions": 6, "max_model_calls": 8, "max_total_tokens": 12000},
  "feedback_condition": "visible",
  "feedback_schedule": [
    {"tick": 1, "actor_id": "reader", "post_id": "latest_candidate",
     "content": "这个建议没有考虑我的预算限制。", "valence": "negative"}
  ]
}
```

`reader` 必须是 episode 中实际存在的 NPC actor ID。`post_id` 也可指定可见帖子的整数 ID；
`latest_candidate` 要求该 tick 前已存在 Candidate 帖子。tick 是模拟世界的绝对 tick。
反馈事件不能代表未经授权的真人反馈。

`hidden` 条件移除 Candidate 所见 Feed、评论树以及工具结果历史中的受众评论，保留环境本身
的互动。它是“隐藏评论反馈”条件，不会隐藏公开点赞数或流量；不是完全无反馈条件。

给配置增加与 `candidate`、`observer` 同级的 `audience` 字段，可启用模型受众：

```json
{
  "audience": {
    "type": "model",
    "policy_id": "audience-v1",
    "policy_version": "1",
    "provider_config": "audience-provider.json"
  }
}
```

provider 使用现有 provider 配置格式、环境变量凭据及请求限制。声明 `supports_vision: true`
时，模型受众能接收本轮帖子的真实图片或视频帧。模型受众与 Observer 应分别配置，前者扮演
环境用户，后者承担独立评估；更换任一策略或 provider 配置都不能直接续跑旧 episode。

NPC 的文化规范在 Persona 的 `culture` 字段配置；场景用户支持独立 `locale` 和 `culture`。
平台、语言、垂域和文化因此可以分别配置，不能默认把三个平台当成三种文化。

## 预算和恢复

- 动作预算包含搜索、查看、发帖和评论；调用预算包含 Candidate 的重试与失败调用。
- 总 token 预算需要 provider 提供完整 usage。缺失 usage 或返回后超预算时，本轮不提交世界
  改动，运行失败，并保存已消耗调用。token 是返回后核算；不能保证网络请求发出前精确预知
  输入 token 成本。
- Candidate、受众和 Observer 调用分别记录。受众/Observer 仍按各自 provider 的请求限制计费。
- 每轮保存数据库检查点；可捕获失败会恢复到上一完整轮。续跑恢复历史、关系和调用计数。
- 无法确定调用消耗的硬中断不会静默重置预算后续跑；需要创建新 run。
- 已完成 episode 的 resume 返回已有结果；更换实现、模型配置或评委不能沿用旧结果。

## 指标与校准

`metrics.json` 增加：

- `behavioral_metrics`：实际曝光机会、各类行为数量和每次曝光的行为率；
- `creator_metrics`：排除作者自己的点赞、评论等互动统计；
- `feedback_adaptation`：具体负反馈 ID、首次被 Candidate 看见的轮次、后续响应及评委估计的
  信任变化，明确标为 `descriptive_not_causal`；
- `audience_usage` 和 `token_usage_complete`：独立受众成本及用量是否可核验。

旧的“首帖与末帖热度差”不再冒充反馈适应，旧 timing/dialogue 等粗略指标明确标为 legacy proxy。
所有结果目前标为 `uncalibrated-development`，没有输出新的万能总分。

人工校准导出会随机化 item ID 和行序，不包含模拟评分、评委身份或 action rationale。
私有对齐表写入 `标注文件名.private-key.jsonl`（权限 0600），不要交给标注者：

```bash
.venv/bin/agora-benchmark calibration-export labels.jsonl /path/to/run
# 完成人类评分后，在实验管理端合并私有对齐表：
.venv/bin/agora-benchmark calibration-report labels.jsonl \
  --private-key labels.jsonl.private-key.jsonl
```

恒定打分造成零方差时，相关系数为 `null`，`correlation_status` 为 `zero_variance`。
跨语境可用 `paired_transfer_report()` 按配对任务/seed 输出各维度的初始差距、适应收益和目标
原生基线差距；原来的平台最强/最弱比值只保留为 legacy 平台分布摘要。

源经验传递、固定预算和配对运行已接入 [跨语境实验](transfer.md)。仍需独立准备真实文化/垂域
任务、人类标注及经授权的真实反馈；这些实证工作不能由规则回归通过代替。
