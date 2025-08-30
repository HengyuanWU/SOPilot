# Agent_Edu_Forge - 教育智能体平台

一个现代化的教育智能体平台，支持多种教育应用。目前实现了基于多Agent协作的智能教材生成系统，能够自动生成高质量的教科书内容。

# Agent_Edu_Forge - 教育智能体平台

一个现代化的教育智能体平台，支持多种教育应用。目前实现了基于多Agent协作的智能教材生成系统，能够自动生成高质量的教科书内容。

## 🏗️ 平台化架构设计

基于分层模块化设计（重构后目录）：

```
SOPilot/
├── backend/
│   ├── src/app/
│   │   ├── core/                  # settings/lifecycle/logging/progress_manager/concurrency
│   │   ├── api/v1/                # runs/kg 路由
│   │   ├── services/              # workflow_service/kg_service
│   │   ├── domain/                # workflows/agents/kg/state/schemas/merger（纯领域）
│   │   ├── infrastructure/        # llm/*, graph_store/*
│   │   ├── main.py                # 应用装配（含前端静态托管）
│   │   └── asgi.py                # ASGI 入口
│   ├── requirements.txt
│   └── .env(.example)
├── frontend/                      # Vue3 + Vite
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig*.json
│   └── src/
│       ├── main.ts
│       ├── router/index.ts
│       ├── store/runs.ts
│       ├── services/api.ts
│       ├── views/{Home.vue, RunDetail.vue}
│       └── components/{RunConsole.vue, KgGraph.vue}
├── Dockerfile                     # 多阶段：前端构建 + 后端运行
├── docker-compose.yml             # backend/frontend/neo4j 服务（挂载 ./output → /app/output）
└── scripts/dev.ps1                # 本地一键启动
```

## 🎯 设计原则

- **可扩展性**: 教材生成只是平台中的一个应用，未来可添加课程生成、评估等应用
- **单一职责**: 工作流只负责编排，算法逻辑收敛到独立模块  
- **面向接口**: 域接口稳定，具体实现可替换（内存/Neo4j、不同LLM提供商）
- **可测试性**: 模块边界清晰，核心逻辑以纯函数/接口为主
- **安全序列化**: 避免将驱动/非序列化对象放入工作流状态
- **配置中心化**: 统一配置管理，支持环境变量覆盖

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置（后端 .env）

后端配置统一由 `backend/.env` 与环境变量提供（前缀 `APP_`，嵌套 `__`）：

```dotenv
# 真实/模拟
APP_USE_REAL_WORKFLOW=true

# LLM Provider（示例：siliconflow）
APP_DEFAULT_PROVIDER=siliconflow
APP_PROVIDERS__siliconflow__BASE_URL=https://api.siliconflow.cn/v1
APP_PROVIDERS__siliconflow__MODEL=Qwen/Qwen3-Coder-30B-A3B-Instruct
APP_PROVIDERS__siliconflow__API_KEYS=["你的SiliconFlowKey"]

# Neo4j（容器示例）
APP_NEO4J__URI=bolt://neo4j:7687
APP_NEO4J__USER=neo4j
APP_NEO4J__PASSWORD=test1234
APP_NEO4J__DATABASE=neo4j

# 运行产物落盘目录（容器内默认 /app/output；Compose 已映射 ./output）
APP_OUTPUT_DIR=/app/output
```

### 3. 启动

容器化（推荐）：

```bash
docker compose up -d --build
```

本地开发：

```powershell
pwsh -File scripts/dev.ps1
```

## 📊 知识图谱集成

支持 **Neo4j** 知识图谱存储，提供：

- **结构化存储**: 节点（概念/算法/实体）和边（关系）
- **幂等写入**: 基于 `section_id` 和 `content_hash` 的增量更新
- **评估分析**: 图结构分析、关系统计、知识覆盖度评估
- **替换模式**: 按章节替换，确保数据一致性

### Neo4j 配置（可选）

```json
{
  "neo4j": {
    "uri": "bolt://localhost:7687",
    "user": "neo4j", 
    "password": "your_password",
    "database": "education"
  }
}
```

如未配置 Neo4j，系统将自动使用内存模式。

## 📝 运行产物落盘

- 落盘位置：容器内 `APP_OUTPUT_DIR`（默认 `/app/output`），已通过 Compose 映射到宿主机 `./output`。
- 目录结构：
  - `output/<run_id>/status.json`（运行状态）
  - `output/<run_id>/final.md`（最终合成内容，若存在）
  - `output/<run_id>/kg_section_ids.json`（KG section id 列表，若存在）
  - `output/<run_id>/meta.json`

示例（PowerShell）：

```powershell
$resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/runs" -Method POST -ContentType 'application/json' -Body '{"topic":"测试","language":"中文","chapter_count":3}'
$ID = $resp.id
Start-Process "http://127.0.0.1:8000/api/v1/runs/$ID/stream"
Start-Sleep -Seconds 5
Get-ChildItem -Recurse .\output\$ID
```

## ⚙️ 核心特性

### 多智能体协作
- **规划智能体**: 生成教材大纲和章节结构
- **研究智能体**: 节点内并发研究各子章节
- **写作智能体**: 并发生成内容，与验证智能体闭环迭代
- **验证智能体**: 统一通过阈值，可配置最大重写次数
- **QA智能体**: 对通过验证的内容即时生成问答
- **KG智能体**: 构建知识图谱，评估知识覆盖度

### 工作流引擎
- **LangGraph**: 可视化工作流编排
- **检查点**: 支持状态持久化和恢复
- **并发执行**: 节点内高效并发处理
- **错误处理**: 优雅的异常处理和重试机制

### 配置管理
- **分层配置**: 基础配置、智能体设置、并发参数分离
- **环境覆盖**: 支持环境变量覆盖配置
- **热更新**: 运行时配置更新

## 🧪 测试与质量保证

```bash
# 运行单元测试
python -m pytest tests/unit/ -v

# 运行集成测试
python -m pytest tests/integration/ -v

# 完整系统测试
python -c "
from apps.textbook import TextbookApp
app = TextbookApp()
print('✅ 系统初始化成功')
"
```

## 📚 文档与示例

- **架构设计**: `docs/ARCHITECTURE_REFACTOR_PLAN.md`
- **重构进度**: `docs/ARCHITECTURE_REFACTOR_PROGRESS.md`  
- **KG集成**: `docs/KG_NEO4J_INTEGRATION_PROGRESS.md`
- **性能分析**: `docs/performance/`

## 🔧 开发与扩展

### 添加新应用

1. 在 `apps/` 下创建新应用目录
2. 实现应用入口类，继承或参考 `TextbookApp`
3. 在 `workflows/` 下定义专用工作流
4. 复用 `modules/` 中的领域模块

### 添加新模块

1. 在 `modules/` 下创建模块目录  
2. 定义清晰的接口和数据契约
3. 实现核心算法逻辑
4. 添加单元测试

### 添加新智能体

1. 在 `agents/` 下实现智能体类
2. 在 `workflows/textbook/nodes/` 下创建工作流节点
3. 更新工作流图定义

## 📈 性能优化

- **并发处理**: 子章节级别的细粒度并发
- **API负载均衡**: `utils/balancer` 统一管理多 Provider、多 Key 的轮转/熔断/恢复
- **内存优化**: 避免大对象在工作流状态中传递
- **缓存机制**: 向量存储和配置缓存
- **增量更新**: Neo4j 幂等写入和替换模式

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 提交 Pull Request

## 📄 许可证

MIT License - 详见 `LICENSE` 文件

## 🎯 路线图

- [ ] **课程生成**: 基于教材的课程设计应用
- [ ] **评估系统**: 学习效果评估应用  
- [ ] **个性化**: 基于学习者特征的内容定制
- [ ] **Web界面**: 可视化编辑和管理界面
- [ ] **API服务**: RESTful API 和微服务架构

---

**Agent_Edu_Forge** - 让AI驱动教育内容创作 🚀