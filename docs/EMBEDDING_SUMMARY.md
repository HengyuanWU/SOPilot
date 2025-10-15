# Embedding 配置完整总结

## 快速答案

**Q: SOPilot 在哪里配置 embedding 模型？**

**A: 有两个配置项：**

1. **RAG 系统**（用于文档检索）：
   ```bash
   APP_RAG__EMBED_MODEL=BAAI/bge-m3
   APP_RAG__EMBED_PROVIDER=siliconflow
   ```

2. **KG 系统**（用于实体链接）：
   ```bash
   APP_KG_EMBEDDING_MODEL=BAAI/bge-m3
   ```

**默认配置**：两者都使用 `BAAI/bge-m3` 模型，通过 SiliconFlow API 调用。

---

## 配置位置

### 1. 代码默认值

```python
# backend/src/app/core/settings.py

class RAGSettings(BaseModel):
    embed_model: str = "BAAI/bge-m3"  # 默认模型
    embed_provider: str = "siliconflow"  # 默认提供商

class AppSettings(BaseSettings):
    KG_EMBEDDING_MODEL: str = 'BAAI/bge-m3'  # KG系统默认模型
```

### 2. 环境变量（docker-compose.yml）

```yaml
backend:
  environment:
    # RAG embedding
    - APP_RAG__EMBED_MODEL=BAAI/bge-m3
    - APP_RAG__EMBED_PROVIDER=siliconflow
    
    # KG embedding
    - APP_KG_EMBEDDING_MODEL=BAAI/bge-m3
```

### 3. .env 文件

```bash
# backend/.env

APP_RAG__EMBED_MODEL=BAAI/bge-m3
APP_RAG__EMBED_PROVIDER=siliconflow
APP_KG_EMBEDDING_MODEL=BAAI/bge-m3
```

---

## 系统架构

### 调用链路

```
应用层 (RAG/KG)
    ↓
Embedder (backend/src/app/infrastructure/rag/embedder.py)
    ↓
LLM Router (backend/src/app/infrastructure/llm/router/core.py)
    ↓
SiliconFlow Adapter (backend/src/app/infrastructure/llm/router/adapters/siliconflow.py)
    ↓
SiliconFlow API (https://api.siliconflow.cn/v1/embeddings)
```

### 关键文件

| 文件路径 | 作用 |
|---------|------|
| `backend/src/app/core/settings.py` | 配置定义 |
| `backend/src/app/infrastructure/rag/embedder.py` | 向量化核心类 |
| `backend/src/app/infrastructure/llm/router/core.py` | LLM 路由 |
| `backend/src/app/infrastructure/llm/router/adapters/siliconflow.py` | SiliconFlow 适配器 |
| `backend/src/app/domain/kg/linker.py` | KG 实体链接（使用 embedder） |
| `backend/src/app/domain/kg/store.py` | KG 存储（使用 embedder） |

---

## 使用场景

### RAG 系统

**场景 1: 文档向量化**
```python
from app.infrastructure.rag.embedder import Embedder
from app.core.settings import get_settings

settings = get_settings()
embedder = Embedder(
    model_name=settings.rag.embed_model,  # BAAI/bge-m3
    provider=settings.rag.embed_provider   # siliconflow
)

# 批量向量化文档
chunks = ["文档块1", "文档块2", ...]
results = embedder.embed_batch(chunks)

# 存储到 Qdrant
for result in results:
    qdrant_store.add(vector=result.vector.tolist(), ...)
```

**场景 2: 查询向量化**
```python
# 用户查询
query = "什么是深度学习？"
query_vector = embedder.embed_single(query)

# 向量检索
similar_docs = qdrant_store.search(
    vector=query_vector.vector.tolist(),
    limit=10
)
```

### KG 系统

**场景 3: 实体链接**
```python
from app.domain.kg.linker import EntityLinker

linker = EntityLinker(settings, neo4j_client)

# 新提取的实体
new_concept = "神经网络"

# 查找相似的已有实体
existing_concepts = ["深度学习", "机器学习", "人工智能"]
similarities = linker.compute_similarities(new_concept, existing_concepts)

# 决策：相似度 > 阈值 → 复用；否则 → 新建
if max(similarities) > settings.KG_LINK_MIN_SIM:  # 0.82
    # 链接到已有实体
    linked = existing_concepts[similarities.index(max(similarities))]
else:
    # 创建新实体
    create_new_entity(new_concept)
```

---

## 支持的模型

| 模型名称 | 维度 | 提供商 | 特点 |
|---------|------|--------|------|
| **BAAI/bge-m3** | 1024 | SiliconFlow | **推荐** - 中英双语，综合性能优秀 |
| BAAI/bge-small-zh-v1.5 | 512 | SiliconFlow | 轻量级，速度快 |
| BAAI/bge-base-zh-v1.5 | 768 | SiliconFlow | 中等规模，平衡性能 |
| BAAI/bge-large-zh-v1.5 | 1024 | SiliconFlow | 大模型，最高精度 |
| text-embedding-ada-002 | 1536 | OpenAI | OpenAI 第二代 |
| text-embedding-3-small | 1536 | OpenAI | OpenAI 第三代小模型 |
| text-embedding-3-large | 3072 | OpenAI | OpenAI 第三代大模型 |

---

## 如何切换模型

### 步骤 1: 修改配置

在 `docker-compose.yml` 中修改：

```yaml
backend:
  environment:
    - APP_RAG__EMBED_MODEL=BAAI/bge-large-zh-v1.5  # 改为大模型
    - APP_KG_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
```

### 步骤 2: 清空向量数据库（如果维度变化）

```bash
# 删除 Qdrant 集合
curl -X DELETE http://localhost:6333/collections/kb_chunks
```

### 步骤 3: 重启服务

```bash
docker-compose down
docker-compose up -d
```

### 步骤 4: 重新上传文档

通过 API 或前端重新上传文档，系统会使用新模型重新向量化。

---

## 性能对比

### API 调用方式

| 方式 | API 调用次数 | 耗时（100个文本） | 推荐度 |
|------|-------------|------------------|--------|
| 逐个调用 | 100 | ~30s | ❌ 不推荐 |
| 批量调用（batch_size=32） | 4 | ~3s | ✅ 推荐 |
| 批量调用（batch_size=64） | 2 | ~2s | ✅✅ 最推荐 |

### 模型选择

| 模型 | 精度 | 速度 | 推荐场景 |
|------|------|------|---------|
| bge-small-zh (512维) | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 快速原型、实时查询 |
| bge-base-zh (768维) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 一般应用 |
| bge-m3 (1024维) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **默认推荐**、生产环境 |
| bge-large-zh (1024维) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 高精度需求 |

---

## 常见问题

### Q1: 为什么 RAG 和 KG 有两个配置项？

**A**: 虽然默认使用相同模型，但两个系统职责不同：
- **RAG**: 文档检索，侧重召回率
- **KG**: 实体对齐，侧重精确度

分开配置允许你根据需要使用不同的模型或策略。

### Q2: 可以使用本地模型吗？

**A**: 目前架构设计为通过 API 调用，不支持本地模型。如需支持，需要：
1. 实现新的 Provider Adapter
2. 集成 sentence-transformers 或 transformers 库
3. 处理模型下载和加载

### Q3: 切换模型需要重新处理数据吗？

**A**: 
- **维度相同**：理论上不需要，但建议重新处理以保证一致性
- **维度不同**：必须清空 Qdrant 并重新向量化所有文档

### Q4: 如何监控 embedding 性能？

**A**: 查看日志：
```bash
docker logs sopilot-backend | grep -i embedding
```

关键指标：
- 向量维度
- 批量大小
- API 延迟
- 错误率

### Q5: API Key 在哪里配置？

**A**: Embedding API 使用与 LLM 相同的 API Key：

```yaml
environment:
  - APP_PROVIDERS__SILICONFLOW__API_KEYS=["sk-your-key"]
```

---

## 验证配置

### 1. 检查配置加载

```bash
docker exec -it sopilot-backend python -c "
from app.core.settings import get_settings
s = get_settings()
print(f'RAG embed_model: {s.rag.embed_model}')
print(f'RAG embed_provider: {s.rag.embed_provider}')
print(f'KG_EMBEDDING_MODEL: {s.KG_EMBEDDING_MODEL}')
"
```

### 2. 测试 Embedding API

```bash
docker exec -it sopilot-backend python -c "
from app.infrastructure.rag.embedder import Embedder
from app.core.settings import get_settings

s = get_settings()
embedder = Embedder(
    model_name=s.rag.embed_model,
    provider=s.rag.embed_provider
)

result = embedder.embed_single('测试')
print(f'✓ Embedding 成功')
print(f'  维度: {result.dimension}')
print(f'  模型: {result.model_name}')
"
```

---

## 相关文档

- **[详细配置文档](EMBEDDING_CONFIG.md)** - 完整的配置说明和 API 参考
- **[快速配置指南](QUICK_CONFIG_GUIDE.md)** - 环境配置快速参考
- **[架构说明](EMBEDDING_ARCHITECTURE.md)** - 架构图和数据流详解
- **[README](../README.md)** - 项目主文档

---

## 总结

1. **默认配置已可用**：项目默认使用 `BAAI/bge-m3` + `siliconflow`，无需额外配置
2. **两个配置项**：`APP_RAG__EMBED_MODEL` 和 `APP_KG_EMBEDDING_MODEL`
3. **优先使用批量 API**：性能提升 10x 以上
4. **切换模型注意维度**：不同维度需要清空数据重新处理
5. **通过环境变量配置**：在 `docker-compose.yml` 或 `backend/.env` 中

**推荐配置**（生产环境）：
```yaml
environment:
  - APP_RAG__EMBED_MODEL=BAAI/bge-m3
  - APP_RAG__EMBED_PROVIDER=siliconflow
  - APP_KG_EMBEDDING_MODEL=BAAI/bge-m3
  - APP_PROVIDERS__SILICONFLOW__API_KEYS=["sk-your-api-key"]
```

