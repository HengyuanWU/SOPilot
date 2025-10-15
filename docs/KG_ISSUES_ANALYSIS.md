# 知识图谱问题分析报告

## 问题总结

根据日志分析，发现以下5个核心问题：

### 1. 唯一性约束（Constraint）警告

**现象：**
```
INFO neo4j.notifications | Received notification from DBMS server: 
{severity: INFORMATION} {code: Neo.ClientNotification.Schema.IndexOrConstraintAlreadyExists} 
{title: `CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (e:Concept) REQUIRE (e.id) IS UNIQUE` has no effect.}
```

**原因：**
- 每次初始化KGStore时都会尝试创建约束
- 约束已存在，Neo4j返回INFORMATION级别通知
- 这是**正常行为**，不是错误

**影响：** 无实际影响，仅是信息提示

**建议：** 可以忽略或降低日志级别

---

### 2. 大量"跳过无效边"警告

**现象：**
```
WARNING app.domain.kg.idempotent | 跳过无效边: concept:本节:facb68 -> concept:本节内容:facb68
WARNING app.domain.kg.idempotent | 跳过无效边: concept:测试设计与方法:facb68 -> concept:本节:facb68
```

**原因分析：**

查看 `idempotent.py:170` 的逻辑：
```python
# 跳过无效的边（节点不存在）
if source_id not in node_id_map.values() or target_id not in node_id_map.values():
    self.logger.warning(f"跳过无效边: {edge.source} -> {edge.target}")
    continue
```

**根本原因：**
1. **LLM关系抽取质量问题**：LLM提取的关系中包含大量低质量边
   - 指代词关系：如"本节"、"该章"、"学生"等
   - 过于泛化的关系：如"测试" -> "软件测试过程"
   - 无实际语义的关系

2. **实体链接（Entity Linking）后节点ID映射失败**：
   - Linker将某些低质量概念合并或过滤
   - 但关系中仍引用这些被过滤的概念
   - 导致在idempotent阶段找不到对应节点ID

**影响：** 
- 损失了部分关系数据
- 但被过滤的多是低质量边，对整体KG质量影响有限

**解决方案：**
1. **短期**：优化LLM Prompt，减少低质量关系抽取
2. **中期**：在Builder阶段添加关系质量过滤
3. **长期**：训练专门的关系抽取模型

---

### 3. "0 节点"、"0 边"问题

**现象：**
```
14132: 总共读取到 0 条section边数据
14132: 整本书图谱存储完成: 0 节点, 0 边
```

**原因分析：**

查看 `book_graph_node.py` 的逻辑流程：

1. **Section级别存储成功**：
   ```
   14109: KG存储完成: {'nodes_created': 103, 'nodes_updated': 85, 'edges_created': 2, 'edges_updated': 2}
   ```
   - 每个section都成功存储了节点和边
   - 边的scope是 `section:{section_id}`

2. **Book级别读取失败**：
   ```python
   # book_graph_node.py 从每个section读取边
   for section_id in section_ids:
       section_edges = store.client.execute_cypher(query, {"scope": f"section:{section_id}"})
       logger.info(f"从section {section_id} 读取到 {len(section_edges)} 条边")
   ```
   
   但日志显示：
   ```
   14121-14131: 从section xxx 读取到 0 条边  # 11个section都是0
   ```

**根本原因：**

查询语句问题！查看 `book_graph_node.py:139-148`：

```python
query = """
    MATCH (source)-[r]->(target) 
    WHERE r.scope = $scope 
    RETURN r.type as type, source.id as source_id, target.id as target_id, 
           r.confidence as confidence, r.weight as weight, r.desc as desc,
           r.rid as old_rid, r.scope as old_scope
"""
section_edges = store.client.execute_cypher(query, {"scope": f"section:{section_id}"})
```

**问题：** 这个查询在Neo4j中可能返回空结果，原因：
1. 关系数量太少（每个section只有2-12条边）
2. 可能存储时scope格式不一致
3. 需要验证实际存储的scope值

---

### 4. 前端API返回空数据

**现象：**
```
GET http://localhost:5173/api/v1/kg/books/book:测试:18beea49
返回: {"nodes":[],"edges":[]}
```

**原因：**

这是**3号问题的直接后果**：

1. Book级别没有存储任何边（因为从section读取到0条）
2. `fetch_book_graph` 查询 `scope = "book:测试:18beea49"` 
3. Neo4j中不存在该scope的边
4. 返回空结果

**调用链：**
```
前端请求 
  -> kg.py:get_book_graph() 
  -> kg_service.py:get_book() 
  -> neo4j_store.py:fetch_book_graph()
  -> Neo4j查询 WHERE r.scope = "book:测试:18beea49"
  -> 返回 []
```

---

### 5. Scope架构混乱

**设计意图（IMPROOVE_GUIDE.md）：**
```
Section级别：scope = "section:{section_id}"  # 临时存储
Book级别：scope = "book:{book_id}"           # 最终存储
```

**实际执行流程：**
```
1. KGPipeline 处理每个section
   -> 存储边时 scope = "section:{section_id}"
   
2. book_graph_node 整书合并
   -> 从各section读取边（scope = "section:xxx"）
   -> 重新存储为book scope（scope = "book:xxx"）
   -> 但读取失败，导致没有book级别的边
   
3. 前端查询
   -> 查询 scope = "book:xxx"
   -> 找不到数据
```

**核心问题：** Section级别的边存储成功，但Book级别的转换失败

---

## 验证步骤

### 1. 验证Section级别数据是否存在

在Neo4j Browser中执行：

```cypher
// 查询所有section级别的边
MATCH ()-[r]->() 
WHERE r.scope STARTS WITH 'section:'
RETURN r.scope, count(r) as edge_count
ORDER BY edge_count DESC
LIMIT 20
```

**预期结果：** 应该能看到各个section的边数据

### 2. 验证Book级别数据是否存在

```cypher
// 查询所有book级别的边
MATCH ()-[r]->() 
WHERE r.scope STARTS WITH 'book:'
RETURN r.scope, count(r) as edge_count
```

**预期结果：** 可能为空或很少

### 3. 检查scope格式

```cypher
// 查看实际存储的scope值
MATCH ()-[r]->()
RETURN DISTINCT r.scope
LIMIT 50
```

### 4. 检查特定section的数据

```cypher
// 查询最新运行的section
MATCH ()-[r]->() 
WHERE r.scope = 'section:e7b3c4fe7550'
RETURN count(r) as edge_count
```

**预期：** 应该有4条边（根据日志 `edges_created': 2, 'edges_updated': 2`）

---

## 修复方案

### 方案A：修复book_graph_node的查询逻辑

**问题定位：** `book_graph_node.py:139-148` 的查询可能有问题

**修复步骤：**
1. 添加调试日志，打印实际查询的scope值
2. 验证查询返回的数据结构
3. 检查 `store.client.execute_cypher` 的返回格式

### 方案B：统一使用Book Scope

**更激进的方案：** 直接在section级别就使用book scope

修改 `idempotent.py:assign()` 方法：
```python
# 不使用 section_scope，直接使用 book_scope
book_id = section.get('book_id', '')
if not book_id:
    # 生成book_id
    from .ids import generate_book_id
    book_id = generate_book_id(section.get('book_topic', 'unknown'))

book_scope = f"book:{book_id}"
```

**优点：**
- 简化架构，无需book级别转换
- 避免scope转换失败问题

**缺点：**
- 失去section级别的隔离
- 重新处理section时需要删除整书数据

### 方案C：修复并优化当前流程

**推荐方案：** 保持当前架构，修复bug

1. **修复book_graph_node查询**
   - 添加详细日志
   - 验证返回数据格式
   - 确保正确解析边数据

2. **添加降级查询**
   - 如果book scope没数据，尝试聚合section scope
   - 在API层动态合并

3. **优化关系质量**
   - 改进LLM Prompt
   - 添加关系过滤规则

---

## 下一步行动

1. **立即执行：** 在Neo4j Browser中运行验证查询，确认数据存储情况
2. **短期修复：** 修复book_graph_node的查询逻辑
3. **中期优化：** 优化关系抽取质量，减少"跳过无效边"
4. **长期改进：** 考虑简化scope架构

---

## 附录：关键代码位置

- **关系抽取：** `backend/src/app/domain/kg/builder.py`
- **实体链接：** `backend/src/app/domain/kg/linker.py`
- **幂等处理：** `backend/src/app/domain/kg/idempotent.py:170`
- **Section存储：** `backend/src/app/domain/kg/store.py`
- **Book转换：** `backend/src/app/domain/workflows/textbook/nodes/book_graph_node.py:139-188`
- **查询接口：** `backend/src/app/infrastructure/graph_store/neo4j_store.py:188-249`

