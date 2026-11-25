# 来源、致谢与迁移范围

Agora 基于 [CAMEL-AI OASIS](https://github.com/camel-ai/oasis) 的早期社媒模拟代码和思路演进：

- 上游基线：`2048ee6dd8d2a9e62f53773f00200ef51a086468`。
- 原上游版本：`camel-oasis 0.2.5`。
- 许可证：Apache-2.0，见根目录 [LICENSE](../LICENSE) 与 [NOTICE](../NOTICE)。

## Agora 当前维护的实现

`agora/core/` 是 Agora 的原生世界基础设施，不是直接复制上游后仅更换名称：

| 模块 | 当前职责 |
| --- | --- |
| `world.py`、`types.py` | 三平台世界、社交实体、人物配置、模拟时间和快照 |
| `storage.py`、`schema/world.sql` | 原生 SQLite 生命周期、增量迁移、嵌套动作事务 |
| `platform_actions.py` | 社区权限、投票、收藏专辑、编辑与删除 |
| `media.py` | 内容寻址媒体、大小与格式检查、图集和视频 |
| `data_import.py`、`audience.py` | 数据导入、外部 ID 映射、开发用规则受众 |
| `cli.py` | `agora-world` 命令行入口 |

`agora/` 的其他模块维护推荐分发、账号 API、模型与视觉输入、记忆、策略调度、
决策回执、实验管理和 Developer/Viewer 页面。默认运行不创建旧 OASIS Platform、
Channel、Clock 或 CAMEL agent，也不要求 Docker、Torch 或本地模型权重。

原生实现仍保留有用的派生实体布局与来源信息。保留的 CAMEL-AI 版权头不意味着
代码未经修改，也不会因为目录迁移而删除；本次迁移在这些原生文件中标明了 Agora 修改。
此前架构与研究依据见 [调研记录](research.md) 和 [设计说明](design.md)。

## 历史派生实现

`archive/legacy_runtime/` 集中保存旧 environment、agent、Clock、platform、神经推荐器、
schema、生成/可视化工具和相关测试。该目录是 **我们维护过的 OASIS 派生历史实现**，包含此前
Agora 的修改；它不作为原封不动的第三方依赖，也不宣称原上游代码由 Agora 原创。详情见其 [README](../archive/legacy_runtime/README.md)。

历史集成只供显式的源码实验使用，不随 `agora-social` wheel 安装，也不被默认测试
或服务加载。额外依赖位于 `archive/legacy_runtime/requirements.txt`；上游代码、旧改动和
测试记录继续保留，避免把归档误认作当前产品实现。

## 导入迁移与历史数据

2026-11-25 起，根目录不再提供 `oasis` Python 包，也删除了旧目录中的兼容转发文件。
代码调用方使用以下入口：

```python
from agora import AgoraWorld, WorldConfig
from agora.core import AssetInput, DatasetImporter, PersonaProfile
from agora.core.media import LocalMediaStore
```

旧 `AgoraOasis` / `AgoraOasisConfig` 调用方分别改为 `AgoraWorld` / `WorldConfig`。
正式包名和主入口保持 `agora-social`、`agora`、`agora-world`、`agora-benchmark`。
目录迁移不改变数据库 schema、媒体对象键或版本号；旧世界仍按原增量迁移打开，
已发布 Artifact 不改写。新报告保留历史 `agora_oasis_version` 字段并添加 `agora_version`，
方便旧分析代码读取；源码指纹覆盖当前 `agora/` 与 `benchmarks/`。
