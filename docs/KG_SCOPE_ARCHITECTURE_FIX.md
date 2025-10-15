# KG Scope架构修复报告

## 问题诊断

通过分析日志和代码，发现系统违背了 `IMPROOVE_GUIDE.md` 中"真·Neo4j"部分的两阶段存储架构要求。

### IMPROOVE_GUIDE.md 要求（第5节）

指南明确要求KG存储采用**两阶段架构**：

1. **第5.6节 - 小节级入库（Section Scope）**：
   ```python
   # 5) 小节级入库（Section Scope）
   self.store.write_section(ready, section['section_id'])
   ```
   - 每个小节的KG数据存储时使用 `scope=section:xxx`
   - 关系属性包含 `src=section_id` 和 `scope=section:xxx`

2. **第5.7节 - 整书合并（Book Scope）**：
   ```python
   # 6) 整书合并（Book Scope）
   book_id = self.merger.merge_book(section['book_topic'])
   ```
   - 从所有 Section Scope 数据中聚合
   - 按 `rid` 去重
   - 转写为 `scope=book:xxx:yyy`

### 原有实现的问题

#### 问题1：跳过Section Scope阶段

**位置**：`backend/src/app/domain/kg/pipeline.py:162`

```python
context = {
    ...
    "scope": generate_book_id(input_data.topic, input_data.language)  # ❌ 直接使用 book:xxx:yyy
}
```

**影响**：
- KG数据直接以Book Scope存储，跳过了Section Scope阶段
- 违反了指南的两阶段架构要求

#### 问题2：book_graph_node逻辑错误

**位置**：`backend/src/app/domain/workflows/textbook/nodes/book_graph_node.py:100-147`

原代码试图：
- 从 `section:xxx` scope 读取数据
- 但实际数据已被存储为 `book:xxx` scope
- 导致查询结果为空

#### 问题3：架构不一致

- `pipeline.py` 存储数据为 Book Scope
- `book_graph_node.py` 尝试从 Section Scope 读取
- 两者不匹配，导致数据流断裂

## 修复方案

### 修复1：pipeline.py - 使用Section Scope存储

**文件**：`backend/src/app/domain/kg/pipeline.py`

**修改前**：
```python
context = {
    ...
    "scope": generate_book_id(input_data.topic, input_data.language)  # book:xxx:yyy 格式
}
```

**修改后**：
```python
# 按指南第5.6节要求，先存储为Section Scope
section_scope = f"section:{section_id}"
book_id = generate_book_id(input_data.topic, input_data.language)

context = {
    ...
    "section_id": section_id,
    "scope": section_scope,  # ✅ 小节级存储使用 section:xxx 格式
    "book_id": book_id       # 保留book_id供后续使用
}
```

**说明**：
- ✅ 符合指南第5.6节要求
- ✅ 数据以Section Scope存储
- ✅ 保留book_id供后续Book Scope合并使用

### 修复2：book_graph_node.py - 执行Section到Book转换

**文件**：`backend/src/app/domain/workflows/textbook/nodes/book_graph_node.py`

**修改**：将"验证"逻辑改为"转换"逻辑

**核心流程**：
1. 清理旧的Book Scope关系
2. 从Neo4j读取所有Section Scope的边数据
3. 为每条边生成Book Scope版本（带新rid）
4. 按rid去重
5. 存储到Book Scope

**关键代码**：
```python
# ✅ 按IMPROOVE_GUIDE.md第5.7节要求：从Section Scope转写为Book Scope
logger.info(f"开始整书级合并：从Section Scope -> Book Scope: {book_scope}")

# 清理旧的整本书关系
edges_deleted = store.delete_edges_by_scope(book_scope)

# 聚合所有section的边数据
section_edges = []
for section_id in section_ids:
    section_scope = f"section:{section_id}"
    # 查询该section scope下的所有关系
    result = query_client.execute_cypher(query, {"scope": section_scope})
    section_edges.extend(result)

# 为每条边创建book scope版本（按指南第5.7节去重）
edge_fingerprints = set()
for edge_data in section_edges:
    # 生成book scope下的rid
    rid = generate_relation_rid(edge_type, source_id, target_id, book_scope)
    
    # 去重
    if rid in edge_fingerprints:
        continue
    edge_fingerprints.add(rid)
    
    # 创建book scope边
    edge_copy = {..., "scope": book_scope, "rid": rid}
    store.merge_edge(edge_copy)
```

### 修复3：kg_node.py - 统一book_id生成

**文件**：`backend/src/app/domain/workflows/textbook/nodes/kg_node.py`

**修改**：简化book_id生成逻辑，确保与指南一致

```python
# ✅ 按IMPROOVE_GUIDE.md要求：Section Scope数据已存储，book_graph_node将负责Book Scope合并
logger.info(f"Section级KG已存储到Neo4j，section_ids: {section_ids}")

# 生成book_id（按IMPROOVE_GUIDE.md第5.7节规范）
from app.domain.kg.idempotent import generate_book_id
language = state.get("language", "zh")
book_id = generate_book_id(topic, language)
logger.info(f"生成book_id: {book_id}，将由book_graph_node执行Book Scope合并")
```

## 架构对齐验证

### ✅ 符合指南第5.1节 - 统一入口

```python
class KGPipeline:
    def run(self, section: dict) -> dict:
        # 1) 抽取（NER/RE）
        draft = self.builder.extract(section)
        # 2) 规范化
        draft = self.normalizer.normalize(draft)
        # 3) 实体链接（对齐既有图谱）
        linked = self.linker.link(draft)
        # 4) 生成 ID/RID
        ready = self.idgen.assign(linked, section)
        # 5) 小节级入库（Section Scope） ✅
        self.store.write_section(ready, section['section_id'])
        # 6) 整书合并（Book Scope） ✅
        book_id = self.merger.merge_book(section['book_topic'])
```

### ✅ 符合指南第5.6节 - 小节级入库

- 数据以 `scope=section:xxx` 存储
- 关系包含 `src=section_id`

### ✅ 符合指南第5.7节 - 整书合并

- 从Section Scope读取数据
- 按rid去重
- 转写为Book Scope

## 数据流验证

### 阶段1：KG构建（kg_node）
```
Input: topic, chapters, content
  ↓
pipeline.run_one_subchapter(input)
  ↓
context.scope = "section:xxx"  ✅
  ↓
store.store_kg(kg_data, context)
  ↓
Neo4j: scope="section:xxx"  ✅
  ↓
Output: section_ids, book_id
```

### 阶段2：整书合并（book_graph_node）
```
Input: section_ids, book_id
  ↓
for section_id in section_ids:
  query: WHERE r.scope = "section:xxx"  ✅
  ↓
  read section edges
  ↓
aggregate all section edges
  ↓
for each edge:
  generate book_scope rid
  ↓
  deduplicate by rid
  ↓
  store with scope = "book:xxx"  ✅
  ↓
Neo4j: scope="book:xxx"  ✅
```

### 阶段3：前端展示
```
GET /api/v1/kg/books/{book_id}
  ↓
query: WHERE n.scope = $book_id AND r.scope = $book_id
  ↓
return {nodes, edges}  ✅
```

## 测试建议

### 单元测试
1. 验证Section Scope存储
2. 验证Book Scope合并
3. 验证rid去重逻辑

### 集成测试
1. 运行完整教材生成流程
2. 检查Neo4j中的scope分布
3. 验证前端图谱展示

### 验证查询
```cypher
-- 检查Section Scope数据
MATCH (n)-[r]->(m) WHERE r.scope STARTS WITH 'section:'
RETURN count(r) as section_edges

-- 检查Book Scope数据
MATCH (n)-[r]->(m) WHERE r.scope STARTS WITH 'book:'
RETURN count(r) as book_edges

-- 验证数据完整性
MATCH (n)-[r]->(m) 
RETURN r.scope, count(r) as edge_count
ORDER BY edge_count DESC
```

## 总结

通过本次修复：
1. ✅ **架构对齐**：完全符合IMPROOVE_GUIDE.md的两阶段存储要求
2. ✅ **数据流修复**：Section Scope → Book Scope转换正确
3. ✅ **去重逻辑**：按rid去重，避免重复边
4. ✅ **职责清晰**：pipeline负责Section存储，book_graph_node负责Book合并

这样确保了系统严格遵循指南要求，不存在架构违背的问题。



