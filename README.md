# SOPilot - 智能教材生成平台

一个基于多智能体协作的现代化教材生成平台，通过 **7个专业化智能体**（规划、研究、写作、验证、QA生成、知识图谱构建、内容合并）的协同工作，自动生成高质量的教育内容并构建结构化知识图谱。

## ✨ 核心特性

- 🤖 **多智能体协作**：7个专业化智能体流水线协作
- 📊 **知识图谱可视化**：基于 Cytoscape.js 的交互式图谱展示
- 🎨 **现代化前端**：Vue 3 + TypeScript + Vite 技术栈
- 🔧 **Prompt工程化**：YAML-based Prompt管理，支持版本控制
- 🌐 **多工作流支持**：可扩展的工作流框架
- 📱 **实时监控**：EventSource 实时进度推送
- 🔄 **多LLM提供商**：支持 OpenAI、SiliconFlow、DeepSeek 等

## 🏗️ 技术架构

### 技术栈详情

**后端技术栈：**
- **FastAPI 0.115.2** - 现代化Python Web框架
- **Uvicorn 0.30.6** - ASGI服务器，支持异步
- **Pydantic 2.9.2** - 数据验证和序列化
- **LangGraph** - 工作流编排引擎，支持多智能体协作
- **LangChain Core** - LLM抽象层和提供商集成
- **Neo4j 5.23.1** - 图数据库驱动，知识图谱存储
- **Jinja2 3.1.4** - 模板引擎，用于Prompt渲染

**前端技术栈：**
- **Vue 3.4.0** - 组合式API，响应式框架
- **TypeScript 5.5.4** - 类型安全的JavaScript超集
- **Vite 5.4.0** - 下一代前端构建工具，HMR支持
- **Pinia 2.1.7** - Vue状态管理
- **Cytoscape 3.33.1** - 图可视化库，用于知识图谱展示
- **Axios 1.7.2** - HTTP客户端

**基础设施：**
- **Docker + Docker Compose** - 容器化部署
- **Neo4j 5.21.0** - 图数据库服务

### 项目结构

```
SOPilot/
├── backend/
│   ├── src/app/
│   │   ├── main.py                # FastAPI 应用入口（含前端托管）
│   │   ├── asgi.py                # ASGI 入口
│   │   ├── api/v1/                # API 路由层
│   │   │   ├── runs.py            # 运行管理API
│   │   │   ├── kg.py              # 知识图谱API
│   │   │   ├── prompts.py         # Prompt管理API
│   │   │   └── workflows.py       # 工作流管理API
│   │   ├── core/                  # 核心基础设施
│   │   │   ├── settings.py        # 配置管理
│   │   │   ├── logging.py         # 日志配置
│   │   │   ├── concurrency.py     # 并发控制
│   │   │   └── progress_manager.py # 进度管理
│   │   ├── domain/                # 领域层
│   │   │   ├── workflows/         # LangGraph 工作流
│   │   │   │   ├── textbook/      # 教材生成工作流
│   │   │   │   └── quiz_maker/    # 问答生成工作流
│   │   │   ├── agents/            # 智能体实现
│   │   │   ├── kg/                # 知识图谱模块
│   │   │   ├── prompts/           # Prompt管理
│   │   │   └── state/             # 状态定义
│   │   ├── infrastructure/        # 基础设施层
│   │   │   ├── llm/               # LLM 客户端和路由
│   │   │   └── graph_store/       # 图数据库接口
│   │   └── services/              # 服务层
│   ├── requirements.txt
│   └── .env(.example)
├── frontend/                      # Vue3 + TypeScript 前端
│   ├── src/
│   │   ├── main.ts                # Vue3 入口
│   │   ├── router/index.ts        # 路由配置
│   │   ├── store/runs.ts          # Pinia 状态管理
│   │   ├── services/api.ts        # API 服务封装
│   │   ├── views/                 # 页面组件
│   │   │   ├── Home.vue           # 工作流选择页
│   │   │   ├── RunDetail.vue      # 运行详情页
│   │   │   └── PromptStudio.vue   # Prompt管理页
│   │   └── components/            # 通用组件
│   │       ├── KgGraph.vue        # 知识图谱可视化
│   │       └── RunConsole.vue     # 运行日志控制台
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── docs/                          # 项目文档
├── output/                        # 运行产物输出
├── Dockerfile                     # 多阶段构建：前端+后端
├── docker-compose.yml             # 服务编排
└── scripts/dev.ps1                # 本地开发脚本
```

### 架构图

```mermaid
flowchart TB
    subgraph "前端层 (Vue3 + TypeScript)"
        A[Home.vue<br/>工作流选择] 
        B[RunDetail.vue<br/>运行监控]
        C[PromptStudio.vue<br/>Prompt管理]
        D[KgGraph.vue<br/>图谱可视化]
    end
    
    subgraph "API层 (FastAPI)"
        E[/api/v1/runs<br/>运行管理]
        F[/api/v1/kg<br/>知识图谱]
        G[/api/v1/prompts<br/>Prompt管理]
        H[/api/v1/workflows<br/>工作流管理]
    end
    
    subgraph "业务层 (LangGraph)"
        I[Planner<br/>规划智能体]
        J[Researcher<br/>研究智能体]
        K[Writer<br/>写作智能体]
        L[KG Builder<br/>图谱构建]
    end
    
    subgraph "数据层"
        M[(Neo4j<br/>知识图谱)]
        N[Output<br/>产物存储]
    end
    
    A --> E
    B --> E
    B --> F
    C --> G
    D --> F
    
    E --> I
    E --> J
    E --> K
    E --> L
    F --> M
    G --> N
    
    I --> M
    J --> M
    K --> M
    L --> M
```

## 🎯 设计原则

- **可扩展性**: 教材生成只是平台中的一个应用，未来可添加课程生成、评估等应用
- **单一职责**: 工作流只负责编排，算法逻辑收敛到独立模块  
- **面向接口**: 域接口稳定，具体实现可替换（内存/Neo4j、不同LLM提供商）
- **可测试性**: 模块边界清晰，核心逻辑以纯函数/接口为主
- **安全序列化**: 避免将驱动/非序列化对象放入工作流状态
- **配置中心化**: 统一配置管理，支持环境变量覆盖

## 🚀 快速开始

### 环境要求

**必需环境：**
```bash
# 检查版本
python --version  # >= 3.11
node --version    # >= 20.0
docker --version  # >= 26.0
docker compose version  # v2.x
```

**可选环境：**
```bash
# Python包管理器（推荐）
pip install uv  # 更快的包管理器

# PowerShell（Windows推荐）
winget install Microsoft.PowerShell
```

### 安装部署

#### 方式1：Docker Compose（推荐，一键部署）

```bash
# 1. 克隆仓库
git clone <repository_url>
cd SOPilot

# 2. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env 文件，配置必要的API密钥

# 3. 一键启动所有服务
docker compose up -d --build

# 4. 验证服务状态
curl http://localhost:8000/api/v1/runs/health
# 期望返回：{"status": "ok"}

# 5. 访问前端
# 浏览器打开：http://localhost:5173
```

#### 方式2：本地开发启动

```powershell
# Windows PowerShell 一键启动
pwsh -File scripts/dev.ps1

# 或者手动分步启动：

# 后端启动
cd backend
pip install -r requirements.txt
export PYTHONPATH=src  # Linux/Mac
# set PYTHONPATH=src   # Windows
python -m uvicorn app.asgi:app --reload --app-dir src --port 8000

# 前端启动（新终端）
cd frontend
npm install
npm run dev

# Neo4j启动（新终端，可选）
docker run --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/test1234 neo4j:5.21.0
```

#### 方式3：混合模式（后端容器 + 前端本地）

```bash
# 启动后端和Neo4j
docker compose up -d backend neo4j

# 本地启动前端（便于开发调试）
cd frontend
npm install
npm run dev
```

### 环境配置详解

创建 `backend/.env` 文件并配置以下参数：

```bash
# ===================
# 核心工作流配置
# ===================
APP_USE_REAL_WORKFLOW=true
APP_OUTPUT_DIR=/app/output

# ===================
# LLM提供商配置（三选一）
# ===================

# 选项1：SiliconFlow（推荐，性价比高）
APP_DEFAULT_PROVIDER=siliconflow
APP_PROVIDERS__siliconflow__BASE_URL=https://api.siliconflow.cn/v1
APP_PROVIDERS__siliconflow__MODEL=Qwen/Qwen3-Coder-30B-A3B-Instruct
APP_PROVIDERS__siliconflow__API_KEYS=["sk-your-siliconflow-key"]

# 选项2：OpenAI
# APP_DEFAULT_PROVIDER=openai
# APP_PROVIDERS__openai__BASE_URL=https://api.openai.com/v1
# APP_PROVIDERS__openai__MODEL=gpt-4o-mini
# APP_PROVIDERS__openai__API_KEYS=["sk-your-openai-key"]

# 选项3：DeepSeek
# APP_DEFAULT_PROVIDER=deepseek
# APP_PROVIDERS__deepseek__BASE_URL=https://api.deepseek.com/v1
# APP_PROVIDERS__deepseek__MODEL=deepseek-coder
# APP_PROVIDERS__deepseek__API_KEYS=["sk-your-deepseek-key"]

# ===================
# Neo4j图数据库配置
# ===================
APP_NEO4J__URI=bolt://localhost:7687     # 本地部署
# APP_NEO4J__URI=bolt://neo4j:7687       # Docker部署
APP_NEO4J__USER=neo4j
APP_NEO4J__PASSWORD=test1234
APP_NEO4J__DATABASE=neo4j

# ===================
# 并发与性能配置
# ===================
APP_CONCURRENCY__WRITER__MAX_WORKERS=50
APP_CONCURRENCY__KG_BUILDER__MAX_WORKERS=50
APP_CONCURRENCY__VALIDATOR__MAX_REWRITE_ATTEMPTS=2

# ===================
# 中间件配置
# ===================
APP_MIDDLEWARE__MAX_RETRIES=3
APP_MIDDLEWARE__DEFAULT_TIMEOUT=300
APP_MIDDLEWARE__REQUESTS_PER_MINUTE=60
```

### 服务端口说明

| 服务 | 端口 | 用途 | 访问地址 |
|------|------|------|----------|
| 前端开发服务器 | 5173 | Vue3 Vite Dev Server | http://localhost:5173 |
| 后端API服务 | 8000 | FastAPI应用 | http://localhost:8000 |
| Neo4j Web控制台 | 7474 | 图数据库管理界面 | http://localhost:7474 |
| Neo4j Bolt协议 | 7687 | 图数据库连接端口 | bolt://localhost:7687 |

### 验证安装

运行以下命令验证各服务状态：

```bash
# 1. 后端健康检查
curl http://localhost:8000/api/v1/runs/health
# 期望返回：{"status": "ok"}

# 2. API文档访问
curl http://localhost:8000/docs
# 或浏览器访问查看 Swagger UI

# 3. 前端页面访问
curl http://localhost:5173
# 或浏览器访问前端界面

# 4. Neo4j连接测试
curl -u neo4j:test1234 http://localhost:7474/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements":[{"statement":"RETURN 1 as test"}]}'

# 5. 创建测试运行
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{"topic":"Python基础","language":"中文","chapter_count":2}'
```

## 📖 使用指南

### 基础使用流程

1. **选择工作流**
   - 访问首页 `http://localhost:5173`
   - 选择"教材生成工作流"或其他可用工作流

2. **配置参数**
   - 输入教材主题（例：Python基础编程）
   - 选择生成语言（中文/English）
   - 设置章节数量（1-20章）

3. **启动生成**
   - 点击"开始生成"按钮
   - 系统自动跳转到运行详情页

4. **监控进度**
   - 实时查看7个智能体的执行进度
   - 观察日志输出和状态更新

5. **查看结果**
   - 浏览生成的教材内容
   - 探索知识图谱可视化
   - 下载产物文件

### 高级功能

#### Prompt管理

访问 `/prompts` 页面进行Prompt编辑：

1. **选择Agent**：从左侧列表选择要编辑的智能体
2. **编辑模式**：支持表单编辑和YAML直接编辑
3. **实时预览**：查看渲染后的Prompt效果
4. **版本管理**：基于Git的版本控制和回滚
5. **模型配置**：为不同Agent配置不同的LLM模型

#### 知识图谱分析

在运行详情页的"知识图谱"标签：

1. **双层视图**：整本书图谱 vs 小节图谱
2. **交互操作**：节点拖拽、缩放、搜索
3. **关系探索**：点击节点查看关联关系
4. **统计信息**：节点数量、边数量、图谱密度

#### 多工作流扩展

系统支持多种工作流类型：

- **教材生成**：完整的多智能体教材创作流程
- **问答生成**：基于内容生成问答对
- **自定义工作流**：通过API扩展新的工作流类型

### API接口使用

#### 创建运行

```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "机器学习基础",
    "language": "中文",
    "chapter_count": 5,
    "workflow_id": "textbook"
  }'
```

#### 获取运行状态

```bash
curl http://localhost:8000/api/v1/runs/{run_id}
```

#### 实时监控

```bash
curl http://localhost:8000/api/v1/runs/{run_id}/stream
```

#### 知识图谱查询

```bash
# 获取整本书图谱
curl http://localhost:8000/api/v1/kg/books/{book_id}

# 获取小节图谱
curl http://localhost:8000/api/v1/kg/sections/{section_id}
```

## 🔧 故障排除

### 常见问题

#### 问题1：端口冲突

```bash
# 检查端口占用
netstat -an | grep ":8000\|:5173\|:7687"
# Windows: netstat -an | findstr ":8000 :5173 :7687"

# 解决方案：修改 docker-compose.yml 中的端口映射
```

#### 问题2：Neo4j连接失败

```bash
# 检查Neo4j容器状态
docker logs sopilot-neo4j

# 常见原因：
# 1. 端口被占用 → 修改端口
# 2. 内存不足 → 增加Docker内存限制
# 3. 密码错误 → 检查环境变量
```

#### 问题3：LLM API调用失败

```bash
# 检查API密钥配置
# 1. 确认密钥格式正确（JSON数组格式）
# 2. 确认密钥有效且有余额
# 3. 检查网络连接和代理设置
# 4. 确认BASE_URL正确
```

#### 问题4：前端构建失败

```bash
# 清理缓存重新安装
cd frontend
rm -rf node_modules package-lock.json
npm install

# 或使用镜像源
npm config set registry https://registry.npmmirror.com
npm install
```

### 日志查看

```bash
# Docker容器日志
docker logs sopilot-backend
docker logs sopilot-frontend
docker logs sopilot-neo4j

# 本地运行日志
# 后端日志会输出到控制台
# 前端日志在浏览器开发者工具中查看
```

## ⚙️ 核心特性详解

### 多智能体协作工作流

基于LangGraph的7节点智能体流水线：

1. **Planner（规划智能体）**
   - 生成教材大纲和章节结构
   - 输出结构化的章节树

2. **Researcher（研究智能体）**
   - 并发研究各子章节
   - 生成关键词和研究摘要

3. **Writer（写作智能体）**
   - 并发生成子章节内容
   - 与验证智能体闭环迭代

4. **Validator（验证智能体）**
   - 多维度内容质量评估
   - 不合格内容触发重写

5. **QA Generator（问答生成智能体）**
   - 为验证通过的内容生成问答对
   - 支持多种问答类型

6. **KG Builder（知识图谱构建智能体）**
   - 构建结构化知识图谱
   - 生成节点和关系

7. **Merger（合并智能体）**
   - 整合所有内容和QA
   - 生成最终教材

### 知识图谱系统

#### 数据模型
- **节点类型**：Concept（概念）、Chapter（章节）、Subchapter（子章节）
- **关系类型**：RELATES_TO、PART_OF、REQUIRES、CONTRASTS_WITH
- **双Scope存储**：section级（局部）+ book级（全局）视图

#### 存储策略
- **幂等写入**：基于RID确保数据一致性
- **替换模式**：按scope删除旧数据再插入新数据
- **增量更新**：支持内容变更的增量构建

### Prompt工程化管理

#### YAML模板系统
- **多段messages**：支持system/user/assistant角色
- **Jinja2渲染**：动态变量注入
- **版本控制**：基于Git的版本管理

#### 绑定机制
- **声明式配置**：通过prompt_bindings.yaml管理
- **模型选择**：支持不同Agent使用不同模型
- **参数覆盖**：运行时参数动态调整

### LLM多提供商支持

#### 适配器模式
- **统一接口**：标准化的LLM调用接口
- **提供商适配**：OpenAI、SiliconFlow、DeepSeek等
- **负载均衡**：多API密钥轮转和故障转移

#### 中间件机制
- **重试机制**：指数退避和熔断器
- **超时控制**：请求级和节点级超时
- **限流保护**：RPM限制和背压控制

## 📊 性能与监控

### 性能优化

- **并发处理**: 子章节级别的细粒度并发，支持50个并发任务
- **API负载均衡**: 多Provider、多Key的轮转/熔断/恢复机制
- **内存优化**: 避免大对象在工作流状态中传递
- **缓存机制**: Prompt缓存和配置热加载
- **增量更新**: Neo4j幂等写入和替换模式

### 监控指标

- **实时进度**: EventSource推送工作流执行状态
- **性能指标**: 响应时间、成功率、并发数
- **资源监控**: 内存使用、API调用次数
- **错误追踪**: 结构化日志和错误分类

### 运行产物管理

运行产物存储在 `output/<run_id>/` 目录：

```
output/
└── <run_id>/
    ├── book.md                 # 合并后的完整教材
    ├── book.json               # 结构化元数据
    ├── qa.json                 # 问答对数据
    ├── kg_section_ids.json     # 小节图谱ID列表
    ├── book_id.txt             # 整本书图谱ID
    └── logs.ndjson             # 运行日志
```

#### 下载接口

```bash
# 列出产物文件
GET /api/v1/runs/{run_id}/artifacts

# 单文件下载
GET /api/v1/runs/{run_id}/download?file=book.md

# 打包下载
GET /api/v1/runs/{run_id}/archive.zip
```

## 🔧 开发与扩展

### 添加新工作流

1. 在 `backend/src/app/domain/workflows/` 下创建新目录
2. 实现 `graph.py` 并导出 `get_workflow()` 和 `get_metadata()` 函数
3. 在前端 `Home.vue` 中工作流选择器会自动发现新工作流

### 添加新智能体

1. 在 `backend/src/app/domain/agents/` 下实现智能体类
2. 在 `backend/src/app/domain/workflows/textbook/nodes/` 下创建节点包装器
3. 更新工作流图定义

### 添加新LLM提供商

1. 在 `backend/src/app/infrastructure/llm/router/adapters/` 下实现新适配器
2. 继承 `BaseLLMAdapter` 并实现 `generate` 方法
3. 在 `LLMRouter` 中注册新适配器

### 前端组件开发

1. 使用 Vue 3 组合式API + TypeScript
2. 遵循现有的目录结构和命名约定
3. 使用 Pinia 进行状态管理
4. 使用 Axios 进行API调用

## 📚 相关文档

- **项目现状**: `docs/PROJECT_CURRENT_STATE.md` - 详细的技术实现说明
- **改进指南**: `docs/IMPROOVE_GUIDE.md` - 系统升级和功能扩展计划
- **前端招募**: `docs/FRONTEND_DEVELOPER_RECRUITMENT.md` - 前端开发者入门指南
- **开发进度**: `docs/DEVELOPMENT_PROGRESS.md` - 项目开发进度跟踪

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 提交 Pull Request

### 开发规范

- **Python代码**: 遵循PEP8规范
- **TypeScript代码**: 使用严格模式，遵循ESLint规则
- **Git提交**: 使用约定式提交格式
- **文档更新**: 重要功能需要更新相应文档

## 📄 许可证

MIT License - 详见 `LICENSE` 文件

## 🎯 路线图

### 近期目标 (Q1 2025)

- [x] **基础多智能体工作流** - 7个智能体协作的教材生成
- [x] **知识图谱可视化** - 基于Cytoscape.js的交互式展示
- [x] **Prompt工程化管理** - YAML-based模板系统
- [x] **多工作流支持** - 可扩展的工作流框架
- [ ] **RAG集成** - 混合检索增强生成系统
- [ ] **性能优化** - 大规模并发和缓存优化

### 中期目标 (Q2-Q3 2025)

- [ ] **课程生成工作流** - 基于教材的课程设计应用
- [ ] **评估系统** - 学习效果评估和反馈机制
- [ ] **个性化定制** - 基于学习者特征的内容适配
- [ ] **移动端支持** - 响应式设计和移动端优化
- [ ] **多语言国际化** - 支持更多语言的内容生成

### 长期愿景 (Q4 2025+)

- [ ] **AI教学助手** - 智能问答和学习指导
- [ ] **协作编辑** - 多用户实时协作编辑
- [ ] **内容市场** - 教材和课程的分享平台
- [ ] **企业级部署** - 私有化部署和权限管理
- [ ] **开放生态** - 插件系统和第三方集成

---

**SOPilot** - 让AI驱动教育内容创作 🚀

> 如有问题或建议，欢迎提交 Issue 或 Pull Request