# 来源、致谢与兼容范围

Agora 早期参考 CAMEL-AI OASIS：

- 仓库：https://github.com/camel-ai/oasis
- 基线：`2048ee6dd8d2a9e62f53773f00200ef51a086468`
- 原上游版本：`camel-oasis 0.2.5`
- 许可证：Apache-2.0，见根目录 `LICENSE`

## 当前主路径

0.3 的 `AgoraWorld` 使用原生 `WorldStore`、版本化 schema、模拟 tick、事务和内容寻址媒体。
`agora/` 拥有推荐、账号会话、模型/视觉输入、记忆、策略调度、实验管理和网页。
启动一次模拟不再创建旧 Platform、Channel、Clock 或 CAMEL agent，也不需要 Docker。

已有增强的帖子/评论/关系/媒体实体布局和经过验证的受控评测保留并继续演进；迁移没有
通过删除有用能力来制造差异，也不把所有派生代码宣称为从零原创。原派生源码保留版权
声明，新增架构和行为的依据见 [调研记录](research.md)。

## 历史集成

历史环境、agent、Clock 与 platform/recommender 实现归档至 `oasis/legacy/`。旧位置的
小模块仅为显式调用方提供兼容转发，默认沙盒不加载它们。它们的额外依赖放在
`requirements-legacy.txt`，不再进入 `pip install -e .` 的默认依赖。

`AgoraOasis` / `AgoraOasisConfig` 是 `AgoraWorld` / `WorldConfig` 的旧高层导入别名。
正式包名和主入口使用 Agora：`agora-social`、`agora`、`agora-world`、`agora-benchmark`。
旧世界数据库通过增量列/表迁移打开，不重写已发布 Artifact；旧 Artifact 校验和仍按原文件
校验，运行副本才进行迁移。归档的低层平台不承诺能操作所有新版世界 schema。
