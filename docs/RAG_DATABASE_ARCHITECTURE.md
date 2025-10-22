# RAG 數據庫架構文檔

## 執行摘要

本項目的 RAG（檢索增強生成）系統採用**雙存儲架構**，同時使用 **Qdrant** 和 **Neo4j** 兩種數據庫，各司其職，協同工作。

## 📊 架構概覽

```
┌─────────────────────────────────────────────────────────┐
│                    RAG Pipeline                          │
│                                                          │
│  ┌──────────────┐           ┌──────────────┐           │
│  │   文檔入庫    │           │   索引建立    │           │
│  │              │           │              │           │
│  │  分塊→嵌入   │           │ 向量+圖譜存儲 │           │
│  └──────────────┘           └──────────────┘           │
│                                                          │
│  ┌──────────────┐           ┌──────────────┐           │
│  │  雙通道檢索   │──────────▶│  合併重排    │           │
│  │              │           │              │           │
│  │ Vector + KG  │           │   Top-K結果  │           │
│  └──────────────┘           └──────────────┘           │
└─────────────────────────────────────────────────────────┘
           │                           │
           ▼                           ▼
    ┌─────────────┐           ┌─────────────┐
    │   Qdrant    │           │   Neo4j     │
    │  向量數據庫  │           │  圖數據庫    │
    └─────────────┘           └─────────────┘
```

## 1. 雙存儲架構說明

### 1.1 Qdrant 向量數據庫

**用途**：語義相似度檢索（向量檢索通道）

**交互方式**：
- 使用 `qdrant-client` Python SDK
- **不使用 Cypher**，使用 Qdrant 原生 API

**存儲內容**：
- 文檔塊的向量表示（embeddings）
- 向量維度：根據嵌入模型確定（如 BAAI/bge-m3）
- Payload 元數據：
  - `chunk_id`: 塊ID
  - `doc_id`: 文檔ID
  - `text`: 文本內容
  - `created_at`: 創建時間
  - `original_chunk_id`: 原始塊ID（用於幂等性）

**主要操作**：
```python
# 連接（無需 Cypher）
from qdrant_client import QdrantClient
client = QdrantClient(url="http://qdrant:6333")

# 向量搜索
results = client.search(
    collection_name="kb_chunks",
    query_vector=query_embedding,
    limit=top_k
)
```

**相關文件**：
- `backend/src/app/infrastructure/rag/vectorstores/qdrant_store.py`
- `backend/src/app/infrastructure/rag/retrievers/retriever_vector.py`

### 1.2 Neo4j 圖數據庫

**用途**：結構化關係檢索（知識圖譜通道）

**交互方式**：
- 使用 `neo4j` Python Driver
- **使用 Cypher 查詢語言**

**存儲內容**：
1. **文檔節點** (Document)
   - 屬性：id, filename, filepath, content_type, size, checksum, metadata
   
2. **塊節點** (Chunk)
   - 屬性：id, doc_id, chunk_index, content, content_hash, vector_id
   
3. **實體節點** (Entity)
   - 屬性：id, name, type, properties
   
4. **關係**：
   - `Document -[:HAS_CHUNK]-> Chunk`
   - `Chunk -[:MENTIONS]-> Entity`
   - `Entity -[:RELATED_TO|PART_OF|INSTANCE_OF]-> Entity`

**主要操作（使用 Cypher）**：
```python
# 創建文檔節點
cypher = """
MERGE (d:Document {id: $id})
SET d.filename = $filename,
    d.filepath = $filepath,
    d.updated_at = datetime()
RETURN d.id as doc_id
"""
client.execute_cypher(cypher, params)

# 查找相關塊
cypher = """
MATCH (e:Entity)-[:MENTIONS]-(c:Chunk)
WHERE e.id IN $entity_ids
RETURN DISTINCT c.id, c.content
ORDER BY count(e) DESC
LIMIT $limit
"""
```

**相關文件**：
- `backend/src/app/infrastructure/rag/kgstores/document_store.py`
- `backend/src/app/infrastructure/rag/kgstores/neo4j_queries.py`
- `backend/src/app/infrastructure/rag/retrievers/retriever_kg.py`
- `backend/src/app/infrastructure/graph_store/neo4j_client.py`

## 2. 雙通道檢索流程

### 2.1 文檔入庫流程

```
原始文檔
    ↓
文檔分塊 (DocumentChunker)
    ↓
生成向量 (Embedder)
    ↓
    ├─→ Qdrant: 存儲向量 + payload
    └─→ Neo4j: 創建 Document/Chunk 節點 (Cypher)
         ↓
    實體提取 (EntityExtractor)
         ↓
    建立 MENTIONS 關係 (Cypher)
```

### 2.2 檢索流程

```
用戶查詢
    ↓
    ├─→ 向量通道（Qdrant）
    │   - 查詢向量化
    │   - 向量相似度搜索
    │   - 返回 Top-K 相似塊
    │
    └─→ KG通道（Neo4j + Cypher）
        - 實體識別
        - 圖遍歷查詢
        - 返回相關實體的塊
    ↓
證據合併 (EvidenceMerger)
    - alpha=0.7 向量權重
    - beta=0.3 KG權重
    ↓
重排序 (可選，BGEReranker)
    ↓
最終 Top-K 結果
```

## 3. 關鍵問題回答

### Q1: 現有代碼使用的是 Cypher 嗎？

**回答**：部分正確。

- **Qdrant 交互**：不使用 Cypher，使用 Qdrant Python SDK
- **Neo4j 交互**：使用 Cypher 查詢語言

**代碼位置**：
- Qdrant 交互（無 Cypher）：`qdrant_store.py`
- Neo4j 交互（使用 Cypher）：`document_store.py`, `neo4j_queries.py`

### Q2: 與 Qdrant 交互用 Cypher 合理嗎？

**回答**：不合理，實際上也不是這樣做的。

Qdrant 是向量數據庫，有自己的 API：
```python
# Qdrant 正確的交互方式
client.search(
    collection_name="kb_chunks",
    query_vector=vector,
    limit=10
)

# 不是使用 Cypher！
```

Cypher 是 Neo4j 圖數據庫的查詢語言，兩者不兼容。

### Q3: RAG 使用的數據庫是什麼？

**回答**：同時使用 Qdrant 和 Neo4j。

這是一個**雙通道混合檢索架構**：

| 組件 | 數據庫 | 查詢語言/API | 用途 |
|------|--------|-------------|------|
| 向量檢索 | Qdrant | Qdrant API | 語義相似度搜索 |
| KG 檢索 | Neo4j | Cypher | 結構化關係檢索 |

**優勢**：
- Qdrant：快速語義檢索，處理「相似內容」
- Neo4j：利用知識圖譜，處理「關聯內容」
- 雙通道：召回更全面，結果更準確

## 4. 配置示例

### 4.1 環境變量配置

```env
# Qdrant 配置
QDRANT__URL=http://qdrant:6333
QDRANT__COLLECTION=kb_chunks
QDRANT__DISTANCE=cosine

# Neo4j 配置
NEO4J__URI=neo4j://neo4j:7687
NEO4J__USER=neo4j
NEO4J__PASSWORD=your_password
NEO4J__DATABASE=neo4j

# RAG 配置
RAG__VECTOR_TOP_K=12
RAG__KG_TOP_K=8
RAG__TOP_K=4
RAG__ALPHA=0.7  # 向量權重
RAG__BETA=0.3   # KG 權重
```

### 4.2 Docker Compose 配置

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  neo4j:
    image: neo4j:5.12
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    volumes:
      - neo4j_data:/data
```

## 5. 代碼結構

```
backend/src/app/infrastructure/rag/
├── pipeline.py              # RAG 主管線
├── chunker.py              # 文檔分塊
├── embedder.py             # 向量嵌入
│
├── vectorstores/
│   └── qdrant_store.py     # Qdrant 封裝（無 Cypher）
│
├── kgstores/
│   ├── document_store.py   # 文檔圖譜存儲（使用 Cypher）
│   └── neo4j_queries.py    # Neo4j 查詢（使用 Cypher）
│
├── retrievers/
│   ├── retriever_vector.py # 向量檢索器（Qdrant）
│   └── retriever_kg.py     # KG 檢索器（Neo4j + Cypher）
│
├── merger.py               # 證據合併
├── rerankers/              # 重排器
└── prompt_builder.py       # 提示構造
```

## 6. API 接口

RAG 系統通過 FastAPI 暴露接口：

```python
# 向量檢索測試
POST /api/v1/rag/test_vector
{
  "query": "查詢內容",
  "top_k": 5
}

# KG 檢索測試
POST /api/v1/rag/test_kg
{
  "query": "查詢內容",
  "top_k": 5,
  "hop": 2
}

# 雙通道檢索
POST /api/v1/rag/test_dual
{
  "query": "查詢內容",
  "top_k": 4,
  "include_kg": true
}
```

## 7. 性能特點

### Qdrant 向量檢索
- **優勢**：毫秒級響應，高並發支持
- **適用場景**：「找相似內容」
- **檢索數量**：Top 12（可配置）

### Neo4j KG 檢索
- **優勢**：利用實體關係，發現隱式關聯
- **適用場景**：「找相關內容」
- **檢索數量**：Top 8（可配置）

### 合併策略
- 加權合併：0.7 × 向量分數 + 0.3 × KG 分數
- 可選重排：使用 BGE Reranker
- 最終返回：Top 4（可配置）

## 8. 監控與維護

### 健康檢查

```python
# Qdrant 健康檢查
GET /api/v1/rag/status
{
  "qdrant": {
    "status": "healthy",
    "collection": "kb_chunks",
    "points_count": 1234
  },
  "neo4j": {
    "status": "healthy",
    "document_count": 10,
    "chunk_count": 1234,
    "entity_count": 567
  }
}
```

### 統計信息

```python
# KG 聯動統計
GET /api/v1/rag/kg_linking/statistics
{
  "document_count": 10,
  "chunk_count": 1234,
  "mentioned_entity_count": 567,
  "mentions_count": 2345
}
```

## 9. 最佳實踐

### 9.1 何時使用雙通道
- 需要高召回率的場景
- 內容有明確的實體關係
- 需要「相似+相關」的全面檢索

### 9.2 何時只用向量檢索
- 純語義匹配場景
- 沒有結構化知識圖譜
- 追求極致性能

### 9.3 權重調整建議
- 向量為主：alpha=0.8, beta=0.2
- 平衡模式：alpha=0.7, beta=0.3（默認）
- KG 為主：alpha=0.5, beta=0.5

## 10. 相關文檔

- [IMPROOVE_GUIDE.md](./IMPROOVE_GUIDE.md) - RAG 系統設計指南
- [KG_Consolidation_Plan.md](./KG_Consolidation_Plan.md) - 知識圖譜整合計劃
- [EMBEDDING_ARCHITECTURE.md](./EMBEDDING_ARCHITECTURE.md) - 嵌入架構文檔
- [項目架構文檔.md](./項目架構文檔.md) - 整體架構文檔

## 11. 總結

本項目 RAG 系統的數據庫架構是：

✅ **使用 Qdrant** - 向量檢索（不使用 Cypher）
✅ **使用 Neo4j** - 圖譜檢索（使用 Cypher）
✅ **雙通道架構** - 語義 + 結構，優勢互補

**不是「用 Qdrant 或 Neo4j」，而是「同時用 Qdrant 和 Neo4j」！**

---

**文檔版本**：v1.0
**創建日期**：2025-10-20
**維護者**：SOPilot 開發團隊






