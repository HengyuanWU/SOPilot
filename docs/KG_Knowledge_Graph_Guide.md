# 知识图谱 (Knowledge Graph) 完整指南

> **版本**: 1.0  
> **更新日期**: 2025-10-22  
> **状态**: ✅ 已完成

---

## 📋 目录

- [概述](#概述)
- [架构设计](#架构设计)
- [Neo4j 集成](#neo4j-集成)
- [Neomodel 迁移](#neomodel-迁移)
- [使用指南](#使用指南)
- [性能优化](#性能优化)
- [验证与测试](#验证与测试)

---

## 🎯 概述

知识图谱 (KG) 是 SOPilot 项目的核心组件之一，用于存储和检索结构化知识。

### 核心功能

- ✅ 教材内容的图谱化存储
- ✅ 实体和关系的提取与管理
- ✅ 知识检索与推理
- ✅ 与 RAG 系统的集成

### 技术栈

- **图数据库**: Neo4j 4.4+
- **ORM**: Neomodel
- **查询语言**: Cypher
- **集成**: LangChain, Qdrant

---

## 🏗️ 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│              Knowledge Graph System                  │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────────┐    ┌──────────────┐              │
│  │   Entities   │────│ Relationships │              │
│  │              │    │               │              │
│  │ • Book       │    │ • CONTAINS    │              │
│  │ • Chapter    │    │ • RELATES_TO  │              │
│  │ • Section    │    │ • REFERENCES  │              │
│  │ • Concept    │    │               │              │
│  └──────────────┘    └──────────────┘              │
│         │                    │                       │
│         └────────────────────┘                       │
│                 │                                     │
│        ┌────────▼─────────┐                         │
│        │   Neo4j Store    │                         │
│        │   (Neomodel)     │                         │
│        └────────┬─────────┘                         │
│                 │                                     │
│        ┌────────▼─────────┐                         │
│        │  RAG Integration │                         │
│        └──────────────────┘                         │
└─────────────────────────────────────────────────────┘
```

### 数据模型

#### 核心实体

**Book** (书籍)
```python
class Book(StructuredNode):
    book_id = StringProperty(unique_index=True, required=True)
    title = StringProperty(required=True)
    author = StringProperty()
    created_at = DateTimeProperty(default_now=True)
```

**Chapter** (章节)
```python
class Chapter(StructuredNode):
    chapter_id = StringProperty(unique_index=True, required=True)
    title = StringProperty(required=True)
    order = IntegerProperty()
    book_id = StringProperty(required=True)
```

**Section** (小节)
```python
class Section(StructuredNode):
    section_id = StringProperty(unique_index=True, required=True)
    title = StringProperty(required=True)
    content = StringProperty()
    chapter_id = StringProperty(required=True)
```

**Concept** (概念)
```python
class Concept(StructuredNode):
    concept_id = StringProperty(unique_index=True, required=True)
    name = StringProperty(required=True)
    description = StringProperty()
    category = StringProperty()
```

#### 关系类型

- `CONTAINS`: 包含关系 (Book → Chapter, Chapter → Section)
- `RELATES_TO`: 相关关系 (Concept ↔ Concept)
- `REFERENCES`: 引用关系 (Section → Concept)
- `NEXT`: 顺序关系 (Chapter → Chapter, Section → Section)

---

## 🔧 Neo4j 集成

### 连接配置

**文件**: `backend/src/app/infrastructure/graph_store/neo4j_client.py`

```python
from neomodel import config, db

# 配置连接
config.DATABASE_URL = 'bolt://neo4j:password@localhost:7687'

# 验证连接
db.cypher_query("MATCH (n) RETURN count(n) LIMIT 1")
```

### Schema 定义

**文件**: `backend/src/app/infrastructure/graph_store/schema.py`

包含所有 Neomodel 模型定义。

### 基本操作

#### 创建节点

```python
from app.infrastructure.graph_store.schema import Book, Chapter

# 创建书籍
book = Book(
    book_id="book_001",
    title="深度学习入门"
).save()

# 创建章节
chapter = Chapter(
    chapter_id="chapter_001",
    title="第一章：神经网络基础",
    order=1,
    book_id="book_001"
).save()

# 建立关系
book.chapters.connect(chapter)
```

#### 查询节点

```python
# 根据 ID 查询
book = Book.nodes.get(book_id="book_001")

# 条件查询
chapters = Chapter.nodes.filter(book_id="book_001").order_by('order')

# Cypher 查询
results, meta = db.cypher_query("""
    MATCH (b:Book)-[:CONTAINS]->(c:Chapter)
    WHERE b.book_id = $book_id
    RETURN c.title, c.order
    ORDER BY c.order
""", {'book_id': 'book_001'})
```

#### 更新节点

```python
# 更新属性
book = Book.nodes.get(book_id="book_001")
book.title = "深度学习入门（第二版）"
book.save()
```

#### 删除节点

```python
# 删除节点
book = Book.nodes.get(book_id="book_001")
book.delete()

# 级联删除（删除相关关系）
db.cypher_query("""
    MATCH (b:Book {book_id: $book_id})
    DETACH DELETE b
""", {'book_id': 'book_001'})
```

---

## 🔄 Neomodel 迁移

### 迁移背景

项目从原始 Cypher 查询迁移到 Neomodel ORM，以提高代码质量和可维护性。

### 迁移步骤

#### 1. 定义模型

在 `schema.py` 中定义所有实体：

```python
from neomodel import StructuredNode, StringProperty, RelationshipTo

class Book(StructuredNode):
    book_id = StringProperty(unique_index=True, required=True)
    title = StringProperty(required=True)
    
    # 定义关系
    chapters = RelationshipTo('Chapter', 'CONTAINS')
```

#### 2. 替换查询代码

**迁移前** (原始 Cypher):
```python
result = self.client.query("""
    MATCH (b:Book {book_id: $book_id})
    RETURN b
""", parameters={'book_id': book_id})
```

**迁移后** (Neomodel):
```python
book = Book.nodes.get(book_id=book_id)
```

#### 3. 更新业务逻辑

**文件**: `backend/src/app/infrastructure/graph_store/neo4j_store.py`

所有知识图谱操作都已更新为使用 Neomodel。

### 迁移清单

- [x] 定义所有 Neomodel 模型
- [x] 更新 Neo4jClient 使用 Neomodel
- [x] 更新 Neo4jStore 的所有方法
- [x] 更新 KG 相关的 domain 层代码
- [x] 更新测试用例
- [x] 验证功能完整性

### 快速参考

**常用操作对照表**:

| 操作 | 原始 Cypher | Neomodel |
|-----|------------|----------|
| 创建节点 | `CREATE (n:Book {...})` | `Book(...).save()` |
| 查询节点 | `MATCH (n:Book {id: $id})` | `Book.nodes.get(book_id=id)` |
| 更新节点 | `MATCH (n) SET n.prop = $val` | `node.prop = val; node.save()` |
| 删除节点 | `MATCH (n) DELETE n` | `node.delete()` |
| 创建关系 | `CREATE (a)-[:REL]->(b)` | `a.rel.connect(b)` |

---

## 📚 使用指南

### 教材图谱构建

#### 1. 导入教材

```python
from app.domain.workflows.textbook.nodes.book_graph_node import BookGraphNode

# 创建图谱节点
graph_node = BookGraphNode()

# 处理教材
result = graph_node.process({
    'book_file': 'path/to/textbook.pdf',
    'book_id': 'book_001'
})
```

#### 2. 知识提取

图谱构建会自动：
- 提取章节结构
- 识别关键概念
- 建立概念关系
- 生成知识卡片

#### 3. 图谱查询

```python
from app.infrastructure.graph_store.neo4j_store import Neo4jStore

store = Neo4jStore()

# 查询书籍信息
book_info = store.get_book("book_001")

# 查询章节列表
chapters = store.get_chapters("book_001")

# 查询相关概念
concepts = store.get_related_concepts("深度学习")
```

### 与 RAG 集成

#### KG 增强检索

```python
from app.infrastructure.rag.langchain_pipeline import LangChainRAGPipeline

pipeline = LangChainRAGPipeline(
    embedder=embedder,
    vectorstore=vectorstore,
    kg_store=kg_store  # 知识图谱
)

# 执行检索（结合向量和图谱）
response = pipeline.run(
    query="什么是卷积神经网络？",
    use_kg=True  # 启用知识图谱增强
)
```

---

## ⚡ 性能优化

### 索引优化

**创建索引**:
```cypher
-- 为常用查询字段创建索引
CREATE INDEX book_id_index FOR (b:Book) ON (b.book_id);
CREATE INDEX chapter_id_index FOR (c:Chapter) ON (c.chapter_id);
CREATE INDEX concept_name_index FOR (c:Concept) ON (c.name);
```

**Neomodel 自动索引**:
```python
class Book(StructuredNode):
    book_id = StringProperty(unique_index=True)  # 自动创建索引
```

### 查询优化

**使用参数化查询**:
```python
# 推荐
db.cypher_query(
    "MATCH (b:Book {book_id: $id}) RETURN b",
    {'id': book_id}
)

# 避免
db.cypher_query(f"MATCH (b:Book {{book_id: '{book_id}'}}) RETURN b")
```

**批量操作**:
```python
# 批量创建节点
with db.transaction:
    for data in batch_data:
        Book(**data).save()
```

### 连接池配置

```python
from neomodel import config

config.MAX_POOL_SIZE = 50
config.CONNECTION_TIMEOUT = 30
```

---

## ✅ 验证与测试

### 连接测试

```python
from neomodel import db

# 测试连接
try:
    db.cypher_query("RETURN 1")
    print("✓ Neo4j 连接成功")
except Exception as e:
    print(f"✗ Neo4j 连接失败: {e}")
```

### 数据验证

```bash
# 进入容器
docker exec -it sopilot-backend /bin/bash

# 运行验证脚本
python -m app.infrastructure.graph_store.validate
```

### 单元测试

**文件**: `backend/tests/test_kg_pipeline.py`

```bash
# 运行测试
pytest backend/tests/test_kg_pipeline.py -v
```

---

## 📊 统计与监控

### 图谱统计

```python
from app.infrastructure.graph_store.neo4j_store import Neo4jStore

store = Neo4jStore()

# 获取统计信息
stats = store.get_stats()
print(f"总书籍数: {stats['books']}")
print(f"总章节数: {stats['chapters']}")
print(f"总概念数: {stats['concepts']}")
print(f"总关系数: {stats['relationships']}")
```

### Neo4j Browser

访问 `http://localhost:7474` 查看图谱可视化。

---

## 🔍 故障排查

### 常见问题

#### 1. 连接失败

**错误**: `Could not connect to Neo4j`

**解决**:
```bash
# 检查容器状态
docker ps | grep neo4j

# 重启 Neo4j
docker-compose restart neo4j
```

#### 2. 索引冲突

**错误**: `Node with this property already exists`

**解决**:
```python
# 使用 get_or_create
book = Book.get_or_create({'book_id': 'book_001'})[0]
```

#### 3. 性能问题

**问题**: 查询缓慢

**解决**:
- 添加索引
- 优化 Cypher 查询
- 使用 EXPLAIN 分析查询计划

---

## 📦 相关文件

### 核心实现

| 文件路径 | 说明 |
|---------|------|
| `backend/src/app/infrastructure/graph_store/schema.py` | Neomodel 模型定义 |
| `backend/src/app/infrastructure/graph_store/neo4j_client.py` | Neo4j 客户端 |
| `backend/src/app/infrastructure/graph_store/neo4j_store.py` | 知识图谱存储层 |
| `backend/src/app/domain/kg/store.py` | 领域层 KG 接口 |
| `backend/src/app/domain/kg/models.py` | KG 数据模型 |

### 配置文件

| 文件路径 | 说明 |
|---------|------|
| `backend/src/app/core/settings.py` | Neo4j 连接配置 |
| `docker-compose.yml` | Neo4j 容器配置 |

---

## 🎯 最佳实践

### 1. 模型设计

- ✅ 使用有意义的节点标签
- ✅ 为频繁查询的属性添加索引
- ✅ 合理设计关系类型
- ✅ 避免过深的关系层次

### 2. 查询优化

- ✅ 使用参数化查询
- ✅ 避免全图扫描
- ✅ 合理使用 LIMIT
- ✅ 使用 PROFILE 分析性能

### 3. 数据管理

- ✅ 定期备份数据
- ✅ 监控图谱大小
- ✅ 清理孤立节点
- ✅ 维护数据一致性

---

**文档版本**: 1.0  
**最后更新**: 2025-10-22  
**维护者**: SOPilot Team

