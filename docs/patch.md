# KG 手册—Neo4j CRUD（neomodel 实现版｜替换块）

> 本文档对《真·Neo4j 教材 → 知识图谱（工程化分层解耦实施手册）》中**所有涉及 Neo4j 的 CRUD 实施细节**进行统一替换，
> 将原生 Cypher/驱动访问改为 **neomodel ORM**。除本文明确列出的替换块外，原手册其他内容保持不变。
>
> **禁止自由发挥**：模型类、字段、关系名、目录和函数签名均为唯一标准，不得擅自更改。

---

## A. 依赖与连接（新增/替换）

### A.1 requirements 追加（固定版本）

```
neomodel==5.0.1
```

> 不得更换版本号；如需升级，须提交 `[KG-SPEC]` 变更 PR 并通过端到端冒烟。

### A.2 连接配置（`settings.py` 固定键名）

```python
class Settings(BaseSettings):
    # ...（保留原有项）
    NEO4J_BOLT_URL: str = 'bolt://neo4j:neo4j@localhost:7687'  # 形如 bolt://user:pass@host:7687
    NEO4J_MAX_CONNECTION_LIFETIME: int = 3600
```

### A.3 连接初始化（新增文件）

**文件**：`backend/src/app/infrastructure/graph_store/neomodel_conn.py`

```python
from neomodel import db

__all__ = ["init_neo4j"]

def init_neo4j(settings) -> None:
    """设置 neomodel 连接（应用启动时调用一次）。"""
    db.set_connection(settings.NEO4J_BOLT_URL)
    # 连接参数按需可在 URL 中指定；不在代码里二次覆盖。
```

> **调用位置**：后端应用启动时（FastAPI lifespan/on_startup）**必须**执行 `init_neo4j(settings)`。

---

## B. 数据模型（neomodel 版，固定，不得改动字段/关系名）

**文件**：`backend/src/app/domain/kg/models.py`

> 仅允许以下 9 类节点标签：`Concept`, `Chapter`, `Subchapter`, `Method`, `Example`, `Dataset`, `Equation`, `Doc`, `Chunk`。
> 关系类型仅允许：结构 `PART_OF|HAS_SECTION|HAS_CHUNK`；语义 `DEFINES|EXPLAINS|REQUIRES|SIMILAR_TO|CONTRASTS_WITH|IMPLEMENTS`；桥接 `MENTIONS`。

```python
from datetime import datetime
from neomodel import (
    StructuredNode, StructuredRel,
    StringProperty, FloatProperty, DateTimeProperty, ArrayProperty,
)

# —— 关系属性：固定最小集合；可选 evidence 便于溯源 ——
class KGRel(StructuredRel):
    rid       = StringProperty(required=True)        # 关系唯一键（由 pipeline 计算）
    type      = StringProperty(required=True)        # 关系类型（与边类型一致）
    src       = StringProperty(required=True)        # 小节级来源 section_id
    scope     = StringProperty(required=True)        # section_id 或 book_id
    confidence= FloatProperty(default=1.0)
    weight    = FloatProperty(default=1.0)
    created_at= DateTimeProperty(default_now=True)
    evidence  = StringProperty()                     # 选填：对齐的 chunk_id

# —— 节点公共基类 ——
class BaseEntity(StructuredNode):
    id         = StringProperty(required=True, unique_index=True)  # 全局唯一
    name       = StringProperty(required=True)
    type       = StringProperty(required=True)                     # 固定为标签名
    desc       = StringProperty()                                  # ≤ 2KB，外部保证截断
    aliases    = ArrayProperty()
    scope      = StringProperty()                                  # 可留空；用于 Doc/Chunk
    created_at = DateTimeProperty(default_now=True)
    updated_at = DateTimeProperty(default_now=True)

    def touch(self):
        self.updated_at = datetime.utcnow()
        self.save()

# —— 9 类节点（标签名 = 类名）——
class Concept(BaseEntity):
    pass

class Chapter(BaseEntity):
    pass

class Subchapter(BaseEntity):
    pass

class Method(BaseEntity):
    pass

class Example(BaseEntity):
    pass

class Dataset(BaseEntity):
    pass

class Equation(BaseEntity):
    pass

class Doc(BaseEntity):
    pass

class Chunk(BaseEntity):
    pass
```

> **说明**：
>
> 1. `id` 采用业务语义 ID（由 `IdGen` 产生），唯一约束由 neomodel 自动生成；
> 2. 关系属性索引（`rid`/`scope`）为 Neo4j 关系属性索引，需在 **C. 架构安装**一步通过 Cypher 创建（neomodel 不为关系属性自动建索引）。

---

## C. 架构安装（替换原 4.5 约束/索引章节）

**文件**：`backend/src/app/infrastructure/graph_store/schema.py`

```python
from neomodel import db
from app.domain.kg.models import (
    Concept, Chunk, BaseEntity
)

__all__ = ["install_schema"]

NODE_CONSTRAINTS = [
    "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id   IF NOT EXISTS FOR (n:Chunk)   REQUIRE n.id IS UNIQUE",
    "CREATE INDEX     node_scope  IF NOT EXISTS FOR (n) ON (n.scope)",
]

REL_INDEXES = [
    "CREATE INDEX rel_scope IF NOT EXISTS FOR ()-[r]-() ON (r.scope)",
    "CREATE INDEX rel_rid   IF NOT EXISTS FOR ()-[r]-() ON (r.rid)",
]

def install_schema() -> None:
    """一次性执行，重复调用安全。"""
    # 节点约束/索引（也可通过 neomodel 的 labels 安装，但此处统一显式执行）
    for cypher in NODE_CONSTRAINTS + REL_INDEXES:
        db.cypher_query(cypher)
```

> **执行位置**：
>
> * 应用启动顺序：`init_neo4j(settings)` → `install_schema()`；
> * `scripts/kg_smoke.ps1` 亦必须调用 `install_schema()`。

---

## D. 入库实现（替换原 5.6《入库（store.py）》）

**文件**：`backend/src/app/domain/kg/store.py`

```python
from typing import Iterable
from itertools import islice
from neomodel import db
from .models import Concept, Chunk, BaseEntity, KGRel

__all__ = ["KGStore"]

class KGStore:
    """使用 neomodel 完成小节级写入（先删旧边 → 节点 MERGE → 关系 MERGE）。"""

    def __init__(self, settings):
        self.batch = settings.KG_TX_BATCH_SIZE
        self.stats = {"nodes": 0, "edges": 0}

    # —————— 公开入口 ——————
    def write_section(self, ready: dict, section_id: str) -> None:
        """
        ready = {
          'concepts': [ {'id': 'concept:rag:xx', 'name': 'RAG', 'aliases': [...]} , ... ],
          'relations': [ {'rid': '...', 'type': 'REQUIRES', 'source_id': '...', 'target_id': '...', 'confidence': 0.92, 'scope': section_id, 'src': section_id, 'evidence': 'doc1#p3'}, ... ]
        }
        """
        self._delete_section_edges(section_id)
        self._merge_concepts_batched(ready.get('concepts', []))
        self._merge_evidence_chunks(ready.get('concepts', []))
        self._merge_relations_batched(ready.get('relations', []))

    # —————— 节点：Concept ——————
    def _merge_concepts_batched(self, concepts: list[dict]) -> None:
        for chunk in _chunked(concepts, self.batch):
            with db.transaction:  # 单事务写入一批
                for c in chunk:
                    node = Concept.nodes.get_or_none(id=c['id'])
                    if node is None:
                        node = Concept(
                            id=c['id'], name=c['name'], type='Concept', aliases=c.get('aliases', [])
                        )
                        node.save()
                        self.stats["nodes"] += 1
                    else:
                        # 幂等更新（不覆盖已有非空 desc/aliases）
                        if c.get('name') and node.name != c['name']:
                            node.name = c['name']
                        if c.get('aliases'):
                            node.aliases = sorted(set((node.aliases or []) + c['aliases']))
                        node.touch()

    # —————— 节点：Chunk（证据） ——————
    def _merge_evidence_chunks(self, concepts: list[dict]) -> None:
        # 从 concepts[*].mentions 中抽取 chunk_id，创建最小 Chunk 节点
        all_mentions = []
        for c in concepts:
            all_mentions.extend(c.get('mentions', []))
        ids = sorted(set(all_mentions))
        for chunk in _chunked(ids, self.batch):
            with db.transaction:
                for cid in chunk:
                    if not cid:
                        continue
                    node = Chunk.nodes.get_or_none(id=cid)
                    if node is None:
                        Chunk(id=cid, name=cid, type='Chunk').save()
                        self.stats["nodes"] += 1

    # —————— 关系：统一 MERGE（按 rid 去重） ——————
    def _merge_relations_batched(self, rels: list[dict]) -> None:
        for batch in _chunked(rels, self.batch):
            with db.transaction:
                for r in batch:
                    self._merge_rel(r)
                    self.stats["edges"] += 1

    @staticmethod
    def _merge_rel(r: dict) -> None:
        """通过 Cypher 在 neomodel 连接上执行 MERGE，保证 rid 幂等。"""
        cypher = (
            "MATCH (s {id:$sid}), (t {id:$tid}) "
            "MERGE (s)-[e:%s {rid:$rid}]->(t) "
            "SET e.type=$type, e.src=$src, e.scope=$scope, e.confidence=$confidence, "
            "    e.weight=coalesce($weight,1.0), e.created_at=coalesce(e.created_at, datetime()), e.evidence=$evidence"
        ) % r['type']
        params = {
            'sid': r['source_id'], 'tid': r['target_id'], 'rid': r['rid'], 'type': r['type'],
            'src': r['src'], 'scope': r['scope'], 'confidence': float(r.get('confidence', 1.0)),
            'weight': r.get('weight'), 'evidence': r.get('evidence'),
        }
        db.cypher_query(cypher, params)

# —————— 工具：批次切分 ——————

def _chunked(iterable: Iterable, size: int):
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            return
        yield batch
```

**强约束**：

1. **禁止**在 `KGStore` 中直接使用 Neo4j 原生驱动；只允许经 `neomodel` 的 `db` 访问；
2. **必须**先删旧 Section 范围的边，再 MERGE 节点、MERGE 关系；
3. MERGE 关系 **必须**以 `rid` 去重；
4. 事务批量大小固定走 `KG_TX_BATCH_SIZE`，不得在代码里硬编码其他值。

---

## E. 整书合并（替换原 5.7《合并（merger.py）》）

**文件**：`backend/src/app/domain/kg/merger.py`

```python
from neomodel import db
from .idempotent import IdGen

__all__ = ["BookMerger"]

class BookMerger:
    def __init__(self, settings):
        self.settings = settings
        self.idgen = IdGen(settings)

    def merge_book(self, topic: str) -> str:
        book_id = f"book:{self.idgen.slug(topic)}:{self.idgen.md5(topic)[:8]}"
        # 1) 删除旧书范围全部边
        db.cypher_query("MATCH ()-[r]-() WHERE r.scope = $scope DELETE r", {"scope": book_id})
        # 2) 汇总所有 section 边 → 按 (type, source, target) 聚合 → 生成新 rid(scope=book_id) → 写入
        cypher = (
            "MATCH (s)-[r]-(t) WHERE r.src IS NOT NULL "
            "WITH DISTINCT type(r) AS typ, s.id AS sid, t.id AS tid "
            "WITH typ, sid, tid, $scope AS scope "
            "WITH typ, sid, tid, scope, toLower(typ) + '|' + sid + '|' + tid + '|' + scope AS sig "
            "WITH typ, sid, tid, scope, right(toHex(apoc.util.md5(sig)),16) AS rid "
            "MATCH (ss {id:sid}), (tt {id:tid}) "
            "MERGE (ss)-[e: `'+"%s"+'` {rid:rid}]->(tt) "
            "SET e.type=typ, e.src='__book_merge__', e.scope=scope, e.confidence=1.0, e.weight=1.0, e.created_at=coalesce(e.created_at, datetime())"
        )
        # 依次为 7 种语义边执行；结构边和 MENTIONS 不参与整书合并
        for typ in ("DEFINES","EXPLAINS","REQUIRES","SIMILAR_TO","CONTRASTS_WITH","IMPLEMENTS"):
            db.cypher_query(cypher % typ, {"scope": book_id})
        return book_id
```

> **说明**：
>
> * 合并以语义边为对象（不含 `PART_OF|HAS_SECTION|HAS_CHUNK|MENTIONS`）；
> * 书级 `rid` 与小节级不同（`scope=book_id`），保证二者互不冲突；
> * 依赖 `apoc.util.md5`；如未启用 APOC，改为将 `rid` 由 `IdGen` 预先生成并通过 `MERGE` 写入（同 D 节 `_merge_rel`）。

---

## F. 统一网关（替换原 6《Neo4j 交互（统一网关）》）

**文件**：`backend/src/app/infrastructure/graph_store/neomodel_store.py`

```python
from typing import Iterable
from neomodel import db

__all__ = ["Neo4jStore"]

class Neo4jStore:
    """提供最小访问面以供其他层调用；内部全部走 neomodel 的 db。"""

    @staticmethod
    def run_cypher(query: str, params: dict | None = None) -> list[dict]:
        results, meta = db.cypher_query(query, params or {})
        # 标准化为 list[dict]
        keys = [m["name"] for m in meta]
        out = []
        for row in results:
            obj = {}
            for k, v in zip(keys, row):
                obj[k] = v
            out.append(obj)
        return out

    @staticmethod
    def run_tx(queries: Iterable[tuple[str, dict]]):
        with db.transaction:
            for q, p in queries:
                db.cypher_query(q, p)
```

> **强制要求**：
>
> * 任何需要执行 Cypher 的地方（如关系 MERGE、整书合并）必须通过本网关；
> * **禁止**在项目中实例化 Neo4j 原生 Driver；所有访问通过 neomodel 连接层完成。

---

## G. 启动顺序与冒烟（必须执行）

1. 应用启动顺序：

   1. `init_neo4j(settings)`；
   2. `install_schema()`；
   3. 启动 FastAPI。
2. `scripts/kg_smoke.ps1` 增加以下步骤：

   * 调用 `install_schema()`；
   * 触发 `POST /api/v1/kg/sections:build`；
   * 查询 `GET /api/v1/kg/books/{book_id}` 非空 → 打印 `OK`。

---

## H. 开发者不得擅改的清单（硬性约束）

* **不得**新增/更名/删除任何 neomodel 模型类与字段；
* **不得**在 neomodel 之外再引入其他 ORM/驱动；
* **不得**修改批量大小、事务边界与 rid 计算方式；
* **不得**将大段文本（>2KB）写入 `desc`；
* **必须**先删旧 Section 边，再写新数据；
* **必须**以 `rid` 作为关系唯一键进行 `MERGE` 幂等写入。

---

## I. 迁移注意事项（一次性操作）

* 旧实现中若遗留 `rid` 冲突（同源/同目标/同类型但 `scope` 不同），清理逻辑：

  * 书级合并前先 `MATCH ()-[r]-() WHERE r.src <> r.scope AND r.scope STARTS WITH 'book:' REMOVE r.rid`；
  * 再按 E 节合并流程重建书级边（rid 以书级 scope 重新计算）。
* 若未安装 APOC，请在 `merger.py` 中**改为**由 `IdGen` 产生 `rid`，并删除 `toHex(apoc.util.md5(...))` 相关语句。

---

### 附：`IdGen.assign` 输出约定（与 D 节严格配合）

`IdGen.assign` 必须保证：

```json
{
  "concepts": [
    {"id": "concept:xxx", "name": "RAG", "aliases": ["检索增强生成"], "mentions": ["doc1#p3","doc1#p4"]}
  ],
  "relations": [
    {"rid":"0123456789abcdef","type":"REQUIRES","source_id":"concept:rag","target_id":"concept:vecsearch","src":"sec_0001","scope":"sec_0001","confidence":0.93,"evidence":"doc1#p3"}
  ]
}
```

> 上述结构为 `KGStore.write_section` 的唯一输入合同；任何字段缺失或更名均视为违例。
