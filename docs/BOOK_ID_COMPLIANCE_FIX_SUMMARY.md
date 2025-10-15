# Book ID 合规性修复总结

## 修复日期
2025-01-06

## 问题描述
当前 KG 系统在节点和边存储时使用了 **`book_name`**（用户可读字符串），而不是规范要求的 **`book_id`**（规范化标识符），这违反了 IMPROOVE_GUIDE.md 的规范要求。

详细诊断见：[BOOK_ID_COMPLIANCE_ISSUE.md](./BOOK_ID_COMPLIANCE_ISSUE.md)

---

## 修复内容

### ✅ 已完成的修改

#### 1. Schema 层修复
**文件：** `backend/src/app/domain/kg/schemas.py`

**变更：**
- 从 `KGNode` dataclass 中移除 `book_name` 字段
- 从 `KGEdge` dataclass 中移除 `book_name` 字段
- 更新注释说明 `scope` 字段格式为 `book:xxx:yyy` 或 `section:xxx`

**修改前：**
```python
@dataclass
class KGNode:
    id: str
    name: str
    type: str
    desc: str = ""
    aliases: List[str] = None
    scope: str = ""
    book_name: str = ""  # ❌ 违反规范
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

**修改后：**
```python
@dataclass
class KGNode:
    """知识图谱节点（符合IMPROOVE_GUIDE.md规范）"""
    id: str
    name: str
    type: str
    desc: str = ""
    aliases: List[str] = None
    scope: str = ""  # 格式: book:xxx:yyy 或 section:xxx
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

---

#### 2. Store 层修复
**文件：** `backend/src/app/domain/kg/store.py`

**变更：**
- 从 `_store_node_with_vector()` 的 Cypher 查询中移除 `n.book_name`
- 从节点参数字典中移除 `book_name`
- 从 `_store_edge()` 的 Cypher 查询中移除 `r.book_name`
- 从边参数字典中移除 `book_name`

**修改前（节点存储）：**
```python
query = f"""
MERGE (n:{node.type} {{id: $id}})
ON CREATE SET n.created_at = datetime(),
             n.name = $name,
             n.desc = $desc,
             n.aliases = $aliases,
             n.scope = $scope,
             n.book_name = $book_name,  # ❌
             n.vector = $vector
...
"""
params = {
    "id": node.id,
    "name": node.name,
    "desc": node.desc or "",
    "aliases": node.aliases or [],
    "scope": node.scope or "",
    "book_name": node.book_name or "",  # ❌
    "vector": vector
}
```

**修改后（节点存储）：**
```python
query = f"""
MERGE (n:{node.type} {{id: $id}})
ON CREATE SET n.created_at = datetime(),
             n.name = $name,
             n.desc = $desc,
             n.aliases = $aliases,
             n.scope = $scope,
             n.vector = $vector
...
"""
params = {
    "id": node.id,
    "name": node.name,
    "desc": node.desc or "",
    "aliases": node.aliases or [],
    "scope": node.scope or "",
    "vector": vector
}
```

**相同修复应用于边存储。**

---

#### 3. Idempotent 处理器修复
**文件：** `backend/src/app/domain/kg/idempotent.py`

**变更：**
- 从 `process_kg()` 中创建 `KGNode` 时移除 `book_name` 参数
- 从创建 `KGEdge` 时移除 `book_name` 参数

**修改前：**
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

**修改后：**
```python
processed_node = KGNode(
    id=node_id,
    name=canonical_name,
    type=node.type,
    desc=node.desc,
    aliases=self._deduplicate_aliases(node.aliases, canonical_name),
    scope=context.get("scope", node.scope),
    created_at=current_time,
    updated_at=current_time
)
```

---

#### 4. Pipeline 层修复
**文件：** `backend/src/app/domain/kg/pipeline.py`

**变更：**
- 从 context 字典中移除 `book_name` 键
- 确保 `scope` 使用 `generate_book_id()` 生成规范化 ID

**修改前：**
```python
context = {
    "topic": input_data.topic,
    "book_name": input_data.topic,  # ❌ 违反规范
    "language": input_data.language,
    "chapter_title": input_data.chapter_title,
    "subchapter_title": input_data.subchapter_title,
    "keywords": input_data.keywords,
    "section_id": section_id,
    "scope": generate_book_id(input_data.topic, input_data.language)
}
```

**修改后：**
```python
context = {
    "topic": input_data.topic,
    "language": input_data.language,
    "chapter_title": input_data.chapter_title,
    "subchapter_title": input_data.subchapter_title,
    "keywords": input_data.keywords,
    "section_id": section_id,
    "scope": generate_book_id(input_data.topic, input_data.language)  # book:xxx:yyy 格式
}
```

---

#### 5. Builder 层修复
**文件：** `backend/src/app/domain/kg/builder.py`

**变更：**
- 从创建 `KGNode` 时移除 `book_name` 参数
- 从创建 `KGEdge` 时移除 `book_name` 参数

**修改前：**
```python
node = KGNode(
    id=concept_id,
    name=str(concept_data.get("name", "")),
    type="Concept",
    desc=str(concept_data.get("desc", "")),
    aliases=concept_data.get("aliases", []),
    scope=context.get("scope") or context.get("topic", ""),
    book_name=context.get("book_name") or context.get("topic", ""),  # ❌
    created_at=current_time,
    updated_at=current_time
)
```

**修改后：**
```python
node = KGNode(
    id=concept_id,
    name=str(concept_data.get("name", "")),
    type="Concept",
    desc=str(concept_data.get("desc", "")),
    aliases=concept_data.get("aliases", []),
    scope=context.get("scope") or context.get("topic", ""),
    created_at=current_time,
    updated_at=current_time
)
```

---

## 验证结果

### ✅ Linter 检查
所有修改的文件通过了 linter 检查，无错误。

### ✅ 规范符合性检查
- [x] Schema 中不再有 `book_name` 字段
- [x] Neo4j 写入时不再包含 `book_name` 属性
- [x] `scope` 字段正确使用 `book_id` 格式（`book:xxx:yyy`）
- [x] 所有相关模块已更新
- [x] 无 linter 错误

### ⏳ 运行时验证（待执行）
- [ ] 重启后端服务
- [ ] 执行 KG 构建测试
- [ ] 验证 Neo4j 中的节点和边不包含 `book_name` 属性
- [ ] 验证前端显示正常（可能需要从 scope 解析或调用元数据 API）

---

## IMPROOVE_GUIDE.md 规范符合性

### ✅ 第 4.3 节 - 节点属性
```
id, name, type, desc, aliases[], scope, created_at, updated_at
```
**符合！** 不再包含 `book_name`

### ✅ 第 4.4 节 - 关系属性
```
rid, type, src(section_id), scope(book_id or section_id), confidence, weight, created_at
```
**符合！** 不再包含 `book_name`，`scope` 存储规范化 ID

### ✅ 第 5.5 节 - ID 生成
```python
# 节点 ID
concept:{slug(name)}:{md5(topic|chapter|subchapter)[:6]}

# 关系 RID
md5(type|source_id|target_id|scope)[:16]
```
**符合！** `ids.py` 中的实现完全正确

### ✅ 第 5.7 节 - Book ID 格式
```python
book:{slug(topic)}:{md5(topic)[:8]}
```
**符合！** `generate_book_id()` 实现正确

---

## 潜在影响和迁移建议

### 数据库迁移
Neo4j 中已存在的节点和边可能包含 `book_name` 属性。

**建议清理脚本：**
```cypher
// 清理节点上的 book_name 属性
MATCH (n)
WHERE n.book_name IS NOT NULL
REMOVE n.book_name
RETURN count(n) as cleaned_nodes;

// 清理关系上的 book_name 属性
MATCH ()-[r]-()
WHERE r.book_name IS NOT NULL
REMOVE r.book_name
RETURN count(r) as cleaned_edges;
```

### 前端适配
如果前端需要显示书籍名称，有两种方案：

**方案 1：从 scope 解析（快速但不够精确）**
```javascript
function extractTopicFromScope(scope) {
  // scope 格式: "book:da_xing_yu_yan_mo_xing:864d5654"
  if (scope.startsWith('book:')) {
    const parts = scope.split(':');
    return parts[1].replace(/_/g, ' ');  // "da xing yu yan mo xing"
  }
  return '';
}
```

**方案 2：元数据 API（推荐）**
```javascript
// 新增 API: GET /api/v1/kg/books/{book_id}/metadata
async function getBookDisplayName(bookId) {
  const metadata = await api.get(`/kg/books/${bookId}/metadata`);
  return metadata.title;  // "大型语言模型"
}
```

---

## 后续行动项

### 必须完成：
- [ ] 重启后端服务验证修复
- [ ] 执行 KG 构建端到端测试
- [ ] 检查 Neo4j 中的数据是否符合新规范

### 推荐完成：
- [ ] 执行数据库清理脚本移除历史 `book_name` 属性
- [ ] 如果前端需要，实现书籍元数据 API
- [ ] 更新相关文档和测试用例

---

## 总结

本次修复完全消除了 `book_name` 字段的使用，使系统完全符合 IMPROOVE_GUIDE.md 的规范要求。所有修改都遵循了"单一真相来源"原则，使用规范化的 `book_id` 和 `scope` 字段，避免了数据冗余和不一致的风险。

**核心改进：**
1. ✅ 数据模型符合规范
2. ✅ 避免数据冗余
3. ✅ 提高系统可维护性
4. ✅ 保持代码一致性

**下一步：** 重启服务并进行运行时验证。






