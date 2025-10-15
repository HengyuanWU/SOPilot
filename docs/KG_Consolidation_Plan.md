# 知识图谱合并：问题分析与实施方案

## 0. 项目现状：当前知识图谱构建流程

### 0.1. 系统架构

SOPilot 项目当前采用分层架构来构建知识图谱，核心模块位于 `backend/src/app/domain/kg/`。整个流程由以下组件组成：

```
API 层 (kg.py)
    ↓
服务层 (service.py)
    ↓
流水线编排 (pipeline.py)
    ↓
六个核心处理模块：
    1. Builder (builder.py)     - NER & RE 提取
    2. Normalizer (normalizer.py) - 数据规范化
    3. EntityLinker (linker.py)   - 实体链接
    4. IdGen (idempotent.py)      - ID 生成
    5. Store (store.py)           - 数据存储
    6. Merger (merger.py)         - 书籍级合并
```

### 0.2. 核心流程：以 Section 为处理单元

#### 0.2.1. API 入口

系统通过 `POST /api/v1/kg/sections:build` 接口接收单个小节（section）的构建请求：

```python
# backend/src/app/api/v1/kg.py (第41-75行)
@router.post("/sections:build", response_model=KGSectionBuildResponse)
async def build_kg_section(request: KGSectionBuildRequest, ...):
    # 构建section数据
    section_data = {
        "section_id": request.section_id,
        "book_topic": request.book_topic,
        "chapter_title": request.chapter_title,
        "subchapter_title": request.subchapter_title,
        "chunks": request.chunks,  # 文本块列表
    }
    
    # 调用服务层
    kg_service = KGService(settings)
    result = kg_service.build_section(section_data)
    ...
```

每次调用处理**一个 section**，该 section 包含多个 chunks（文本段落）。

#### 0.2.2. 流水线执行

服务层调用 `KGPipeline.run(section)` 方法，该方法执行以下六个步骤：

```python
# backend/src/app/domain/kg/pipeline.py (第178-225行)
def run(self, section: dict) -> dict:
    # 1) 抽取（NER/RE）
    draft = self.builder.extract(section)
    
    # 2) 规范化
    draft = self.normalizer.normalize(draft)
    
    # 3) 实体链接（对齐既有图谱）
    linked = self.linker.link(draft)
    
    # 4) 生成 ID/RID
    ready = self.idgen.assign(linked, section)
    
    # 5) 小节级入库（Section Scope）
    self.store.write_section(ready, section["section_id"])
    
    # 6) 书籍级合并（目前已禁用）
    # 注：原本每个section都会调用merger.merge_book()
    # 现已移除，由外层统一负责
    
    return {
        "section_id": section["section_id"],
        "book_id": None,
        "stats": self.store.stats,
    }
```

#### 0.2.3. Builder：原子化的 NER & RE

**这是问题的核心所在。** `KGBuilder.extract()` 方法以 section 为输入，执行以下操作：

```python
# backend/src/app/domain/kg/builder.py (第79-108行)
def extract(self, section: dict) -> dict:
    concepts = []
    relations = []
    
    # 遍历当前section的所有chunks
    for chunk in section.get("chunks", []):
        text = chunk.get("text", "")
        chunk_id = chunk.get("id", "")
        
        # 1. NER：使用 spaCy 提取概念（实体 + 名词）
        chunk_concepts = self._extract_concepts(text, chunk_id)
        concepts.extend(chunk_concepts)
        
        # 2. RE：对每个句子调用 LLM 提取关系
        candidate_names = [c['name'] for c in chunk_concepts]
        chunk_relations = self._extract_relations(text, chunk_id, candidate_names)
        relations.extend(chunk_relations)
    
    # 去重（仅在当前section内部去重）
    concepts = self._dedup_concepts(concepts)
    relations = self._dedup_relations(relations)
    
    return {"concepts": concepts, "relations": relations}
```

**关键特征**：
- **输入作用域**：仅限当前 section 的文本。
- **NER**：使用 spaCy (`zh_core_web_sm`) 提取命名实体和名词短语，作为候选概念。
- **RE**：对每个句子调用 LLM（通过 `llm_service.call_structured()`），提取三元组 `(head, relation, tail)`。
- **去重范围**：仅在当前 section 内部基于 `name` 去重。

#### 0.2.4. 关系提取的 LLM 调用

```python
# backend/src/app/domain/kg/builder.py (第195-281行)
def _extract_relations_llm(self, sent: str, chunk_id: str, candidates: list[str] = None):
    # 调用 llm_service，使用受控 JSON Schema
    schema = {
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
                    'required': ['head', 'relation', 'tail']
                }
            }
        },
        'required': ['relations']
    }
    
    # 调用 LLM（SiliconFlow，温度=0.1）
    res = llm_service.call_structured({'task': 're', 'text': sent, ...})
    
    # 后处理：
    # - 规范化关系类型（映射到预定义枚举 RELATION_TYPES）
    # - 过滤低置信度（< KG_RE_MIN_CONF）
    # - 验证 head/tail 是否在句子中出现
    ...
```

**支持的关系类型**（第28-53行）：
```python
RELATION_TYPES = {
    "DEFINES", "EXPLAINS", "REQUIRES", "SIMILAR_TO", 
    "CONTRASTS_WITH", "IMPLEMENTS", "PART_OF"
}
```

### 0.3. 问题根源：无状态、原子化处理

#### 0.3.1. 上下文隔离（Context Isolation）

当系统处理 `Section A` 时：
- **可见数据**：仅限 `Section A` 的 chunks。
- **不可见数据**：`Section B`、`Section C` 或任何其他 section 的内容。

这意味着：
- NER 无法利用跨 section 的术语一致性（例如，`Section A` 中的 "数据库" 和 `Section C` 中的 "数据库" 是同一概念）。
- RE 无法发现跨 section 的关系（例如，`Section A` 定义了 "微服务"，`Section D` 解释了其优势，两者之间应有 `EXPLAINS` 关系）。

#### 0.3.2. 无状态节点创建（Stateless Node Creation）

`Builder.extract()` 的去重逻辑（第284-306行）仅在**当前 section 内部**生效：

```python
def _dedup_concepts(concepts: list[dict]) -> list[dict]:
    seen = {}
    for c in concepts:
        name = c["name"]
        if name in seen:
            seen[name]["mentions"].extend(c["mentions"])  # 合并 mentions
        else:
            seen[name] = c
    return list(seen.values())
```

**执行流程**：
1. 处理 `Section A`：提取到 `"数据库"` → 创建节点 `Node_1`。
2. 处理 `Section C`：提取到 `"数据库"` → **创建新节点 `Node_5`**（因为没有全局记忆）。

结果：同一个概念在图谱中存在多个节点，且这些节点互不相连。

#### 0.3.3. EntityLinker 的局限性

虽然流水线包含 `EntityLinker` 模块（第3步），但它的作用仅限于：
- 将**当前 section 提取的实体**链接到**已存储在 Neo4j 中的既有节点**。
- 这是一种"后验对齐"，而非"构建时全局去重"。

**问题**：
- 如果 `Section A` 和 `Section C` 并行处理，EntityLinker 无法在构建时就识别出重复。
- 即使串行处理，EntityLinker 也只能减少部分冗余，无法根本解决问题。

### 0.4. 当前流程总结

| 阶段 | 输入 | 输出 | 作用域 |
|------|------|------|--------|
| API 调用 | Section 数据 | Section ID + 统计 | 单个 section |
| Builder | Section chunks | Concepts + Relations | 单个 section |
| Normalizer | Draft 数据 | 规范化数据 | 单个 section |
| EntityLinker | 规范化数据 | 链接结果 | 单个 section（对齐已存储节点） |
| IdGen | 链接数据 | 带 ID 的数据 | 单个 section |
| Store | 带 ID 的数据 | 存储统计 | 单个 section |
| Merger | （已禁用） | - | - |

**核心特征**：
- **处理单元**：以 section 为粒度。
- **并行能力**：支持多个 section 并行处理（互不干扰）。
- **全局视野**：❌ **无**。每个 section 在处理时对其他 section 一无所知。

---

## 1. 问题分析

在对整本书（book）进行知识图谱构建后，我们观察到两个核心问题，这两个问题本质上是同一根源的不同表现。

### 1.1. 观察到的现象

1.  **图谱呈多分量结构 (Disconnected Components)**：最终生成的知识图谱并非一个单一、连贯的整体，而是由多个独立的、互不相连的子图（连通分量）组成。
2.  **概念节点重复出现 (Duplicate Nodes)**：同一个真实世界的概念（例如，`"微服务"`）在图谱中以多个不同节点的形式存在，并分散在上述不同的连通分量中。

这表明，不同章节（section）中本应关联的概念之间缺乏联系，导致了知识的碎片化。

### 1.2. 根本原因：原子化的章节处理流程

问题的根源在于项目当前`backend/src/app/domain/kg/builder.py`中的核心处理逻辑。该逻辑是**以`section`为单位进行原子化、无状态处理的**。

-   **上下文隔离 (Context Isolation)**：在处理`Section A`时，系统对`Section B`或任何其他`section`的内容一无所知。所有的概念提取（NER）和关系提取（RE）都严格限制在当前`section`的文本内部。这导致系统**天然无法发现和建立跨越`section`边界的关系**。

-   **无状态节点创建 (Stateless Node Creation)**：当系统在`Section A`中提取出`"数据库"`概念时，会为其创建一个节点。随后，当在`Section C`中再次遇到`"数据库"`时，由于处理`Section C`是一个独立的、无记忆的操作，系统无法识别出这与`Section A`的`"数据库"`是同一个概念。因此，它会**创建一个全新的、独立的节点**。

这种设计虽然简化了并行处理，但也正是它导致了最终图谱的割裂和节点冗余。

## 2. 解决方案：构建后全局合并 (Post-Processing Consolidation)

为了解决上述问题，我们采纳业界主流的SOTA（State-of-the-Art）方案，即**策略一：构建后的全局链接与合并**。

此方案将知识图谱的构建分为两个解耦的阶段：

1.  **阶段一：局部提取 (Local Extraction)**：保持现有流程不变，并行地、独立地从每个`section`中提取出局部的子图。
2.  **阶段二：全局合并 (Global Consolidation)**：在所有`section`的子图都生成后，运行一个独立的、全新的合并流程，将所有子图融合成一个单一、完整、无冗余的全局知识图谱。

### 2.1. 实施方案：`merge_graphs` 核心逻辑

我们将设计一个新的核心函数（或服务），其逻辑如下。

**函数签名 (示意)**：
```python
def merge_graphs(subgraphs: List[KnowledgeGraph]) -> KnowledgeGraph:
    # ... implementation ...
```

**输入**：一个`KnowledgeGraph`对象的列表，每个对象代表一个`section`的子图。
**输出**：一个统一的、合并后的`KnowledgeGraph`对象。

**核心算法步骤**：

1.  **初始化**:
    *   创建一个新的、空的`KnowledgeGraph`实例，命名为`merged_graph`，用于存放最终结果。
    *   创建一个核心映射字典 `name_to_merged_node_id = {}`。
        *   **键 (Key)**：概念的名称（`node.name`），例如`"微服务"`。
        *   **值 (Value)**：该概念在`merged_graph`中对应的**唯一**节点ID。
        *   此字典是实现节点去重的关键。

2.  **遍历所有子图 (Subgraph Iteration)**:
    *   按顺序遍历输入的`subgraphs`列表中的每一个`subgraph`。
    *   对于每个`subgraph`，创建一个临时的本地ID映射 `local_id_map = {}`，用于记录当前子图的旧节点ID到`merged_graph`中新节点ID的映射关系。

3.  **第一轮：节点合并 (Node Consolidation)**:
    *   遍历当前`subgraph`中的所有`nodes`。
    *   对于每一个`node`：
        *   检查`node.name`是否存在于全局的`name_to_merged_node_id`字典中。
        *   **如果不存在**:
            *   说明这是我们第一次遇到这个概念。
            *   在`merged_graph`中创建一个**新的节点**（可以完整复制旧节点的属性）。
            *   获取这个新节点的ID (`new_node.id`)。
            *   更新全局字典：`name_to_merged_node_id[node.name] = new_node.id`。
            *   更新本地映射：`local_id_map[node.id] = new_node.id`。
        *   **如果已存在**:
            *   说明这个概念在之前的某个`subgraph`中已经遇到过了。
            *   从全局字典中获取该概念已有的唯一ID：`merged_id = name_to_merged_node_id[node.name]`。
            *   更新本地映射：`local_id_map[node.id] = merged_id`。

4.  **第二轮：关系迁移 (Edge Migration)**:
    *   在处理完当前`subgraph`的所有节点后，遍历其中的所有`edges`（关系）。
    *   对于每一个`edge`：
        *   使用`local_id_map`来查找其`source_id`和`target_id`在`merged_graph`中对应的新ID。
            *   `new_source_id = local_id_map[edge.source_id]`
            *   `new_target_id = local_id_map[edge.target_id]`
        *   在`merged_graph`中创建一条新的`edge`，其`source_id`和`target_id`使用上述查询到的新ID，其他属性（如关系类型`label`）直接复制。
        *   **（可选）关系去重**：在添加新关系前，可以检查`merged_graph`中是否已存在完全相同的三元组 (`new_source_id`, `label`, `new_target_id`)，避免重复添加。

5.  **返回结果**:
    *   当所有`subgraphs`都处理完毕后，返回最终的`merged_graph`。

这个流程清晰地将节点去重和关系重定向分离开来，确保了最终图谱的全局一致性和完整性。
