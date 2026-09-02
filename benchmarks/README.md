# Agora 评测层

`benchmarks/` 是 Agora-OASIS 的评测层，负责场景、Candidate、Observer、独占式 Runner、指标
和报告，不实现平台存储。

主评测每个 episode 只允许一个 Candidate，且只使用受控曝光或确定性 Feed。可选多模型混战
必须使用独立协议和结果，不能混入主报告。

完整流程见 [评测流程](../docs/evaluation.md)。
