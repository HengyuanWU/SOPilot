# 知识图谱实现总结

## 概述

本次实现严格按照 `IMPROOVE_GUIDE.md` 规范，完成了知识图谱（KG）功能的端到端实现。

## 实现清单

### 1. 依赖管理
- ✅ 添加 Python 依赖：`neomodel==5.0.1`, `spacy==3.7.4`, `rapidfuzz==3.9.6`, `numpy==1.26.4`
- ✅ 更新 `backend/requirements.txt`

### 2. 配置管理
- ✅ 更新 `backend/src/app/core/settings.py`
  - 添加 KG_* 配置项（MIN_TERM_LEN, RE_MIN_CONF, LINK_MIN_SIM, TX_BATCH_SIZE等）
  - 添加 NEO4J_* 配置项（BOLT_URL, USE_APOC）

### 3. 基础设施层
- ✅ `backend/src/app/infrastructure/graph_store/neomodel_conn.py`
  - Neo4j 连接初始化
- ✅ `backend/src/app/infrastructure/graph_store/schema.py`
  - Schema 约束和索引安装
- ✅ `backend/src/app/infrastructure/graph_store/neomodel_store.py`
  - Neo4j 统一网关（Cypher执行）

### 4. 领域层
- ✅ `backend/src/app/domain/kg/models.py`
  - neomodel 模型定义（9类节点 + KGRel关系）
- ✅ `backend/src/app/domain/kg/idempotent.py`
  - ID 和 RID 生成器
- ✅ `backend/src/app/domain/kg/normalizer.py`
  - 实体名称规范化器
- ✅ `backend/src/app/domain/kg/linker.py`
  - 实体链接器（规则匹配 + 模糊匹配）
- ✅ `backend/src/app/domain/kg/builder.py`
  - NER/RE 构建器（spaCy + LLM）
- ✅ `backend/src/app/domain/kg/store.py`
  - 存储层（批量事务写入）
- ✅ `backend/src/app/domain/kg/merger.py`
  - 整书合并器（Section → Book）
- ✅ `backend/src/app/domain/kg/pipeline.py`
  - 端到端流水线（唯一入口）
- ✅ `backend/src/app/domain/kg/service.py`
  - 服务层（供 API 调用）

### 5. API 层
- ✅ 更新 `backend/src/app/api/v1/kg.py`
  - POST `/api/v1/kg/sections:build` - 构建小节图谱
  - GET `/api/v1/kg/books/{book_id}` - 查询整书图谱
  - GET `/api/v1/kg/sections/{section_id}` - 查询小节图谱

### 6. 应用生命周期
- ✅ 更新 `backend/src/app/core/lifecycle.py`
  - 集成 Neo4j 初始化和 Schema 安装

### 7. 测试
- ✅ `backend/tests/test_kg_pipeline.py`
  - 端到端测试
- ✅ `scripts/kg_smoke.ps1`
  - 冒烟测试脚本

## 架构说明

### 流水线流程
```
Section Input
    ↓
1. Builder (NER/RE)
    ↓
2. Normalizer (规范化)
    ↓
3. Linker (实体链接)
    ↓
4. IdGen (ID生成)
    ↓
5. Store (写入Neo4j)
    ↓
6. Merger (整书合并)
    ↓
Result (section_id, book_id, stats)
```

### 关键设计决策

1. **幂等性**
   - 节点ID：`concept:{slug(name)}:{md5(topic|chapter|subchapter)[:6]}`
   - 关系RID：`md5(type|source_id|target_id|scope)[:16]`

2. **双Scope设计**
   - Section Scope：小节级别图谱
   - Book Scope：整书级别图谱（聚合）

3. **批量事务**
   - 默认批次大小：256
   - 写入顺序：删除旧边 → MERGE节点 → MERGE关系

4. **NER/RE策略**
   - NER：本地 spaCy（zh_core_web_sm）
   - RE：句级 LLM 调用（受控 JSON）
   - 关系类型枚举：DEFINES, EXPLAINS, REQUIRES, SIMILAR_TO, CONTRASTS_WITH, IMPLEMENTS, PART_OF

5. **实体链接**
   - 优先级：完全匹配 → 别名匹配 → 模糊匹配（rapidfuzz）
   - 预留：语义匹配（Embedding API）

## 使用说明

### 1. 环境准备
```bash
# 安装依赖
pip install -r backend/requirements.txt

# 下载 spaCy 中文模型（可选）
python -m spacy download zh_core_web_sm

# 启动 Neo4j
docker run -d \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

### 2. 配置环境变量
```bash
export NEO4J_BOLT_URL="bolt://neo4j:password@localhost:7687"
export KG_MIN_TERM_LEN=2
export KG_RE_MIN_CONF=0.7
export KG_LINK_MIN_SIM=0.8
export KG_TX_BATCH_SIZE=256
```

### 3. 启动应用
```bash
cd backend
python -m app.main
```

### 4. 运行冒烟测试
```powershell
.\scripts\kg_smoke.ps1
```

### 5. API 调用示例
```bash
# 构建小节图谱
curl -X POST http://localhost:8000/api/v1/kg/sections:build \
  -H "Content-Type: application/json" \
  -d '{
    "section_id": "sec_001",
    "book_topic": "大型语言模型",
    "chapter_title": "RAG基础",
    "subchapter_title": "向量检索",
    "chunks": [
      {"id": "p1", "text": "向量检索是RAG的关键组成。"},
      {"id": "p2", "text": "RAG依赖于检索。"}
    ]
  }'

# 查询整书图谱
curl http://localhost:8000/api/v1/kg/books/book:topic:hash

# 查询小节图谱
curl http://localhost:8000/api/v1/kg/sections/sec_001
```

## 已知限制与待完善

1. **NER/RE 集成**
   - 当前 RE 使用模拟数据，需集成实际 LLM 服务
   - spaCy 模型可能需要根据领域数据微调

2. **实体链接**
   - 语义匹配（Embedding API）待实现
   - 需要集成 SiliconFlow 或其他 Embedding 服务

3. **性能优化**
   - 批量大小可根据实际负载调优
   - 考虑引入缓存机制

4. **错误处理**
   - 完善事务回滚机制
   - 增加重试逻辑（指数退避）

## 遵循的规范

- ✅ 文件目录结构严格按照 `IMPROOVE_GUIDE.md` 第1节
- ✅ 配置项命名严格按照第2节
- ✅ Neo4j Schema 严格按照第4节
- ✅ 流水线流程严格按照第5节
- ✅ API 合同严格按照第7节
- ✅ 测试要求严格按照第9节

## 变更控制

任何对本实现的修改必须：
1. 遵循 `IMPROOVE_GUIDE.md` 规范
2. 通过端到端测试
3. 通过冒烟测试
4. 更新本文档

## 参考文档

- `docs/IMPROOVE_GUIDE.md` - 知识图谱实现规范（主要依据）
- `docs/真·Neo4j 教材 → 知识图谱.md` - Neo4j 技术教材
- `docs/KG_404_ISSUE_DIAGNOSIS.md` - 问题诊断文档










