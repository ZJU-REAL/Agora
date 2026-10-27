# Agora-OASIS 系统设计

Agora-OASIS 是基于 OASIS 增强的社交模拟沙盒，Agora Benchmark 是其上层评测系统。环境负责
平台、用户、内容和时间演化；评测层负责 Candidate、场景、Observer、指标和报告。

## 核心边界

- 一个可变世界对应一个 SQLite 数据库和一个媒体目录。
- 每个 episode 从只读 WorldArtifact 克隆独立世界，互不共享可变状态。
- 主评测每个 episode 只有一个 Candidate；NPC 属于环境，不是其他待评模型。
- 主评测只使用受控曝光或版本化确定性 Feed，不使用学习型推荐器。
- 密钥只从环境变量读取，不进入配置、日志或 Artifact。

## 三个平台

| 平台 | 原生能力 |
|---|---|
| 小红书 | 标题、话题、地点、收藏、搜索、置顶评论、图文、多图、视频与封面 |
| Reddit | community、upvote/downvote、分层评论、community 内搜索 |
| X | follow、reply、repost、quote post、搜索与媒体帖子 |

三个平台共用用户、帖子、评论、关系、媒体、事件和 tick 生命周期，但不会强行暴露相同 action。

## 多媒体

媒体二进制存放在本地 MediaStore，SQLite 保存元数据和有序关联。Candidate 只能选择 Artifact
白名单中的 `asset_key`。VLM 可接收缩放图片、有序 Gallery、视频首/中/末关键帧、alt text
和 transcript；每轮最多 12 个视觉单元。请求中的 base64 不写入轨迹。

## 世界与复现

WorldArtifact 冻结初始数据库、媒体、NPC、场景、事件、曝光规则、随机种子和配置版本，并为
所有文件记录 SHA-256。任何内容变化都必须生成新版本，不能修改已发布 Artifact。

运行输出包括 manifest、provenance、私有世界、trajectory、result、metrics 和 attribution。
相同 Artifact、策略版本和 seed 应产生相同的环境骨架与确定性行为。

## 共享内容池与动态排序

主评测的受控曝光采用 `controlled-dynamic-v2`。每个 tick 先冻结一个共享内容池，内容由任务
主题下的人类帖子和 Candidate 在本 episode 发布的帖子组成。所有 NPC 面对相同的帖子集合，
但根据各自兴趣、关注关系、内容时效和实时互动量得到不同排序。

NPC 行动顺序由 seed 和 tick 固定。每个 NPC 行动前重新排序，因此先行动者的点赞和评论会
影响后行动者看到的名次；NPC 在本 tick 新发布的帖子从下一 tick 才进入共享池。共享池、NPC
顺序、每人的实际排名和动作都会进入事件或轨迹。该机制模拟平台传播反馈，但不依赖学习型
推荐器，因而仍可复现并支持 Candidate 间的同条件比较。

## 状态与评测

Observer 估计 NPC 的态度、唤醒度、信任和互动意愿变化。每次变化都绑定 Candidate 的
`action_id`，并保留更新前后状态、置信度和证据。Observer 可以产生旁观者效应和延迟效应；
延迟更新仍归因到最初触发它的 action。

环境受众与评测 Observer 分离。受众按“用户—作者”持久化自己的关系状态和最近 20 次互动，
据此决定后续行为；Observer 在实际曝光和公开反应产生后独立评分，其评分不直接操纵环境。
默认使用确定性开发规则，可通过独立 provider 配置模型受众及视觉输入。

跨语境的正式任务/经验传递协议、正式异构 Observer 和真人校准仍需完成；不能以工程回归
通过代替实证验证。当前协议和运行示例见 [社会反馈闭环](social-feedback.md)。
