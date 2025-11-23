# SOPilot 系统架构设计指南

> **版本**: 1.0  
> **更新日期**: 2025-10-23  
> **状态**: ✅ 最新

---

## 📖 文档说明

本文档详细描述了 SOPilot AI 教材生成平台的系统架构设计，包括技术栈、分层架构、核心组件、以及 FastAPI 官方推荐实践的应用。

**图例说明**：
- ✅ **FastAPI 官方推荐** - 符合 FastAPI 官方文档推荐的最佳实践
- 🎯 **架构模式** - 采用的架构设计模式
- ⚡ **性能优化** - 性能优化相关的设计

---

## 项目概述

SOPilot 是一个基于现代化架构的 AI 教材生成平台，采用分层设计、模块化开发，集成了 RAG(检索增强生成)、KG(知识图谱)、多工作流等核心技术，提供智能化教材创作和知识管理服务。

### 技术特色

- **现代化全栈架构**: FastAPI 后端 + Vue3 前端 + 微服务基础设施
- **AI 工程化**: 多 Provider LLM 路由、Prompt 统一管理、工作流编排
- **RAG+KG 双引擎**: 向量检索与知识图谱检索并行，智能合并重排
- **分层解耦设计**: 领域驱动、依赖注入、面向对象、可插拔组件
- **容器化部署**: Docker Compose 编排，支持生产级部署

### FastAPI 最佳实践应用

本项目严格遵循 FastAPI 官方文档推荐的最佳实践：

1. ✅ **项目结构**: 采用多文件模块化结构，清晰的分层架构
2. ✅ **依赖注入**: 使用 `Depends()` 实现依赖注入和复用
3. ✅ **配置管理**: 使用 `pydantic-settings` 管理配置
4. ✅ **类型检查**: 全面使用 Pydantic 模型进行请求/响应验证
5. ✅ **异步编程**: 全面采用 `async/await` 模式
6. ✅ **生命周期管理**: 使用 startup/shutdown 事件管理资源
7. ✅ **路由组织**: 使用 APIRouter 组织模块化路由
8. ✅ **OpenAPI 文档**: 自动生成 API 文档

## 整体架构设计

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    SOPilot AI教材生成平台                    │
├─────────────────────────────────────────────────────────────┤
│                      前端层 (Frontend)                       │
│  Vue3 + TypeScript + Vite + Pinia + Vue Router              │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐   │
│  │   工作流     │  Prompt     │   运行详情   │   知识库    │   │
│  │   选择器     │  Studio     │   管理      │   管理      │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                      API层 (FastAPI)                        │
│  RESTful APIs + OpenAPI + 异步处理 + CORS                    │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐   │
│  │  Workflows  │   Prompts   │    Runs     │     RAG     │   │
│  │     API     │     API     │     API     │     API     │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    服务层 (Services)                         │
│  工作流服务 + Prompt服务 + LLM服务 + RAG服务                 │
├─────────────────────────────────────────────────────────────┤
│                    领域层 (Domain)                          │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐   │
│  │   智能体     │   工作流     │   知识图谱  │   状态管理   │   │
│  │  (Agents)   │ (Workflows) │    (KG)     │  (State)    │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                  基础设施层 (Infrastructure)                  │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐   │
│  │   LLM路由    │   RAG引擎   │   图存储    │   文件存储   │   │
│  │  (Router)   │ (Pipeline)  │(GraphStore) │ (Storage)   │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    数据层 (Data)                            │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │    Neo4j    │   Qdrant    │   文件系统   │   配置存储   │  │
│  │  知识图谱    │  向量数据库  │    输出     │    YAML     │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 架构分层

```
project_root/
├── 前端应用层 (frontend/)          # Vue3现代化SPA应用
├── 后端应用层 (backend/)          # FastAPI微服务应用
│   ├── API层 (api/)              # RESTful接口定义
│   ├── 服务层 (services/)         # 业务逻辑服务
│   ├── 领域层 (domain/)          # 核心业务领域
│   ├── 基础设施层 (infrastructure/) # 外部依赖集成
│   └── 核心层 (core/)            # 框架核心功能
├── 基础设施编排 (docker-compose.yml) # 容器服务编排
├── 知识库 (knowledge_base/)       # RAG知识库存储
├── 输出产物 (output/)            # 生成结果存储
└── 项目文档 (docs/)             # 架构与开发文档
```

## 详细架构解析

### 1. 前端应用层 (`frontend/`)

**技术栈**: Vue 3 + TypeScript + Vite + Pinia + Vue Router + Cytoscape

```
frontend/
├── src/
│   ├── main.ts                   # 应用入口(TypeScript)
│   ├── App.vue                   # 根组件(现代化导航栏)
│   ├── router/
│   │   └── index.ts             # Vue Router配置(4个主要页面)
│   ├── store/
│   │   └── runs.ts              # Pinia状态管理(运行状态)
│   ├── services/
│   │   └── api.ts               # API服务封装(统一接口)
│   ├── views/                   # 页面组件
│   │   ├── Home.vue             # 首页(工作流选择+动态表单)
│   │   ├── RunDetail.vue        # 运行详情(三标签页布局)
│   │   ├── PromptStudio.vue     # Prompt编辑器(三栏布局)
│   │   └── KnowledgeBase.vue    # 知识库管理(双栏布局)
│   └── components/              # 可复用组件
│       ├── KgGraph.vue          # 知识图谱可视化(Cytoscape)
│       └── RunConsole.vue       # 运行控制台组件
├── package.json                 # 项目依赖和构建配置
├── vite.config.ts              # Vite构建工具配置
└── tsconfig.json               # TypeScript编译配置
```

**核心特性**:
- **现代化UI框架**: Vue 3 Composition API + TypeScript严格类型检查
- **响应式设计**: 适配多屏幕，统一设计语言
- **动态表单**: 基于JSON Schema的智能表单生成
- **实时可视化**: Cytoscape知识图谱渲染
- **状态管理**: Pinia集中式状态管理
- **模块化路由**: Vue Router SPA路由管理

### 2. 后端应用层 (`backend/src/`)

**技术栈**: FastAPI + Pydantic + AsyncIO + Dependency Injection

#### 2.1 API 层 (`api/v1/`) ✅

```
backend/src/app/api/v1/
├── router.py                    # API路由聚合器 ✅ FastAPI APIRouter
├── runs.py                      # 运行管理API
├── workflows.py                 # 工作流API  
├── prompts.py                   # Prompt管理API
├── kg.py                        # 知识图谱API
└── rag.py                       # RAG检索API
```

**✅ FastAPI 官方推荐的 API 设计实践**:

1. **模块化路由组织** ✅
   - 使用 `APIRouter` 将相关端点分组到独立文件
   - 通过 `prefix` 和 `tags` 组织 API 结构
   - 在主路由器中聚合所有子路由

2. **路由聚合器实现** ✅
   ```python
   # backend/src/app/api/v1/router.py
   from fastapi import APIRouter
   
   api_router = APIRouter(prefix="/api/v1")  # ✅ 统一前缀
   api_router.include_router(runs_router, tags=["runs"])  # ✅ 模块化路由
   api_router.include_router(kg_router, tags=["kg"])
   api_router.include_router(prompts_router, tags=["prompts"])
   # ... 其他路由
   ```

3. **异步端点定义** ✅
   ```python
   @router.get("", response_model=List[Dict[str, Any]])  # ✅ 类型注解
   async def get_workflows():  # ✅ 异步处理
       """获取所有可用工作流列表"""  # ✅ 文档字符串
       try:
           workflows = list_workflows()
           return [...]  # ✅ 直接返回可序列化对象
       except Exception as e:
           raise HTTPException(status_code=500, detail=str(e))  # ✅ 标准异常处理
   ```

**API 设计原则**:
- ✅ **RESTful 标准**: 标准 HTTP 方法和状态码
- ✅ **统一响应格式**: 结构化错误处理和数据返回
- ✅ **OpenAPI 文档**: 自动生成交互式 API 文档
- ✅ **异步处理**: 全面使用 `async/await` 模式
- ✅ **参数验证**: Pydantic 模型自动验证
- ✅ **路径操作装饰器**: 使用 `@router.get/post/put/delete`

#### 2.2 服务层 (`services/`)

```
backend/src/app/services/
├── workflow_service.py          # 工作流编排服务
├── prompt_service.py            # Prompt管理服务
└── llm_service.py              # LLM调用服务
```

**服务特性**:
- **业务逻辑封装**: 纯业务逻辑，无外部依赖
- **服务组合**: 跨领域协调和编排
- **错误处理**: 统一异常处理机制
- **事务管理**: 复杂操作的一致性保证

#### 2.3 领域层 (`domain/`)

```
backend/src/app/domain/
├── agents/                      # 智能体定义
│   ├── kg_builder.py           # KG构建智能体
│   ├── planner.py              # 规划智能体
│   ├── researcher.py           # 研究智能体
│   ├── writer.py               # 写作智能体
│   └── validator.py            # 验证智能体
├── workflows/                   # 工作流编排
│   ├── registry.py             # 工作流注册中心
│   ├── textbook/               # 教材生成工作流
│   │   ├── graph.py            # 工作流图定义
│   │   └── nodes/              # 工作流节点
│   └── quiz_maker/             # 问答生成工作流
├── kg/                         # 知识图谱引擎
│   ├── pipeline.py             # KG构建流水线
│   ├── builder.py              # 实体关系抽取
│   ├── normalizer.py           # 概念标准化
│   ├── idempotent.py           # 幂等处理
│   ├── store.py                # 图存储
│   ├── merger.py               # 整书级合并
│   └── service.py              # 查询服务
├── prompts/                    # Prompt模板
│   ├── agents/                 # 智能体Prompt
│   ├── workflows/              # 工作流Prompt
│   ├── prompt_bindings.yaml    # 模型绑定配置
│   └── schema.json             # Prompt Schema
├── schemas/                    # 数据模型
└── state/                      # 状态管理
```

**领域驱动设计**:
- **智能体模式**: 单一职责的AI智能体
- **工作流编排**: LangGraph图式工作流
- **KG工程化**: 6层流水线架构
- **Prompt管理**: YAML化模板系统
- **状态管理**: TypedDict严格类型

#### 2.4 基础设施层 (`infrastructure/`)

```
backend/src/app/infrastructure/
├── llm/                        # LLM集成
│   ├── router/                 # LLM路由器
│   │   ├── core.py             # 路由核心
│   │   └── adapters/           # Provider适配器
│   │       ├── openai.py       # OpenAI适配器
│   │       ├── siliconflow.py  # 硅基流动适配器
│   │       └── deepseek.py     # DeepSeek适配器
│   └── providers/              # Provider实现
├── rag/                        # RAG检索引擎
│   ├── pipeline.py             # RAG主管线
│   ├── chunker.py              # 文档分块
│   ├── embedder.py             # 嵌入服务(API化)
│   ├── vectorstores/           # 向量存储
│   │   └── qdrant_store.py     # Qdrant集成
│   ├── kgstores/               # KG存储
│   │   ├── neo4j_queries.py    # Neo4j查询
│   │   └── document_store.py   # 文档-KG桥接
│   ├── retrievers/             # 检索器
│   │   ├── retriever_vector.py # 向量检索
│   │   └── retriever_kg.py     # KG检索
│   ├── nlp/                    # NLP工具
│   │   └── entity_extractor.py # 实体抽取
│   ├── rerankers/              # 重排器
│   │   └── bge_reranker.py     # BGE重排(API化)
│   ├── merger.py               # 证据合并
│   └── prompt_builder.py       # RAG Prompt构造
├── graph_store/                # 图数据库
└── storage/                    # 文件存储
    └── output_writer.py        # 输出写入器
```

**基础设施特性**:
- **LLM路由**: 多Provider透明切换
- **RAG双通道**: 向量+KG并行检索
- **API化嵌入**: 无本地模型依赖
- **智能合并**: 证据重排算法
- **存储抽象**: 可插拔存储后端

#### 2.5 核心层 (`core/`) ✅

```
backend/src/app/core/
├── settings.py                 # 应用配置管理 ✅ Pydantic Settings
├── logging.py                  # 日志配置
├── lifecycle.py                # 应用生命周期 ✅ FastAPI Events
├── concurrency.py              # 并发控制
└── progress_manager.py         # 进度管理
```

**✅ FastAPI 官方推荐的核心实践**:

1. **配置管理** ✅
   ```python
   # backend/src/app/core/settings.py
   from pydantic_settings import BaseSettings, SettingsConfigDict
   
   class AppSettings(BaseSettings):
       app_name: str = "SOPilot API"
       env: str = "dev"
       debug: bool = True
       
       # LLM 配置
       default_provider: Optional[str] = None
       providers: Dict[str, ProviderSettings] = Field(default_factory=dict)
       
       # 数据库配置
       neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
       qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
       
       # ✅ 环境变量配置
       model_config = SettingsConfigDict(
           env_file=".env",                # ✅ 支持 .env 文件
           env_prefix="APP_",              # ✅ 环境变量前缀
           env_nested_delimiter="__"       # ✅ 嵌套配置支持
       )
   
   @lru_cache(maxsize=1)  # ✅ 单例模式缓存配置
   def get_settings() -> AppSettings:
       return AppSettings()
   ```

2. **生命周期管理** ✅
   ```python
   # backend/src/app/core/lifecycle.py
   from contextlib import asynccontextmanager
   
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       # ✅ 启动阶段
       # 初始化数据库连接
       init_neo4j(settings)
       install_schema()
       
       yield  # ✅ 应用运行期间
       
       # ✅ 关闭阶段
       # 清理资源
       logger.info("应用正在关闭...")
   ```

3. **应用工厂模式** ✅
   ```python
   # backend/src/app/main.py
   def create_app() -> FastAPI:
       setup_logging()
       app = FastAPI(
           title="SOPilot API", 
           version="0.1.0",
           lifespan=lifespan  # ✅ 使用 lifespan 上下文管理器
       )
       
       # ✅ CORS 中间件
       app.add_middleware(
           CORSMiddleware,
           allow_origins=["*"],
           allow_credentials=True,
           allow_methods=["*"],
           allow_headers=["*"],
       )
       
       # ✅ 路由注册
       app.include_router(api_router)
       
       return app
   ```

**核心功能**:
- ✅ **配置管理**: Pydantic Settings 分层配置，环境变量优先
- ✅ **日志系统**: 结构化日志记录
- ✅ **生命周期**: lifespan 上下文管理器（FastAPI 官方推荐）
- ⚡ **并发控制**: 异步任务管理
- 🎯 **进度跟踪**: 实时进度反馈

### 3. 基础设施编排

#### 3.1 容器化架构 (`docker-compose.yml`)

```yaml
services:
  neo4j:           # 知识图谱数据库
    image: neo4j:5.21.0
    ports: ["7474:7474", "7687:7687"]
    
  qdrant:          # 向量数据库  
    image: qdrant/qdrant:latest
    ports: ["6333:6333", "6334:6334"]
    
  backend:         # FastAPI应用
    build: .
    ports: ["8000:8000"]
    depends_on: [neo4j, qdrant]
    
  frontend:        # Vue3应用
    image: node:20-bookworm-slim
    ports: ["5173:5173"]
    depends_on: [backend]
```

**部署特性**:
- **服务编排**: Docker Compose统一管理
- **数据持久化**: 数据卷挂载
- **网络隔离**: 容器间网络通信
- **环境配置**: 环境变量驱动配置
- **健康检查**: 服务健康监控

#### 3.2 依赖管理

**后端依赖** (`backend/requirements.txt`):
```
fastapi==0.115.2              # Web框架
uvicorn==0.30.6               # ASGI服务器
pydantic==2.9.2               # 数据验证
neo4j==5.23.1                 # 图数据库驱动
qdrant-client>=1.7.0          # 向量数据库客户端
langgraph                     # 工作流引擎
langchain-openai              # LLM集成
jinja2==3.1.4                 # 模板引擎
pyyaml==6.0.2                 # YAML解析
httpx==0.27.2                 # HTTP客户端
```

**前端依赖** (`frontend/package.json`):
```json
{
  "dependencies": {
    "vue": "^3.4.0",           // Vue3框架
    "vue-router": "^4.3.0",    // 路由管理
    "pinia": "^2.1.7",         // 状态管理
    "axios": "^1.7.2",         // HTTP客户端
    "cytoscape": "^3.33.1",    // 图可视化
    "js-yaml": "^4.1.0"        // YAML解析
  },
  "devDependencies": {
    "typescript": "^5.5.4",    // TypeScript
    "vite": "^5.4.0",          // 构建工具
    "vue-tsc": "^2.0.28"       // Vue类型检查
  }
}
```

## 核心技术架构

### 1. AI工程化架构

#### 1.1 LLM路由系统

```python
# LLM Router架构
class LLMRouter:
    """多Provider LLM路由器"""
    
    def __init__(self):
        self.adapters = {
            'openai': OpenAIAdapter(),
            'siliconflow': SiliconFlowAdapter(), 
            'deepseek': DeepSeekAdapter()
        }
    
    async def call(self, provider: str, model: str, **kwargs):
        """统一LLM调用接口"""
        adapter = self.adapters[provider]
        return await adapter.call(model, **kwargs)
```

**核心特性**:
- **适配器模式**: 统一多Provider接口
- **透明切换**: 配置驱动的模型选择
- **错误处理**: 重试机制和降级策略
- **负载均衡**: 请求分发和限流控制

#### 1.2 Prompt管理系统

```yaml
# Prompt YAML模板示例
agent: researcher
locale: zh
version: 2
prompt:
  system: |
    你是一个专业的教材内容研究员。
    
  user: |
    主题: {{ topic }}
    章节: {{ chapter_title }}
    小节: {{ subchapter_title }}
    
    请研究以下内容...
    
model_config:
  temperature: 0.7
  max_tokens: 2000
```

**管理特性**:
- **YAML模板**: 结构化Prompt存储
- **版本控制**: Git版本管理
- **绑定配置**: 模型参数配置
- **热更新**: 运行时动态加载
- **前端编辑**: 可视化编辑器

#### 1.3 工作流编排系统

```python
# 工作流注册系统
class WorkflowRegistry:
    """工作流注册中心"""
    
    def list_workflows(self) -> List[WorkflowMetadata]:
        """动态发现工作流"""
        return self._scan_workflow_directories()
    
    def get_workflow(self, workflow_id: str):
        """获取工作流实例"""
        return self._dynamic_import(workflow_id)

# 工作流元数据
@dataclass
class WorkflowMetadata:
    id: str
    name: str
    description: str
    input_schema: Dict[str, Any]  # JSON Schema
    ui_schema: Dict[str, Any]     # UI配置
    version: str
    tags: List[str]
```

**编排特性**:
- **动态发现**: 自动扫描工作流模块
- **Schema驱动**: JSON Schema定义输入
- **前端集成**: 动态表单生成
- **版本管理**: 工作流版本控制
- **插件化**: 可插拔工作流模块

### 2. RAG+KG双引擎架构

#### 2.1 RAG双通道检索

```python
# RAG主管线
class RAGPipeline:
    """RAG系统主管线"""
    
    async def dual_channel_retrieve(self, query: str) -> RAGResult:
        """双通道并行检索"""
        # 并行执行向量检索和KG检索
        vector_task = self.vector_retriever.search(query)
        kg_task = self.kg_retriever.search(query)
        
        vector_hits, kg_hits = await asyncio.gather(
            vector_task, kg_task
        )
        
        # 智能合并重排
        merged = self.evidence_merger.merge(vector_hits, kg_hits)
        
        # 构造RAG Prompt
        prompt = self.prompt_builder.build(query, merged)
        
        return RAGResult(
            vector_hits=vector_hits,
            kg_hits=kg_hits, 
            merged=merged,
            prompt=prompt
        )
```

**检索特性**:
- **双通道并行**: Qdrant向量 + Neo4j KG
- **智能合并**: 证据权重计算和重排
- **API化嵌入**: 硅基流动embedding服务
- **语义理解**: 向量语义召回
- **结构推理**: KG关系推理

#### 2.2 KG工程化流水线

```python
# KG 6层流水线
class KGPipeline:
    """工程化KG流水线"""
    
    def run_subchapter(self, input_data: KGInput) -> KGOutput:
        """处理单个小节"""
        # 1. Builder: LLM抽取 → JSON Schema
        raw_kg = self.builder.build_kg(input_data.content)
        
        # 2. Normalizer: 别名/词形/同义词处理
        normalized_kg = self.normalizer.normalize(raw_kg)
        
        # 3. Idempotent: 幂等ID生成与查重
        idempotent_kg = self.idempotent.process(normalized_kg)
        
        # 4. Store: Neo4j写入，唯一约束
        self.store.save(idempotent_kg)
        
        # 5. Merger: 整书级合并去重
        merged_kg = self.merger.merge_book_scope(idempotent_kg)
        
        # 6. Service: 查询API服务
        return self.service.query(merged_kg)
```

**KG特性**:
- **分层流水线**: 6层工程化处理
- **幂等机制**: content_hash去重
- **统一Book Scope**: 整书级知识图谱
- **MENTIONS桥接**: 文档-实体关联
- **实体标准化**: 同义词合并处理

### 3. 前端现代化架构

#### 3.1 Vue3组件化设计

```vue
<!-- 工作流选择器组件 -->
<template>
  <div class="workflow-selector">
    <!-- 工作流卡片 -->
    <div v-for="workflow in workflows" 
         :key="workflow.id"
         @click="selectWorkflow(workflow)">
      {{ workflow.name }}
    </div>
    
    <!-- 动态表单 -->
    <DynamicForm v-if="selectedWorkflow"
                 :schema="selectedWorkflow.input_schema"
                 v-model="formData" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { getWorkflows } from '@/services/api'

// 响应式数据
const workflows = ref<Workflow[]>([])
const selectedWorkflow = ref<Workflow | null>(null)
const formData = ref<Record<string, any>>({})

// 加载工作流
onMounted(async () => {
  workflows.value = await getWorkflows()
})
</script>
```

**前端特性**:
- **Composition API**: Vue3现代化开发模式
- **TypeScript**: 严格类型检查
- **响应式设计**: 适配多设备屏幕
- **组件复用**: 模块化组件设计
- **状态管理**: Pinia集中状态

#### 3.2 知识图谱可视化

```typescript
// 知识图谱可视化组件
import cytoscape from 'cytoscape'

export default defineComponent({
  setup() {
    const graphContainer = ref<HTMLElement>()
    let cy: cytoscape.Core
    
    const renderGraph = (nodes: Node[], edges: Edge[]) => {
      cy = cytoscape({
        container: graphContainer.value,
        elements: [
          ...nodes.map(node => ({ data: node })),
          ...edges.map(edge => ({ data: edge }))
        ],
        style: [
          {
            selector: 'node',
            style: {
              'label': 'data(name)',
              'background-color': '#409eff'
            }
          }
        ],
        layout: { name: 'force-directed' }
      })
    }
    
    return { graphContainer, renderGraph }
  }
})
```

## 配置管理架构 ✅

### 1. 分层配置系统

**✅ FastAPI 官方推荐：使用 Pydantic Settings**

本项目完全遵循 FastAPI 官方文档中关于配置管理的最佳实践：

```python
# backend/src/app/core/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field
from functools import lru_cache

# ✅ 嵌套配置模型
class ProviderSettings(BaseModel):
    base_url: Optional[str] = None
    model: str = ""
    api_keys: List[str] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 2000

class Neo4jSettings(BaseModel):
    uri: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None

class QdrantSettings(BaseModel):
    url: str = "http://qdrant:6333"
    collection: str = "kb_chunks"

class RAGSettings(BaseModel):
    base_dir: str = "knowledge_base"
    embed_model: str = "BAAI/bge-m3"
    chunk_size: int = 800
    top_k: int = 4

# ✅ 主配置类
class AppSettings(BaseSettings):
    # 基础配置
    app_name: str = "SOPilot API"
    env: str = "dev"
    debug: bool = True
    
    # LLM 配置
    default_provider: Optional[str] = None
    providers: Dict[str, ProviderSettings] = Field(default_factory=dict)
    
    # 数据库配置
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    
    # RAG 配置
    rag: RAGSettings = Field(default_factory=RAGSettings)
    
    # KG 配置
    KG_ENABLED: bool = True
    KG_LANGUAGE: Literal['zh', 'en'] = 'zh'
    KG_MIN_TERM_LEN: int = 2
    
    # ✅ 环境变量配置
    model_config = SettingsConfigDict(
        env_file=".env",                    # ✅ 从 .env 文件加载
        env_file_encoding="utf-8",          # ✅ UTF-8 编码
        env_prefix="APP_",                  # ✅ 环境变量前缀
        env_nested_delimiter="__",          # ✅ 嵌套配置：APP_NEO4J__URI
        extra="ignore"                      # ✅ 忽略额外字段
    )

# ✅ 单例模式：使用 lru_cache 缓存配置实例
@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    获取应用配置单例
    
    使用 lru_cache 确保整个应用只创建一次配置对象
    这是 FastAPI 官方推荐的配置管理模式
    """
    return AppSettings()
```

**✅ 配置特性（符合 FastAPI 官方最佳实践）**:

1. **分层配置** ✅
   - 基础配置、环境配置、业务配置完全分离
   - 使用嵌套的 Pydantic 模型组织配置

2. **环境变量优先级** ✅
   ```bash
   # .env 文件
   APP_ENV=production
   APP_DEBUG=false
   APP_DEFAULT_PROVIDER=openai
   
   # 嵌套配置
   APP_NEO4J__URI=bolt://localhost:7687
   APP_NEO4J__USER=neo4j
   APP_NEO4J__PASSWORD=password
   
   # 嵌套字典配置
   APP_PROVIDERS__OPENAI__API_KEYS='["sk-xxx","sk-yyy"]'
   ```

3. **类型安全** ✅
   - Pydantic 自动验证配置类型
   - 运行时类型检查，启动时快速失败
   - IDE 类型提示支持

4. **依赖注入友好** ✅
   ```python
   from fastapi import Depends
   from app.core.settings import get_settings, AppSettings
   
   @router.get("/config")
   async def get_config(settings: AppSettings = Depends(get_settings)):
       # ✅ 通过依赖注入获取配置
       return {"env": settings.env, "debug": settings.debug}
   ```

5. **配置验证** ✅
   ```python
   # 在应用启动时自动验证配置
   def settings_diagnostics() -> Dict[str, Any]:
       """生成配置诊断信息"""
       s = get_settings()  # ✅ 如果配置无效，这里会抛出异常
       return {
           "env": s.env,
           "default_provider": s.default_provider,
           "providers": {...}
       }
   ```

**配置加载优先级**（从高到低）：
1. 环境变量（`APP_*`）- 最高优先级
2. `.env` 文件
3. 代码中的默认值 - 最低优先级

**实际应用示例**：
```python
# 在 API 端点中使用配置
@router.post("/workflow")
async def create_workflow(
    payload: dict,
    settings: AppSettings = Depends(get_settings)  # ✅ 依赖注入
):
    # 使用配置
    provider = settings.default_provider
    neo4j_uri = settings.neo4j.uri
    # ...
```

### 2. Prompt配置管理

```yaml
# prompt_bindings.yaml
bindings:
  - target_type: agent
    target_id: researcher
    locale: zh
    prompt_file: agents/researcher.subchapter.zh.yaml
    model_ref: siliconflow:Qwen/Qwen3-Coder-30B-A3B-Instruct
    params:
      temperature: 0.7
      max_tokens: 1500
```

**Prompt管理**:
- **声明式绑定**: YAML配置文件
- **模型绑定**: 智能体-模型映射
- **参数配置**: 模型调用参数
- **多语言支持**: locale本地化
- **版本控制**: Git管理Prompt版本

## 数据存储架构

### 1. 多数据库架构

```yaml
# 数据存储分布
数据层:
  Neo4j:           # 知识图谱存储
    - 概念实体节点
    - 语义关系边
    - 文档-实体桥接
    - Book Scope查询
    
  Qdrant:          # 向量数据库
    - 文档块向量
    - 语义相似检索
    - 分块元数据
    - 实时索引更新
    
  文件系统:        # 结构化存储
    - 运行输出结果
    - Prompt模板文件
    - 配置文件
    - 日志文件
```

**存储特性**:
- **图数据库**: Neo4j存储知识图谱
- **向量数据库**: Qdrant高性能向量检索
- **文件存储**: 结构化输出管理
- **数据一致性**: 跨存储事务保证
- **备份恢复**: 数据持久化策略

### 2. 数据模型设计

#### 2.1 知识图谱模型

```cypher
// Neo4j数据模型
// 节点类型
CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT chapter_id IF NOT EXISTS FOR (c:Chapter) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

// 关系类型
(:Concept)-[:DEFINES]->(:Concept)      // 概念定义关系
(:Chapter)-[:HAS_SECTION]->(:Chapter)  // 章节结构关系
(:Chunk)-[:MENTIONS]->(:Concept)       // 文档-实体桥接
(:Document)-[:HAS_CHUNK]->(:Chunk)     // 文档分块关系
```

#### 2.2 向量存储模型

```python
# Qdrant文档块模型
class DocumentChunk:
    id: str                    # 块唯一ID
    text: str                  # 文档内容
    vector: List[float]        # 向量表示
    metadata: Dict[str, Any]   # 元数据
    
class ChunkMetadata:
    doc_name: str              # 源文档名
    chunk_index: int           # 块索引
    section_title: str         # 章节标题
    created_at: datetime       # 创建时间
    content_hash: str          # 内容哈希
```

## 最佳实践

### 1. 架构原则

1. **分层解耦**: 清晰的层次边界，避免跨层依赖
2. **依赖注入**: 接口抽象，便于测试和扩展
3. **配置驱动**: 外部化配置，环境无关部署
4. **异步优先**: 全面异步，提升并发性能
5. **类型安全**: 严格类型检查，减少运行时错误

### 2. 开发规范

1. **代码组织**: 按功能模块组织，单一职责
2. **接口设计**: RESTful API，统一响应格式
3. **错误处理**: 统一异常处理，友好错误信息
4. **文档管理**: 代码注释，API文档自动生成
5. **版本控制**: Git工作流，语义化版本

### 3. 性能优化

1. **异步编程**: async/await并发处理
2. **连接池**: 数据库连接复用
3. **缓存策略**: 热数据内存缓存
4. **分页查询**: 大数据集分页处理
5. **索引优化**: 数据库查询优化

### 4. 安全实践

1. **输入验证**: Pydantic模型验证
2. **SQL注入防护**: ORM参数化查询
3. **CORS配置**: 跨域请求控制
4. **API限流**: 防止恶意请求
5. **错误信息**: 敏感信息脱敏

## 扩展指南

### 1. 添加新工作流

1. 在 `domain/workflows/` 创建工作流目录
2. 实现 `graph.py` 工作流定义
3. 定义 `input_schema` 和 `ui_schema`
4. 工作流自动注册，前端动态发现

### 2. 集成新LLM Provider

1. 在 `infrastructure/llm/router/adapters/` 创建适配器
2. 实现 `BaseLLMAdapter` 接口
3. 在配置中添加Provider配置
4. 路由器自动发现新Provider

### 3. 扩展RAG检索

1. 实现新的检索器接口
2. 在 `retrievers/` 目录添加实现
3. 在RAG管线中注册检索器
4. 配置检索权重和参数

### 4. 添加新数据源

1. 实现存储接口抽象
2. 在对应存储目录添加实现
3. 更新配置管理支持新存储
4. 测试数据迁移和备份

## FastAPI 最佳实践总结 ✅

本项目严格遵循 FastAPI 官方文档推荐的最佳实践，以下是实现细节：

### 1. 项目结构 ✅

**✅ 采用多文件模块化结构**（符合 FastAPI 官方推荐）

```
backend/src/app/
├── main.py                 # ✅ 应用入口和工厂函数
├── asgi.py                 # ✅ ASGI 应用导出
├── api/                    # ✅ API 层
│   └── v1/                 # ✅ API 版本管理
│       ├── router.py       # ✅ 路由聚合器
│       ├── runs.py         # ✅ 按功能模块组织
│       ├── workflows.py
│       └── ...
├── core/                   # ✅ 核心功能
│   ├── settings.py         # ✅ Pydantic Settings 配置
│   ├── lifecycle.py        # ✅ 生命周期管理
│   └── logging.py
├── domain/                 # 🎯 领域模型（DDD）
├── infrastructure/         # 🎯 基础设施层
└── services/              # 🎯 服务层
```

### 2. 配置管理 ✅

**✅ 使用 Pydantic Settings**（FastAPI 官方推荐）

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_"
    )

@lru_cache(maxsize=1)  # ✅ 单例模式
def get_settings() -> AppSettings:
    return AppSettings()
```

### 3. 路由组织 ✅

**✅ 使用 APIRouter 模块化路由**

```python
# ✅ 子路由模块
router = APIRouter(prefix="/workflows")

@router.get("")
async def get_workflows(): ...

# ✅ 主路由聚合
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(workflows_router, tags=["workflows"])
```

### 4. 异步编程 ✅

**✅ 全面使用 async/await**

```python
# ✅ 异步端点
@router.get("/workflows")
async def get_workflows():
    workflows = list_workflows()
    return workflows

# ✅ 异步数据库操作
async def query_database():
    async with database.session() as session:
        result = await session.execute(query)
        return result
```

### 5. 依赖注入 ✅

**✅ 使用 Depends() 实现依赖注入**

```python
from fastapi import Depends

# ✅ 配置依赖注入
@router.get("/config")
async def get_config(
    settings: AppSettings = Depends(get_settings)
):
    return {"env": settings.env}

# ✅ 可复用的依赖
async def get_current_user(token: str = Depends(oauth2_scheme)):
    # 验证逻辑
    return user
```

### 6. 请求/响应模型 ✅

**✅ 使用 Pydantic 模型验证**

```python
from pydantic import BaseModel

class WorkflowCreate(BaseModel):
    name: str
    description: str

@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(workflow: WorkflowCreate):
    # ✅ 自动验证和序列化
    return created_workflow
```

### 7. 生命周期管理 ✅

**✅ 使用 lifespan 上下文管理器**（FastAPI 官方推荐）

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动阶段：初始化资源
    await init_database()
    
    yield  # 应用运行期间
    
    # 关闭阶段：清理资源
    await close_database()

# 在创建应用时传入 lifespan
app = FastAPI(lifespan=lifespan)
```

### 8. 中间件 ✅

**✅ 使用 FastAPI 中间件**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 9. 异常处理 ✅

**✅ 使用 HTTPException**

```python
from fastapi import HTTPException

@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    workflow = find_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_id} not found"
        )
    return workflow
```

### 10. OpenAPI 文档 ✅

**✅ 自动生成 API 文档**

```python
app = FastAPI(
    title="SOPilot API",           # ✅ API 标题
    version="0.1.0",                # ✅ API 版本
    description="AI教材生成平台",    # ✅ API 描述
)

@router.get("/workflows", summary="获取工作流列表")
async def get_workflows():
    """
    获取所有可用的工作流列表
    
    Returns:
        工作流元数据列表
    """
    # ✅ 文档字符串会显示在 OpenAPI 文档中
```

### 实践对照表

| FastAPI 最佳实践 | 项目实现 | 位置 | 状态 |
|----------------|---------|------|-----|
| 多文件模块化结构 | ✅ | `backend/src/app/` | ✅ 完全符合 |
| Pydantic Settings | ✅ | `core/settings.py` | ✅ 完全符合 |
| APIRouter 路由组织 | ✅ | `api/v1/router.py` | ✅ 完全符合 |
| async/await 异步 | ✅ | 所有 API 端点 | ✅ 完全符合 |
| Depends() 依赖注入 | ✅ | 配置、服务注入 | ✅ 完全符合 |
| Pydantic 模型验证 | ✅ | `domain/schemas/` | ✅ 完全符合 |
| lifespan 上下文管理器 | ✅ | `core/lifecycle.py` | ✅ 完全符合 |
| CORS 中间件 | ✅ | `main.py` | ✅ 完全符合 |
| HTTPException | ✅ | 所有 API 模块 | ✅ 完全符合 |
| OpenAPI 自动文档 | ✅ | `/docs`, `/redoc` | ✅ 完全符合 |

### 参考资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [FastAPI 项目结构最佳实践](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Pydantic Settings 文档](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [FastAPI 依赖注入](https://fastapi.tiangolo.com/tutorial/dependencies/)

---

## 总结

SOPilot 采用现代化的分层架构设计，通过模块化、可插拔的组件实现了一个完整的 AI 教材生成平台。系统具备以下核心优势：

### 技术优势

1. **✅ FastAPI 最佳实践**: 完全遵循 FastAPI 官方推荐的项目结构和开发模式
2. **🎯 架构清晰性**: 分层设计（API → Service → Domain → Infrastructure），职责分离
3. **⚡ 性能优化**: 全异步处理、连接池、缓存策略
4. **🔒 类型安全**: Pydantic 模型全面验证，运行时类型检查
5. **📦 模块化设计**: 可插拔组件，支持功能扩展

### 核心特性

- **技术先进性**: FastAPI + Vue3 + RAG + KG 现代技术栈
- **工程化**: 完整的开发工具链和部署流程
- **扩展性**: 插件化架构，工作流动态注册
- **可维护性**: 清晰的代码组织，完善的文档
- **产品化**: 用户友好的界面和完整的功能覆盖

该架构为 AI 教材生成领域提供了一个可扩展、可维护的工程化解决方案，支持快速迭代和功能扩展。

---

**文档维护者**: SOPilot Team  
**最后更新**: 2025-10-23  
**文档版本**: 1.0

