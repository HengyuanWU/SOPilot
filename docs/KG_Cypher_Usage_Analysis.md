# 知识图谱 Cypher 使用情况分析报告

## 执行摘要

本报告分析了 SOPilot 项目中知识图谱（KG）部分的 Cypher 查询使用情况，重点识别哪些地方直接使用 Cypher 而不经过 neomodel ORM。

根据 IMPROOVE_GUIDE.md 规范，项目应该：
- ✅ **允许使用 Cypher**：通过 `Neo4jStore` 统一网关（`neomodel_store.py`）执行 Cypher
- ❌ **禁止直接使用**：Neo4j 原生 Driver（`driver.session()`, `session.run()`）

## 1. 符合规范的 Cypher 使用（✅ 合规）

这些文件通过 `Neo4jStore` 网关使用 Cypher，符合 IMPROOVE_GUIDE.md 第 6 节要求：

### 1.1 基础设施层
- **`neomodel_store.py`** - Neo4j 统一网关
  - `run_cypher()`: 执行单个 Cypher 查询
  - `run_tx()`: 批量事务执行
  - ✅ 使用 `neomodel.db.cypher_query()` - 符合规范

### 1.2 Schema 管理
- **`schema.py`** - Schema 约束和索引安装
  - 第 49, 60, 109 行：使用 `db.cypher_query()` 创建约束和索引
  - ✅ 场景合理：Schema DDL 必须使用 Cypher

### 1.3 领域层 - KG 核心功能
- **`store.py`** - 存储层（批量写入）
  - 通过 `Neo4jStore.run_cypher()` 和 `Neo4jStore.run_tx()` 执行
  - 使用场景：
    - 删除旧边：`DELETE r WHERE r.scope = $scope`
    - 批量 MERGE 节点：`MERGE (n:Concept {id: $id})`
    - 批量 MERGE 关系：`MERGE ()-[r:DEFINES {rid: $rid}]-()`
  - ✅ 批量操作，neomodel ORM 无法高效实现

- **`merger.py`** - 整书合并器
  - 通过 `Neo4jStore.run_cypher()` 和 `Neo4jStore.run_tx()` 执行
  - 使用场景：
    - 节点去重：按 name 分组、合并元数据
    - 关系聚合：`(type, source, target)` 去重
    - 批量更新关系端点
  - ✅ 复杂聚合查询，必须使用 Cypher

## 2. 不符合规范的 Cypher 使用（❌ 待优化）

这些文件直接使用 Neo4j 原生 Driver，违反规范：

### 2.1 Neo4j 客户端（旧架构）

#### `neo4j_client.py` - 原生 Driver 实现
```python
# ❌ 问题：直接使用 GraphDatabase.driver() 和 driver.session()
self.driver = GraphDatabase.driver(uri, auth=(user, password))
with self.driver.session(database=self.database) as session:
    result = session.run(query, params or {})
```

**使用位置**：
- 第 45-46 行：连接测试
- 第 60, 77 行：`merge_node()` 方法
- 第 87, 147 行：`merge_edge()` 方法
- 第 175, 179 行：`get_section_graph()` 方法
- 第 198, 202 行：`get_book_graph()` 方法
- 第 213-215 行：`get_graph_stats()` 方法
- 第 230-231 行：`execute_cypher()` 通用方法

**影响范围**：被以下文件依赖
1. `neo4j_store.py` - 旧的 Neo4jStore 实现
2. `document_store.py` - 文档和块存储
3. `neo4j_queries.py` - KG 查询器
4. `book_graph_node.py` - 工作流节点
5. `rag.py` - RAG API

### 2.2 具体使用场景

#### A. `neo4j_store.py` - 旧 Neo4jStore 实现
```python
# ❌ 使用 Neo4jClient.execute_cypher()
result = self.client.execute_cypher(query, params or {})
```
- 第 50 行：`run_cypher()` 方法
- 第 154, 174, 217, 238 行：图查询方法

**问题**：这是一个旧的 `Neo4jStore` 实现，与新的 `neomodel_store.py` 冲突

#### B. `infrastructure/rag/kgstores/document_store.py`
```python
# ❌ 使用 Neo4jClient.execute_cypher()
result = self.client.execute_cypher(cypher, params)
```
- 第 64 行：`create_document_node()`
- 第 114 行：`create_chunk_node()`
- 第 146 行：`create_has_chunk_relation()`
- 第 194 行：`create_mentions_relation()`
- 第 230 行：`get_document_chunks()`
- 第 259 行：`get_chunk_entities()`
- 第 292 行：`search_related_chunks()`

**影响**：文档和块的知识图谱管理完全绕过 neomodel

#### C. `infrastructure/rag/kgstores/neo4j_queries.py`
```python
# ❌ 使用 Neo4jClient.execute_cypher()
records = self._client.execute_cypher(cypher, params)
```
- 第 121 行：`search_entities()`
- 第 180 行：`find_paths()`
- 第 260 行：`get_subgraph()`
- 第 331 行：`get_entity_context()`
- 第 396 行：`health_check()`

**影响**：KG 检索查询完全绕过 neomodel

#### D. `domain/workflows/textbook/nodes/book_graph_node.py`
```python
# ❌ 使用 Neo4jClient.execute_cypher()
result = query_client.execute_cypher(query, {"scope": section_scope})
```
- 第 138 行：图谱查询节点

#### E. `api/v1/rag.py`
```python
# ❌ 使用 Neo4jClient.execute_cypher()
result = rag_pipeline.neo4j_queries._client.execute_cypher(stats_query)
```
- 第 587 行：获取图统计信息

## 3. 架构问题分析

### 3.1 双轨并行问题

项目中存在**两套 Neo4j 访问机制**：

#### ✅ **新架构（符合规范）**
```
neomodel_conn.py (连接初始化)
    ↓
neomodel_store.py (统一网关)
    ↓ 使用 neomodel.db
store.py, merger.py (领域层)
```

#### ❌ **旧架构（不符合规范）**
```
neo4j_client.py (原生 Driver)
    ↓
neo4j_store.py, document_store.py, neo4j_queries.py
    ↓ 使用 driver.session()
各个业务层
```

### 3.2 命名冲突

存在两个 `Neo4jStore` 类：
1. ✅ `infrastructure/graph_store/neomodel_store.py::Neo4jStore` - 新的符合规范的实现
2. ❌ `infrastructure/graph_store/neo4j_store.py::Neo4jStore` - 旧的使用 Neo4jClient 的实现

## 4. 优化建议

### 4.1 立即行动（高优先级）

#### 方案 A：渐进式迁移（推荐）
1. **保留 `neo4j_client.py`**（暂时）
2. **修改 `neo4j_client.py` 内部实现**
   ```python
   # 将所有 driver.session() 改为使用 neomodel.db
   from neomodel import db
   
   def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None):
       results, meta = db.cypher_query(query, params or {})
       # 转换为原有返回格式
       return self._format_results(results, meta)
   ```
3. **优点**：
   - 最小化改动
   - 保持 API 兼容性
   - 逐步迁移到 neomodel

#### 方案 B：完全重构（彻底）
1. **删除文件**：
   - `neo4j_client.py`
   - `neo4j_store.py`（旧版）
2. **统一使用** `neomodel_store.py`
3. **修改所有依赖**：
   - `document_store.py` → 使用 `Neo4jStore.run_cypher()`
   - `neo4j_queries.py` → 使用 `Neo4jStore.run_cypher()`
   - 其他所有依赖文件

### 4.2 中期优化

1. **文档和块管理迁移到 neomodel 模型**
   - 在 `domain/kg/models.py` 中已定义 `Doc` 和 `Chunk` 模型
   - 修改 `document_store.py` 使用这些模型

2. **查询层统一**
   - `neo4j_queries.py` 应该基于 `neomodel_store.py`
   - 考虑是否可以使用 neomodel 的查询 API

### 4.3 长期规划

1. **完全移除原生 Driver 依赖**
2. **所有 Cypher 查询通过 `Neo4jStore` 网关**
3. **复杂查询封装为领域服务**

## 5. 风险评估

### 5.1 当前风险

| 风险项 | 影响 | 概率 | 缓解措施 |
|--------|------|------|----------|
| 连接池竞争 | 高 | 中 | 两套机制可能导致连接冲突 |
| 数据不一致 | 中 | 低 | 不同机制可能看到不同的事务状态 |
| 维护困难 | 高 | 高 | 需要维护两套实现 |
| 性能问题 | 中 | 低 | 双重连接池开销 |

### 5.2 迁移风险

| 风险项 | 影响 | 缓解措施 |
|--------|------|----------|
| API 破坏 | 高 | 使用适配器模式保持兼容 |
| 功能回归 | 中 | 全面测试覆盖 |
| 性能下降 | 低 | neomodel 性能通常可接受 |

## 6. 实施路线图

### 阶段 1：统一底层（1-2 天）
- [ ] 修改 `neo4j_client.py` 内部使用 neomodel
- [ ] 确保所有现有功能正常工作
- [ ] 添加集成测试

### 阶段 2：迁移 RAG 模块（2-3 天）
- [ ] 修改 `document_store.py` 使用 neomodel 模型
- [ ] 修改 `neo4j_queries.py` 基于 `Neo4jStore`
- [ ] 更新相关测试

### 阶段 3：清理旧代码（1 天）
- [ ] 删除 `neo4j_store.py`（旧版）
- [ ] 可选：删除 `neo4j_client.py`（如果所有依赖已迁移）
- [ ] 更新文档

### 阶段 4：验证和优化（1-2 天）
- [ ] 端到端测试
- [ ] 性能基准测试
- [ ] 代码审查

## 7. 总结

### 当前状态
- ✅ **KG 核心功能**（store.py, merger.py）：符合规范，通过 `Neo4jStore` 网关
- ❌ **RAG 相关功能**（document_store.py, neo4j_queries.py）：不符合规范，使用原生 Driver
- ❌ **基础设施冲突**：存在两套 Neo4j 访问机制

### 推荐行动
1. **立即**：采用方案 A（渐进式迁移），修改 `neo4j_client.py` 内部实现
2. **短期**：迁移 RAG 模块到 neomodel
3. **中期**：完全移除原生 Driver 依赖

### 预期收益
- 统一技术栈，降低维护成本
- 消除潜在的连接池竞争问题
- 更好的类型安全和代码可读性
- 符合项目架构规范

---

**生成时间**：2025-10-15  
**分析范围**：`backend/src/app/` 下所有 Python 文件  
**规范依据**：`docs/IMPROOVE_GUIDE.md` 第 6 节

