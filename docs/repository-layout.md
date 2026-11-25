# 仓库目录与本地工作树

整理日期：2026-11-25。

| 路径 | 用途 |
| --- | --- |
| `agora/core/` | Agora 维护的世界、存储、平台动作、媒体与导入 |
| `agora/` 其他模块 | 三平台 API、模型接入、推荐、实验与回放 |
| `agora/web/`、`agora/fixtures/` | 网页与小型虚构测试世界 |
| `benchmarks/`、`configs/` | 受控评测、环境及运行配置 |
| `tests/` | 当前产品与评测回归 |
| `archive/legacy_runtime/` | 历史派生集成、工具、schema 和测试 |
| `examples/social_simulation/` | 数据导入、社会反馈与迁移示例 |
| `assets/source/`、`licenses/` | 原始插画、字体与来源记录 |
| `docs/`、`docs/archive/` | 当前说明、验证记录与历史路线图 |
| `deploy/iap/`、`scripts/` | 服务部署与世界压力检查 |
| `data/` | 本地世界、实验、媒体和私有模型配置，不提交 Git |

根目录 `oasis/` 的原生实现已迁至 `agora/core/`；旧兼容转发删除。历史路线图
`TODO.md` 迁入 `docs/archive/roadmap-20261118.md`。重复且过时的
`requirements-sandbox.txt` 删除，当前依赖统一由 `pyproject.toml` 与 `uv.lock` 管理。
旧版权头注入脚本随历史工具归档，提交钩子不再给所有新文件自动写入 CAMEL-AI 版权。

## 统一主目录

原 `/data/project/Agora-platform-behavior` 是独立开发工作树，曾在
`improve/platform-behavior` 的 `c275724` 验收平台行为/推荐优化、连续模型链路、
两种世界模式和账号起点。2026-11-25 已将这些功能与原生命名空间迁移整合到当前主目录，
并处理旧导入、目录重命名和验证文档冲突。原提交保留在合并历史中。

整合验收后移除多余工作树，`/data/project/Agora` 是唯一开发与部署目录。
当前运行代码位于 `agora/`；含有我们历次修改的旧 OASIS 派生集成放在
`archive/legacy_runtime/`。它属于历史实现，不作为未经修改的第三方依赖；来源与原版权
声明继续保留。归档不进入默认 wheel、主流程或当前产品测试。

本次清理只删除可再生成的缓存、旧构建产物和历史日志。本地数据库、媒体、实验记录、
私有配置、虚拟环境、用户文档与原始插画保留。数据规模和内容用途不能仅凭文件名判断，
因此不把 `data/` 中的历史运行当作垃圾。
