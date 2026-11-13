# Agora

Agora 是用于研究 AI 社交行为的多平台模拟沙盒，支持小红书、Reddit 和 X。目标是让 AI
在有推荐、浏览、创作、互动和社会反馈的世界中运营账号，并为舆情传播、情感对齐与社会学
实验留下可检查、可复现的记录。

**0.2 新增：独立的 Agora 推荐、浏览会话、多账号策略调度和本地可视化。** 新服务由
`agora/` 实现，当前数据库、平台动作与媒体仍通过 OASIS 适配器提供。迁移尚未完成，
详细边界与后续计划见 [架构审查与路线](docs/agora-roadmap.md)。

## 启动社交沙盒

Python 3.10–3.11。轻量路径不需要 CAMEL、Torch、Docker 或模型 API：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-sandbox.txt

# 创建 7 个账号、48 条带合成封面的帖子，并保存三个账号的浏览轨迹
python -m agora demo agora-demo

# 打开 http://127.0.0.1:8765：切换账号、开始新会话或回放已有记录
python -m agora serve agora-demo
```

演示需要空世界；再次运行请换一个 `world_id`。世界保存在 `data/worlds/`，不会提交到 Git。
可选安装命令入口：`pip install --no-deps -e .`；之后可使用 `agora`。
`pip install -e .` 仍会安装上游完整依赖，轻量沙盒使用上面的安装路径。

```bash
python -m agora simulate agora-demo --user-id 7 --user-id 1 \
  --ticks 5 --steps-per-tick 6 \
  --recommendation-config configs/environments/recommendation.hybrid.json

# 接入现有模型 provider；凭据通过环境变量提供
python -m agora simulate agora-demo --user-id 7 --ticks 3 \
  --provider-config configs/benchmarks/providers.example.json

python -m agora export agora-demo --session-id 1 \
  --output data/worlds/agora-demo/session-1.json
```

新的推荐流水线为多路召回 → 行为兴趣排序 → 曝光疲劳 → 多样性重排 → 探索位。
AI 使用刷新、滚动、打开、停留、返回、点赞、收藏、关注、搜索、评论和文字发布等会话
工具；视觉 provider 可看到当前屏幕的实际图片或视频帧。仅实际显示页面计曝光，排序分数
留在研究者诊断中。网页支持实时操作、逐步回放与曝光话题分布。

推荐器是常见平台机制的工程代理，**尚未用真实平台日志拟合、校准或训练**。合成演示和
规则用户用于开发验证，不能将结果直接解释为真实用户行为或厂商推荐效果。新会话层尚未
覆盖底座的全部多媒体创作和三平台原生动作。详见 [推荐与会话协议](docs/simulation.md)。

## 现有世界与受控评测

OASIS 世界底座和独占式 Arena 评测继续可用：每个 episode 只有一个待评 Candidate，
其余用户由环境控制。自适应推荐沙盒与受控评测是不同的实验模式。

当前分为三层：

- **Agora 服务（`agora/`）**：推荐、持久浏览会话、多账号策略调度、可视化与 CLI。

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
agora/                 Agora 推荐、会话、策略与本地可视化
agora/backends/        OASIS 及现有多媒体编码适配器
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
  `snapshot`），创建用户及发布/查看图文（`user-create`、`post-create`、`post-view`）。
- `agora-benchmark`：运行评测（`artifact-create`、`scenario-build`、`episode-init`、`run`、
  `batch-run`、`aggregate`、`transfer-run` 等）。

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
- [社会反馈闭环](docs/social-feedback.md)：受众关系记忆、反馈条件、模型受众、预算与匿名校准。
- [跨语境实验](docs/transfer.md)：源经验迁移、目标经验基线、预算对照及配对报告。
- [上游说明](docs/upstream.md)：OASIS 来源和 Agora 扩展边界。
