# Book ID vs Book Name 说明文档

## 概述
本文档说明KG模块中 `book_id` 和 `book_name` 两个字段的区别、用途及相互关系。

## 一、字段定义

### 1. book_id (唯一标识符)
- **类型**: `str`
- **格式**: `book:{slug}:{hash}`
  - 例如: `book:software-testing:a1b2c3d4`
- **生成逻辑**: 
  ```python
  topic_slug = slug(topic)  # URL安全的slug
  topic_hash = md5(topic)[:8]  # MD5哈希前8位
  book_id = f"book:{topic_slug}:{topic_hash}"
  ```
- **用途**: 
  - **唯一标识**: 在系统中唯一标识一本书的知识图谱
  - **数据隔离**: 通过 `scope` 字段区分不同书籍的KG数据
  - **API路由**: 作为RESTful API的路径参数 (`/kg/books/{book_id}`)
  - **数据库查询**: 在Neo4j中按 `scope=book_id` 查询/删除数据

### 2. book_name (显示名称)
- **类型**: `str`
- **格式**: 人类可读的书籍名称
  - 例如: "软件测试教材"
- **来源**: 通常来自 `input_data.topic` 或用户提供的书籍名称
- **用途**:
  - **前端显示**: 在知识图谱可视化界面中显示书籍名称
  - **用户友好**: 提供易于理解的书籍标识
  - **辅助信息**: 作为节点/边的元数据，方便追踪数据来源

## 二、在代码中的位置

### 1. book_id 的使用

#### (1) 生成位置
```python
# backend/src/app/domain/kg/idempotent.py
def generate_book_id(topic: str, language: str = "zh") -> str:
    """生成book_id"""
    import hashlib
    topic_slug = _slug(topic)
    topic_hash = hashlib.md5(topic.encode('utf-8')).hexdigest()[:8]
    return f"book:{topic_slug}:{topic_hash}"
```

#### (2) 存储位置
- **节点**: `KGNode.scope` 字段
- **边**: `KGEdge.scope` 字段
- 格式: `book:{topic}:{hash}` 或 `section:{section_id}`

#### (3) 使用场景
- **数据隔离**: 
  ```cypher
  MATCH (n) WHERE n.scope = $book_id RETURN n
  ```
- **数据清理**:
  ```cypher
  MATCH ()-[r]->() WHERE r.scope = $book_id DELETE r
  ```
- **整书合并** (`KGMerger.merge_book`):
  ```python
  book_id = generate_book_id(topic)
  # 将所有section scope转换为book scope
  rel_copy['scope'] = book_id
  ```

### 2. book_name 的使用

#### (1) 添加位置
- `KGNode.book_name` (新增)
- `KGEdge.book_name` (新增)

#### (2) 数据流

```
Pipeline.run()
  ↓
context = {
    "topic": "软件测试",
    "book_name": input_data.topic,  # ← 来源
    ...
}
  ↓
Builder.build_kg() 
  → 生成 KGNode(book_name=context.get("book_name"))
  → 生成 KGEdge(book_name=context.get("book_name"))
  ↓
Idempotent.process()
  → 传递 book_name 到处理后的节点和边
  ↓
Store.store_kg()
  → 存储到Neo4j (节点/边属性中包含 book_name)
  ↓
API返回给前端
  → nodes: [{..., book_name: "软件测试"}, ...]
  → edges: [{..., book_name: "软件测试"}, ...]
```

#### (3) 前端使用
```javascript
// frontend/src/components/KgGraph.vue
nodes.forEach(node => {
  console.log(`节点 ${node.name} 来自书籍: ${node.book_name}`)
})
```

## 三、两者关系

| 维度 | book_id | book_name |
|------|---------|-----------|
| **性质** | 系统标识符（ID） | 人类可读名称 |
| **唯一性** | 唯一（基于哈希） | 不唯一（可能重名） |
| **格式** | `book:slug:hash` | 自由文本 |
| **主要用途** | 数据隔离、路由、查询 | 前端显示、用户识别 |
| **存储位置** | `scope` 字段 | `book_name` 字段 |
| **可变性** | 不变（基于topic生成） | 可变（可以修改） |
| **依赖关系** | 独立生成 | 通常来自 `topic` |

### 类比关系
- **book_id** ≈ 数据库主键 (UUID)
- **book_name** ≈ 数据库记录的显示名称

## 四、是否冲突？

### **结论：不冲突，功能互补**

1. **职责分离**:
   - `book_id`: 系统内部使用，保证数据一致性和隔离性
   - `book_name`: 用户界面使用，提供友好的显示信息

2. **数据层面**:
   - `book_id` 存储在 `scope` 字段（已有）
   - `book_name` 存储在 `book_name` 字段（新增）
   - 两者在Neo4j中是独立的属性，不会相互覆盖

3. **使用场景**:
   - **后端查询**: 使用 `book_id` (通过 `scope` 字段)
     ```python
     # 查询某本书的所有节点
     query = "MATCH (n) WHERE n.scope = $book_id RETURN n"
     ```
   - **前端显示**: 使用 `book_name`
     ```vue
     <div>{{ node.book_name }}</div>
     ```

## 五、实际示例

### 场景：处理《软件测试教材》

1. **输入数据**:
   ```python
   KGPipelineInput(
       topic="软件测试教材",
       chapter_title="第一章",
       ...
   )
   ```

2. **生成标识**:
   ```python
   book_id = generate_book_id("软件测试教材")
   # 结果: "book:software-testing-textbook:a1b2c3d4"
   
   book_name = "软件测试教材"
   ```

3. **存储到Neo4j**:
   ```cypher
   MERGE (n:Concept {id: "concept:unit-testing:12345678"})
   SET n.name = "单元测试",
       n.scope = "book:software-testing-textbook:a1b2c3d4",
       n.book_name = "软件测试教材"
   ```

4. **API返回**:
   ```json
   {
     "nodes": [{
       "id": "concept:unit-testing:12345678",
       "name": "单元测试",
       "type": "Concept",
       "scope": "book:software-testing-textbook:a1b2c3d4",
       "book_name": "软件测试教材"
     }]
   }
   ```

5. **前端显示**:
   ```
   知识图谱: 软件测试教材  ← 显示 book_name
   节点: 单元测试 (来自: 软件测试教材)
   ```

## 六、设计原则

这种设计遵循以下软件工程原则：

1. **关注点分离** (Separation of Concerns):
   - ID用于系统内部逻辑
   - 名称用于用户交互

2. **单一职责原则** (Single Responsibility):
   - 每个字段有明确的职责
   - 互不干扰

3. **开闭原则** (Open/Closed):
   - 添加 `book_name` 不影响现有 `book_id` 功能
   - 向后兼容

## 七、总结

- ✅ **不冲突**: `book_id` 和 `book_name` 是互补的字段
- ✅ **各司其职**: ID用于系统逻辑，名称用于显示
- ✅ **共存**: 同时存在于节点和边的属性中
- ✅ **增强**: `book_name` 的添加增强了前端的可读性，不影响后端逻辑

