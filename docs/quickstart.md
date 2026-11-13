# 快速开始

## 安装与启动

Python 3.10–3.12，无需 Docker。视频需要系统 `ffmpeg` 和 `ffprobe`。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
agora serve agora-demo --bootstrap
```

打开 `http://127.0.0.1:8765`。默认启动一次合成源世界，页面选择账号和参数后创建独立
实验。每次实验有独立数据库/媒体，源世界不被污染。观察速度只改变展示速度。

## 接入模型

修改 `configs/models/provider.example.json` 的服务地址、模型 ID、视觉能力和预算，然后
设置配置声明的环境变量：

```bash
export AGORA_API_KEY='...'
agora serve agora-demo --provider-config configs/models/provider.example.json
```

页面选择对应模型。缺少凭据的 provider 不可启动；本地 transformers 配置检查模型目录，
相关依赖需另外安装。开发策略明确显示为无模型调用，不将它伪装为真实 LLM。

## 导入自己的世界

```bash
agora-world --data-root data/worlds world-create xhs-study --preset xiaohongshu --seed 42
agora-world --data-root data/worlds data-import xhs-study /path/to/manifest.json
agora-world --data-root data/worlds world-inspect xhs-study
agora serve xhs-study
```

详细字段和匿名化约定见 [数据准备](data.md)。X/Reddit 用相应 preset 建世界，底层保留
各自原生语义；页面会话尚未覆盖全部特殊动作。

## 运行与记录

```bash
agora simulate agora-demo --user-id 1 --user-id 2 --ticks 6 --steps-per-tick 8
agora export agora-demo --session-id 1 --output data/worlds/agora-demo/session.json
agora-benchmark --help
```

页面“导出实验记录”包含配置/指纹、世界事件、每步公开观察、动作/结果、推荐诊断和
模型调用。实验目录在 `data/worlds/<source>/experiments/<run_id>/`。进程中断保留记录并标记
interrupted；不会静默重复模型调用。

## 验证

```bash
pip install -e '.[test,dev]'
python -m pytest -q tests/test_*.py tests/benchmark tests/infra/database
```

受控评测见 [evaluation.md](evaluation.md)，原生实验见 [simulation.md](simulation.md)。
归档的 CAMEL/neural runtime 需要 `requirements-legacy.txt`，不属于默认运行或本次验证。
