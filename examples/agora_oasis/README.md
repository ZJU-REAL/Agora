# 数据示例

本目录展示 `manifest.json` 及 users、personas、posts、comments JSONL 的最小导入格式。

```bash
agora-oasis --data-root data/worlds world-create xhs-demo --preset xiaohongshu --seed 42
agora-oasis --data-root data/worlds data-import xhs-demo manifest.json
agora-oasis --data-root data/worlds world-inspect xhs-demo
```

`manifest.json` 使用相对路径引用 JSONL 和媒体目录。所有 external ID 会按 `id_namespace` 映射
到内部 ID；重复导入同一 manifest 会跳过已有实体。字段说明见
[数据准备](../../docs/data.md)。
