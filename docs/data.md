# 数据准备与交付说明

本文说明你需要获取什么数据、最低字段是什么、如何匿名化，以及哪些数据能直接导入当前
Agora-OASIS。建议先准备一个小红书垂类的小样本，验证完整流程后再扩大规模。

## 1. 第一批建议规模

最低可运行样本：

- 100 个匿名用户；
- 500 条帖子；
- 2,000 条评论；
- 至少 50 条图片、多图或视频帖子；
- 10–20 类 NPC Persona；
- 20 个开发场景；
- 2 个 Candidate 模型，其中至少一个支持视觉输入。

数据不足时可以先交付 20 个用户、50 条帖子和 200 条评论做导入验证。数据量不是第一优先级，
用户—帖子—评论—媒体之间的关联完整性更重要。

## 2. 交付目录

```text
dataset/
├── manifest.json
├── users.jsonl
├── personas.jsonl
├── posts.jsonl
├── comments.jsonl
├── relations.jsonl        # 可选，关注关系
├── interactions.jsonl     # 可选，点赞、收藏和 downvote
└── media/
    ├── images/
    └── videos/
```

JSONL 表示每行一个完整 JSON 对象，编码统一使用 UTF-8。不要使用 Excel 行号作为永久 ID；
每个实体应有稳定、不可重复的匿名 ID。

## 3. Manifest

`manifest.json` 告诉导入器各文件的位置和 ID 命名空间：

```json
{
  "dataset": {
    "name": "xhs-travel-dev",
    "version": "0.1"
  },
  "files": {
    "users": "users.jsonl",
    "personas": "personas.jsonl",
    "posts": "posts.jsonl",
    "comments": "comments.jsonl",
    "relations": "relations.jsonl",
    "interactions": "interactions.jsonl",
    "media_root": "media"
  },
  "import": {
    "id_namespace": "xhs-travel-dev-v01"
  }
}
```

`id_namespace` 必须随数据版本变化。同一 namespace 重复导入时，已有实体会跳过；不同版本不要
复用同一个 namespace，否则旧 ID 可能错误映射到新数据。

## 4. 用户数据

`users.jsonl` 每行表示一个背景用户或真实数据中的匿名账号。

### 当前直接导入字段

| 字段 | 必需 | 含义 |
|---|---:|---|
| `external_id` | 是 | 数据集内稳定且唯一的匿名用户 ID |
| `handle` | 是 | 匿名账号名，建议同一世界唯一 |
| `display_name` | 否 | 显示名；缺省时使用 `handle` |
| `bio` | 否 | 简介，缺省为空字符串 |

```json
{"external_id":"u_0001","handle":"city_seed_01","display_name":"城市散步者","bio":"记录街区与摄影"}
```

### 建议额外交付的原始字段

当前导入器不会直接写入这些字段，但它们可用于生成 Persona 和分层抽样：

- `locale`、语言、国家/地区和时区；
- 账号垂类、兴趣标签、注册时长；
- 粉丝数、关注数、发帖数等分桶值；
- 是否创作者、普通浏览者、专业用户或机构账号；
- 活跃频率和典型在线时段。

数值建议做区间化，例如把精确粉丝数改成 `1k-10k`，减少重新识别风险。

## 5. Persona 与 NPC 角色

`personas.jsonl` 用于创建沙盒中的 AI/scripted 角色。它不是给每个真实匿名用户都必填的文件；
可以先根据用户行为聚类，再为每类生成少量代表 Persona。

`users.jsonl` 中的普通账号默认只是人类历史内容的作者，不会在模拟中自动行动；只有
`personas.jsonl` 创建的账号才默认进入主动 NPC 池。这样可以把“事先导入的人类内容”和
“当前 episode 中会观察、点赞、评论的 NPC”明确区分开。

```json
{
  "profile_id": "persona_travel_skeptic_01",
  "profile_version": "1.0",
  "identity": {
    "handle": "careful_traveler",
    "display_name": "谨慎旅行者",
    "bio": "关注价格和信息来源",
    "locale": "zh-CN",
    "timezone": "Asia/Shanghai"
  },
  "creator": {
    "niche": ["旅行", "摄影"],
    "content_formats": {"text": 0.2, "image": 0.5, "gallery": 0.3}
  },
  "interests": {"城市漫游": 0.9, "摄影": 0.7},
  "activity": {"posting_probability": 0.05},
  "social_behavior": {
    "reply_probability": 0.45,
    "like_probability": 0.25
  },
  "style": {
    "tone": ["谨慎", "直接"],
    "example_posts": ["这个价格包含哪些项目？", "有原始来源吗？"]
  },
  "policy_type": "scripted"
}
```

### Persona 最需要准备的信息

- 角色类型：浏览者、创作者、质疑者、支持者、专业用户等；
- 兴趣和不感兴趣的话题；
- 语言、文化背景和常用语气；
- 发帖、评论、点赞和关注倾向；
- 对广告、冲突、道歉、证据和事实错误的态度；
- 2–10 条匿名示例内容；
- 角色在第一版 NPC 中所占比例。

`posting_probability`、`reply_probability` 和 `like_probability` 取值应在 0–1。第一版建议大多数
NPC 使用 `scripted`，避免调用费用和不可复现性。

注意：当前 Persona 导入会创建一个新用户。不要同时在 `users.jsonl` 中重复创建同一个 Persona
账号，除非后续转换器明确处理绑定关系。

## 6. 帖子数据

`posts.jsonl` 每行表示一个帖子。

### 当前直接导入字段

| 字段 | 必需 | 含义 |
|---|---:|---|
| `external_id` | 是 | 稳定且唯一的帖子 ID |
| `author_external_id` | 是 | 必须能在用户或 Persona 映射中找到 |
| `post_type` | 否 | `text/image/gallery/video`，缺省为 `text` |
| `body` | 视类型 | 文字正文；text 帖必须非空 |
| `title` | 否 | 标题，小红书任务建议保留 |
| `assets` | 视类型 | 有序媒体数组 |
| `topics` | 否 | 话题或标签数组，不包含 `#` 也可以 |
| `language` | 否 | 如 `zh-CN`、`en-US` |
| `visibility` | 否 | `public/followers/private/group`，缺省 `public` |
| `community` | 否 | Reddit community，例如 `r/hiking` |
| `location` | 否 | 小红书粗粒度地点 |
| `reply_to_post_external_id` | 否 | 回复的帖子；目标帖子须先出现 |

```json
{
  "external_id": "p_0001",
  "author_external_id": "u_0001",
  "post_type": "gallery",
  "title": "雨后的旧街",
  "body": "傍晚沿着街区走了一圈。",
  "topics": ["城市漫游", "摄影"],
  "language": "zh-CN",
  "assets": [
    {"path": "images/p_0001_01.jpg", "role": "content", "caption": "街口"},
    {"path": "images/p_0001_02.jpg", "role": "content", "caption": "路灯"}
  ]
}
```

### 媒体数量规则

- `text`：不能带媒体；
- `image`：恰好一张 content 图片；
- `gallery`：2–20 张 content 图片，数组顺序就是展示顺序；
- `video`：恰好一个 content 视频，可再带一张 `cover` 图片。

### 建议额外交付的原始字段

以下平台字段很有价值，但当前通用 JSONL 导入器尚未全部直接映射；保留后由数据转换器写入：

- 原始发布时间和相对时间顺序；
- X repost/quote 的原帖 ID 和 quote 文案；
- 初始点赞、收藏、downvote、评论、repost 和曝光计数；
- 帖子删除、隐藏、编辑状态；
- 数据采集批次和来源证明。

不要因为当前导入器暂未消费这些字段就丢弃它们；它们对平台真实性和后续冻结世界很重要。

## 7. 评论数据

`comments.jsonl` 每行表示一个顶层评论或回复。

| 字段 | 必需 | 含义 |
|---|---:|---|
| `external_id` | 是 | 稳定且唯一的评论 ID |
| `post_external_id` | 是 | 所属帖子 ID |
| `author_external_id` | 是 | 评论者 ID |
| `content` | 是 | 评论正文 |
| `parent_external_id` | 否 | 父评论 ID；顶层评论不填 |

```json
{"external_id":"c_0001","post_external_id":"p_0001","author_external_id":"u_0002","content":"周末人多吗？"}
{"external_id":"c_0002","post_external_id":"p_0001","author_external_id":"u_0001","parent_external_id":"c_0001","content":"下午会多一些，建议上午去。"}
```

子评论可以出现在父评论之前，导入器会分轮解析。但父评论必须存在、必须属于可解析的数据集，
且评论关系不能形成环。建议额外保留原始时间、reply-to 用户、点赞数、是否置顶、删除状态和
语言，供转换器恢复平台细节。

## 8. 媒体文件

### 支持格式

- 图片：JPEG、PNG、WebP；
- 视频：MP4、WebM、MOV；
- 默认图片上限 20 MB；
- 默认视频上限 500 MB、时长上限 10 分钟。

媒体 `path` 应相对于 `media_root`，交付数据不得使用绝对路径或 `../`。文件名建议使用匿名帖子
ID 和顺序，例如 `p_0001_02.jpg`，不要保留用户名、手机号或设备导出的真实姓名。

建议随媒体提供：

- `caption` 和 `alt_text`；
- 图片 OCR 文本及 OCR 工具版本；
- 视频 transcript、语言、ASR 工具版本和时间戳；
- 原始 checksum；
- 是否允许发送给外部 VLM。

当前通用导入器会把 `caption` 或 `alt_text` 作为帖子内 caption 导入。更完整的 alt text、OCR、
ASR 和 transcript 可由后续版本化转换器写入媒体记录。

## 9. 关注与互动数据

为了模拟真实社区，建议额外交付：

```json
{"external_id":"r_0001","type":"follow","actor_external_id":"u_0002","target_external_id":"u_0001","sequence":12}
{"external_id":"i_0001","type":"like","actor_external_id":"u_0002","post_external_id":"p_0001","sequence":18}
{"external_id":"i_0002","type":"collect","actor_external_id":"u_0003","post_external_id":"p_0001","sequence":21}
```

当前导入器直接支持 `follow` relation，以及 `like`、`collect`、`downvote` interaction。每条记录
必须有唯一 `external_id`，涉及的用户和帖子必须已经导入。repost、quote、曝光及带时间的历史
事件需要根据实际数据格式编写转换器。至少保留 actor、target、类型和相对顺序。

## 10. 平台特有数据

### 小红书

优先保留标题、话题、地点的粗粒度表示、收藏、作者回复、置顶评论、多图顺序、视频封面和
搜索关键词。不要保留精确住宅位置或设备定位。

### Reddit

优先保留 subreddit/community、帖子与评论层级、upvote/downvote、moderation 状态、锁帖和
删除状态。用户跨 community 的身份应使用同一匿名 ID，除非隐私要求禁止关联。

### X

优先保留 follow graph、reply-to、mention、repost、quote source、thread 顺序和媒体。引用帖
必须同时保留原帖 ID 和新增引用文案。

## 11. 匿名化与合规

交付前至少完成：

- 删除姓名、手机号、邮箱、身份证、精确地址、设备 ID 和私信；
- 用户、帖子、评论使用稳定的随机匿名 ID；
- 检查正文、图片 OCR、视频画面和字幕中的个人信息；
- 精确时间可转换成相对顺序或时间桶；
- 精确位置降级到城市、区域或场景类别；
- 记录数据许可、用途限制、保存周期和删除流程；
- 明确真实媒体能否发送给外部模型服务。

匿名 ID 必须在同一数据版本中稳定，否则无法恢复关注、帖子和评论关系；但不要直接使用原始
平台 ID 的可逆编码。

## 12. 交付前验收

建议同时提供一份数据说明，回答：

1. 数据来自哪里，采集或生成时间是什么？
2. 是否允许用于研究、模型调用、论文示例和公开发布？
3. 各文件有多少行，缺失比例是多少？
4. 用户、帖子、评论和媒体 ID 是否唯一？
5. 是否存在找不到作者、帖子或父评论的记录？
6. 媒体缺失、损坏和格式分布如何？
7. 做过哪些匿名化，仍有哪些敏感风险？
8. 哪些字段是原始数据，哪些是推断、聚类或模型生成？

拿到第一批样本后，项目侧会继续完成数据审计、转换器、Persona 生成、世界导入、Artifact
冻结和 dry-run。无需在交付前手工转换成 SQLite。
