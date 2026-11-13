# 银发守护 —— 智慧养老 AI 助手

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/Vue-3-42b883.svg)](https://vuejs.org/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![Version](https://img.shields.io/badge/Version-0.7.1.beta1-purple.svg)](docs/develop-guides/changelog.md)

> 面向养老场景的 AI 对话与知识库问答系统，融合 RAG 技术与知识图谱，针对老年用户进行适老化改造。
>
> 本项目基于开源平台 [Yuxi](https://github.com/xerrors/Yuxi) 二次开发。

## 项目概述

银发守护是一个为老年人及其照护者设计的 AI 智能助手平台，提供健康咨询、政策解读、护理知识和生活陪伴等服务。系统集成 DeepSeek 大模型，并针对老年用户的使用习惯进行了适老化改造。

## 系统架构

![系统架构](docs/architecture.svg)

## 核心功能

### AI 对话

- **内置 4 类养老场景能力**（健康顾问 / 政策助手 / 护理知识 / 生活陪伴）：代码内置人设，「问 AI」单一入口自动识别场景，重启容器即生效
- **多模型支持**：DeepSeek、SiliconFlow、OpenAI 兼容 API、Anthropic 等
- **子智能体调度**（平台通用能力）：主智能体可自动委派子智能体完成专项任务
- **快捷问题入口**：无对话时展示常见问题，降低使用门槛
- **历史对话搜索**：命令面板式搜索，支持方向键选择与快速跳转

### 知识库

- **4 份养老领域文档**：政策法规、健康管理、护理规范、防诈骗指南（由 seed 脚本一键入库并挂载到默认智能体）
- **RAG 检索增强**（需配置 Embedding API）：从知识库中语义检索相关内容，回答附带来源引用
- **知识图谱**：基于 Neo4j 构建实体关系图谱，支持可视化浏览
- **思维导图**：自动生成知识库文件结构思维导图，支持增量更新
- **多格式文档解析**：Markdown、DOCX、PDF、HTML，支持 MinerU / PaddleOCR / RapidOCR

### 适老化设计

- **大字号高对比度界面**：CSS 变量控制，可切换标准/大字/超大字三档
- **多色主题**：琥珀（默认）、海蓝、翠绿、青碧四套色系可切换
- **语音输入**：Web Speech API 语音转文字，老人可以直接说
- **语音朗读（TTS）**：AI 回复可一键朗读，支持自动朗读模式，Markdown 自动转纯文本
- **紧急求助按钮**：浮动 SOS 按钮，一键拨打 120/110/紧急联系人
- **紧急关键词检测**：7 类急症关键词（心血管、脑血管、跌倒、呼吸、意识、出血、心理危机）自动识别并弹窗提醒

### 自定义技能

- **elderly-assessment**：老年人综合评估（ADL、MMSE、跌倒风险、营养状况、情绪状态）
- **care-plan-generator**：个性化护理计划生成（日常安排、饮食方案、运动方案、用药管理）
- **deep-research**：深度研究编排，并行调度子智能体调研并生成结构化报告
- **knowledge-base**：知识库检索、文档定位、思维导图查看

### 平台能力

- **CLI 工具**：`yuxi` 命令行支持远程连接、浏览器/API Key 登录、知识库批量上传
- **多租户权限**：superadmin / admin / 普通用户三级角色，部门隔离
- **MCP 集成**：支持 Model Context Protocol 工具扩展
- **品牌定制**：名称、Logo、主题色、登录背景可配置
- **任务中心**：后台作业实体化，只读进度面板
- **Agent 评估**：RAG 评估与基准测试

## 快速开始

### 1. 环境要求

- Docker Desktop（含 Docker Compose）
- DeepSeek API Key（[获取地址](https://platform.deepseek.com)）
- SiliconFlow API Key（可选，用于知识库向量化，[获取地址](https://siliconflow.cn)，`BAAI/bge-m3` 免费版）

### 2. 配置

从 `.env.template` 复制 `.env` 并按需填入 API Key：

```env
# 必需 - 大模型对话
DEEPSEEK_API_KEY=sk-你的key

# 可选 - 知识库向量化（不配则知识内容嵌入提示词）
# SILICONFLOW_API_KEY=sk-你的key

# 品牌配置
YUXI_BRAND_FILE_PATH=package/yuxi/config/static/info.local.yaml
LITE_MODE=false
```

> 数据库、Redis、MinIO 等服务地址在 Docker 模式下由 `docker-compose.yml` 自动注入，无需手动配置。

### 3. 启动

#### 方式一：本地开发模式（推荐）

后端 + 基础设施在 Docker 中运行，前端本地 `pnpm dev`：

```powershell
# 一键启动（Docker 后端 + 本地前端）
.\dev.ps1

# 或分步启动
.\dev.ps1 docker       # 启动 Docker 服务（后端 + 基础设施）
.\dev.ps1 frontend    # 启动前端 (localhost:5173)
.\dev.ps1 stop        # 停止全部
```

#### 方式二：全 Docker 模式（服务器部署）

```bash
docker compose --profile full up -d
```

需要知识库 RAG 和知识图谱时加上完整服务：
```bash
docker compose --profile full --profile all up -d
```

访问 `http://localhost:5173` 即可使用。

### 4. 首次配置

1. 设置管理员账号密码
2. 系统设置 → 模型配置 → 启用 SiliconFlow → 确认 API Key → 默认模型为 `deepseek-ai/DeepSeek-V4-Flash`
3. （可选）启用 SiliconFlow → 填入 API Key → 添加 `BAAI/bge-m3` 作为 Embedding 模型
4. （可选，依赖上一步）挂载养老知识库：`docker compose exec api uv run python scripts/seed_knowledge_base.py`（幂等可重复执行；配了多个 Embedding 模型时需以环境变量 `YUXI_KB_EMBEDDING_MODEL_SPEC` 指定）
5. 开始对话

## 项目结构

```
silver-guardian-yuxi/
├── README.md                              # 本文档
├── LICENSE                                # MIT 许可证
├── CONTRIBUTING.md                        # 贡献指南
├── FAQ.md                                 # 常见问题
├── SECURITY.md                            # 安全策略
├── ARCHITECTURE.md                        # 架构代码地图
├── DEPLOYMENT.md                          # 部署指南
├── Makefile                               # 构建/测试/格式化命令
├── dev.ps1                                # 本地开发一键启动脚本
├── docker-compose.yml                     # Docker 编排
├── .env.template                          # 环境变量模板
├── knowledge_docs/                        # 养老知识文档（4 份）
│   ├── 老年人权益保障法要点.md
│   ├── 老年慢性病日常管理指南.md
│   ├── 老年人护理操作规范.md
│   └── 老年人防诈骗安全指南.md
├── docs/                                  # VitePress 文档站
│   ├── architecture.svg                   # 系统架构图
│   ├── scripts/generate_architecture.py   # 架构图生成脚本
│   ├── intro/                             # 快速入门、项目概览
│   ├── agents/                            # 智能体配置、工具、MCP、Skills
│   ├── advanced/                          # 高级配置、部署、Langfuse
│   └── develop-guides/                    # 开发规范、changelog、设计文档
├── backend/                               # 后端
│   ├── run_dev.py                         # 本地启动脚本
│   ├── pyproject.toml                     # 工作区依赖与工具配置
│   ├── server/                            # FastAPI HTTP 适配层
│   │   ├── main.py                        # 应用入口
│   │   ├── routers/                       # 路由（18 个领域路由）
│   │   ├── utils/                         # 认证、生命周期、日志
│   │   └── worker_main.py                 # Worker 入口
│   ├── package/yuxi/                      # 核心业务包
│   │   ├── agents/                        # LangGraph 智能体
│   │   │   ├── buildin/                   # 内置智能体（chatbot / subagent）
│   │   │   ├── skills/buildin/            # 内置技能（6 个）
│   │   │   ├── toolkits/                  # 工具注册
│   │   │   └── backends/                  # 沙盒与 Skills 后端
│   │   ├── services/                      # 用例层（21 个服务模块）
│   │   ├── repositories/                  # 数据库访问层
│   │   ├── knowledge/                     # 知识库与图谱
│   │   ├── models/                        # LLM / Embedding 模型适配
│   │   ├── storage/                       # PostgreSQL / MinIO / Redis
│   │   ├── config/                        # 应用配置与品牌信息
│   │   └── utils/                         # 通用工具
│   ├── test/                              # 测试（unit / integration / e2e）
│   └── scripts/                           # 数据初始化脚本
└── web/                                   # 前端（Vue 3）
    └── src/
        ├── views/                         # 页面（对话、知识库、仪表盘等）
        ├── components/                    # 可复用组件（68 个）
        ├── composables/                   # 组合式逻辑（12 个）
        ├── apis/                          # 后端接口封装（20 个）
        ├── stores/                        # Pinia 状态管理
        ├── router/                        # 路由配置
        ├── utils/                         # 前端工具函数
        └── assets/css/                    # 全局样式与适老化样式
```

## 开发命令

```bash
# 启动开发环境
make up              # Docker 启动（后端 + 基础设施）

# 代码格式化与检查
make format          # 格式化后端 + 前端
make lint            # 静态检查（不修复）

# 测试
make test            # 全部测试
make test-unit       # 单元测试
make test-integration # 集成测试
make test-e2e        # 端到端测试

# 数据管理
make seed            # 初始化种子用户
make seed-kb         # 创建养老知识库并挂载到默认智能体（需先配置 Embedding 模型）
make reset           # 重置全部数据并重新初始化
make down            # 停止全部容器
```

## 截图

<!-- TODO: 截图待补充 -->

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + Ant Design Vue + Vite + Pinia |
| 后端 | FastAPI + Python 3.12+ + uv |
| 智能体框架 | LangGraph v1 + DeepAgents |
| 大模型 | DeepSeek-V4-Flash（SiliconFlow）· OpenAI 兼容 · Anthropic |
| 向量数据库 | Milvus |
| 图数据库 | Neo4j |
| 缓存 | Redis |
| 数据库 | PostgreSQL |
| 对象存储 | MinIO |
| 异步任务 | ARQ |
| 文档解析 | MinerU · PaddleOCR · RapidOCR |
| 部署 | Docker Compose |

## 版本历史

| 版本 | 说明 |
|------|------|
| v0.1.0 | 项目初始化，品牌定制，Docker 部署 |
| v0.2.0 | 4 个养老智能体 + 知识库文档 + 子智能体调度 + 自定义 Skills |
| v0.3.0 | 适老化界面 + 紧急求助识别 + 语音输入 + 快捷问题 + 设置页 |
| v0.4.0 | 语音朗读(TTS) + 稳定性加固 |
| v0.7.1 | 平台升级：CLI 工具、知识库大规模优化、多色主题、安全加固（当前版本） |

> 完整变更记录见 [docs/develop-guides/changelog.md](docs/develop-guides/changelog.md)。

## 相关文档

- [架构设计](ARCHITECTURE.md) — 系统边界与代码地图
- [部署指南](DEPLOYMENT.md) — 详细部署说明
- [参与贡献](CONTRIBUTING.md) — 开发流程与规范
- [常见问题](FAQ.md) — FAQ
- [安全策略](SECURITY.md) — 漏洞报告与安全配置
- [开发文档](docs/) — VitePress 文档站

## 许可证

本项目基于 [MIT License](LICENSE) 开源。

Copyright (c) 2025-present LPK3215 and contributors.

## 致谢

感谢以下开源项目：

- [Yuxi](https://github.com/xerrors/Yuxi) —— 智能知识库与知识图谱智能体框架
- [LangGraph](https://github.com/langchain-ai/langgraph) —— 智能体编排框架
- [FastAPI](https://github.com/fastapi/fastapi) —— 高性能 Web 框架
- [Vue.js](https://github.com/vuejs/core) —— 前端渐进式框架
- [LightRAG](https://github.com/HKUDS/LightRAG) —— 轻量级知识图谱检索增强生成




