# 跨语境迁移实验

`agora-transfer-v1` 把源语境准备、公开经验迁移、目标语境连续互动和配对统计接到实际运行器。
当前测的是上下文经验迁移，不修改模型权重，不把源世界的粉丝、信任、数据库或隐藏评分带到
目标世界。全部报告仍标为 `uncalibrated-development`。

## 离线运行

在仓库根目录运行，输出目录必须不存在：

```bash
PYTHONPATH=. .venv/bin/python examples/agora_oasis/transfer_demo.py \
  --output /tmp/agora-transfer-demo --seeds 1,2
```

这个工程示例使用人为定义的两个 toy 社群、同一小红书平台、同一中文旅行任务，以及明确标为
开发用途的规则 Agent/受众/评委。相反的偏好仅用于检查迁移与恢复链路，不代表真实文化差异。
示例没有调用外部模型，不可作为模型或人类能力的证据。

只生成模板、不运行：

```bash
PYTHONPATH=. .venv/bin/python examples/agora_oasis/transfer_demo.py \
  --output /tmp/agora-transfer-config --prepare-only
.venv/bin/agora-benchmark transfer-run /tmp/agora-transfer-config/transfer.json
.venv/bin/agora-benchmark transfer-run /tmp/agora-transfer-config/transfer.json --resume
```

## 每个 seed 的七个阶段

| 阶段 | 起点 | 携带的前序经验 | 用途 |
|---|---|---|---|
| source_preparation | 源 Artifact 新副本 | 无 | 获取源语境公开经验 |
| target_preparation | 目标 Artifact 新副本 | 无 | 获取目标语境公开经验 |
| source_reference | 源 Artifact 新副本 | 源经验 | 源语境参考表现 |
| target_cold | 目标 Artifact 新副本 | 无 | 无前序经验的目标基线 |
| target_transfer | 目标 Artifact 新副本 | 源经验 | 测迁移后的首次表现和适应 |
| target_transfer_hidden | 目标 Artifact 新副本 | 相同源经验 | 隐藏本轮评论反馈的对照 |
| target_native | 目标 Artifact 新副本 | 目标经验 | 目标语境经验基线 |

所有目标评测使用相同目标 Artifact、seed、任务、模拟时长和预算上限。源准备和目标准备的
预算上限也一致。每个阶段创建新的 Candidate、Observer、受众及客户端实例，防止把对象内存
或聊天会话作为未记录的迁移通道；可以复用无会话状态的外部推理服务。

`target_native` 不是“原生模型能力”的真值，只是经过同等准备预算的目标经验条件。
`target_cold` 不支付准备成本，不能声称它与有经验条件的端到端成本相同。

## 语境与任务配对

每个 Artifact 的 metadata 必须冻结：

```json
{
  "context": {
    "platform": "xiaohongshu",
    "culture": "community-a",
    "domain": "travel",
    "language": "zh-CN"
  },
  "transfer_pair_id": "travel-pair"
}
```

可以在创建 Artifact 时使用：

```bash
.venv/bin/agora-benchmark artifact-create source-world data/artifacts/source-v1 \
  --artifact-id source-v1 --version 1 --candidate-user-id 1 \
  --context-config source-context.json --transfer-pair-id travel-pair
```

`scenario-build` 同样支持这两个参数。它们冻结配对注释，不会自动生成符合该文化的内容或
受众；研究者仍需准备并审查配对数据和 Persona。

`axis` 只能是此次唯一改变的语境字段。例如 `axis=culture` 时，平台、语言和垂域必须相同。
源与目标还必须保持任务族版本、评委池版本、曝光策略、初始 tick 和角色数量一致，并声明同一
`transfer_pair_id`。一个实验对应一个任务对和多个 seed；不同任务对分别运行，避免把任务难度
变化直接解释为文化变化。这些检查不能代替人类对任务语义和文化真实性的审核。

## 配置结构

实验配置指向两个已有 episode 模板，实际 Candidate/Observer/受众由同一个顶层 `runtime`
统一配置。episode 模板中的 runtime 设置不用于迁移实验。

```json
{
  "experiment_id": "travel-culture-v1",
  "pair_id": "travel-pair",
  "axis": "culture",
  "source": {
    "episode_config": "source-episode.json",
    "context": {"platform":"xiaohongshu","culture":"community-a","domain":"travel","language":"zh-CN"}
  },
  "target": {
    "episode_config": "target-episode.json",
    "context": {"platform":"xiaohongshu","culture":"community-b","domain":"travel","language":"zh-CN"}
  },
  "seeds": [1, 2, 3],
  "preparation": {"max_ticks":3,"budget":{"max_actions":3,"max_model_calls":4}},
  "evaluation": {"max_ticks":3,"probe_ticks":1,"budget":{"max_actions":3,"max_model_calls":4}},
  "memory_max_chars": 12000,
  "output_root": "outputs/travel-culture-v1",
  "runtime": {
    "candidate_policy": "feedback-adaptive-development",
    "observer": "scripted-development",
    "audience": {"type":"scripted-development"}
  }
}
```

episode 配置路径和 provider 配置路径相对实验配置文件解析；Artifact 路径相对各自 episode
配置文件解析。`--output-root` 可以覆盖输出目录。

接真实模型时，沿用已有 provider 配置和环境变量凭据，把顶层 runtime 改为 model 类型：

```json
{
  "candidate": {"type":"model","policy_id":"candidate-v1","policy_version":"1","provider_config":"candidate-provider.json"},
  "observer": {"type":"model","observer_id":"judge-v1","observer_version":"1","provider_config":"judge-provider.json"},
  "audience": {"type":"model","policy_id":"audience-v1","policy_version":"1","provider_config":"audience-provider.json"}
}
```

这些配置放在实验文件的 `runtime` 下。模型请求次数限制要足够覆盖单阶段预算和重试；受众和
评委有独立请求量。上面是结构示例，没有验证任一外部 endpoint。

## 经验如何迁移

经验文件为 `seed-N-source-experience.json` / `seed-N-target-experience.json`。内容包括源语境
描述、Candidate 已实际观察的 Feed/评论、自己执行的动作，以及随后一轮能看到的公开工具结果。
不会读取评委分数、隐藏 Persona/关系状态、环境内部事件或模型推理文本。最后一步尚未提供给
后续 `act()` 的工具结果也不迁移。

用户、帖子、评论和媒体文件的结构化 ID 与路径会被移除；当前世界的 ID 和可用素材仍来自
当前 observation。图片不跨世界复制，只保留公开文字描述。经验使用统一的字符上限，优先保留
最近记录，必要时截短文本。字符上限不等于 token 上限；经验带来的输入 token 成本照常计入
目标阶段预算。

经验以 `transfer_experience` 提供给 Candidate，且有 SHA-256 校验和来源 run 记录。Agent
收到副本，不能修改其他条件的经验。Observer 不会收到该经验，也不会收到迁移条件标签。

## 怎么读结果

`transfer-report.json` 含每个 seed 的全部阶段、失败/不完整状态、经验校验和、资源用量和：

- 初始迁移差距：源参考条件初始窗口减去携带源经验的目标初始窗口；
- 适应增益：携带源经验的目标末窗口减去其初始窗口；
- 目标经验基线差距：目标经验条件末窗口减去源经验条件末窗口；
- 同目标语境对照：源经验减去无经验、可见评论减去隐藏评论，以及目标经验减去无经验。

窗口长度由 `probe_ticks` 指定，初末窗口不重叠。每个维度使用归属于该窗口动作的独立评委
增量除以实际曝光机会，分别报告态度、信任和继续互动意愿；这不是累计信任水平或热度总分。
延迟评估按最初触发它的 action 归属；若缺少曝光、仍有待结算判断、评委信心为零，或提前停止
导致窗口不完整，就报告缺失，不用零分伪造完整结果。失败、不完整 seed 的数量与阶段始终保留。

置信区间仅描述当前任务对的 seed 重复，单个样本不报告区间；不能解释为跨真实文化、人群或
任务总体的置信区间。初始迁移差距还受语境难度影响，应结合目标语境内部对照与目标经验基线
理解，不能只拿跨语境分差宣称因果迁移效果。

`phase_costs` 记录实际实验各阶段的 Candidate、受众和评委调用/token；
`standalone_condition_costs` 为每个条件加上对应准备阶段成本和动作数。后者是独立复现实验
条件所需的成本分解，多个条件共享同一份源经验时，不要把准备成本重复算进实际总账。

## 恢复与正式实验边界

`--resume` 只复用已完成的阶段，不会再次发模型请求。实验计划、实现、模型、Artifact 或预算
变化会被拒绝。已经失败或调用消耗不明的阶段不静默重置后重跑，需要新实验目录，已花费成本
仍保留在旧报告中。

当前已补齐执行协议与开发验证，真实文化/垂域配对数据、模型选择、经授权的真实反馈和人类
校准仍需另行准备。不要把 toy 示例、词汇规则策略或未校准评委的输出写成论文实证结果。
