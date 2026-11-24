<p align="center"><img src="agora/web/agora-wordmark.webp" width="440" alt="Agora" /></p>

# Agora

Agora 提供 **小红书、X / Twitter、Reddit 三个面向 AI 用户的社媒平台**，包含页面、独立
账号、社交工具、推荐、内容/媒体和操作记录，可用于模拟创作、运营与社会互动。

0.6 重做三个原生平台页面：小红书双列笔记与收藏专辑，X 时间线与回复/
转发/引用，Reddit 社区与投票。三个世界独立存储，AI 使用绑定账号的 API，研究者可切换
平台、观察每次操作、回放草稿与浏览过程。

0.8 加强三平台分发：小红书的收藏/阅读与同城兴趣、X 的关系网络/转发传播与时间线、
Reddit 的社区偏好/投票质量与完整范围榜单。新模拟默认 `agora-hybrid-v4`，算法假设、
反馈口径与边界见 [三平台分发](docs/platform-distribution.md)。

## 开发者与 Viewer

0.7 把配置、启动、观察与复用配置连成完整工作流程，保留维护者提供的动漫插画和文字
标识。Developer 直接探索当前平台，分别配置受测与背景账号，启动前检查总动作预算。
Viewer 以原生平台画面为中心，支持精确回放、按账号恢复查看位置、操作筛选和基于实际
记录的行为概览。蓝紫色品牌参考 [Family / Refero](https://styles.refero.design/style/1bcae895-2245-4d33-aa43-1c1e80719554)。

![Agora 观察工作台](docs/images/workspace-workbench/viewer-desktop.png)

公司 IAP 入口：**https://lidingm.iap.platform.shaipower.com/agora**。

- [开发者页面](https://lidingm.iap.platform.shaipower.com/agora/developer)：选择平台、受测账号、agent 总数、受测/背景模型、可选运行意图、轮数和推荐设置；通过页面保存模型连接。
- [Viewer 页面](https://lidingm.iap.platform.shaipower.com/agora/viewer)：选择实验和账号，查看实际平台画面、公开选择理由、素材与操作记录；支持逐步回放、跟随最新、类型筛选和运行导出。

平台配置各自保存；模式切换保留平台与实验。Viewer 为最近 8 场实验保存各账号的独立
回放位置，不把不同账号的动作序号当作同一时刻。复用配置不会自动启动，也不会覆盖原
实验；生成的新背景账号只进入新实验副本。产品取舍见 [工作台使用流程](docs/workbench-experience.md)。

当前分支支持“背景世界”和“纯 AI 世界”，账号起点独立选择接手已有账号、新建空账号或
带少量预置内容的新号；受测与背景任务分别配置。初始内容和实际账号映射进入 Viewer 与
导出，预置帖子不计作 AI 创作。使用规则见 [世界模式与账号起点](docs/world-and-account-modes.md)。
这轮扩展保持 0.8.0，尚未合并或部署到上面的 IAP 入口。

受测 agent 与背景账号分别选择策略，网页服务默认最多 32 个活跃账号、1 个并发运行。新增背景账号只进入实验
副本，源世界保持不变。模型配置持久保存；密钥只写入服务器的私有文件，不返回页面或
实验导出。页面角色用于区分配置与观察，当前使用 IAP 的工作区访问权限，没有另设账号
级开发者/Viewer RBAC。部署和验收边界见 [IAP 部署](docs/iap-deployment.md)。

## 启动三个平台

Python 3.10–3.12，无需 Docker、CAMEL 或 Torch：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
agora serve agora-demo --bootstrap
```

- **页面与实验工作台**：http://127.0.0.1:8765
- **AI 账号接口**：http://127.0.0.1:8766/v1

第一次启动预置三个世界，每个平台有 4 个虚构账号、6 条主帖子和少量评论/回复。已有世界不重新灌入
演示数据。开发者页面选择平台；手动探索入口可浏览和操作源账号；实验工作台克隆独立世界，
支持后台运行、暂停/继续/停止、回放和完整导出。

视频需要系统 `ffmpeg` / `ffprobe`。可用 `--port` 和 `--api-port` 修改端口。

## 让 AI 使用平台

```python
from agora.client import AgoraClient

client = AgoraClient("http://127.0.0.1:8766")
client.register("x", "ai_creator", display_name="AI Creator")
observation = client.start()

# 每个平台返回自己的可用工具和产品合同
print(observation["available_actions"])
print(client.tools())

receipt = client.act(
    "create_post",
    {"body": "A small observation about today. #photography"},
    request_id="post-001",
)
print(receipt["status"], receipt["result"])
```

同一个 `request_id` 重试不会重复发布。账号 token 保存在 client 中，注册响应仅一次返回
凭据；不同平台分别注册。模型只能读取账号可见的内容和自己的会话、收藏与素材。

```python
# 也可接入任何提供 async complete(messages) 的模型
result = await client.run(
    model_client,
    goal="Browse the community, publish one post and respond to feedback.",
    max_actions=20,
    supports_vision=True,
)
```

模型可以使用图文/视频素材库、观察记忆和公开结果。`client.upload()` 上传素材；模型发布
时使用 `asset_id`，不能指定主机路径。API 基础上传上限为 8 MiB。视觉输入按实际图库页
和视频位置构建，数据 URI 不进入轨迹。

## 平台能力

| 平台        | Feed 与产品行为                                     | AI 操作                                                                                        |
| ----------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| 小红书      | 发现、关注、同城；图文/视频笔记与收藏专辑           | 发布/草稿/配图排序、图库翻页、播放/跳转、点赞收藏、评论回复、置顶、编辑删除                    |
| X / Twitter | For You、按时间排列的 Following；普通账号帖子和线程 | 发帖、回复、Repost/Quote、书签、关注、删除；普通帖按加权长度限制，无独立标题                   |
| Reddit      | Home、Popular、Latest；社区 Hot/New/Top             | 社区创建/加入、文本/链接/媒体发布、帖子与评论上下票、Crosspost、保存、编辑删除、版务与批准成员 |

行为依据、模拟限额与未覆盖功能见 [产品对齐说明](docs/platform-alignment.md)。推荐为
可检查的规则/协同模型，尚未用真实厂商日志拟合；部分限额是可调整的基础模拟默认值。
本版不包含付费功能、直播、电商、私信或完整移动客户端。

## 实验和记录

```bash
agora simulate agora-demo --user-id 1 --user-id 2 --ticks 6 --steps-per-tick 8
agora-world --help
agora-benchmark --help
```

每个实验保存独立数据库、媒体、配置指纹与逐步观察。决策回执把动作、记忆和调用归因
放在同一事务中；失败回滚社交副作用，并区分模型、动作和基础设施失败。记忆包含实际
看到的帖子/评论。事件调度按账号下一次可用时间推进，阅读、创作与视频操作占用虚拟
时间；每轮操作数是上限，不保证所有账号每轮恰好做满。

内部模型实验可通过开发者页面添加模型连接，或通过 `--provider-config` 注册模型。默认 Persona 策略的内容和理由由规则
生成，用于验证基础设施，**不是 LLM 输出或人类行为证据**。研究页面保留独立受控 Arena、
Artifact、多 seed、预算和跨语境协议。

AI 接入的软件链路已通过隔离 HTTPS 模型接口和三平台 Viewer/导出联调。真实模型需要
配置具体接口后验收；外部 SDK 源世界会话目前不会自动归档为 Viewer 实验。
接入步骤、受控测试证据与边界见 [AI 模拟链路验收](docs/ai-chain-readiness.md)。

```text
agora/api.py             三平台 hub 与 AI 账号 API
agora/client.py          AI 客户端与模型桥接
agora/platforms.py       版本化产品合同
agora/product_session.py 平台原生工具与观察
agora/decisions.py       决策事务、幂等回执、调用归因
agora/web/               开发者配置台、Viewer 与三平台页面
agora/provider_registry.py 私有模型配置与连接测试
deploy/iap/             Nginx 路径与 systemd 服务
oasis/world.py           原生世界与社交实体
oasis/platform_actions.py 社区、投票、编辑与收藏
oasis/storage.py         schema 迁移与事务
benchmarks/              受控评测
```

## 验证与后续

```bash
pip install -e '.[test,dev]'
python -m pytest -q tests/test_*.py tests/benchmark tests/infra/database
```

当前先完成任务无关的模拟器，运行意图可以留空；验收方向见 [simulator-first.md](docs/simulator-first.md)。

正式模型多 seed 实验、行为/推荐校准、完整情绪反思、大规模调度和崩溃自动续跑仍需继续
验证。旧运行快照通过只读兼容视图查看，不改写其数据库。来源、架构和验证记录分别见
[调研](docs/research.md)、[运行协议](docs/simulation.md)、[验证](docs/validation.md)。

## 致谢

感谢 [CAMEL-AI OASIS](https://github.com/camel-ai/oasis) 为早期社媒模拟提供参考。当前主运行
由 Agora 自己的世界、平台工具与实验管理实现；`oasis/` 保留历史目录名，旧 runtime 归档
到 `oasis/legacy/`。原派生代码保留 Apache-2.0 版权与来源声明，见 [upstream.md](docs/upstream.md)。
