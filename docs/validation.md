# 验证状态

截至 2026-08-27：

- 105 个环境、数据库、平台和评测测试通过；
- 小红书、Reddit、X 均通过确定性多 tick 测试；
- scripted 路径通过 100 NPC/2 tick 和 1,000 NPC/1 tick 压力测试；
- 相同 Artifact、场景、seed 和策略的独立运行得到相同语义轨迹与指标；
- 图片、多图、视频与封面通过端到端执行；
- VLM 可接收真实像素、视频关键帧和 transcript，轨迹不保存请求 base64；
- 三平台原生 action 可通过沙盒和 exclusive runner 执行；
- 真实命令链已覆盖“导入世界 → 冻结 Artifact → 初始化配置 → 完整 episode”，并确认源世界不被运行污染；
- 共享内容池覆盖“人类内容 + Candidate 内容”，NPC 顺序点赞可确定性改变后续 NPC 的排名；
- Python 编译、格式检查和密钥扫描通过。

本地 Qwen2-1.5B 和 Qwen2.5-7B Observer 已通过结构化输出与聚合测试，但同属一个模型家族，
只用于开发。Runway Gemini 不公开真实模型身份且 JSON 不稳定；当前凭据无法访问独立 GLM
MaaS。因此正式发布前仍需冻结跨模型家族的 Observer pool，并完成目标平台用户盲测校准。

上游 CAMEL agent 和神经推荐器测试不属于轻量 Agora 主路径；前者需要可选 `camel-ai` runtime，
后者需要模型包和权重，而 Agora 主评测明确不使用学习型推荐器。
