# Book ID 合规性问题诊断

## 问题概述

当前 KG 系统在节点和边存储时使用了 **`book_name`** (书籍名称字符串) 而不是 **`book_id`** (规范化ID)，这违反了 IMPROOVE_GUIDE.md 的规范要求。

---

## IMPROOVE_GUIDE.md 的规范要求

### 第 4.3 节 - 节点属性
```
id, name, type, desc, aliases[], scope, created_at, updated_at
```
**注意：没有 `book_name` 字段！**

### 第 4.4 节 - 关系属性
```
rid, type, src(section_id), scope(book_id or section_id), confidence, weight, created_at
```
**注意：`scope` 应该存储 `book_id` 或 `section_id`，而不是 `book_name`！**

### 第 5.7 节 - Book ID 格式
```python
# 生成 book_id = book:{slug(topic)}:{md5(topic)[:8]}
```
**明确要求使用 book_id，而非原始的 topic 字符串！**

---

## 当前实现的问题

### ❌ 问题 1: Schema 定义错误

**文件：** `backend/src/app/domain/kg/schemas.py`

```python
@dataclass
class KGNode:
    id: str
    name: str
    type: str
    desc: str = ""
    aliases: List[str] = None
    scope: str = ""
    book_name: str = ""  # ❌ 不应该存在！
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class KGEdge:
    rid: str
    type: str
    source: str
    target: str
    desc: str = ""
    confidence: float = 0.8
    weight: float = 1.0
    scope: str = ""
    book_name: str = ""  # ❌ 不应该存在！
    src_section: str = ""
    created_at: Optional[datetime] = None
```

**应该改为：**
- 移除 `book_name` 字段
- `scope` 字段应存储规范化的 `book:xxx:yyy` 格式

---

### ❌ 问题 2: Store 层使用 book_name

**文件：** `backend/src/app/domain/kg/store.py:503-524`

```python
query = f"""
MERGE (n:{node.type} {{id: $id}})
ON CREATE SET n.created_at = datetime(),
             n.name = $name,
             n.desc = $desc,
             n.aliases = $aliases,
             n.scope = $scope,
             n.book_name = $book_name,  # ❌ 不应该存在！
             n.vector = $vector
ON MATCH SET n.updated_at = datetime(),
            n.name = $name,
            n.desc = $desc,
            n.aliases = $aliases,
            n.scope = $scope,
            n.book_name = $book_name,  # ❌ 不应该存在！
            n.vector = $vector
...
"""

params = {
    "id": node.id,
    "name": node.name,
    "desc": node.desc or "",
    "aliases": node.aliases or [],
    "scope": node.scope or "",
    "book_name": node.book_name or "",  # ❌ 不应该存在！
    "vector": vector
}
```

---

### ❌ 问题 3: Idempotent 处理器传递 book_name

**文件：** `backend/src/app/domain/kg/idempotent.py:153`

```python
processed_node = KGNode(
    id=node_id,
    name=canonical_name,
    type=node.type,
    desc=node.desc,
    aliases=self._deduplicate_aliases(node.aliases, canonical_name),
    scope=context.get("scope", node.scope),
    book_name=context.get("book_name", getattr(node, "book_name", "")),  # ❌
    created_at=current_time,
    updated_at=current_time
)
```

---

## 根本原因分析

### 设计混淆
当前代码混淆了两个概念：
1. **`book_name`** - 用户可读的书籍名称（如 "大型语言模型"）
2. **`book_id`** - 规范化的唯一标识符（如 "book:da_xing_yu_yan_mo_xing:864d5654"）

### 正确的设计应该是：
- **scope 字段**：存储 `book:xxx:yyy` 或 `section:xxx` 格式的规范化 ID
- **查询时**：前端可以从 scope 中提取 topic 信息，或者通过单独的 API 获取书籍元数据

---

## 修复方案

### ✅ 方案 A：完全移除 book_name（推荐）

**优点：**
- 完全符合 IMPROOVE_GUIDE.md 规范
- 数据模型简洁，单一真相来源（scope）
- 避免数据冗余和不一致

**步骤：**
1. 从 `KGNode` 和 `KGEdge` schema 中删除 `book_name` 字段
2. 从 store.py 的 Cypher 查询中删除 `book_name` 属性
3. 修改 idempotent.py，不再传递 `book_name`
4. 确保 `scope` 字段始终使用规范化的 book_id
5. 前端需要时，从 scope 字段解析或通过元数据 API 获取显示名称

### ⚠️ 方案 B：保留 book_name 作为冗余字段（不推荐）

**理由：**
- 如果前端需要频繁显示书籍名称
- 但这违反了规范，且会造成数据不一致风险

---

## 影响范围评估

### 需要修改的文件：
1. ✅ `backend/src/app/domain/kg/schemas.py` - 移除 book_name
2. ✅ `backend/src/app/domain/kg/store.py` - 移除 book_name 存储
3. ✅ `backend/src/app/domain/kg/idempotent.py` - 移除 book_name 传递
4. ✅ `backend/src/app/domain/kg/pipeline.py` - 检查是否使用 book_name
5. ✅ `backend/src/app/domain/kg/merger.py` - 确保使用 book_id
6. ✅ `backend/src/app/api/v1/kg.py` - 检查 API 响应
7. ⚠️ `frontend/src/components/KgGraph.vue` - 可能需要适配显示逻辑

### 数据库迁移：
- Neo4j 中已存在的节点可能有 `book_name` 属性
- 建议：创建清理脚本移除历史数据的 `book_name` 属性

---

## 验证清单

修复完成后需要验证：

- [ ] Schema 中不再有 book_name 字段
- [ ] Neo4j 写入时不再包含 book_name
- [ ] scope 字段正确使用 book_id 格式
- [ ] 前端能正确显示（从 scope 解析或调用元数据 API）
- [ ] 测试脚本通过
- [ ] 冒烟测试通过

---

## 示例对比

### ❌ 错误的当前实现：
```json
{
  "id": "concept:rag:a1b2c3",
  "name": "RAG",
  "type": "Concept",
  "scope": "book:da_xing_yu_yan_mo_xing:864d5654",
  "book_name": "大型语言模型"  // ❌ 冗余！
}
```

### ✅ 正确的规范实现：
```json
{
  "id": "concept:rag:a1b2c3",
  "name": "RAG",
  "type": "Concept",
  "scope": "book:da_xing_yu_yan_mo_xing:864d5654"
}
```

前端需要显示名称时：
```javascript
// 选项1：从 scope 解析
const bookId = node.scope; // "book:da_xing_yu_yan_mo_xing:864d5654"
const displayName = bookId.split(':')[1].replace(/_/g, ' '); // 近似

// 选项2：调用元数据 API
const metadata = await api.getBookMetadata(bookId);
console.log(metadata.title); // "大型语言模型"
```

---

## 结论

**当前实现偏离了 IMPROOVE_GUIDE.md 规范**，需要立即修复以确保：
1. 数据模型符合规范
2. 避免数据冗余和不一致
3. 保持系统的可维护性

**推荐执行方案 A**，完全移除 book_name 字段，使用规范化的 book_id 和 scope 字段。






