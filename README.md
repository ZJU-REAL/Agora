# Agora

Agora 是可操作、可观察的 AI 社交模拟与实验平台，支持小红书、Reddit 和 X。用于研究
社媒创作与运营、传播反馈、社会互动，以及后续的舆情与情感对齐实验。

**0.3 提供完整的本地实验工作台**：从页面创建独立沙盒，启动多个账号，观察选择与图文
草稿，暂停/继续/停止模拟，再逐步回放或导出记录。主运行使用 Agora 自己的世界存储、
动作事务、推荐、记忆与策略调度，不调用旧 OASIS Platform、Channel、时钟或 CAMEL agent。

`oasis/` 是保留的历史目录名，原生世界入口为 `AgoraWorld`。软件包名为 `agora-social`。

## 一条命令启动沙盒

Python 3.10–3.12，**不需要 Docker、Torch 或 CAMEL**：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

agora serve agora-demo --bootstrap
```

打开 **http://127.0.0.1:8765**。第一次启动创建 7 个账号和 48 条有合成封面的帖子；已有
世界不会重新灌入演示内容。页面选择账号、轮数、任务、种子与推荐参数，点击“创建独立
沙盒并运行”。可选择快速运行或逐步观察速度。

- **实验工作台 `/`**：实验列表、进度、暂停/继续/停止、创作/评论/曝光计数、关注网络、
  每次公开选择理由、草稿与素材顺序、模型调用记录、配置指纹和完整导出。
- **账号观察**：实验中的实际卡片/详情、个人主页、通知、创作工作台与历史步骤回放。
- **手动探索 `/account`**：操作源世界；实验克隆不修改源世界。

每次实验存放在 `data/worlds/<source>/experiments/<run_id>/`：独立数据库、媒体、manifest
和轨迹。状态隔离依靠世界副本，不需要为每次模拟启动容器。

## 模型与开发策略

默认 Persona 开发策略可离线验证完整流程：查看个人页 → 进入工作台 → 选择图片与顺序 →
保存草稿 → 发布 → 浏览、评论及通知。它的文案和公开理由由规则生成，**不是 LLM 输出**。

接入真实 LLM/VLM 时，启动服务时注册 provider 配置，页面选择对应模型：

```bash
export AGORA_API_KEY='...'
agora serve agora-demo --provider-config configs/models/provider.example.json
```

密钥通过配置指定的环境变量读取，不写入配置文件、manifest 或轨迹。模型通过与网页
相同的社交工具操作账号，可读取有界记忆和公开结果；VLM 看到当前屏幕与素材库的实际
图片/视频帧。公开理由、模型身份、已知 token、延迟和失败单独记录。请求数还受 provider
预算限制，暂停在动作边界生效，已发出的模型请求会先完成。

## 命令行与受控评测

```bash
# 离线完整会话模拟
agora simulate agora-demo --user-id 1 --user-id 2 --ticks 6 --steps-per-tick 8

# 单账号公开轨迹与推荐诊断
agora export agora-demo --session-id 1 --output data/worlds/agora-demo/session.json

# 数据导入、媒体发布、世界检查与快照
agora-world --help

# 独立受控 Arena、Artifact、多 seed、预算与报告
agora-benchmark --help
```

推荐默认 `agora-hybrid-v2`：新内容、兴趣、关注、热门、探索和协同召回 → 反馈排序 →
曝光疲劳与作者/话题重排。只有进入页面的内容计曝光，打开与停留单独记录。v1 保留用于
读取既有会话；受控 Arena 保持自己的实验协议。

```text
agora/                 实验管理、推荐、账号会话、记忆、模型与可视化
  web/                 实验工作台与账号观察页面
  world.py             原生世界公开入口
oasis/world.py         平台实体与社交动作
oasis/storage.py       SQLite 生命周期、迁移与动作事务
oasis/media.py         内容寻址媒体与校验
oasis/schema/          原生世界 schema
benchmarks/            受控评测、受众/Observer、指标与实验协议
```

## 验证与边界

```bash
pip install -e '.[test,dev]'
python -m pytest -q tests/test_*.py tests/benchmark tests/infra/database
```

开发策略、推荐器和模拟受众尚未用真实平台日志/真人反馈校准。当前没有学习型 embedding
推荐、完整情绪反思或大规模分布式执行，不能把合成实验结果直接解释为真实用户或厂商
算法。视频需要 `ffmpeg`/`ffprobe`。运行中实验在进程重启后标记为 interrupted，保留记录，
不静默重发模型请求；旧受控 Runner 的 checkpoint/resume 继续可用。

- [相关工作调研](docs/research.md)
- [实验与浏览协议](docs/simulation.md)
- [架构、已实现能力与下一阶段](docs/agora-roadmap.md)
- [数据准备](docs/data.md)、[受控评测](docs/evaluation.md)、[验证记录](docs/validation.md)

## 致谢

感谢 [CAMEL-AI OASIS](https://github.com/camel-ai/oasis) 为早期社媒实体、动作和模拟研究提供
参考。Agora 已替换主运行依赖，并保留原派生代码的 Apache-2.0 版权/来源声明。旧高层类名
仅作为兼容导入，历史集成可选安装 `requirements-legacy.txt`；它们不属于默认运行路径。
来源、兼容范围与许可证见 [upstream.md](docs/upstream.md)。
