# 上游 OASIS 说明

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
