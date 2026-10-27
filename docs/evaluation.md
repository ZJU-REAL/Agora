# Agora 评测流程

## 1. 准备输入

一次评测需要平台数据、NPC Persona、场景、媒体、Candidate 配置、Observer 配置、曝光规则、
最大 tick 和随机种子。原始数据先导入可编辑世界，检查后冻结为 WorldArtifact。

## 2. 启动 Episode

Runner 会依次：

1. 校验 EpisodeManifest，确保只有一个 Candidate；
2. 校验 Candidate、Artifact、平台、Observer 和曝光策略版本；
3. 校验 Artifact 文件 SHA-256；
4. 克隆独立 SQLite 和媒体目录；
5. 写入 manifest 和 provenance；
6. 初始化 NPC 四维状态和延迟判断队列。

## 3. 模拟器中的单 Tick

```text
生成 Candidate Observation
（主题内人类内容 + 此前的 Candidate 内容）
        ↓
Candidate 观察并选择一个 Action
        ↓
Agora-OASIS 校验并执行
        ↓
冻结本 tick 的 NPC 共享内容池
（主题内人类内容 + 最新 Candidate 内容）
        ↓
按 seed 冻结 NPC 行动顺序
        ↓
每个 NPC 个性化排序同一个内容池并行动
（较早的点赞/评论可影响较晚 NPC 的排序）
        ↓
保存受众关系记忆并推进模拟时钟
        ↓
Observer 对实际曝光受众判断直接、旁观和延迟影响
        ↓
更新独立评测状态
        ↓
写入 trajectory.jsonl
```

这里的“共享内容池”表示所有 NPC 在同一 tick 面对相同的候选帖子集合，并不表示所有 NPC
看到完全相同的顺序。内容池包含 Artifact 中按任务主题冻结的人类帖子，以及该 episode 内
Candidate 已发布的帖子；NPC 在当前 tick 新发的帖子到下一 tick 才进入池。排序使用固定公式，
综合兴趣、关注关系、时效和当前互动量，不调用 Twhin 等学习型推荐模型。

NPC 的处理顺序由世界 seed 和 tick 唯一决定并写入事件日志。每个 NPC 行动前重新计算排序，
因此排在前面的 NPC 点赞后，帖子热度会立刻变化，后面的 NPC 可能看到不同排名。这种顺序效应
是模拟对象，但在相同 Artifact、Candidate、seed 和配置下完全可复现。轨迹会保存每个 NPC 的
共享池、实际排序和点赞/评论动作，便于解释传播路径。

Candidate 可以看到账号资料、当前 tick、受控 Feed、评论树、公开互动数据、平台 action 和允许
使用的媒体，还会收到明确任务、文化背景、此前动作/工具结果和剩余预算；不能看到 NPC 隐藏
状态、未来事件、Observer 判断或其他 Candidate 的结果。预定公开反馈在 Candidate 观察前注入。

VLM 还会收到真实图片、多图顺序、视频关键帧和 transcript。模型返回一个 JSON action，
Runner 校验 action 类型、必填参数、目标 ID 和媒体白名单后才修改世界。
Provider 配置必须显式设置 `"supports_vision": true` 才会发送视觉内容；纯文本模型保持
`false`，避免把图片请求误发给不支持视觉的 endpoint。

`sandbox.advance()` 先执行受众策略，写入受众关系记忆与公开动作，并推进 tick。默认是明确
标为开发用途的内容规则策略，也可配置独立模型受众。之后 Observer 仅对实际看到本轮内容的
受众，根据 action、原帖、Persona、文化、历史、公开反应和相关媒体生成四维 delta 与证据。
评分状态更新经过范围校验、置信度加权和裁剪，并绑定唯一 `action_id`。评分不直接驱动 NPC。

## 4. 结束与报告

达到 `max_ticks`、Candidate 返回 `stop` 或发生不可恢复错误时结束。Runner 结算到期的延迟
影响，并输出：

- `trajectory.jsonl`：逐 tick observation、action、outcome、模型调用和状态变化；
- `metrics.json`：态度、唤醒度、信任、互动意愿、对话、冲突和时机指标；
- `attribution.json`：最正向和最负向的 action；
- `result.json`：运行状态、tick 和 action 数。

## 5. 多 Seed 比较

每个 Candidate 在同一 Artifact 和场景上独立运行多个 seed。聚合前必须保证协议、世界、平台、
场景、Observer 和曝光策略版本一致。报告给出成功/失败数、均值、标准差和 95% 置信区间。
新增 Candidate 只运行自己的 episode，不需要重跑历史 Candidate。

`social-feedback-v1` 另输出行为率、创作者统计、负反馈观察/响应窗口和各类模型成本。旧对话/
时机等粗略指标明确标为 legacy proxy；所有未校准报告标为 `uncalibrated-development`。
配置、恢复语义和匿名校准方法见 [社会反馈闭环](social-feedback.md)。

## 6. 命令示例

```bash
agora-benchmark scenario-build \
  configs/benchmarks/xhs-conflict-dev.scenarios.json \
  xhs-questioning-001 data/artifacts/xhs-questioning-v1 \
  --artifact-id xhs-questioning-v1 --version 1

# 对已导入的数据世界，可直接声明 Candidate 用户并冻结：
agora-benchmark artifact-create xhs-demo data/artifacts/xhs-v1 \
  --data-root data/worlds --artifact-id xhs-v1 --version 1 \
  --candidate-user-id 1 --scenario-id xhs-operation-v1 \
  --content-topic 旅行 --content-topic 摄影 \
  --candidate-asset cover.jpg=dataset/media/cover.jpg

agora-benchmark episode-init \
  data/artifacts/xhs-questioning-v1 configs/benchmarks/run.json \
  --run-id candidate-seed-1 \
  --candidate-provider-config providers.local.json \
  --candidate-policy-id candidate-v1

agora-benchmark run configs/benchmarks/run.json --dry-run
agora-benchmark run configs/benchmarks/run.json
agora-benchmark batch-run configs/benchmarks/run.json \
  --seeds 1,2,3,4,5 --max-concurrency 2
```

正式发布结果前还需冻结跨模型家族的 Observer pool，并使用目标平台用户进行盲测校准；这不
影响当前开发测评流程。
