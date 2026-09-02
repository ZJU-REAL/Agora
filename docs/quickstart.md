# 快速开始

项目使用 Python 3.11，不要求 Docker。视频功能需要系统安装 `ffmpeg` 和 `ffprobe`。

## 安装与建世界

```bash
pip install -e .
agora-oasis --data-root data/worlds \
  world-create xhs-demo --preset xiaohongshu --seed 42
agora-oasis --data-root data/worlds world-inspect xhs-demo
```

平台可选 `xiaohongshu`、`reddit` 或 `x`。一个世界包含 `sandbox.db`、`media/` 和世界清单。

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
