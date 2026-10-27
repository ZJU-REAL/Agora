# 快速开始

项目使用 Python 3.11，不要求 Docker。视频功能需要系统安装 `ffmpeg` 和 `ffprobe`。

## 安装与建世界

只使用 Agora 沙盒与评测层时，可以安装轻量依赖，无需 PyTorch、CAMEL 或推荐模型权重：

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements-sandbox.txt
uv pip install --python .venv/bin/python --no-deps -e .
source .venv/bin/activate
```

需要上游 CAMEL agent 或学习型推荐器时，使用完整安装：

```bash
pip install -e .
```

然后创建世界：

```bash
agora-oasis --data-root data/worlds \
  world-create xhs-demo --preset xiaohongshu --seed 42
agora-oasis --data-root data/worlds world-inspect xhs-demo
```

平台可选 `xiaohongshu`、`reddit` 或 `x`。一个世界包含 `sandbox.db`、`media/` 和世界清单。

## 发布小红书图文

下面在新建的 `xhs-demo` 世界里创建第一个用户，并发布真实的本地图片。`--author-id` 使用
`user-create` 输出的 `user_id`（空世界的第一个用户为 1）。

```bash
agora-oasis user-create xhs-demo creator --display-name '旅行博主'
agora-oasis post-create xhs-demo --author-id 1 \
  --title '旧街散步' --body '傍晚的光线很适合拍照。' \
  --image /path/to/street.jpg --topic 城市漫游 --location 上海
agora-oasis post-view xhs-demo 1 --user-id 1
```

一个 `--image` 发布单图图文（`image`）；重复传入 `--image` 发布有序多图（`gallery`，2–20 张），
图片顺序与参数顺序一致。标题和正文与图片一起保存，Feed 和评测均可读取。媒体会复制进世界
目录，不依赖原始文件后续是否存在。`post-view` 的帖子 ID 使用 `post-create` 返回值。

发布视频使用 `--video /path/to/clip.mp4`，可加 `--cover /path/to/cover.jpg`；不传媒体时发布
纯文字。这些发布命令同样支持 Reddit 和 X 世界，Reddit 可额外指定 `--community r/hiking`。

## 导入和推进

数据格式见 [数据准备](data.md)。

```bash
agora-oasis --data-root data/worlds \
  data-import xhs-demo dataset/manifest.json
agora-oasis --data-root data/worlds run xhs-demo --ticks 10
agora-oasis --data-root data/worlds \
  snapshot xhs-demo --snapshot-id before-experiment
```

相同初始世界、策略版本和 seed 会产生相同的 scripted 行为。

## Python 调用

```python
import asyncio
from oasis import AgoraOasis, DatasetImporter

sandbox = AgoraOasis.local("xhs-demo", "data/worlds")
asyncio.run(DatasetImporter(sandbox).import_manifest("dataset/manifest.json"))
observation = sandbox.observe(user_id=1)
result = asyncio.run(sandbox.advance())
sandbox.close()
```

接入 Candidate、创建 Artifact 和批量评测见 [评测流程](evaluation.md)。

## 本地验证

```bash
uv pip install --python .venv/bin/python pytest==8.2.0 pytest-asyncio==0.23.6
.venv/bin/python -m pytest -q tests/test_*.py tests/benchmark tests/infra/database
```

`test_platform_readiness.py` 覆盖三平台单图/多图命令行发布，以及完整的多图评测 episode、
NPC 互动和源世界隔离。上游 agent 与学习型推荐器测试另需完整依赖。
