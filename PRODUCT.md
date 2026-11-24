# Agora 产品语境

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

开发者和研究者配置社交世界、模型 API 和 AI 账号数量；观察者通过 Viewer 查看单一账号
收到的平台画面、行为、创作和公开选择理由。AI 账号通过平台工具接口浏览和操作。

## Product Purpose

搭建可用的社媒模拟沙盒，先完善小红书、X/Twitter、Reddit 的平台行为和世界，再允许用户
导入数据、配置 agent、下发自己的任务，支持传播、对齐和社会行为研究。

## Operating Context

Developer 设置模型和独立模拟；Viewer 查看实时状态或精确历史快照。部署到公司的
IAP `/agora` 路径，三种社媒页面在独立 iframe 中保持原生平台的视觉和交互。
0.7 按配置、启动、观察与复用组织产品流程，Viewer 以实际画面为中心；各平台配置和
账号回放位置独立保存。

## Capabilities and Constraints

现有 Python / SQLite / 静态网页服务。每次模拟不要求 Docker。默认 1 个并发模拟、32 个
活跃 agent、2400 个动作；模型通过 API 接入。保留历史运行和私有模型设置，种子数据
保持小规模。回放只读，观察缓存有界。运行意图可留空，不强加固定评测任务。

世界初始化分为保留历史的背景世界与纯 AI 世界。受测账号可接手已有账号，或新建空账号/
显式预置少量公开内容的新账号；纯 AI 世界全部使用新账号。初始内容、活跃账号数量与
各账号任务需可追溯，预置内容不计作 agent 创作成绩。

## Brand Commitments

产品名 Agora。本轮用户指定 Refero Family 风格用于 Developer 和 Viewer 框架，
明确保留三种社媒的原生页面。用户随后要求加强动漫插画、减少单一暖黄底色，并指定
`agora_icon.png` 为正式项目图标及蓝紫色插画的视觉依据。参考：
https://styles.refero.design/style/1bcae895-2245-4d33-aa43-1c1e80719554

## Evidence on Hand

`agora/fixtures/sample_worlds.json` 是虚构的小型测试数据，不能作为真实用户行为或模型
能力证据。现有运行、HTTP 与浏览器检查见 `docs/validation.md`。

## Product Principles

- 社交模拟器优先，任务由使用者配置。
- 配置、模型调用、行为和实际观察可以追溯。
- 框架便于操作，原生社媒保留平台差异。
- 控制资源消耗，避免网页进程载入模型权重或完整大数据集。
