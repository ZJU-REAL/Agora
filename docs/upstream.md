# OASIS 参考底座与迁移边界

Agora 的新推荐、浏览会话、策略调度、研究控制台和入口位于 `agora/`，不调用上游
神经推荐器或 CAMEL agent 调度。`agora/backends/oasis.py` 提供当前世界适配器；视觉
编码暂通过 `agora/backends/visual.py` 复用既有评测工具。

数据库 schema/migration、帖子/评论/关注 CRUD 和媒体存储仍使用 `oasis/`，因此目前尚未
彻底脱离 OASIS。下一阶段会迁移这些底层能力，保留兼容 adapter 与原来源声明，具体
验收见 [架构审查与路线](agora-roadmap.md)。重命名包不等于完成独立内核。

Agora-OASIS 基于 CAMEL-AI OASIS：

- 仓库：`https://github.com/camel-ai/oasis.git`
- 基线提交：`2048ee6dd8d2a9e62f53773f00200ef51a086468`
- 上游版本：`camel-oasis 0.2.5`
- 许可证：Apache-2.0

上游兼容代码主要位于 `oasis/environment/`、`oasis/social_agent/` 和
`oasis/social_platform/`。Agora 扩展集中在统一世界 API、数据导入、多媒体、评论线程、事件、
快照、小红书平台，以及独立的 `benchmarks/` 评测层。

上游学习型推荐器只用于兼容性实验；Agora 主评测会在 manifest 校验时拒绝它们。派生源码保留
原版权声明，详情见根目录 `LICENSE` 和 `licenses/`。
