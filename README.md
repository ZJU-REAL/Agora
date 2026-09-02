# Agora-OASIS

Agora-OASIS 是基于 [OASIS](https://github.com/camel-ai/oasis) 增强的多平台、多媒体 AI 社交
模拟沙盒。当前支持小红书、Reddit 和 X，并提供独占式 Arena 评测：每个 episode 只有一个待评
Candidate，其余用户由环境控制。

项目分为两层：

- **模拟环境（`oasis/`）**：负责平台、用户、内容和时间演化，一个可变世界对应一个 SQLite
  数据库和一个媒体目录。
- **评测层（`benchmarks/`）**：负责 Candidate、场景、Observer、指标和报告。每个 episode 从
  只读 `WorldArtifact` 克隆独立世界，主评测只使用受控曝光或确定性 Feed，不引入学习型推荐器。

## 已实现

- 文字、图片、有序多图、视频、封面和楼中楼评论；
- 三平台原生 action、确定性 Feed、NPC Persona、事件、tick 和快照；
- 主题内人类内容与 Candidate 内容混排、NPC 顺序互动和动态重排；
- VLM 图片输入、视频关键帧和 transcript；
- SQLite 世界隔离、版本化 WorldArtifact 和 SHA-256 校验；
- Candidate/Observer provider、多 seed 运行、恢复、指标和 action attribution；
- 无需 Docker，主评测不使用学习型推荐器。

## 目录

```text
oasis/                 模拟环境
benchmarks/            评测协议、Runner 和指标
configs/               环境与评测配置
examples/              数据示例
docs/                  项目文档
tests/                 测试
data/                  本地世界和 Artifact（默认忽略）
```

## 命令行工具

安装后提供两个命令行入口：

- `agora-oasis`：管理模拟世界（`world-create`、`data-import`、`world-inspect`、`run`、
  `snapshot`）。
- `agora-benchmark`：运行评测（`artifact-create`、`scenario-build`、`episode-init`、`run`、
  `batch-run`、`aggregate` 等）。

## 开始使用

```bash
pip install -e .

# 1. 创建并检查一个小红书演示世界
agora-oasis --data-root data/worlds \
  world-create xhs-demo --preset xiaohongshu --seed 42
agora-oasis --data-root data/worlds world-inspect xhs-demo

# 2. 查看评测层命令
agora-benchmark --help
```

导入数据的最小示例见 [`examples/agora_oasis`](examples/agora_oasis)；完整评测流程见
[快速开始](docs/quickstart.md) 与 [评测流程](docs/evaluation.md)。

## 文档

- [项目 TODO](TODO.md)：已完成内容和需要准备的数据、角色、任务与模型。
- [系统设计](docs/design.md)：架构、平台、多媒体和复现边界。
- [评测流程](docs/evaluation.md)：模拟器内部每个 tick 如何运行。
- [快速开始](docs/quickstart.md)：安装、建世界、导入和运行。
- [数据准备](docs/data.md)：详细字段、JSONL 示例、Persona、媒体、匿名化和交付验收。
- [验证状态](docs/validation.md)：测试范围和实验限制。
- [上游说明](docs/upstream.md)：OASIS 来源和 Agora 扩展边界。
