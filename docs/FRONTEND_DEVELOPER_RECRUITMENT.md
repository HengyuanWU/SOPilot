# SOPilot 前端开发人员招募文档

这是个前后端+向量数据库的项目。包使用的技术包括Langgraph、RAG、知识图谱、Neo4j、FastAPI、VUE等。
前置知识点：RAG、知识图谱

功能是
1. 多智能体协作生成教材
2. 基于教材的问答

idea来自蔚来某面试官的“如何设计智能体对销售员工进行考核”，中基集团的“内部系统的操作手册问答bot”，以及招聘网站用“大模型应用”、“Agent”为关键词搜出来的那些岗位的JD。

总体设想是
1. 用户可以在前端上传文档作为知识库，文档就是“企业的基本信息”或者是“某某维修手册”（现在还没有文档，后续去闲鱼找一份）。
2. 工作流中的多个节点协作生成“培训材料”（教材），生成教材时，智能体会利用RAG先阅读并参考本地文档。工作流中的每个节点就是一个智能体，可以编写prompt，工作流workflow安排它们的协作方式。前端可以编辑每个智能体的prompt。
3. 生成的教材以及知识库都会被解析并生成知识图谱存在Neo4j数据库中。
4. 问答对话功能。用户在前端与bot对话，bot收到提问，会根据知识库、知识图谱、“教材”这些东西做出回答。问答界面由前端实现。
---
>以下内容由Cursor生成
## 项目概述

SOPilot 是一个基于多智能体协作的智能教材生成平台，通过7个专业化智能体（规划、研究、写作、验证、QA生成、知识图谱构建、内容合并）的协同工作，自动生成高质量的培训内容并构建结构化知识图谱。

**项目愿景：** 成为培训内容自动化的标杆平台，支持多语言、多学科、多工作流的内容生成，并具备强大的知识图谱可视化和交互能力。

## 技术栈总览

### 前端技术栈（当前实现）

**核心框架：**
- **Vue 3.4.0** - 组合式API，响应式框架
- **TypeScript 5.5.4** - 类型安全的JavaScript超集
- **Vite 5.4.0** - 下一代前端构建工具，支持HMR

**状态管理与路由：**
- **Pinia 2.1.7** - Vue状态管理，替代Vuex
- **Vue Router 4.3.0** - 官方路由解决方案

**UI与可视化：**
- **Cytoscape 3.33.1** - 专业图可视化库，用于知识图谱展示
- **原生CSS** - 自定义样式系统，支持暗色主题

**HTTP客户端：**
- **Axios 1.7.2** - Promise-based HTTP客户端

**工具库：**
- **js-yaml 4.1.0** - YAML文件解析和编辑

### 后端技术栈（协作接口）

**Web框架：**
- **FastAPI 0.115.2** - 现代化Python Web框架
- **Uvicorn 0.30.6** - ASGI服务器

**AI与工作流：**
- **LangGraph** - 多智能体工作流编排引擎
- **LangChain Core** - LLM抽象层
- **Neo4j 5.23.1** - 图数据库

**数据验证：**
- **Pydantic 2.9.2** - 数据验证和序列化

## 项目架构与前后端协作

### 整体架构图

```mermaid
flowchart TB
    subgraph "前端层 (Vue3 + TypeScript)"
        A[Home.vue<br/>工作流选择] 
        B[RunDetail.vue<br/>运行监控]
        C[PromptStudio.vue<br/>Prompt管理]
        D[KgGraph.vue<br/>图谱可视化]
        E[RunConsole.vue<br/>日志控制台]
    end
    
    subgraph "API层 (FastAPI)"
        F[/api/v1/runs<br/>运行管理]
        G[/api/v1/kg<br/>知识图谱]
        H[/api/v1/prompts<br/>Prompt管理]
        I[/api/v1/workflows<br/>工作流管理]
    end
    
    subgraph "业务层"
        J[多智能体工作流<br/>LangGraph]
        K[知识图谱构建<br/>Neo4j]
        L[Prompt管理<br/>YAML + Git]
    end
    
    A --> F
    B --> F
    B --> G
    C --> H
    D --> G
    E --> F
    
    F --> J
    G --> K
    H --> L
    I --> J
```

### 前后端协作模式

**1. RESTful API 通信**
- 前端通过 Axios 发送 HTTP 请求
- 后端返回 JSON 格式数据
- 统一的错误处理和状态码

**2. 实时数据流**
- 使用 EventSource 实现 Server-Sent Events (SSE)
- 实时推送工作流执行进度和日志
- 支持自动重连和错误恢复

**3. 静态资源托管**
- 后端 FastAPI 托管前端构建产物
- 支持 SPA 路由回退
- 开发环境前后端分离，生产环境一体化部署

## 前端项目结构详解

### 目录结构

```
frontend/
├── src/
│   ├── main.ts                 # 应用入口
│   ├── App.vue                 # 根组件
│   ├── app.css                 # 全局样式
│   ├── router/
│   │   └── index.ts           # 路由配置
│   ├── store/
│   │   └── runs.ts            # Pinia状态管理
│   ├── services/
│   │   └── api.ts             # API服务封装
│   ├── views/                 # 页面组件
│   │   ├── Home.vue           # 首页-工作流选择
│   │   ├── RunDetail.vue      # 运行详情页
│   │   └── PromptStudio.vue   # Prompt管理页
│   └── components/            # 通用组件
│       ├── KgGraph.vue        # 知识图谱可视化
│       └── RunConsole.vue     # 运行日志控制台
├── package.json               # 依赖配置
├── vite.config.ts            # Vite配置
└── tsconfig.json             # TypeScript配置
```

### 核心页面功能

#### 1. Home.vue - 工作流选择与运行创建

**功能特性：**
- 动态工作流选择器（卡片式布局）
- 基于 JSON Schema 的动态表单渲染
- 支持多种输入类型：文本、数字、选择框、文本域
- 实时表单验证和错误提示

**技术实现：**
```typescript
// 动态表单渲染
<div v-for="(field, key) in workflowFields" :key="key" class="form-group">
  <label>{{ field.title || key }}</label>
  
  <!-- 文本输入 -->
  <input 
    v-if="field.type === 'string' && !field.enum"
    v-model="formData[key]"
    :placeholder="field.ui_placeholder"
    :required="isRequired(String(key))"
  />
  
  <!-- 选择框 -->
  <select v-else-if="field.enum" v-model="formData[key]">
    <option v-for="option in field.enum" :key="option" :value="option">
      {{ option }}
    </option>
  </select>
</div>
```

#### 2. RunDetail.vue - 运行监控与结果展示

**功能特性：**
- 实时工作流执行状态监控
- 多标签页布局：内容、知识图谱、日志、产物下载
- 支持整本书和小节级知识图谱切换
- 实时日志流显示

**技术实现：**
```typescript
// 实时状态监控
const watchStream = (id: string) => {
  const es = openRunStream(id)
  es.addEventListener('log', (e: MessageEvent) => {
    logs.value.push(e.data)
  })
  es.addEventListener('progress', (e: MessageEvent) => {
    const progress = JSON.parse(e.data)
    updateProgress(progress)
  })
}
```

#### 3. PromptStudio.vue - Prompt管理与编辑

**功能特性：**
- 三栏布局：Prompt列表、编辑器、预览区
- 支持表单编辑和YAML直接编辑
- 实时预览和变量校验
- Git版本管理和回滚功能

**技术实现：**
```typescript
// 编辑模式切换
const editMode = ref<'form' | 'yaml'>('form')

// 表单编辑
<div v-if="editMode === 'form'" class="form-editor">
  <div class="form-section">
    <label>Agent</label>
    <input v-model="editingPrompt.agent" type="text" readonly>
  </div>
  <!-- 更多表单字段 -->
</div>

// YAML编辑
<div v-else class="yaml-editor">
  <textarea v-model="yamlContent" class="yaml-textarea"></textarea>
</div>
```

#### 4. KgGraph.vue - 知识图谱可视化

**功能特性：**
- 基于 Cytoscape.js 的交互式图谱展示
- 支持多种节点类型和关系类型
- 自动布局算法（cose、cola等）
- 节点/边的点击交互和详情展示

**技术实现：**
```typescript
// Cytoscape 初始化
const initCytoscape = () => {
  cy = cytoscape({
    container: graphContainer.value,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#0074D9',
          'label': 'data(label)',
          'text-valign': 'center',
          'color': '#fff'
        }
      },
      {
        selector: 'node[type="concept"]',
        style: { 'background-color': '#FF851B' }
      }
    ],
    layout: {
      name: 'cose',
      idealEdgeLength: 100,
      nodeOverlap: 20
    }
  })
}
```

### 状态管理架构

#### Pinia Store 设计

```typescript
// store/runs.ts
export const useRunsStore = defineStore('runs', {
  state: (): RunState => ({
    currentId: null,
    status: null,
    logs: []
  }),
  
  actions: {
    async createRun(payload: RunCreate) {
      const created = await postRun(payload)
      this.currentId = created.id
      this.watchStream(created.id)
      return created
    },
    
    watchStream(id: string) {
      const es = openRunStream(id)
      es.addEventListener('log', (e: MessageEvent) => {
        this.logs.push(e.data)
      })
    }
  }
})
```

### API 服务层设计

#### 统一的 API 接口

```typescript
// services/api.ts
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
})

// 运行管理
export const postRun = async (payload: RunCreate) => {
  const { data } = await api.post<RunCreated>('/api/v1/runs', payload)
  return data
}

// 知识图谱
export const getKnowledgeGraph = async (bookId?: string, sectionId?: string) => {
  if (bookId) return await getKgBook(bookId)
  if (sectionId) return await getKgSection(sectionId)
  throw new Error('Neither bookId nor sectionId provided')
}

// 工作流管理
export const getWorkflows = async (): Promise<WorkflowMetadata[]> => {
  const { data } = await api.get<WorkflowMetadata[]>('/api/v1/workflows')
  return data
}
```

## 后端 API 接口详解

### 核心 API 端点

#### 1. 运行管理 API (`/api/v1/runs`)

```typescript
// 创建运行
POST /api/v1/runs
{
  "topic": "大型语言模型与知识图谱",
  "language": "中文", 
  "chapter_count": 3,
  "workflow_id": "textbook",
  "workflow_params": {}
}

// 获取运行状态
GET /api/v1/runs/{run_id}
Response: {
  "id": "run_12345678",
  "status": "completed",
  "result": {
    "final_content": "...",
    "section_ids": ["section_1", "section_2"],
    "book_id": "book:python_basics:12345678"
  }
}

// 实时事件流
GET /api/v1/runs/{run_id}/stream
Response: text/event-stream
```

#### 2. 知识图谱 API (`/api/v1/kg`)

```typescript
// 获取整本书图谱
GET /api/v1/kg/books/{book_id}
Response: {
  "nodes": [
    {
      "id": "concept_1",
      "label": "注意力机制",
      "type": "concept",
      "properties": {...}
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "concept_1",
      "target": "concept_2", 
      "label": "relates_to",
      "type": "relation"
    }
  ]
}

// 获取小节图谱
GET /api/v1/kg/sections/{section_id}
Response: 同上格式
```

#### 3. Prompt管理 API (`/api/v1/prompts`)

```typescript
// 获取Prompt列表
GET /api/v1/prompts
Response: [
  {
    "id": "planner.zh",
    "agent": "planner",
    "locale": "zh",
    "version": 1,
    "last_modified": 1640995200
  }
]

// 获取Prompt详情
GET /api/v1/prompts/{prompt_id}
Response: {
  "id": "planner.zh",
  "agent": "planner",
  "locale": "zh",
  "messages": [
    {
      "role": "system",
      "content": "你是一位专业的教材规划专家..."
    }
  ],
  "meta": {
    "temperature": 0.7,
    "max_tokens": 2000
  }
}

// 更新Prompt
PUT /api/v1/prompts/{prompt_id}
Body: PromptContent
```

#### 4. 工作流管理 API (`/api/v1/workflows`)

```typescript
// 获取工作流列表
GET /api/v1/workflows
Response: [
  {
    "id": "textbook",
    "name": "教材生成工作流",
    "description": "基于多智能体协作的教材生成",
    "version": "1.0.0",
    "tags": ["education", "content-generation"],
    "input_schema": {
      "type": "object",
      "properties": {
        "topic": {"type": "string", "title": "主题"},
        "chapter_count": {"type": "integer", "minimum": 1, "maximum": 20}
      }
    }
  }
]
```

## 开发环境与工具链

### 开发环境配置

**必需环境：**
```bash
# Node.js 版本要求
node --version  # >= 20.0

# 包管理器
npm --version   # >= 10.0
# 或使用 yarn/pnpm
```

**开发命令：**
```bash
# 安装依赖
npm install

# 开发服务器
npm run dev

# 类型检查
npm run build

# 预览构建结果
npm run preview
```

### 构建与部署

**Vite 配置：**
```typescript
// vite.config.ts
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
```

**TypeScript 配置：**
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "types": ["vite/client", "node"],
    "skipLibCheck": true
  }
}
```

## 项目理想完成态

### 当前实现状态

**已完成功能：**
- ✅ 基础工作流选择和运行创建
- ✅ 实时运行状态监控和日志显示
- ✅ 知识图谱可视化（Cytoscape.js）
- ✅ Prompt Studio 基础编辑功能
- ✅ 多工作流支持框架
- ✅ 产物下载和管理

**技术债务：**
- ⚠️ 部分组件存在 .vue.js 和 .vue 重复文件
- ⚠️ 样式系统需要统一和优化
- ⚠️ 错误处理和用户体验需要完善

### 理想完成态目标

#### 1. 用户体验优化

**界面设计：**
- 现代化暗色主题设计系统
- 响应式布局，支持移动端
- 流畅的动画和交互效果
- 无障碍访问支持

**交互优化：**
- 拖拽式工作流配置
- 实时协作编辑（多人同时编辑Prompt）
- 智能提示和自动补全
- 快捷键支持

#### 2. 功能完善

**Prompt Studio 增强：**
- Monaco Editor 集成（代码高亮、智能提示）
- 版本对比和差异显示
- 批量操作和模板管理
- A/B测试支持

**知识图谱增强：**
- 3D图谱可视化
- 图谱搜索和过滤
- 节点详情面板
- 图谱导出功能

**工作流管理：**
- 可视化工作流编辑器
- 工作流模板市场
- 性能监控和分析
- 自定义节点开发

#### 3. 技术架构升级

**前端架构：**
- 微前端架构支持
- 组件库建设
- 状态管理优化
- 性能监控集成

**开发体验：**
- 完整的测试覆盖
- 自动化CI/CD
- 代码质量检查
- 文档自动生成

## 前端开发人员职责

### 核心职责

1. **Vue3 + TypeScript 开发**
   - 使用组合式API开发可复用组件
   - 严格的TypeScript类型定义
   - 响应式数据流管理

2. **知识图谱可视化**
   - Cytoscape.js 深度定制
   - 自定义布局算法
   - 交互式图谱操作

3. **实时数据流处理**
   - EventSource 集成
   - 状态同步和缓存
   - 错误恢复机制

4. **Prompt管理界面**
   - 富文本编辑器集成
   - 版本控制系统
   - 实时预览功能

### 技术要求

**必备技能：**
- Vue 3 + TypeScript 熟练使用
- 现代前端构建工具（Vite/Webpack）
- 状态管理（Pinia/Vuex）
- HTTP客户端和API集成
- CSS3 和响应式设计

**加分技能：**
- 图可视化库（Cytoscape.js/D3.js）
- 富文本编辑器（Monaco/CodeMirror）
- 实时通信（WebSocket/SSE）
- 微前端架构
- 测试框架（Vitest/Jest）

### 工作内容

**短期任务（1-2个月）：**
1. 完善现有组件的TypeScript类型定义
2. 优化知识图谱可视化交互
3. 实现Prompt Studio的高级编辑功能
4. 完善错误处理和用户反馈

**中期任务（3-6个月）：**
1. 开发工作流可视化编辑器
2. 实现实时协作功能
3. 构建组件库和设计系统
4. 性能优化和监控

**长期任务（6个月+）：**
1. 微前端架构改造
2. 移动端适配
3. 国际化支持
4. 高级分析功能

## 项目价值与前景

### 技术价值

- **多智能体系统前端实践**：在复杂AI系统中的前端架构设计
- **图可视化技术**：大规模知识图谱的交互式展示
- **实时协作开发**：现代Web应用的实时数据流处理
- **AI工具集成**：LLM和传统Web技术的深度融合


### 个人成长

- **全栈能力**：前后端协作的深度理解
- **AI应用开发**：AI时代的前端开发技能
- **复杂系统设计**：大型项目的架构思维
- **开源贡献**：参与开源项目的经验积累

---

**我们期待有激情、有技术、有想法的前端开发人员加入SOPilot团队，共同打造下一代AI培训平台！**