# OASIS 派生历史集成

来源：[CAMEL-AI OASIS](https://github.com/camel-ai/oasis)，基线
`2048ee6dd8d2a9e62f53773f00200ef51a086468`，原版本 `camel-oasis 0.2.5`，Apache-2.0。
原版权头与根目录许可证继续保留。

本目录归档旧 CAMEL agent/environment、Clock、平台与推荐器、schema、数据生成及
可视化工具、历史测试。它包含此前 Agora 的数据库扩展、多媒体、小红书动作、评论树
等改动；不是未经修改的上游副本。2026-11-25 的整理只调整命名空间与 schema 定位，
媒体兼容模块引用当前 `agora.core.media`。

Agora 主世界、推荐、API、实验工作台和 Viewer 不依赖此归档。默认安装包排除整个
`third_party/`；默认 `python -m pytest -q` 只收集 `tests/` 中的当前产品测试。

仍可在源码目录显式检查无需 CAMEL/神经网络依赖的历史功能：

```bash
python -m pytest -q third_party/oasis/tests/infra/database \
  third_party/oasis/tests/test_xiaohongshu_platform.py
```

需要研究旧 agent 或神经推荐器时，额外依赖列于 `requirements.txt`。这些旧测试还可能
要求原始上游数据、模型配置或外部服务，不属于当前轻量模拟器的验收范围。
归档的旧 GPU 部署脚本留作来源记录；Agora 的部署入口是 `deploy/iap/`。
