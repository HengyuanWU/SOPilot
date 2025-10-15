# 快速配置指南

## 目录
- [配置 Embedding 模型](#配置-embedding-模型)
- [配置 LLM Provider](#配置-llm-provider)
- [配置示例](#配置示例)
- [验证配置](#验证配置)

## 配置 Embedding 模型

### 方式 1: 通过 docker-compose.yml（推荐）

编辑 `docker-compose.yml` 文件，在 `backend` 服务的 `environment` 部分添加：

```yaml
backend:
  environment:
    # RAG embedding 配置
    - APP_RAG__EMBED_MODEL=BAAI/bge-m3
    - APP_RAG__EMBED_PROVIDER=siliconflow
    
    # KG embedding 配置
    - APP_KG_EMBEDDING_MODEL=BAAI/bge-m3
```

### 方式 2: 通过 .env 文件

在 `backend/.env` 文件中添加：

```bash
# RAG embedding 配置
APP_RAG__EMBED_MODEL=BAAI/bge-m3
APP_RAG__EMBED_PROVIDER=siliconflow

# KG embedding 配置
APP_KG_EMBEDDING_MODEL=BAAI/bge-m3
```

### 支持的 Embedding 模型

| 模型名称 | 维度 | 描述 |
|---------|------|------|
| `BAAI/bge-m3` | 1024 | **默认推荐** - 支持中英文，综合性能优秀 |
| `BAAI/bge-small-zh-v1.5` | 512 | 轻量级中文模型，速度快 |
| `BAAI/bge-base-zh-v1.5` | 768 | 中等规模中文模型，平衡性能和速度 |
| `BAAI/bge-large-zh-v1.5` | 1024 | 大规模中文模型，最高精度 |

## 配置 LLM Provider

### SiliconFlow（推荐用于国内）

```yaml
backend:
  environment:
    - APP_DEFAULT_PROVIDER=siliconflow
    - APP_PROVIDERS__SILICONFLOW__API_KEYS=["sk-your-api-key"]
    - APP_PROVIDERS__SILICONFLOW__MODEL=Qwen/Qwen2.5-7B-Instruct
```

### OpenAI

```yaml
backend:
  environment:
    - APP_DEFAULT_PROVIDER=openai
    - APP_PROVIDERS__OPENAI__API_KEYS=["sk-your-openai-key"]
    - APP_PROVIDERS__OPENAI__MODEL=gpt-4o-mini
```

### DeepSeek

```yaml
backend:
  environment:
    - APP_DEFAULT_PROVIDER=deepseek
    - APP_PROVIDERS__DEEPSEEK__API_KEYS=["sk-your-deepseek-key"]
    - APP_PROVIDERS__DEEPSEEK__MODEL=deepseek-chat
```

## 配置示例

### 完整的 docker-compose.yml backend 配置示例

```yaml
backend:
  build: .
  container_name: sopilot-backend
  env_file:
    - backend/.env  # 可选，用于敏感信息
  environment:
    # 基础配置
    - PYTHONPATH=/app/backend/src
    - APP_ENV=dev
    - APP_DEBUG=true
    - APP_USE_REAL_WORKFLOW=true
    - APP_OUTPUT_DIR=/app/output
    
    # LLM Provider
    - APP_DEFAULT_PROVIDER=siliconflow
    - APP_PROVIDERS__SILICONFLOW__API_KEYS=["sk-your-siliconflow-key"]
    - APP_PROVIDERS__SILICONFLOW__MODEL=Qwen/Qwen2.5-7B-Instruct
    - APP_PROVIDERS__SILICONFLOW__BASE_URL=https://api.siliconflow.cn/v1
    
    # Embedding 配置
    - APP_RAG__EMBED_MODEL=BAAI/bge-m3
    - APP_RAG__EMBED_PROVIDER=siliconflow
    - APP_KG_EMBEDDING_MODEL=BAAI/bge-m3
    
    # Neo4j
    - APP_NEO4J__URI=bolt://neo4j:7687
    - APP_NEO4J__USER=neo4j
    - APP_NEO4J__PASSWORD=test1234
    - APP_NEO4J__DATABASE=neo4j
    
    # Qdrant
    - APP_QDRANT__URL=http://qdrant:6333
    - APP_QDRANT__COLLECTION=kb_chunks
    - APP_QDRANT__DISTANCE=cosine
    
    # RAG 参数
    - APP_RAG__CHUNK_SIZE=800
    - APP_RAG__CHUNK_OVERLAP=120
    - APP_RAG__TOP_K=4
    - APP_RAG__VECTOR_TOP_K=12
    - APP_RAG__KG_TOP_K=8
    - APP_RAG__ALPHA=0.7
    - APP_RAG__BETA=0.3
    
    # KG 参数
    - APP_KG_ENABLED=true
    - APP_KG_LANGUAGE=zh
    - APP_KG_MIN_TERM_LEN=2
    - APP_KG_RE_MIN_CONF=0.55
    - APP_KG_LINK_MIN_SIM=0.82
    - APP_KG_LINK_TOPK=3
    
  ports:
    - "8000:8000"
  depends_on:
    - neo4j
    - qdrant
  volumes:
    - ./backend/src:/app/backend/src
    - ./backend/requirements.txt:/app/backend/requirements.txt
    - ./output:/app/output
  restart: unless-stopped
```

### backend/.env 示例（用于敏感信息）

创建 `backend/.env` 文件（不提交到 git）：

```bash
# SiliconFlow API Key
APP_PROVIDERS__SILICONFLOW__API_KEYS=["sk-xxxxxxxxxxxxxxxxxxxxxxxxxx"]

# OpenAI API Key (可选)
# APP_PROVIDERS__OPENAI__API_KEYS=["sk-xxxxxxxxxxxxxxxxxxxxxxxxxx"]

# DeepSeek API Key (可选)
# APP_PROVIDERS__DEEPSEEK__API_KEYS=["sk-xxxxxxxxxxxxxxxxxxxxxxxxxx"]
```

## 验证配置

### 1. 检查配置是否正确加载

```bash
# 进入 backend 容器
docker exec -it sopilot-backend bash

# 查看当前配置
python -c "
from app.core.settings import get_settings, settings_diagnostics
import json

# 打印配置诊断信息
diag = settings_diagnostics()
print(json.dumps(diag, indent=2))

# 打印 Embedding 配置
settings = get_settings()
print(f'\nRAG Embedding:')
print(f'  model: {settings.rag.embed_model}')
print(f'  provider: {settings.rag.embed_provider}')
print(f'\nKG Embedding:')
print(f'  model: {settings.KG_EMBEDDING_MODEL}')
"
```

### 2. 测试 Embedding API

```bash
# 在容器内测试
python -c "
from app.infrastructure.rag.embedder import Embedder
from app.core.settings import get_settings

settings = get_settings()
embedder = Embedder(
    model_name=settings.rag.embed_model,
    provider=settings.rag.embed_provider
)

# 测试单个文本
result = embedder.embed_single('这是一个测试文本')
print(f'✓ Embedding 成功')
print(f'  维度: {result.dimension}')
print(f'  模型: {result.model_name}')
print(f'  向量前10维: {result.vector[:10]}')
"
```

### 3. 测试批量 Embedding

```bash
python -c "
from app.infrastructure.rag.embedder import Embedder
from app.core.settings import get_settings

settings = get_settings()
embedder = Embedder(
    model_name=settings.rag.embed_model,
    provider=settings.rag.embed_provider
)

# 测试批量
texts = ['文本1', '文本2', '文本3']
results = embedder.embed_batch(texts, show_progress=False)
print(f'✓ 批量 Embedding 成功')
print(f'  处理数量: {len(results)}')
print(f'  向量维度: {results[0].dimension}')
"
```

## 常见问题排查

### 问题 1: API Key 未配置

**错误信息**:
```
LLMException: No API key configured for provider siliconflow
```

**解决方案**:
1. 检查 `docker-compose.yml` 中是否配置了 `APP_PROVIDERS__SILICONFLOW__API_KEYS`
2. 检查 `backend/.env` 文件是否存在且配置正确
3. 确保 API Key 格式为 JSON 数组: `["sk-..."]`

### 问题 2: 模型不支持

**错误信息**:
```
SiliconFlow embedding API调用失败: 404
```

**解决方案**:
1. 检查模型名称是否正确
2. 访问 [SiliconFlow 官方文档](https://docs.siliconflow.cn/) 查看支持的模型列表
3. 确保使用的是 embedding 模型，而不是 LLM 模型

### 问题 3: 向量维度不匹配

**错误信息**:
```
向量维度不匹配: 期望1024, 实际768
```

**解决方案**:
1. 清空 Qdrant 数据:
   ```bash
   curl -X DELETE http://localhost:6333/collections/kb_chunks
   ```
2. 重启服务:
   ```bash
   docker-compose down
   docker-compose up -d
   ```
3. 重新上传文档

### 问题 4: 无法连接到 Neo4j 或 Qdrant

**错误信息**:
```
Failed to connect to neo4j:7687
```

**解决方案**:
1. 检查 Neo4j 和 Qdrant 容器是否正常运行:
   ```bash
   docker ps | grep -E 'neo4j|qdrant'
   ```
2. 检查容器日志:
   ```bash
   docker logs sopilot-neo4j
   docker logs sopilot-qdrant
   ```
3. 确保 `depends_on` 配置正确

## 高级配置

### 配置多个 API Key（负载均衡）

```yaml
environment:
  # 配置多个 API Key，系统会自动轮询
  - APP_PROVIDERS__SILICONFLOW__API_KEYS=["sk-key1", "sk-key2", "sk-key3"]
```

### 配置 Embedding 批处理大小

在代码中可以调整批处理大小（默认 32）：

```python
from app.infrastructure.rag.embedder import Embedder

embedder = Embedder(
    model_name="BAAI/bge-m3",
    provider="siliconflow",
    batch_size=64  # 增大批处理大小
)
```

### 配置超时时间

```yaml
environment:
  # 配置 LLM 超时时间
  - APP_MIDDLEWARE__DEFAULT_TIMEOUT=300
  - APP_PROVIDERS__SILICONFLOW__TIMEOUT=300
```

## 更多信息

- 详细的 Embedding 配置文档: [EMBEDDING_CONFIG.md](./EMBEDDING_CONFIG.md)
- 项目架构文档: [ARCHITECTURE.md](./ARCHITECTURE.md)
- API 文档: 启动服务后访问 http://localhost:8000/docs

