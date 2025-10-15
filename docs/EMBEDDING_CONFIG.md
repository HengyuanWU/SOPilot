# Embedding 模型配置文档

## 概述

SOPilot 项目中有两个地方使用了 embedding 模型：
1. **RAG 系统** - 用于文档检索的向量化
2. **KG 系统** - 用于实体链接的语义相似度计算

## 当前配置

### 1. RAG 系统配置

**位置**: `backend/src/app/core/settings.py` → `RAGSettings` 类

```python
class RAGSettings(BaseModel):
    embed_model: str = "BAAI/bge-m3"  # SiliconFlow支持的embedding模型（1024维）
    embed_provider: str = "siliconflow"  # embedding模型提供商
    # ... 其他配置
```

**配置方式**:
- 通过环境变量: `APP_RAG__EMBED_MODEL` 和 `APP_RAG__EMBED_PROVIDER`
- 在 `backend/.env` 中配置
- 在 `docker-compose.yml` 中配置

**使用场景**:
- 文档分块向量化（用于存储到 Qdrant）
- 查询向量化（用于相似度检索）
- 文档相似度计算

### 2. KG 系统配置

**位置**: `backend/src/app/core/settings.py` → `AppSettings` 类

```python
class AppSettings(BaseSettings):
    # ... 其他配置
    KG_EMBEDDING_MODEL: str = 'BAAI/bge-m3'  # 实体链接使用的向量模型（API 侧实现）
    # ... 其他配置
```

**配置方式**:
- 通过环境变量: `APP_KG_EMBEDDING_MODEL`
- 在 `backend/.env` 中配置
- 在 `docker-compose.yml` 中配置

**使用场景**:
- KG 实体链接（Entity Linking）
- 概念相似度计算
- 新旧实体对齐

## 实现架构

### Embedding API 调用链路

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

### 关键组件

#### 1. Embedder 类
- **文件**: `backend/src/app/infrastructure/rag/embedder.py`
- **功能**:
  - 单文本向量化: `embed_single(text) -> EmbeddingResult`
  - 批量文本向量化: `embed_batch(texts) -> List[EmbeddingResult]`
  - 相似度计算: `compute_similarity(text1, text2) -> float`
  - 最相似文本查找: `find_most_similar(query, candidates, top_k) -> List[tuple]`

#### 2. LLM Router
- **文件**: `backend/src/app/infrastructure/llm/router/core.py`
- **功能**:
  - 统一的 embedding 接口
  - 支持单个向量生成: `generate_embedding(request)`
  - 支持批量向量生成: `generate_embedding_batch(request)`

#### 3. SiliconFlow Adapter
- **文件**: `backend/src/app/infrastructure/llm/router/adapters/siliconflow.py`
- **功能**:
  - 实现 SiliconFlow 的 embedding API 调用
  - 支持批量请求（通过 `input` 字段传入数组）
  - 返回标准化的 `LLMResponse` 对象

## 支持的 Embedding 模型

### SiliconFlow 支持的模型（推荐）

| 模型名称 | 维度 | 适用场景 |
|---------|------|---------|
| `BAAI/bge-m3` | 1024 | **默认推荐** - 支持中英文，综合性能优秀 |
| `BAAI/bge-small-zh-v1.5` | 512 | 轻量级中文模型 |
| `BAAI/bge-base-zh-v1.5` | 768 | 中等规模中文模型 |
| `BAAI/bge-large-zh-v1.5` | 1024 | 大规模中文模型 |

### 如何切换模型

#### 方法 1: 环境变量（推荐）

在 `docker-compose.yml` 的 `backend` 服务中添加：

```yaml
environment:
  # RAG embedding 配置
  - APP_RAG__EMBED_MODEL=BAAI/bge-large-zh-v1.5
  - APP_RAG__EMBED_PROVIDER=siliconflow
  
  # KG embedding 配置
  - APP_KG_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
```

#### 方法 2: .env 文件

在 `backend/.env` 文件中：

```bash
# RAG embedding 配置
APP_RAG__EMBED_MODEL=BAAI/bge-large-zh-v1.5
APP_RAG__EMBED_PROVIDER=siliconflow

# KG embedding 配置
APP_KG_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
```

#### 方法 3: 代码直接修改

修改 `backend/src/app/core/settings.py`:

```python
class RAGSettings(BaseModel):
    embed_model: str = "BAAI/bge-large-zh-v1.5"  # 修改这里
    embed_provider: str = "siliconflow"

class AppSettings(BaseSettings):
    KG_EMBEDDING_MODEL: str = 'BAAI/bge-large-zh-v1.5'  # 修改这里
```

## 性能优化建议

### 1. 批量处理

Embedder 类支持批量处理，能显著减少 API 调用次数：

```python
# ❌ 不推荐：逐个处理
for text in texts:
    embedding = embedder.embed_single(text)

# ✅ 推荐：批量处理
embeddings = embedder.embed_batch(texts)
```

### 2. 批处理大小调整

在 `Embedder` 初始化时可以调整批处理大小：

```python
embedder = Embedder(
    model_name="BAAI/bge-m3",
    provider="siliconflow",
    batch_size=32  # 默认32，可根据 API 限制调整
)
```

### 3. 向量维度注意事项

切换模型时需要注意：
- **Qdrant 集合的向量维度必须匹配**
- 如果切换到不同维度的模型，需要：
  1. 清空 Qdrant 数据
  2. 重新创建集合
  3. 重新向量化所有文档

## 常见问题

### Q1: 为什么 RAG 和 KG 使用不同的配置项？

**A**: 虽然默认都使用相同的模型，但两个系统有不同的职责：
- **RAG**: 侧重文档检索，可能需要不同的 embedding 策略
- **KG**: 侧重实体对齐，可能需要更高精度的 embedding

分开配置提供了更大的灵活性。

### Q2: 可以使用不同的 provider 吗？

**A**: 目前主要支持 SiliconFlow，因为它提供了高质量的中文 embedding 模型。如需支持其他 provider（如 OpenAI、DeepSeek），需要在对应的 adapter 中实现 `generate_embedding` 和 `generate_embedding_batch` 方法。

### Q3: 如何验证 embedding 配置是否生效？

**A**: 可以通过以下方式验证：

```bash
# 进入 backend 容器
docker exec -it sopilot-backend bash

# 运行 Python 测试
python -c "
from app.infrastructure.rag.embedder import Embedder
from app.core.settings import get_settings

settings = get_settings()
print(f'RAG embed_model: {settings.rag.embed_model}')
print(f'KG_EMBEDDING_MODEL: {settings.KG_EMBEDDING_MODEL}')

embedder = Embedder(
    model_name=settings.rag.embed_model,
    provider=settings.rag.embed_provider
)
result = embedder.embed_single('测试文本')
print(f'Embedding dimension: {result.dimension}')
"
```

### Q4: 切换模型后需要重新处理数据吗？

**A**: 是的，如果切换到不同维度的 embedding 模型，需要：

1. **清空 Qdrant 向量数据库**:
   ```bash
   # 删除集合
   curl -X DELETE http://localhost:6333/collections/kb_chunks
   ```

2. **清空 Neo4j 中的向量数据**（如果有存储）

3. **重新向量化所有文档**

如果只是切换相同维度的模型（如 `bge-base-zh-v1.5` 到 `bge-large-zh-v1.5`），理论上不需要清空数据，但为了保证向量质量一致性，建议还是重新处理。

## API Key 配置

Embedding API 调用需要 SiliconFlow 的 API Key，配置方式：

### 在 docker-compose.yml 中配置

```yaml
backend:
  env_file:
    - backend/.env
  environment:
    # 通过 providers 配置传递
    - APP_PROVIDERS__SILICONFLOW__API_KEYS=["sk-your-api-key-here"]
```

### 在 backend/.env 中配置

```bash
APP_PROVIDERS__SILICONFLOW__API_KEYS=["sk-your-api-key-here"]
```

注意：`APP_PROVIDERS__SILICONFLOW__API_KEYS` 需要是 JSON 数组格式，支持多个 API Key 轮询。

## 监控和调试

### 查看 Embedding API 调用日志

```bash
# 查看 backend 日志
docker logs -f sopilot-backend | grep -i embedding
```

日志会显示：
- API 调用参数
- 返回的向量维度
- 调用延迟
- 错误信息（如果有）

### 常见错误

1. **API Key 未配置**:
   ```
   LLMException: No API key configured for provider siliconflow
   ```
   解决：配置 `APP_PROVIDERS__SILICONFLOW__API_KEYS`

2. **模型不支持**:
   ```
   SiliconFlow embedding API调用失败: 404
   ```
   解决：检查模型名称是否正确，参考 SiliconFlow 官方文档

3. **向量维度不匹配**:
   ```
   向量维度不匹配: 期望1024, 实际768
   ```
   解决：清空 Qdrant 数据后重新向量化

## 参考资料

- [SiliconFlow API 文档](https://docs.siliconflow.cn/)
- [BGE Embedding 模型](https://huggingface.co/BAAI/bge-m3)
- [Qdrant 文档](https://qdrant.tech/documentation/)

