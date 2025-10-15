# 真·Neo4j 教材 → 知识图谱（工程化分层解耦实施手册）

> 本手册是 **SOPilot** 项目中“教材 → 知识图谱”部分的**唯一实施标准**。 目标：让**新接手的开发者**在 1 天内完成一次端到端小节级 KG 构建，并在 2 天内完成整书级合并与前端可视化接入。
>
> **禁止自由发挥**：所有模块路径、函数命名、输入输出模式、配置键名、默认阈值、索引约束、API 合同均已在本文中固定，不得擅自更改。

---

## 0. 成果定义（Definition of Done）

一次成功的“教材 → 知识图谱”流水线运行，必须满足：

1. **小节级图谱（Section Scope）** 已存入 Neo4j：

   * 至少 10 个 `Concept` 节点、20 条 `REQUIRES/EXPLAINS/PART_OF/MENTIONS` 关系；
   * 每条关系带 `src=<section_id>`、`scope=<section_id>`、`rid` 唯一键；
   * 每个被关系引用的节点均唯一（`id` 唯一约束生效）。
2. **整书级图谱（Book Scope）** 已合并：

   * `scope=book:{topic}:{8位短哈希}`；
   * 合并时按 `rid` 去重，按 `scope` 替换更新（删除旧书、写入新书）。
3. **RAG 联动**：每个 `Concept` 至少被一个 `Chunk` 以 `MENTIONS` 连接（证据可回链）。
4. **前端渲染**：`/runs/:id` 的 KG 标签页可成功拉取 **Book Scope** 并渲染。
5. **自动化校验**：执行 `pytest -k test_kg_pipeline` 全部通过；运行 `scripts/kg_smoke.ps1` 返回 `OK`。

---

## 1. 目录与文件落位（固定，不得变更）

```
backend/src/app/domain/kg/
├── pipeline.py         # KGPipeline：端到端编排（唯一入口）
├── builder.py          # NER/RE 抽取（句级/段级，不得整篇丢 LLM）
├── normalizer.py       # 规范化（大小写、词形、别名映射、停用词）
├── linker.py           # 实体链接（对齐已有节点；规则+向量）
├── idempotent.py       # ID 与 RID 生成、查重
├── store.py            # 写 Neo4j（节点/关系 MERGE；批量事务）
├── merger.py           # 整书合并（Section → Book 合并与去重）
└── service.py          # 查询与服务层（供 API 调用）

backend/src/app/infrastructure/graph_store/
├── neomodel_conn.py      # neomodel 连接初始化
├── schema.py             # 约束/索引安装
└── neomodel_store.py     # 统一 Neo4j 会话与执行器（neomodel）

backend/src/app/api/v1/kg.py           # KG API（新增/完善端点）
backend/src/app/core/settings.py       # 配置入口（增加 KG_* 配置）
backend/tests/test_kg_pipeline.py      # 端到端与单元测试
scripts/kg_smoke.ps1                   # 一键冒烟
```

> **说明**：如需新增工具文件，只能放入 `backend/src/app/domain/kg/_utils/`，且需在本文新增“白名单”清单。

---

## 2. 运行前置与依赖（固定版本）

### 2.1 Python 依赖（追加到 `requirements.txt`）

```
# 本模块新增（固定安装）
neomodel==5.0.1
spacy==3.7.4
rapidfuzz==3.9.6
numpy==1.26.4
```

> 说明：
>
> 1. **仅安装 spaCy**（用于分词/句切分/NER/依存句法），**不安装 transformers / sentence-transformers / scispacy**。
> 2. 本项目已全局依赖 `httpx`，无需在本模块重复声明；RE 与 Embedding **全部通过 API** 调用完成（见 2.2）。

> **禁止** 在 builder 中对**整篇文档**进行 LLM 抽取。允许在 **句级/段级（按 chunk）** 通过项目内 `llm_service` 调用通用 LLM 执行 **关系抽取（RE）** 的**结构化 JSON** 输出；**NER 不使用 LLM**，由 spaCy 完成。

### 2.2 外部 API 资源（RE / Embedding）

* **关系抽取（RE）**：调用 `llm_service` 统一路由的通用 LLM（默认 **SiliconFlow** 提供商），模型示例：`Qwen/Qwen2.5-7B-Instruct` 或等价兼容模型。**不下载本地 RE 模型**。
* **Embedding（实体链接）**：调用 `llm_service` 的 Embedding 接口（默认 **SiliconFlow** + `BAAI/bge-m3` 或等价多语模型）。**不安装 sentence-transformers**。

> 运行策略：严格按 **句级/段级** 发送最小上下文（<= 800 汉字）；超限截断；返回 **受控 JSON**（见 5.2.1）。

---

## 3. 配置（`settings.py` 固定键名）

在 `Settings` 中新增以下字段（下划线分隔、可被环境变量覆盖）：

```python
class Settings(BaseSettings):
    # —— KG 主开关 ——
    KG_ENABLED: bool = True

    # —— 语言（仅 'zh' 或 'en'；本手册以中文为既定）——
    KG_LANGUAGE: Literal['zh', 'en'] = 'zh'

    # —— 抽取阈值（固定，不提供开关）——
    KG_MIN_TERM_LEN: int = 2            # 概念最小字符数
    KG_RE_MIN_CONF: float = 0.55        # RE 最小置信度（LLM 输出中的 confidence 字段低于此阈值丢弃）

    # —— 链接相似度（Embedding 相似度阈值）——
    KG_LINK_MIN_SIM: float = 0.82
    KG_LINK_TOPK: int = 3

    # —— 并发与批量 ——
    KG_MAX_WORKERS: int = 50
    KG_TX_BATCH_SIZE: int = 256

    # —— 提供商（固定走 llm_service，不落地模型）——
    KG_RE_PROVIDER: str = 'llm'                 # 关系抽取统一使用通用 LLM
    KG_RE_MODEL: str = 'Qwen/Qwen2.5-7B-Instruct'
    KG_EMBEDDING_MODEL: str = 'BAAI/bge-m3'     # 实体链接使用的向量模型（API 侧实现）

    # —— Neo4j / neomodel 连接 ——
    NEO4J_BOLT_URL: str = 'bolt://neo4j:neo4j@localhost:7687'  # 形如 bolt://user:pass@host:7687
    NEO4J_MAX_CONNECTION_LIFETIME: int = 3600
```

**环境变量示例（**\`\`**）**

```
APP_KG__ENABLED=true
APP_KG__LANGUAGE=zh
APP_KG__RE_MIN_CONF=0.55
APP_KG__LINK_MIN_SIM=0.82
APP_KG__TX_BATCH_SIZE=256
```

### 3.1 启动顺序（必须执行）

1. 在应用启动时调用 `init_neo4j(settings)`（文件：`backend/src/app/infrastructure/graph_store/neomodel_conn.py`）。
2. 紧接着执行 `install_schema()`（文件：`backend/src/app/infrastructure/graph_store/schema.py`）。
3. 然后启动 FastAPI 应用。

### 3.2 连接初始化（`neomodel_conn.py`）

```python
from neomodel import db

__all__ = ["init_neo4j"]

def init_neo4j(settings) -> None:
    """设置 neomodel 连接（应用启动时调用一次）。"""
    db.set_connection(settings.NEO4J_BOLT_URL)
    # 连接参数按需可在 URL 中指定；不在代码里二次覆盖。
```

---

## 4. 数据模型（节点/关系/索引：固定）

### 4.1 节点标签（仅允许以下）

`Concept`, `Chapter`, `Subchapter`, `Method`, `Example`, `Dataset`, `Equation`, `Doc`, `Chunk`

### 4.2 关系类型（仅允许以下）

* 结构：`PART_OF`（Subchapter→Chapter）、`HAS_SECTION`（Chapter→Subchapter）、`HAS_CHUNK`（Doc→Chunk）
* 语义：`DEFINES`, `EXPLAINS`, `REQUIRES`, `SIMILAR_TO`, `CONTRASTS_WITH`, `IMPLEMENTS`
* 桥接：`MENTIONS`（Chunk→Entity）

### 4.3 节点属性（最小集合）

`id, name, type, desc, aliases[], scope, created_at, updated_at`

### 4.4 关系属性（最小集合）

`rid, type, src(section_id), scope(book_id or section_id), confidence, weight, created_at, evidence`

### 4.5 架构安装（通过 `schema.py` 一次性执行）

文件：`backend/src/app/infrastructure/graph_store/schema.py`

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

> 执行位置：应用启动顺序中 `init_neo4j(settings)` 之后调用 `install_schema()`；`scripts/kg_smoke.ps1` 亦应调用。

### 4.6 neomodel 模型定义（固定）

文件：`backend/src/app/domain/kg/models.py`

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

---

## 5. 流水线（端到端强约束）

### 5.1 统一入口（禁止旁路）

`KGPipeline.run(section: SectionInput) -> KGPipelineResult`

```python
# backend/src/app/domain/kg/pipeline.py
from .builder import KGBuilder
from .normalizer import KGNormalizer
from .linker import EntityLinker
from .idempotent import IdGen
from .store import KGStore
from .merger import BookMerger

class KGPipeline:
    def __init__(self, settings):
        self.builder = KGBuilder(settings)
        self.normalizer = KGNormalizer(settings)
        self.linker = EntityLinker(settings)
        self.idgen = IdGen(settings)
        self.store = KGStore(settings)
        self.merger = BookMerger(settings)

    def run(self, section: dict) -> dict:
        """section = {
            'section_id': 'sec_xxx',
            'book_topic': '大型语言模型',
            'chapter_title': 'RAG 基础',
            'subchapter_title': '向量检索',
            'chunks': [
                {'id': 'doc1#p3', 'text': '...'},
                ...
            ]
        }"""
        # 1) 抽取（NER/RE）
        draft = self.builder.extract(section)
        # 2) 规范化
        draft = self.normalizer.normalize(draft)
        # 3) 实体链接（对齐既有图谱）
        linked = self.linker.link(draft)
        # 4) 生成 ID/RID
        ready = self.idgen.assign(linked, section)
        # 5) 小节级入库（Section Scope）
        self.store.write_section(ready, section['section_id'])
        # 6) 整书合并（Book Scope）
        book_id = self.merger.merge_book(section['book_topic'])
        return {'section_id': section['section_id'], 'book_id': book_id, 'stats': self.store.stats}
```

### 5.2 抽取（`builder.py`）

* **粒度**：以 **Chunk（段落）** 为单位；内部再做**句切分**。
* **NER**：使用 **spaCy** 抽取候选概念（最小长度、停用词过滤）。
* **RE**：对每个**句子**调用 `llm_service` → 通用 LLM（默认 SiliconFlow）输出**受控 JSON** 的 `(head, relation, tail, confidence, evidence)` 三元组。**禁止**整篇/整段直接让 LLM“自由发挥”。
* **去噪**：丢弃 `confidence < KG_RE_MIN_CONF`；head/tail 必须能在 NER 或文本片段中对齐；relation 必须能规约到**枚举**（见 8.4）。

```python
class KGBuilder:
    def __init__(self, settings):
        self.nlp = load_spacy('zh_core_web_sm')  # 仅 spaCy，本地
        self.min_len = settings.KG_MIN_TERM_LEN
        self.conf_threshold = settings.KG_RE_MIN_CONF

    def extract(self, section: dict) -> dict:
        concepts, relations = [], []
        for ch in section['chunks']:
            doc = self.nlp(ch['text'])
            # 1) NER：收集候选概念
            ents = [e.text for e in doc.ents if len(e.text) >= self.min_len]
            concepts.extend({'name': t, 'mentions': [ch['id']]} for t in set(ents))
            # 2) RE：句级调用 llm_service（受控 JSON）
            for sent in doc.sents:
                payload = {
                    'task': 're',
                    'text': sent.text,
                    'language': 'zh',
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'relations': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'head': {'type': 'string'},
                                        'relation': {'type': 'string'},
                                        'tail': {'type': 'string'},
                                        'confidence': {'type': 'number'}
                                    },
                                    'required': ['head','relation','tail']
                                }
                            }
                        },
                        'required': ['relations']
                    }
                }
                res = llm_service.call_structured(payload)  # 统一路由
                for r in res.get('relations', []):
                    rel = normalize_relation(r['relation'])  # 映射到枚举
                    if rel and r.get('confidence', 1.0) >= self.conf_threshold:
                        relations.append({
                            'src_name': r['head'],
                            'tgt_name': r['tail'],
                            'type': rel,
                            'confidence': r.get('confidence', 1.0),
                            'evidence': ch['id']
                        })
        return {'concepts': dedup(concepts), 'relations': dedup(relations)}
```

#### 5.2.1 RE API（受控 JSON）合同

* **调用入口**：内部统一走 `llm_service`；Provider 默认 **SiliconFlow**；温度固定 `0.1`；不允许流式。
* **输入**：单句文本（来自 chunk 的句切分），可附上候选实体清单 `candidates=[...]` 以降低幻觉。
* **输出**：

```json
{"relations":[{"head":"RAG","relation":"REQUIRES","tail":"向量检索","confidence":0.91}]}
```

* **后处理**：

  * `relation` 必须映射到枚举：`DEFINES|EXPLAINS|REQUIRES|SIMILAR_TO|CONTRASTS_WITH|IMPLEMENTS|PART_OF`；否则丢弃。
  * `head/tail` 必须能在句内出现或与 NER 候选对齐；否则丢弃。
  * 每条关系绑定 `evidence=chunk_id`。

### 5.3 规范化（`normalizer.py`）

* 小写化、全半角、去噪；
* 同义/别名映射（静态词典 + 规则）；
* 术语词形归一（英文词形还原）。

```python
class KGNormalizer:
    def normalize(self, draft: dict) -> dict:
        # 归一 name/aliases；去重；剔除过短项
        return draft
```

### 5.4 实体链接（`linker.py`）

* **先规则**：名称规范化后做**完全/别名匹配**；
* **再语义**：通过 **Embedding API**（SiliconFlow + `BAAI/bge-m3`）计算相似度；`cosine ≥ KG_LINK_MIN_SIM` 复用已有节点，否则新建；
* **不安装本地 sentence-transformers**；不做本地向量推理。

```python
class EntityLinker:
    def __init__(self, settings):
        self.threshold = settings.KG_LINK_MIN_SIM
        self.knn = preload_concept_vectors()  # 从 Neo4j/Qdrant 预取 name/alias 向量

    def link(self, draft: dict) -> dict:
        out = []
        for c in draft['concepts']:
            # 规则匹配
            found = exact_or_alias_match(c['name'])
            if found:
                c['existing_id'] = found['id']
                out.append(c)
                continue
            # 语义匹配（API）
            v = embedding_api.embed(c['name'])
            hits = self.knn.search(v, top_k=3)
            if hits and hits[0].score >= self.threshold:
                c['existing_id'] = hits[0].id
            out.append(c)
        draft['concepts'] = out
        return draft
```

### 5.5 幂等与 ID（`idempotent.py`）

* 节点 `id = concept:{slug(name)}:{md5(topic|chapter|subchapter)[:6]}`；
* 关系 `rid = md5(type|source_id|target_id|scope)[:16]`。

```python
class IdGen:
    def assign(self, linked: dict, section: dict) -> dict:
        # 对 new 概念生成 id；对每条关系生成 rid；补齐 src/scope/evidence
        return ready
```

### 5.6 入库（`store.py`）

* 通过 neomodel 的 `db` 执行；
* **必须** 批量事务（`KG_TX_BATCH_SIZE`）；
* 删除旧 Section 边 → MERGE 节点 → MERGE 关系（以 `rid` 幂等）；
* 失败回滚并抛出。

```python
from typing import Iterable
from itertools import islice
from neomodel import db
from .models import Concept, Chunk
from app.infrastructure.graph_store.neomodel_store import Neo4jStore

class KGStore:
    """使用 neomodel 完成小节级写入（先删旧边 → 节点 MERGE → 关系 MERGE）。"""

    def __init__(self, settings):
        self.batch = settings.KG_TX_BATCH_SIZE
        self.stats = {"nodes": 0, "edges": 0}

    def write_section(self, ready: dict, section_id: str) -> None:
        self._delete_section_edges(section_id)
        self._merge_concepts_batched(ready.get('concepts', []))
        self._merge_evidence_chunks(ready.get('concepts', []))
        self._merge_relations_batched(ready.get('relations', []))

    def _delete_section_edges(self, section_id: str) -> None:
        Neo4jStore.run_cypher("MATCH ()-[r]-() WHERE r.scope = $scope DELETE r", {"scope": section_id})

    def _merge_concepts_batched(self, concepts: list[dict]) -> None:
        for chunk in _chunked(concepts, self.batch):
            with db.transaction:
                for c in chunk:
                    node = Concept.nodes.get_or_none(id=c['id'])
                    if node is None:
                        Concept(id=c['id'], name=c['name'], type='Concept', aliases=c.get('aliases', [])).save()
                        self.stats["nodes"] += 1
                    else:
                        if c.get('name') and node.name != c['name']:
                            node.name = c['name']
                        if c.get('aliases'):
                            node.aliases = sorted(set((node.aliases or []) + c['aliases']))
                        node.touch()

    def _merge_evidence_chunks(self, concepts: list[dict]) -> None:
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

    def _merge_relations_batched(self, rels: list[dict]) -> None:
        for batch in _chunked(rels, self.batch):
            with db.transaction:
                for r in batch:
                    self._merge_rel(r)
                    self.stats["edges"] += 1

    @staticmethod
    def _merge_rel(r: dict) -> None:
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
        Neo4jStore.run_cypher(cypher, params)


def _chunked(iterable: Iterable, size: int):
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            return
        yield batch
```

### 5.7 合并（`merger.py`）

* 生成 `book_id = book:{slug(topic)}:{md5(topic)[:8]}`；
* 删除旧 `scope=book_id` 的全部关系；
* 汇总 Section 关系 → 写入 Book Scope（语义边，按 `(type, source, target)` 聚合）。

```python
from .idempotent import IdGen
from app.infrastructure.graph_store.neomodel_store import Neo4jStore

class BookMerger:
    def __init__(self, settings):
        self.settings = settings
        self.idgen = IdGen(settings)

    def merge_book(self, topic: str) -> str:
        book_id = f"book:{self.idgen.slug(topic)}:{self.idgen.md5(topic)[:8]}"
        Neo4jStore.run_cypher("MATCH ()-[r]-() WHERE r.scope = $scope DELETE r", {"scope": book_id})
        cypher = (
            "MATCH (s)-[r]-(t) WHERE r.src IS NOT NULL "
            "WITH DISTINCT type(r) AS typ, s.id AS sid, t.id AS tid "
            "WITH typ, sid, tid, $scope AS scope "
            "WITH typ, sid, tid, scope, toLower(typ) + '|' + sid + '|' + tid + '|' + scope AS sig "
            "WITH typ, sid, tid, scope, right(toHex(apoc.util.md5(sig)),16) AS rid "
            "MATCH (ss {id:sid}), (tt {id:tid}) "
            "MERGE (ss)-[e:%s {rid:rid}]->(tt) "
            "SET e.type=typ, e.src='__book_merge__', e.scope=scope, e.confidence=1.0, e.weight=1.0, e.created_at=coalesce(e.created_at, datetime())"
        )
        for typ in ("DEFINES","EXPLAINS","REQUIRES","SIMILAR_TO","CONTRASTS_WITH","IMPLEMENTS"):
            Neo4jStore.run_cypher(cypher % typ, {"scope": book_id})
        return book_id
```

---

## 6. Neo4j 交互（统一网关）

`backend/src/app/infrastructure/graph_store/neomodel_store.py` 提供以下**固定**方法（若缺失则补齐）：

```python
from typing import Iterable
from neomodel import db

class Neo4jStore:
    """提供最小访问面以供其他层调用；内部全部走 neomodel 的 db。"""

    @staticmethod
    def run_cypher(query: str, params: dict | None = None) -> list[dict]:
        results, meta = db.cypher_query(query, params or {})
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

> 强制要求：任何需要执行 Cypher 的地方必须通过本网关；禁止在项目中实例化 Neo4j 原生 Driver，所有访问通过 neomodel 连接层完成。

---

## 7. API 合同（Contract-First，不得更改路径）

### 7.1 小节构建（触发流水线）

* **POST** `/api/v1/kg/sections:build`
* **Body**（固定 Schema）：

```json
{
  "section_id": "sec_20250912_0001",
  "book_topic": "大型语言模型",
  "chapter_title": "RAG 基础",
  "subchapter_title": "向量检索",
  "chunks": [
    {"id": "doc1#p3", "text": "向量检索是..."},
    {"id": "doc1#p4", "text": "RAG 依赖于..."}
  ]
}
```

* **200 响应**：`{"section_id":"...","book_id":"book:...","stats":{"nodes":N,"edges":M}}`

### 7.2 整书查询（前端优先）

* **GET** `/api/v1/kg/books/{book_id}` → 返回 `{nodes:[...], edges:[...]}`

### 7.3 小节查询（降级使用）

* **GET** `/api/v1/kg/sections/{section_id}`

> **注意**：前端 `KgGraph.vue` 必须优先请求 **Book Scope**，失败再降级 Section。

---

## 8. 前端对接（强约束）

### 8.1 组件：`frontend/src/components/KgGraph.vue`

* **数据源优先级**：`bookId > sectionId`（禁止反转）；
* **布局**：默认 `cose`；提供“重置布局/刷新数据”按钮；
* **节点样式**：

  * `Concept`：圆角矩形；
  * `Chapter/Subchapter`：圆形；
  * 关系按 `type` 颜色区分；
* **点击行为**：控制台打印 `id/name/type`，下一期再接详情面板。

### 8.2 路由：`/runs/:id` 中 KG 页签

* 进入时调用：`GET /api/v1/kg/books/{book_id}`；
* 如果 404/空，则改为：`GET /api/v1/kg/sections/{latest_section_id}`。

---

## 9. 测试与冒烟（必须通过）

### 9.1 单元测试模板：`backend/tests/test_kg_pipeline.py`

```python
from app.domain.kg.pipeline import KGPipeline

FAKE_SEC = {
  'section_id': 'sec_demo',
  'book_topic': '测试主题',
  'chapter_title': 'Ch1',
  'subchapter_title': 'Sc1',
  'chunks': [
    {'id': 'doc1#p1', 'text': '向量检索属于 RAG 的关键组成。'},
    {'id': 'doc1#p2', 'text': 'RAG 依赖于 检索。'}
  ]
}

def test_run(neo4j, settings):
    out = KGPipeline(settings).run(FAKE_SEC)
    assert out['book_id'].startswith('book:')
```

### 9.2 冒烟脚本：`scripts/kg_smoke.ps1`

```
# 1) 提交约束
# 2) 调用 sections:build
# 3) 查询 book 图返回非空
# 打印 OK
```

---

## 10. 运维与性能（默认值，不得擅改）

* `KG_TX_BATCH_SIZE=256`；
* 写入顺序：**删除旧 Section 关系 → MERGE 节点 → MERGE 关系**；
* 超时：单次事务 ≤ 30s；失败重试 2 次（指数退避）。

---

## 11. 安全与合规

* 所有 `LLM` 调用必须通过项目的 `llm_service` 路由；
* 默认关闭 `KG_USE_LLM_FALLBACK`；
* 不得将整段文本内容写入节点属性 `desc` 超过 2KB（超限截断）。

---

## 12. 变更控制

* 对本文任何改动必须提交 PR，标题以 `[KG-SPEC]` 开头，且在合并前完成：

  1. 端到端冒烟；
  2. 前端渲染验证；
  3. 生产约束重复执行验证（无副作用）。

---

## 13. 附录：查询与调试

### 13.1 证据回链（从实体取证据 Chunk）

```cypher
MATCH (e:Concept {name:$name})
OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(e)
WITH e, collect(c.id)[..10] AS chunk_ids
MATCH p = (e)-[r*1..2]-(nbr)
RETURN e, nodes(p) AS nodes, relationships(p) AS rels, chunk_ids
LIMIT 50;
```

### 13.2 由 Chunk 反查实体与邻域

```cypher
MATCH (c:Chunk {id:$chunk_id})-[:MENTIONS]->(e:Concept)
OPTIONAL MATCH p = (e)-[r*1..2]-(nbr)
RETURN e, nodes(p) AS nodes, relationships(p) AS rels
LIMIT 30;
```

---

### 13.3 异常排查清单

* 图为空：确认 `sections:build` 请求体是否包含 `chunks`；
* 节点未复用：检查 `linker` 相似度阈值 `KG_LINK_MIN_SIM` 是否过高；
* 写入很慢：调低 `KG_TX_BATCH_SIZE` 至 128；
* 前端无图：确认优先请求的是 **Book Scope** 接口；

---

## 14. 迁移注意事项（一次性操作）

* 旧实现中若遗留 `rid` 冲突（同源/同目标/同类型但 `scope` 不同），清理逻辑：

  * 书级合并前先 `MATCH ()-[r]-() WHERE r.src <> r.scope AND r.scope STARTS WITH 'book:' REMOVE r.rid`；
  * 再按合并流程重建书级边（`rid` 以书级 scope 重新计算）。
* 若未安装 APOC，请在 `merger.py` 中改为由 `IdGen` 产生 `rid`，并删除 `toHex(apoc.util.md5(...))` 相关语句。

---

## 15. 开发者不得擅改的清单（硬性约束）

* **不得**新增/更名/删除任何 neomodel 模型类与字段；
* **不得**在 neomodel 之外再引入其他 ORM/驱动；
* **不得**修改批量大小、事务边界与 rid 计算方式；
* **不得**将大段文本（>2KB）写入 `desc`；
* **必须**先删旧 Section 边，再写新数据；
* **必须**以 `rid` 作为关系唯一键进行 `MERGE` 幂等写入。

---

### 附：`IdGen.assign` 输出约定（与 5.6 严格配合）

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
