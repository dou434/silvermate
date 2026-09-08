# Changelog

本项目变更记录遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范。

## [Unreleased]

### Added
- 添加开源必备文件（CHANGELOG.md）

## [0.7.1.beta1] - 2026-09

### Added
- 银发守护智慧养老 AI 助手平台核心功能
- 4 个养老场景智能体：银发健康顾问、养老政策助手、护理知识助手、生活陪伴
- RAG 检索增强（需配置 Embedding API），回答附带来源引用
- 知识图谱：基于 Neo4j 构建实体关系图谱，支持可视化浏览
- 思维导图：自动生成知识库文件结构思维导图
- 适老化设计：大字号高对比度界面（标准/大字/超大字三档）
- 多色主题：琥珀（默认）、海蓝、翠绿、青碧四套色系
- 语音输入（Web Speech API）与语音朗读（TTS）
- 紧急求助按钮：浮动 SOS 按钮，一键拨打 120/110/紧急联系人
- 紧急关键词检测：7 类急症关键词自动识别并弹窗提醒
- 自定义技能：老年人综合评估、护理计划生成、深度研究编排、知识库检索
- CLI 工具：远程连接、浏览器/API Key 登录、知识库批量上传
- 多租户权限：superadmin / admin / 普通用户三级角色
- MCP 集成：支持 Model Context Protocol 工具扩展
- 品牌定制：名称、Logo、主题色、登录背景可配置
- 任务中心：后台作业实体化，只读进度面板
- 完整文档体系：ARCHITECTURE.md / DEPLOYMENT.md / FAQ.md / SECURITY.md

### Fixed
- 修正 SSE end 事件格式，使 demo 对话可正常回复
- 头像 fallback 不再显示"用户"字样
- 修正 Demo 帖正文中产品截图的文字说明与实际内容不匹配的问题

### Changed
- 为静态演示版添加"静态演示"水印与未覆盖提示
