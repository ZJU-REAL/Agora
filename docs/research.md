# 相关工作调研与 Agora 0.3 的设计依据

调研日期：2026-11-13。阅读了以下项目的公开 README，以及 Generative Agents 的检索/反思
实现和 RecSim 的选择模型实现。下面区分上游公开设计、Agora 已实现机制及尚需实证的部分。
没有将其他工作的规模或人类一致性结果当作 Agora 的验证结果。

| 工作与一手来源 | 与本项目相关的设计 | Agora 0.3 的具体选择 |
|---|---|---|
| [OASIS](https://github.com/camel-ai/oasis)、[论文](https://arxiv.org/abs/2411.11581) | 社媒动作、社交网络、兴趣与热度推荐、可扩展的用户模拟 | 保留有用的实体兼容布局和原有评测，主世界改用原生存储/事务/模拟时间，不调用旧 Platform、Channel 或 CAMEL 调度 |
| [Generative Agents](https://github.com/joonspk-research/generative_agents)、[论文](https://arxiv.org/abs/2304.03442) | 记忆、检索、计划、反思，以及独立的前端回放 | 账号记忆从真实动作/结果积累，按重要度、时效和相关性检索；采用浏览/创作/反馈计划和逐步公开观察回放。尚未实现其完整反思架构 |
| [RecSim](https://github.com/google-research/recsim)、[论文](https://arxiv.org/abs/1909.04847) | 连续推荐环境；用户状态、响应与推荐策略分离；logit/cascade 选择模型 | 明确卡片、曝光、打开与停留；反馈会影响后续推荐；位置偏置属于用户策略，不与推荐排序混为一谈 |
| [RecSim NG](https://github.com/google-research/recsim_ng)、[论文](https://arxiv.org/abs/2103.08057) | 可组合的用户/内容/创作者生态、概率模型、推断与不确定性 | 账号策略、世界、推荐、记忆与实验管理分层，分别记录环境动作和模型调用。没有引入 TensorFlow/Edward2 或冒充可微校准 |
| [AgentSociety / AgentSociety 2](https://github.com/tsinghua-fib-lab/AgentSociety)、[v1 论文](https://arxiv.org/abs/2502.08691)、[v2 论文](https://arxiv.org/abs/2607.11895) | v1 城市社会环境；当前 v2 的研究工作台、可插拔环境、Ray 任务与 trace/replay 服务 | 加入显式实验配置、独立世界副本、后台任务、进度/暂停/停止、过程观察与导出；当前使用本地线程和 SQLite，不声称实现 Ray 规模 |
| [Sotopia](https://github.com/sotopia-lab/sotopia)、[论文](https://arxiv.org/abs/2310.11667) | 开放社会互动场景与社会能力评估 | 继续保留独立受控评测和公开交互观察，开发策略与模型实验分别标注；不把互动计数直接解释为社会智能或情感对齐 |
| [Monolith](https://github.com/bytedance/monolith)、[论文](https://arxiv.org/abs/2209.07663) | 推荐特征表示、实时训练及训练/服务链路 | v2 推荐增加基于共同正反馈的协同召回，并持久记录曝光/响应供后续训练；当前没有训练 embedding 或实时神经模型 |

## 直接检查的实现

- [Generative Agents retrieve.py](https://github.com/joonspk-research/generative_agents/blob/main/reverie/backend_server/persona/cognitive_modules/retrieve.py)：分别计算时效、重要度和相关性。Agora 采用有界事件检索，尚未复现其 embedding 检索。
- [Generative Agents reflect.py](https://github.com/joonspk-research/generative_agents/blob/main/reverie/backend_server/persona/cognitive_modules/reflect.py)：重要度触发反思。Agora 当前保存公开经验，不自动增加隐藏反思调用或额外模型预算。
- [RecSim choice_model.py](https://github.com/google-research/recsim/blob/master/recsim/choice_model.py)：包含 logit、proportional 和 cascade 选择模型。Agora 开发策略显式加入位置偏置与不同动作计划；这些参数需要真实用户数据校准。

读取快照的 SHA-256：

```text
retrieve.py    a609d9ba431dd8cb0f3ec804d128ff9d1755719221127b45a248d20c51dc7120
reflect.py     5e2658a90f658ce4f42f6a7c3859fe47fd08925eb77c179a4c38e9233d1c205c
choice_model.py 04dc64f7c9d5ccda73d126a9286d808478198a655c5b775715302216ec6b81fb
```

这些源码用于设计核对，没有新增复制其他项目的代理或学习模型依赖。仓库原有派生代码
继续保留许可证和来源声明。

## 结论与实验边界

一个有用的研究平台需要闭合三条链：

1. **产品链**：浏览 → 选择 → 创作/互动 → 通知/反馈 → 再次行动。
2. **推荐链**：召回 → 排序/重排 → 实际曝光 → 用户响应 → 下一次推荐。
3. **实验链**：冻结初始条件 → 隔离运行 → 过程观察 → 成本/失败记录 → 回放与导出。

0.3 已把这三条工程链连接起来。真实行为概率、情绪演化、推荐参数、文化规范及模型
能力仍需要外部数据和配对实验，不会因为链路跑通而自动成立。

Docker 是部署/进程隔离的一种方式，并不是社交世界的定义。当前运行无需 Docker，每次
实验拥有独立 SQLite、媒体副本和配置清单；模型使用受限的社交工具接口。Sotopia README
建议用 Docker 启动 Redis，这也不等于每个 episode 必须新建一个容器。
