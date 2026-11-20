---
version: 1
slug: "agora-web-studio-html"
primary_target: "agora/web/studio.html"
related_targets: ["agora/web/studio.css","agora/web/studio.js"]
---

# Developer / Viewer 方向约定

范围：`agora/web/studio.html`、`studio.css`、`studio.js`，访客模式 Operate。
依据用户已明确的产品角色、现有运行流程与指定 Family 参考，不另换页面概念。

## Direction contract

THESIS：暖白的社交模拟工作台。Developer 聚焦平台、参与者、模型和启动；Viewer 聚焦
一个账号的真实历史画面与对应动作，不用装饰挤占操作空间。

OWN-WORLD：Family 的 #fbfaf9 暖白、#f2f0ed 石色、#121212 墨黑，圆润标题、黑色胶囊
主操作、明亮的小型选择提示。公开授权的 Bricolage Grotesque 标题、Inter 正文字体本地
提供；中文保留系统字体回退。三种社媒 iframe 的颜色、布局、脚本保持原状。

STORY：开发者先选平台与参与者，接模型并调整预算，再启动独立世界；观察者选择运行
和账号，在平台画面旁查看理由与时间线，播放、定位步骤或放大平台画面。

FIRST VIEWPORT：暖白顶栏、轻量左导航；Developer 主列显示平台与参与者配置，右列
石色启动摘要。Viewer 紧凑运行标题和筛选栏下，平台画面占最大区域，账号与动作分居
两侧；窄屏先保证画面与回放控件可用，其余面板顺序排列。

FORM：seed: none (pinned)。用户原话：“跟觉这种风格……就主要是我们的框架前端页面……
developer 还有 viewer 页面都需要优化一下”；保留现有配置与单账号回放体验。

FINISH：unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

命名交互：Viewer 放大画面时只改变外层排布，iframe 保持同一个实例和历史步骤。运动
只用于按钮、面板和选中状态的 160–200ms 反馈，减少动态效果偏好时取消过渡。
